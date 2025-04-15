import json
import boto3
import os
import time
from botocore.exceptions import ClientError
from typing import List, Dict, Any
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayProxyEvent

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
        pipe_arn = connector.get("pipeArn")
        pipe_role_arn = connector.get("pipeRoleArn")

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
        pipes = boto3.client("pipes", region_name=region)

        errors: List[str] = []

        # Delete Lambda
        if lambda_arn:
            try:
                lambda_client.delete_function(FunctionName=lambda_arn.split(":")[-1])
                logger.info(f"Deleted Lambda function {lambda_arn}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    error_msg = f"Error deleting Lambda: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Delete EventBridge Pipe if present
        if pipe_arn:
            try:
                delete_eventbridge_pipe(pipes, pipe_arn)
            except ClientError as e:
                error_msg = f"Error deleting EventBridge Pipe: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Delete IAM role
        if iam_role_arn:
            try:
                delete_iam_role(iam, iam_role_arn)
                logger.info(f"Deleted IAM role {iam_role_arn}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    error_msg = f"Error deleting IAM role: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Delete EventBridge Pipe IAM role if present
        if pipe_role_arn:
            try:
                delete_iam_role(iam, pipe_role_arn)
                logger.info(f"Deleted EventBridge Pipe IAM role {pipe_role_arn}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    error_msg = f"Error deleting EventBridge Pipe IAM role: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Delete SQS queue
        if queue_url:
            try:
                sqs.delete_queue(QueueUrl=queue_url)
                logger.info(f"Deleted SQS queue {queue_url}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
                    error_msg = f"Error deleting SQS queue: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Handle different integration methods
        integration_method = connector.get("integrationMethod")
        if integration_method == "s3Notifications":
            errors.extend(remove_s3_notifications(s3, bucket_name))
        elif integration_method == "eventbridge":
            errors.extend(remove_eventbridge_rule(eventbridge, connector_id, region))
        else:
            logger.info(
                f"No specific cleanup needed for integration method: {integration_method}"
            )

        # Delete connector from DynamoDB only if all other resources are cleaned up
        if not errors:
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


def delete_iam_role(iam_client: Any, role_arn: str) -> None:
    """Delete IAM role and its policies"""
    role_name = role_arn.split("/")[-1]

    # Detach all managed policies
    attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)[
        "AttachedPolicies"
    ]
    for policy in attached_policies:
        iam_client.detach_role_policy(
            RoleName=role_name, PolicyArn=policy["PolicyArn"]
        )
        logger.info(f"Detached policy {policy['PolicyArn']} from role {role_name}")

    # Delete all inline policies
    inline_policies = iam_client.list_role_policies(RoleName=role_name)["PolicyNames"]
    for policy_name in inline_policies:
        iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
        logger.info(f"Deleted inline policy {policy_name} from role {role_name}")

    # Delete the role
    iam_client.delete_role(RoleName=role_name)


def delete_eventbridge_pipe(pipes_client: Any, pipe_arn: str) -> None:
    """Delete an EventBridge Pipe"""
    # Get the pipe name from ARN
    pipe_name = pipe_arn.split("/")[-1]
    
    # Check if pipe exists and get its current state
    try:
        pipe_info = pipes_client.describe_pipe(Name=pipe_name)
        current_state = pipe_info.get('CurrentState')
        
        # If pipe is running, stop it first
        if current_state == 'RUNNING':
            pipes_client.stop_pipe(Name=pipe_name)
            logger.info(f"Stopped EventBridge Pipe {pipe_name}")
            
            # Wait for pipe to stop before deleting
            max_retries = 10
            for i in range(max_retries):
                time.sleep(2)  # Wait 2 seconds between checks
                pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                if pipe_info.get('CurrentState') != 'RUNNING':
                    break
                if i == max_retries - 1:
                    logger.warning(f"Pipe {pipe_name} did not stop in time, attempting delete anyway")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    
    # Delete the pipe
    pipes_client.delete_pipe(Name=pipe_name)
    logger.info(f"Deleted EventBridge Pipe {pipe_name}")


def remove_s3_notifications(s3: Any, bucket_name: str) -> List[str]:
    errors: List[str] = []
    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration={},  # Empty config removes all notifications
        )
        logger.info(f"Removed S3 bucket notifications for bucket: {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            error_msg = f"Error removing S3 bucket notification: {str(e)}"
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
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            error_msg = f"Error removing EventBridge rule: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    return errors
