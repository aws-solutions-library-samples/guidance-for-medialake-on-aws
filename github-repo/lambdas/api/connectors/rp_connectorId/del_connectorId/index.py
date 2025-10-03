import json
import os
from typing import Any, List

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MEDIALAKE_CONNECTOR_TABLE"])


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext):
    try:
        # Get connector_id from path parameters
        connector_id = event.get("pathParameters", {}).get("connector_id")

        if not connector_id:
            logger.error("No connector_id provided in path parameters")
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Connector ID is required"}),
            }

        # Get connector details from DynamoDB
        try:
            response = table.get_item(Key={"id": connector_id})
        except ClientError as e:
            logger.error(f"DynamoDB get_item failed: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"message": "Failed to retrieve connector details"}),
            }

        if "Item" not in response:
            logger.warning(f"Connector not found with ID: {connector_id}")
            return {
                "statusCode": 404,
                "body": json.dumps({"message": "Connector not found"}),
            }

        connector = response["Item"]
        region = connector.get(
            "region", "us-east-1"
        )  # Default to us-east-1 if not specified
        queue_url = connector.get("queueUrl")
        bucket_name = connector.get("storageIdentifier")
        lambda_arn = connector.get("lambdaArn")
        iam_role_arn = connector.get("iamRoleArn")

        if not all([queue_url, bucket_name, lambda_arn, iam_role_arn]):
            logger.error(f"Invalid connector configuration for ID: {connector_id}")
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Invalid connector configuration"}),
            }

        # Create AWS clients in the specified region
        lambda_client = boto3.client("lambda", region_name=region)
        iam = boto3.client("iam", region_name=region)
        s3 = boto3.client("s3", region_name=region)
        sqs = boto3.client("sqs", region_name=region)
        eventbridge = boto3.client("events", region_name=region)
        pipes_client = boto3.client("pipes", region_name=region)

        errors = []

        # Get pipe and pipe role information from connector
        pipe_arn = connector.get("pipeArn")
        pipe_role_arn = connector.get("pipeRoleArn")
        integration_method = connector.get("integrationMethod")

        # Delete EventBridge Pipe if it exists
        if pipe_arn and integration_method == "eventbridge":
            pipe_name = pipe_arn.split(":")[-1].split("/")[
                -1
            ]  # Extract pipe name from ARN
            try:
                # Check pipe state and stop if running
                pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                if pipe_info.get("CurrentState") == "RUNNING":
                    logger.info(f"Stopping pipe: {pipe_name}")
                    pipes_client.stop_pipe(Name=pipe_name)
                    # Add a short wait for the pipe to stop (adjust as needed)
                    import time

                    time.sleep(10)

                # Delete pipe with exponential backoff retry logic
                import time

                max_retries = 4
                base_delay = 2  # seconds

                for attempt in range(max_retries):
                    try:
                        pipes_client.delete_pipe(Name=pipe_name)
                        logger.info(f"Deleted EventBridge Pipe: {pipe_name}")
                        break
                    except ClientError as delete_error:
                        if (
                            delete_error.response["Error"]["Code"]
                            == "ConflictException"
                        ):
                            if (
                                attempt < max_retries - 1
                            ):  # Don't sleep on the last attempt
                                delay = base_delay * (2**attempt)  # Exponential backoff
                                logger.warning(
                                    f"Pipe {pipe_name} is updating concurrently. Retrying in {delay} seconds (attempt {attempt + 1}/{max_retries})"
                                )
                                time.sleep(delay)
                            else:
                                error_msg = f"Error deleting Pipe {pipe_name} after {max_retries} attempts: {str(delete_error)}"
                                logger.error(error_msg)
                                errors.append(error_msg)
                        else:
                            # Different error, don't retry
                            if (
                                delete_error.response["Error"]["Code"]
                                == "ResourceNotFoundException"
                            ):
                                logger.warning(
                                    f"Pipe {pipe_name} does not exist, skipping deletion"
                                )
                            else:
                                error_msg = f"Error deleting Pipe {pipe_name}: {str(delete_error)}"
                                logger.error(error_msg)
                                errors.append(error_msg)
                            break

            except ClientError as e:
                if e.response["Error"]["Code"] in [
                    "ResourceNotFoundException",
                    "NotFoundException",
                ]:
                    logger.warning(
                        f"Pipe {pipe_name} does not exist, skipping deletion"
                    )
                else:
                    error_msg = f"Error describing/stopping Pipe {pipe_name}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Delete Pipe IAM role if it exists
        if pipe_role_arn and integration_method == "eventbridge":
            pipe_role_name = pipe_role_arn.split("/")[-1]
            try:
                # Detach all managed policies from pipe role
                attached_policies = iam.list_attached_role_policies(
                    RoleName=pipe_role_name
                )["AttachedPolicies"]
                for policy in attached_policies:
                    iam.detach_role_policy(
                        RoleName=pipe_role_name, PolicyArn=policy["PolicyArn"]
                    )

                # Delete all inline policies from pipe role
                inline_policies = iam.list_role_policies(RoleName=pipe_role_name)[
                    "PolicyNames"
                ]
                for policy_name in inline_policies:
                    iam.delete_role_policy(
                        RoleName=pipe_role_name, PolicyName=policy_name
                    )

                # Delete the pipe role
                iam.delete_role(RoleName=pipe_role_name)
                logger.info(f"Deleted Pipe IAM role: {pipe_role_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchEntity":
                    logger.warning(
                        f"Pipe IAM role {pipe_role_name} does not exist, skipping deletion"
                    )
                else:
                    error_msg = f"Error deleting Pipe IAM role: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Delete Lambda
        try:
            lambda_client.delete_function(FunctionName=lambda_arn.split(":")[-1])
            logger.info(f"Deleted Lambda function: {lambda_arn}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning(
                    f"Lambda function {lambda_arn} does not exist, skipping deletion"
                )
            else:
                error_msg = f"Error deleting Lambda: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Delete IAM role
        role_name = iam_role_arn.split("/")[-1]
        try:
            # Detach all managed policies
            attached_policies = iam.list_attached_role_policies(RoleName=role_name)[
                "AttachedPolicies"
            ]
            for policy in attached_policies:
                iam.detach_role_policy(
                    RoleName=role_name, PolicyArn=policy["PolicyArn"]
                )

            # Delete all inline policies
            inline_policies = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
            for policy_name in inline_policies:
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

            # Delete the role
            iam.delete_role(RoleName=role_name)
            logger.info(f"Deleted IAM role: {role_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                logger.warning(
                    f"IAM role {role_name} does not exist, skipping deletion"
                )
            else:
                error_msg = f"Error deleting IAM role: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Delete SQS queue
        try:
            sqs.delete_queue(QueueUrl=queue_url)
            logger.info(f"Deleted SQS queue: {queue_url}")
        except ClientError as e:
            # Handle potential variations in error codes for non-existent queues
            if e.response["Error"]["Code"] in [
                "AWS.SimpleQueueService.NonExistentQueue",
                "QueueDoesNotExist",
            ]:
                logger.warning(
                    f"SQS queue {queue_url} does not exist, skipping deletion"
                )
            else:
                error_msg = f"Error deleting SQS queue: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Remove S3 bucket notification or EventBridge rule
        try:
            # Handle different integration methods
            if integration_method == "s3Notifications":
                notification_name = (
                    f"{os.environ.get('RESOURCE_PREFIX')}_notifications_{connector_id}"
                )
                errors.extend(
                    remove_event_notification_by_name(
                        s3, bucket_name, notification_name
                    )
                )
            elif integration_method == "eventbridge":
                errors.extend(
                    remove_eventbridge_rule(eventbridge, connector_id, region)
                )
            else:
                logger.info(
                    f"No specific cleanup needed for integration method: {integration_method}"
                )

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                logger.warning(
                    f"S3 bucket {bucket_name} does not exist, skipping notification cleanup"
                )
            else:
                error_msg = f"Error removing S3 bucket notification: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Delete connector from DynamoDB only if all other resources are cleaned up
        if not errors:
            logger.info(
                f"Core connector resources deleted successfully for ID: {connector_id}"
            )
            # Conditionally Delete S3 Bucket (if managed by MediaLake and empty)
            creation_type = connector.get("creationType")
            if creation_type == "new":
                logger.info(
                    f"Connector indicates bucket '{bucket_name}' was created by MediaLake. Attempting deletion."
                )
                try:
                    # Check if bucket is empty
                    list_response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    if (
                        "Contents" in list_response
                        and len(list_response["Contents"]) > 0
                    ):
                        logger.warning(
                            f"Bucket '{bucket_name}' is not empty. Skipping deletion."
                        )
                        # Optionally, update connector status to 'error' or add a note?
                    else:
                        logger.info(
                            f"Bucket '{bucket_name}' is empty. Proceeding with deletion."
                        )
                        s3.delete_bucket(Bucket=bucket_name)
                        logger.info(f"Successfully deleted S3 bucket: {bucket_name}")

                except ClientError as e:
                    # Handle cases like AccessDenied, NoSuchBucket (if already deleted elsewhere)
                    error_msg = f"Error checking or deleting S3 bucket '{bucket_name}': {str(e)}"
                    logger.error(error_msg)
                    # Decide if this should prevent DynamoDB deletion - likely not, log and proceed.
                    # errors.append(error_msg) # Uncomment if bucket deletion failure should block connector deletion

            else:
                logger.info(
                    f"Bucket '{bucket_name}' was pre-existing (creationType: {creation_type}). Skipping deletion."
                )

            # Delete DynamoDB record (moved after potential bucket deletion)
            try:
                table.delete_item(Key={"id": connector_id})
                logger.info(f"Successfully deleted connector with ID: {connector_id}")
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "Connector deleted successfully"}),
                }
            except ClientError as e:
                logger.error(f"Failed to delete connector from DynamoDB: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {
                            "message": "Failed to delete connector record",
                            "error": str(e),
                        }
                    ),
                }
        else:
            logger.error(
                f"Errors occurred while deleting connector {connector_id}: {errors}"
            )
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {"message": "Error deleting connector", "errors": errors}
                ),
            }

    except Exception as e:
        logger.exception("Unexpected error occurred")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error", "error": str(e)}),
        }


