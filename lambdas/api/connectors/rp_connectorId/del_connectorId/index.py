import json
import os
import time
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from cors_utils import create_error_response, create_response

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
            return create_error_response(400, "Connector ID is required")

        # Get connector details from DynamoDB
        try:
            response = table.get_item(Key={"id": connector_id})
        except ClientError as e:
            logger.error(f"DynamoDB get_item failed: {str(e)}")
            return create_error_response(500, "Failed to retrieve connector details")

        if "Item" not in response:
            logger.warning(f"Connector not found with ID: {connector_id}")
            return create_error_response(404, "Connector not found")

        connector = response["Item"]
        region = connector.get("region", "us-east-1")
        queue_url = connector.get("queueUrl")
        bucket_name = connector.get("storageIdentifier")
        lambda_arn = connector.get("lambdaArn")
        iam_role_arn = connector.get("iamRoleArn")
        pipe_arn = connector.get("pipeArn")
        pipe_role_arn = connector.get("pipeRoleArn")
        integration_method = connector.get("integrationMethod")
        event_bridge_rule_name = connector.get("eventBridgeRuleName")

        # Create AWS clients in the specified region
        lambda_client = boto3.client("lambda", region_name=region)
        iam = boto3.client("iam", region_name=region)
        s3 = boto3.client("s3", region_name=region)
        sqs = boto3.client("sqs", region_name=region)
        eventbridge = boto3.client("events", region_name=region)
        pipes_client = boto3.client("pipes", region_name=region)

        # Best-effort cleanup — each step is wrapped individually

        # Delete EventBridge Pipe if it exists (regardless of recorded
        # integration method — clean it up whenever a pipe ARN is present).
        if pipe_arn:
            pipe_name = pipe_arn.split(":")[-1].split("/")[-1]
            try:
                pipe_info = pipes_client.describe_pipe(Name=pipe_name)
                if pipe_info.get("CurrentState") == "RUNNING":
                    logger.info(f"Stopping pipe: {pipe_name}")
                    pipes_client.stop_pipe(Name=pipe_name)
                    time.sleep(10)

                max_retries = 4
                base_delay = 2
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
                            if attempt < max_retries - 1:
                                delay = base_delay * (2**attempt)
                                logger.warning(
                                    f"Pipe {pipe_name} is updating concurrently. Retrying in {delay} seconds (attempt {attempt + 1}/{max_retries})"
                                )
                                time.sleep(delay)
                            else:
                                logger.warning(
                                    f"Error deleting Pipe {pipe_name} after {max_retries} attempts: {str(delete_error)}"
                                )
                        elif (
                            delete_error.response["Error"]["Code"]
                            == "ResourceNotFoundException"
                        ):
                            logger.warning(
                                f"Pipe {pipe_name} does not exist, skipping deletion"
                            )
                            break
                        else:
                            logger.warning(
                                f"Error deleting Pipe {pipe_name}: {str(delete_error)}"
                            )
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
                    logger.warning(
                        f"Error describing/stopping Pipe {pipe_name}: {str(e)}"
                    )

        # Delete Pipe IAM role
        if pipe_role_arn:
            pipe_role_name = pipe_role_arn.split("/")[-1]
            try:
                attached_policies = iam.list_attached_role_policies(
                    RoleName=pipe_role_name
                )["AttachedPolicies"]
                for policy in attached_policies:
                    iam.detach_role_policy(
                        RoleName=pipe_role_name, PolicyArn=policy["PolicyArn"]
                    )
                inline_policies = iam.list_role_policies(RoleName=pipe_role_name)[
                    "PolicyNames"
                ]
                for policy_name in inline_policies:
                    iam.delete_role_policy(
                        RoleName=pipe_role_name, PolicyName=policy_name
                    )
                iam.delete_role(RoleName=pipe_role_name)
                logger.info(f"Deleted Pipe IAM role: {pipe_role_name}")
            except ClientError as e:
                logger.warning(f"Error deleting Pipe IAM role: {str(e)}")

        # Delete Lambda
        if lambda_arn:
            function_name = lambda_arn.split(":")[-1]
            try:
                lambda_client.delete_function(FunctionName=function_name)
                logger.info(f"Deleted Lambda function: {lambda_arn}")
            except ClientError as e:
                logger.warning(f"Error deleting Lambda: {str(e)}")

            # Delete the Lambda's CloudWatch log group — AWS does NOT remove it
            # when the function is deleted, so it would otherwise be orphaned.
            logs_client = boto3.client("logs", region_name=region)
            try:
                logs_client.delete_log_group(
                    logGroupName=f"/aws/lambda/{function_name}"
                )
                logger.info(f"Deleted log group for function: {function_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    logger.warning(f"Error deleting log group: {str(e)}")

        # Delete main IAM role
        if iam_role_arn:
            role_name = iam_role_arn.split("/")[-1]
            try:
                attached_policies = iam.list_attached_role_policies(RoleName=role_name)[
                    "AttachedPolicies"
                ]
                for policy in attached_policies:
                    iam.detach_role_policy(
                        RoleName=role_name, PolicyArn=policy["PolicyArn"]
                    )
                inline_policies = iam.list_role_policies(RoleName=role_name)[
                    "PolicyNames"
                ]
                for policy_name in inline_policies:
                    iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                iam.delete_role(RoleName=role_name)
                logger.info(f"Deleted IAM role: {role_name}")
            except ClientError as e:
                logger.warning(f"Error deleting IAM role: {str(e)}")

        # Delete SQS queue
        if queue_url:
            try:
                sqs.delete_queue(QueueUrl=queue_url)
                logger.info(f"Deleted SQS queue: {queue_url}")
            except ClientError as e:
                logger.warning(f"Error deleting SQS queue: {str(e)}")

        # Remove S3 bucket notification or EventBridge rule
        if integration_method == "s3Notifications" and bucket_name:
            try:
                notification_name = (
                    f"{os.environ.get('RESOURCE_PREFIX')}_notifications_{connector_id}"
                )
                remove_event_notification_by_name(s3, bucket_name, notification_name)
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

        # Remove CORS configuration if allowUploads was enabled and corsRuleId exists
        allow_uploads = connector.get("allowUploads", False)
        cors_rule_id = connector.get("corsRuleId")
        if allow_uploads and cors_rule_id:
            try:
                remove_medialake_cors_rule(s3, bucket_name, cors_rule_id)
            except Exception as e:
                logger.warning(f"Error removing CORS rule: {str(e)}")

        # Conditionally delete S3 bucket (if managed by MediaLake and empty)
        creation_type = connector.get("creationType")
        if creation_type == "new" and bucket_name:
            try:
                list_response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                if "Contents" in list_response and len(list_response["Contents"]) > 0:
                    logger.warning(
                        f"Bucket '{bucket_name}' is not empty. Skipping deletion."
                    )
                else:
                    s3.delete_bucket(Bucket=bucket_name)
                    logger.info(f"Successfully deleted S3 bucket: {bucket_name}")
            except ClientError as e:
                logger.warning(
                    f"Error checking or deleting S3 bucket '{bucket_name}': {str(e)}"
                )

        # Always delete the DynamoDB record
        try:
            table.delete_item(Key={"id": connector_id})
            logger.info(f"Successfully deleted connector with ID: {connector_id}")
            return create_response(200, {"message": "Connector deleted successfully"})
        except ClientError as e:
            logger.error(f"Failed to delete connector from DynamoDB: {str(e)}")
            return create_response(
                500,
                {"message": "Failed to delete connector record", "error": str(e)},
            )

    except Exception as e:
        logger.exception("Unexpected error occurred")
        return create_error_response(500, f"Internal server error: {str(e)}")


def remove_event_notification_by_name(
    s3: Any, bucket_name: str, notification_name: str
) -> None:
    try:
        current_config = s3.get_bucket_notification_configuration(Bucket=bucket_name)
        new_config = {}
        if "EventBridgeConfiguration" in current_config:
            new_config["EventBridgeConfiguration"] = current_config[
                "EventBridgeConfiguration"
            ]

        notification_config_types = [
            "TopicConfigurations",
            "QueueConfigurations",
            "LambdaFunctionConfigurations",
        ]
        for config_type in notification_config_types:
            configs = current_config.get(config_type)
            if configs and isinstance(configs, list):
                filtered_configs = [
                    config
                    for config in configs
                    if config.get("Id", "") != notification_name
                ]
                if filtered_configs:
                    new_config[config_type] = filtered_configs

        s3.put_bucket_notification_configuration(
            Bucket=bucket_name, NotificationConfiguration=new_config
        )
        logger.info(
            f"Removed notification '{notification_name}' from bucket: {bucket_name}"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            logger.warning(
                f"Error removing S3 bucket notification '{notification_name}': {str(e)}"
            )


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


def remove_medialake_cors_rule(
    s3: Any, bucket_name: str, cors_rule_id: str | None = None
) -> None:
    """Remove only MediaLake's CORS rule from the bucket, preserving other rules."""
    try:
        try:
            cors_config = s3.get_bucket_cors(Bucket=bucket_name)
            rules = cors_config.get("CORSRules", [])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchCORSConfiguration":
                logger.warning(f"No CORS configuration found for bucket {bucket_name}")
                return
            raise

        if cors_rule_id:
            filtered_rules = [r for r in rules if r.get("ID") != cors_rule_id]
        else:
            filtered_rules = [
                r for r in rules if not r.get("ID", "").startswith("medialake-upload-")
            ]

        rules_removed = len(rules) - len(filtered_rules)
        if rules_removed == 0:
            return

        if filtered_rules:
            s3.put_bucket_cors(
                Bucket=bucket_name, CORSConfiguration={"CORSRules": filtered_rules}
            )
        else:
            s3.delete_bucket_cors(Bucket=bucket_name)
        logger.info(f"Removed {rules_removed} CORS rule(s) from bucket {bucket_name}")
    except ClientError as e:
        logger.warning(f"Error removing CORS rule from bucket {bucket_name}: {str(e)}")
