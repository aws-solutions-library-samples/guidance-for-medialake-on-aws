import json
import os
import time
from typing import Any

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
        region = connector.get("region", "us-east-1")
        queue_url = connector.get("queueUrl")
        bucket_name = connector.get("storageIdentifier")
        lambda_arn = connector.get("lambdaArn")
        iam_role_arn = connector.get("iamRoleArn")
        pipe_arn = connector.get("pipeArn")
        pipe_role_arn = connector.get("pipeRoleArn")
        event_bridge_rule_name = connector.get("eventBridgeRuleName")

        # Create AWS clients in the specified region
        lambda_client = boto3.client("lambda", region_name=region)
        iam = boto3.client("iam", region_name=region)
        s3 = boto3.client("s3", region_name=region)
        sqs = boto3.client("sqs", region_name=region)
        eventbridge = boto3.client("events", region_name=region)
        pipes = boto3.client("pipes", region_name=region)

        # Best-effort cleanup — each step is wrapped individually
        # Delete Lambda
        if lambda_arn:
            try:
                lambda_client.delete_function(FunctionName=lambda_arn.split(":")[-1])
                logger.info(f"Deleted Lambda function {lambda_arn}")
            except ClientError as e:
                logger.warning(f"Error deleting Lambda: {str(e)}")

        # Delete EventBridge Pipe
        if pipe_arn:
            try:
                delete_eventbridge_pipe(pipes, pipe_arn)
                time.sleep(3)
            except ClientError as e:
                logger.warning(f"Error deleting EventBridge Pipe: {str(e)}")

        # Delete EventBridge Pipe IAM role
        if pipe_role_arn:
            try:
                delete_iam_role(iam, pipe_role_arn)
                logger.info(f"Deleted EventBridge Pipe IAM role {pipe_role_arn}")
            except ClientError as e:
                logger.warning(f"Error deleting EventBridge Pipe IAM role: {str(e)}")

        # Delete SQS queue
        if queue_url:
            try:
                sqs.delete_queue(QueueUrl=queue_url)
                logger.info(f"Deleted SQS queue {queue_url}")
            except ClientError as e:
                logger.warning(f"Error deleting SQS queue: {str(e)}")

        # Handle different integration methods
        integration_method = connector.get("integrationMethod")
        if integration_method == "s3Notifications" and bucket_name:
            try:
                remove_s3_notifications(s3, bucket_name)
            except Exception as e:
                logger.warning(f"Error removing S3 notifications: {str(e)}")
        elif integration_method == "eventbridge":
            try:
                remove_eventbridge_rule(
                    eventbridge,
                    connector_id,
                    region,
                    stored_rule_name=event_bridge_rule_name,
                    bucket_name=bucket_name,
                )
            except Exception as e:
                logger.warning(f"Error removing EventBridge rule: {str(e)}")

        # Delete main IAM role LAST
        if iam_role_arn:
            try:
                time.sleep(5)
                delete_iam_role(iam, iam_role_arn)
                logger.info(f"Deleted IAM role {iam_role_arn}")
            except ClientError as e:
                logger.warning(f"Error deleting IAM role: {str(e)}")

        # Always delete the DynamoDB record
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
        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
        logger.info(f"Detached policy {policy['PolicyArn']} from role {role_name}")

    # Delete all inline policies
    inline_policies = iam_client.list_role_policies(RoleName=role_name)["PolicyNames"]
    for policy_name in inline_policies:
        iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
        logger.info(f"Deleted inline policy {policy_name} from role {role_name}")

    # Remove permission boundary if exists
    try:
        role_info = iam_client.get_role(RoleName=role_name)
        if "PermissionsBoundary" in role_info["Role"]:
            iam_client.delete_role_permissions_boundary(RoleName=role_name)
            logger.info(f"Removed permissions boundary from role {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            logger.warning(f"Error checking/removing permission boundary: {str(e)}")

    # Remove any instance profiles associated with the role
    try:
        instance_profiles = iam_client.list_instance_profiles_for_role(
            RoleName=role_name
        )["InstanceProfiles"]
        for profile in instance_profiles:
            profile_name = profile["InstanceProfileName"]
            iam_client.remove_role_from_instance_profile(
                InstanceProfileName=profile_name, RoleName=role_name
            )
            logger.info(
                f"Removed role {role_name} from instance profile {profile_name}"
            )
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            logger.warning(f"Error removing role from instance profiles: {str(e)}")

    # Wait a bit to ensure all detachments are processed
    time.sleep(2)

    # Delete the role
    try:
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Successfully deleted role {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            logger.error(f"Failed to delete role {role_name}: {str(e)}")
            raise


def delete_eventbridge_pipe(pipes_client: Any, pipe_arn: str) -> None:
    """Delete an EventBridge Pipe"""
    # Get the pipe name from ARN
    pipe_name = pipe_arn.split("/")[-1]

    # Check if pipe exists and get its current state
    try:
        pipe_info = pipes_client.describe_pipe(Name=pipe_name)
        current_state = pipe_info.get("CurrentState")

        # Handle different pipe states
        if current_state in ["RUNNING", "STARTING"]:
            # Stop the pipe if it's running or starting
            pipes_client.stop_pipe(Name=pipe_name)
            logger.info(f"Stopping EventBridge Pipe {pipe_name}")

            # Wait for pipe to stop before deleting
            max_retries = 15
            for i in range(max_retries):
                time.sleep(3)
                try:
                    pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                    if pipe_info.get("CurrentState") in [
                        "STOPPED",
                        "STOP_FAILED",
                        "INACTIVE",
                        "CREATED",
                    ]:
                        logger.info(
                            f"EventBridge Pipe {pipe_name} is now in state: {pipe_info.get('CurrentState')}"
                        )
                        break
                    logger.info(
                        f"Waiting for pipe {pipe_name} to stop. Current state: {pipe_info.get('CurrentState')}"
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        logger.info(f"Pipe {pipe_name} no longer exists")
                        return
                    else:
                        logger.warning(f"Error checking pipe state: {str(e)}")
                        break

                if i == max_retries - 1:
                    logger.warning(
                        f"Pipe {pipe_name} did not reach stopped state in time, attempting delete anyway"
                    )
        elif current_state in ["CREATING", "UPDATING", "DELETING"]:
            logger.info(
                f"Pipe {pipe_name} is in {current_state} state. Waiting before deletion attempt."
            )
            max_retries = 20
            for i in range(max_retries):
                time.sleep(3)
                try:
                    pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                    new_state = pipe_info.get("CurrentState")
                    if new_state not in ["CREATING", "UPDATING", "DELETING"]:
                        logger.info(
                            f"Pipe {pipe_name} state changed from {current_state} to {new_state}"
                        )
                        break
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        logger.info(f"Pipe {pipe_name} no longer exists")
                        return
                    else:
                        logger.warning(f"Error checking pipe state: {str(e)}")
                        break

                if i == max_retries - 1:
                    logger.warning(
                        f"Pipe {pipe_name} state remained {current_state} after waiting, attempting delete anyway"
                    )

        # Delete the pipe with retries
        max_delete_retries = 3
        for i in range(max_delete_retries):
            try:
                pipes_client.delete_pipe(Name=pipe_name)
                logger.info(f"Deleted EventBridge Pipe {pipe_name}")
                break
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.info(f"Pipe {pipe_name} already deleted")
                    break
                elif (
                    e.response["Error"]["Code"] == "ConflictException"
                    and i < max_delete_retries - 1
                ):
                    logger.info(
                        f"Pipe {pipe_name} in transition state, retrying deletion in 5 seconds"
                    )
                    time.sleep(5)
                else:
                    logger.error(f"Failed to delete pipe {pipe_name}: {str(e)}")
                    raise

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"Pipe {pipe_name} does not exist, no need to delete")
        else:
            raise


def remove_s3_notifications(s3: Any, bucket_name: str) -> None:
    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration={},
        )
        logger.info(f"Removed S3 bucket notifications for bucket: {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            logger.warning(f"Error removing S3 bucket notification: {str(e)}")


def _verify_rule_bucket(
    eventbridge: Any, rule_name: str, bucket_name: str, connector_id: str
) -> bool:
    try:
        response = eventbridge.describe_rule(Name=rule_name)
        event_pattern = response.get("EventPattern")
        if not event_pattern:
            logger.warning(
                f"rule_name={rule_name}, connector_id={connector_id}, reason=missing_event_pattern"
            )
            return False
        try:
            pattern = json.loads(event_pattern)
        except Exception:
            logger.warning(
                f"rule_name={rule_name}, connector_id={connector_id}, reason=unparseable_event_pattern"
            )
            return False
        bucket_names = pattern.get("detail", {}).get("bucket", {}).get("name", [])
        if bucket_name in bucket_names:
            return True
        logger.warning(
            f"rule_name={rule_name}, connector_id={connector_id}, reason=bucket_not_in_pattern"
        )
        return False
    except Exception as e:
        logger.warning(f"rule_name={rule_name}, connector_id={connector_id}, error={e}")
        return False


def _delete_rule_best_effort(
    eventbridge: Any, rule_name: str, connector_id: str
) -> bool:
    try:
        targets = eventbridge.list_targets_by_rule(Rule=rule_name)["Targets"]
        if targets:
            eventbridge.remove_targets(Rule=rule_name, Ids=[t["Id"] for t in targets])
        eventbridge.delete_rule(Name=rule_name)
        logger.info(
            f"Deleted EventBridge rule: {rule_name}, connector_id={connector_id}"
        )
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("ResourceNotFoundException", "ValidationException"):
            logger.warning(
                f"EventBridge rule not found, skipping: rule_name={rule_name}, connector_id={connector_id}, error_code={code}"
            )
        else:
            logger.warning(
                f"Error deleting EventBridge rule: rule_name={rule_name}, connector_id={connector_id}, error={e}"
            )
        return False


def remove_eventbridge_rule(
    eventbridge: Any,
    connector_id: str,
    region: str,
    stored_rule_name: str | None = None,
    bucket_name: str | None = None,
) -> None:
    if stored_rule_name:
        logger.info(
            f"cleanup_path=stored_name, rule_name={stored_rule_name}, connector_id={connector_id}"
        )
        _delete_rule_best_effort(eventbridge, stored_rule_name, connector_id)
        return

    logger.info(
        f"cleanup_path=legacy_fallback, connector_id={connector_id}, bucket_name={bucket_name}"
    )

    candidates = [f"medialake-connector-{connector_id}"]

    if bucket_name:
        full_prefix = f"medialake-{bucket_name}-s3-events"
        # Derive truncated prefix matching create_resource_name_with_suffix for eventbridge_rule (max 64, minus 5 for -XXXX suffix)
        truncated_prefix = full_prefix[:59]
        prefixes = list(
            dict.fromkeys([full_prefix, truncated_prefix])
        )  # dedupe, preserve order
        for prefix in prefixes:
            try:
                paginator = eventbridge.get_paginator("list_rules")
                for page in paginator.paginate(NamePrefix=prefix):
                    for rule in page.get("Rules", []):
                        name = rule["Name"]
                        if name not in candidates:
                            if _verify_rule_bucket(
                                eventbridge, name, bucket_name, connector_id
                            ):
                                logger.info(
                                    f"rule_name={name}, connector_id={connector_id}, bucket_name={bucket_name}, status=bucket_verified"
                                )
                                candidates.append(name)
                            else:
                                logger.warning(
                                    f"rule_name={name}, connector_id={connector_id}, bucket_name={bucket_name}, status=bucket_mismatch_skipped"
                                )
                logger.info(
                    f"legacy_discovery prefix={prefix}, rules_found={len(candidates) - 1}"
                )
            except Exception as e:
                logger.warning(
                    f"Error during legacy rule discovery: prefix={prefix}, error={e}"
                )

    for rule_name in candidates:
        deleted = _delete_rule_best_effort(eventbridge, rule_name, connector_id)
        if deleted:
            logger.info(
                f"Legacy cleanup deleted rule: {rule_name}, connector_id={connector_id}"
            )
        else:
            logger.warning(
                f"Legacy cleanup skipped rule: {rule_name}, connector_id={connector_id}"
            )