def remove_event_notification_by_name(
    s3: Any, bucket_name: str, notification_name: str
) -> List[str]:
    errors: List[str] = []
    try:
        # Get current configuration
        current_config = s3.get_bucket_notification_configuration(Bucket=bucket_name)

        # Create new configuration
        new_config = {}

        # Preserve EventBridge configuration if it exists
        if "EventBridgeConfiguration" in current_config:
            new_config["EventBridgeConfiguration"] = current_config[
                "EventBridgeConfiguration"
            ]

        # Process all configuration types except EventBridgeConfiguration
        for config_type, configs in current_config.items():
            if config_type != "EventBridgeConfiguration":
                filtered_configs = [
                    config
                    for config in configs
                    if config.get("Id", "") != notification_name
                ]
                if filtered_configs:  # Only add if there are remaining configurations
                    new_config[config_type] = filtered_configs

        # Apply the new configuration
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name, NotificationConfiguration=new_config
        )

        logger.info(
            f"Removed notification '{notification_name}' from bucket: {bucket_name}"
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            logger.warning(
                f"S3 bucket {bucket_name} does not exist, skipping notification '{notification_name}' removal"
            )
        else:
            error_msg = (
                f"Error removing S3 bucket notification '{notification_name}': {str(e)}"
            )
            logger.error(error_msg)
            errors.append(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error removing S3 bucket notification '{notification_name}': {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    return errors


def remove_eventbridge_rule(
    eventbridge: Any, connector_id: str, region: str
) -> List[str]:
    errors: List[str] = []
    rule_name = f"medialake-connector-{connector_id}"

    try:
        # List targets for the rule
        targets = eventbridge.list_targets_by_rule(Rule=rule_name)["Targets"]

        # Remove targets from the rule
        if targets:
            target_ids = [target["Id"] for target in targets]
            eventbridge.remove_targets(Rule=rule_name, Ids=target_ids)

        # Delete the rule
        eventbridge.delete_rule(Name=rule_name)

        logger.info(
            f"Successfully removed EventBridge rule and targets for connector: {connector_id}"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(
                f"EventBridge rule {rule_name} does not exist, skipping deletion"
            )
        else:
            error_msg = f"Error removing EventBridge rule: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    return errors
