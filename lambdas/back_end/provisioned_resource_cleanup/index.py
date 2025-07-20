import os
import time
from typing import Any, List

import boto3
import cfnresponse
from botocore.exceptions import ClientError
from lambda_utils import logger, tracer

# Initialize AWS clients using regular boto3
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
iam = boto3.client("iam")
s3 = boto3.client("s3")
sqs = boto3.client("sqs")
cloudwatch_logs = boto3.client("logs")
eventbridge = boto3.client("events")
pipes = boto3.client("pipes")
secrets_manager = boto3.client("secretsmanager")

# Define log groups to clean up
LOG_GROUPS_TO_CLEAN = ["/aws/apigateway/medialake-access-logs"]


def get_s3_vector_client():
    """Initialize S3 Vector Store client with custom boto3 SDK."""
    try:
        # Import custom boto3 from the layer for S3 Vector operations only
        # The custom boto3 layer will override the regular boto3 import within this function scope
        import boto3 as custom_boto3

        session = custom_boto3.Session()
        client = session.client(
            "s3vectors", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
        return client
    except Exception as e:
        logger.error(f"Failed to initialize S3 Vector client: {str(e)}")
        return None


def delete_s3_vector_indexes(client, bucket_name: str):
    """Delete all vector indexes in a bucket."""
    try:
        # List all indexes in the bucket
        response = client.list_indexes(vectorBucketName=bucket_name)
        indexes = response.get("indexes", [])

        for index in indexes:
            index_name = index.get("indexName")
            if index_name:
                try:
                    client.delete_index(
                        vectorBucketName=bucket_name, indexName=index_name
                    )
                    logger.info(
                        f"Deleted S3 Vector index {index_name} from bucket {bucket_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to delete S3 Vector index {index_name}: {str(e)}"
                    )

    except Exception as e:
        logger.error(
            f"Failed to list/delete S3 Vector indexes in bucket {bucket_name}: {str(e)}"
        )


def delete_s3_vector_bucket(client, bucket_name: str):
    """Delete S3 Vector bucket and all its indexes."""
    try:
        # First delete all indexes in the bucket
        delete_s3_vector_indexes(client, bucket_name)

        # Then delete the bucket
        client.delete_vector_bucket(vectorBucketName=bucket_name)
        logger.info(f"Deleted S3 Vector bucket {bucket_name}")

    except Exception as e:
        if "NotFoundException" in str(e) or "NoSuchBucket" in str(e):
            logger.warning(
                f"S3 Vector bucket {bucket_name} not found or already deleted"
            )
        else:
            logger.error(f"Failed to delete S3 Vector bucket {bucket_name}: {str(e)}")
            raise


def cleanup_s3_vector_resources():
    """Clean up S3 Vector Store resources."""
    try:
        # Get S3 Vector client
        s3_vector_client = get_s3_vector_client()
        if not s3_vector_client:
            logger.warning(
                "Could not initialize S3 Vector client, skipping S3 Vector cleanup"
            )
            return

        # Get bucket name from environment or use default pattern
        vector_bucket_name = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket_name:
            # Try to construct bucket name from environment
            environment = os.environ.get("ENVIRONMENT", "dev")
            region = os.environ.get("AWS_REGION", "us-east-1")
            vector_bucket_name = f"medialake-vectors-{region}-{environment}"

        logger.info(f"Cleaning up S3 Vector bucket: {vector_bucket_name}")
        delete_s3_vector_bucket(s3_vector_client, vector_bucket_name)

    except Exception as e:
        logger.error(f"Error during S3 Vector cleanup: {str(e)}")
        # Don't raise the exception to avoid failing the entire cleanup process


def delete_lambda_function(function_arn: str):
    """Delete Lambda function and its event source mappings"""
    try:
        # Delete event source mappings first
        try:
            mappings = lambda_client.list_event_source_mappings(
                FunctionName=function_arn
            )
            for mapping in mappings.get("EventSourceMappings", []):
                try:
                    lambda_client.delete_event_source_mapping(UUID=mapping["UUID"])
                    logger.info(f"Deleted event source mapping {mapping['UUID']}")
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        raise
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        # Delete the function
        lambda_client.delete_function(FunctionName=function_arn.split(":")[-1])
        logger.info(f"Deleted Lambda function {function_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"Lambda function {function_arn} already deleted")


def delete_iam_role(role_arn: str):
    """Delete IAM role and its policies"""
    try:
        role_name = role_arn.split("/")[-1]

        # Detach managed policies
        attached_policies = iam.list_attached_role_policies(RoleName=role_name)[
            "AttachedPolicies"
        ]
        for policy in attached_policies:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
            logger.info(f"Detached policy {policy['PolicyArn']} from role {role_name}")

        # Delete inline policies
        inline_policies = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
        for policy_name in inline_policies:
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            logger.info(f"Deleted inline policy {policy_name} from role {role_name}")

        # Delete the role
        iam.delete_role(RoleName=role_name)
        logger.info(f"Deleted IAM role {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        logger.warning(f"IAM role {role_name} already deleted")


def clean_up_table_resources(table_name, clean_up_function):
    table = dynamodb.Table(table_name)
    response = table.scan()
    items = response["Items"]

    for item in items:
        try:
            logger.info(f"Cleaning up {table_name} item: %s", item["id"])
            clean_up_function(item, table)
        except Exception as e:
            logger.error(
                f"Error cleaning up {table_name} item %s: %s", item["id"], str(e)
            )
            continue


def clean_up_connector(item, table):
    errors = []

    # Existing connector cleanup logic
    if "lambdaArn" in item:
        try:
            delete_lambda_function(item["lambdaArn"])
        except Exception as e:
            errors.append(f"Error deleting Lambda function: {str(e)}")

    if "iamRoleArn" in item:
        try:
            delete_iam_role(item["iamRoleArn"])
        except Exception as e:
            errors.append(f"Error deleting IAM role: {str(e)}")

    if "queueUrl" in item:
        try:
            logger.info(
                f"Attempting to delete SQS queue from connector with queueUrl: {item['queueUrl']}"
            )
            delete_sqs_queue(item["queueUrl"])
        except Exception as e:
            errors.append(f"Error deleting SQS queue: {str(e)}")

    if "storageIdentifier" in item:
        try:
            remove_s3_bucket_notification(item)
        except Exception as e:
            errors.append(f"Error removing S3 bucket notification: {str(e)}")

    # Handle different integration methods
    integration_method = item.get("integrationMethod")
    if integration_method == "eventbridge":
        if "eventBridgeDetails" in item:
            event_bus_name = item["eventBridgeDetails"].get("eventBusName")
            if event_bus_name:
                try:
                    delete_event_bus_and_rules(event_bus_name)
                except Exception as e:
                    errors.append(f"Error deleting event bus and rules: {str(e)}")

            rule_name = item["eventBridgeDetails"].get("ruleName")
            parent_event_bus_name = item["eventBridgeDetails"].get("parentEventBusName")
            if rule_name and parent_event_bus_name:
                try:
                    delete_eventbridge_rule(rule_name, parent_event_bus_name)
                except Exception as e:
                    errors.append(f"Error deleting EventBridge rule: {str(e)}")
    elif integration_method == "s3Notifications":
        # S3 notifications are already handled by remove_s3_bucket_notification
        pass
    else:
        logger.warning(f"Unknown integration method: {integration_method}")

    # Clean up EventBridge Pipe if present
    if "pipeArn" in item:
        try:
            delete_eventbridge_pipe(item["pipeArn"])
        except Exception as e:
            errors.append(f"Error deleting EventBridge Pipe: {str(e)}")

    # Clean up EventBridge Pipe IAM role if present
    if "pipeRoleArn" in item:
        try:
            delete_iam_role(item["pipeRoleArn"])
        except Exception as e:
            errors.append(f"Error deleting EventBridge Pipe IAM role: {str(e)}")

    # Delete the connector record
    try:
        table.delete_item(Key={"id": item["id"]})
        logger.info(f"Deleted connector record {item['id']}")
    except Exception as e:
        errors.append(f"Error deleting connector record: {str(e)}")

    if errors:
        logger.error(
            f"Errors occurred while cleaning up connector {item['id']}: {errors}"
        )
    else:
        logger.info(f"Successfully cleaned up connector {item['id']}")

    return errors


def clean_up_pipeline(item, table):
    errors = []

    if "dependentResources" in item:
        for resource in item["dependentResources"]:
            try:
                # Check if resource is a sequence (list or tuple) with at least 2 elements
                if not isinstance(resource, (list, tuple)) or len(resource) < 2:
                    logger.warning(
                        f"Invalid resource format: {resource}. Expected [type, identifier]"
                    )
                    continue

                resource_type = resource[0]
                resource_identifier = resource[1]

                logger.info(
                    f"Cleaning up resource of type {resource_type}: {resource_identifier}"
                )

                if resource_type == "sqs" or resource_type == "sqs_queue":
                    logger.info(
                        f"Attempting to delete SQS queue with identifier: {resource_identifier}"
                    )
                    delete_sqs_queue(resource_identifier)
                elif resource_type == "eventbridge_rule":
                    # Handle the new format where resource_identifier is an ARN string
                    # Format: arn:aws:events:region:account-id:rule/event-bus-name/rule-name
                    if isinstance(
                        resource_identifier, str
                    ) and resource_identifier.startswith("arn:aws:events:"):
                        # Parse the ARN to extract rule name and event bus name
                        parts = resource_identifier.split(":")
                        if len(parts) >= 6:
                            rule_path = parts[5]
                            if rule_path.startswith("rule/"):
                                path_parts = rule_path[5:].split(
                                    "/", 1
                                )  # Remove 'rule/' prefix and split
                                if len(path_parts) == 2:
                                    event_bus_name = path_parts[0]
                                    rule_name = path_parts[1]
                                    delete_eventbridge_rule(rule_name, event_bus_name)
                                else:
                                    # Default event bus
                                    rule_name = path_parts[0]
                                    delete_eventbridge_rule(rule_name, "default")
                            else:
                                logger.warning(
                                    f"Invalid EventBridge rule ARN format: {resource_identifier}"
                                )
                    # Handle the old format where resource_identifier is a dictionary
                    elif (
                        isinstance(resource_identifier, dict)
                        and "rule_name" in resource_identifier
                        and "eventbus_name" in resource_identifier
                    ):
                        delete_eventbridge_rule(
                            resource_identifier["rule_name"],
                            resource_identifier["eventbus_name"],
                        )
                    else:
                        logger.warning(
                            f"Unrecognized EventBridge rule format: {resource_identifier}"
                        )
                elif resource_type in [
                    "iam_stepfunction_role",
                    "iam_lambda_trigger_role",
                    "iam_role",
                    "lambda_role",
                    "sfn_role",
                    "events_role",
                    "service_role",
                ]:
                    delete_iam_role(resource_identifier)
                elif resource_type == "step_function":
                    delete_step_function(resource_identifier)
                elif resource_type == "lambda" or resource_type == "trigger_lambda":
                    delete_lambda_function(resource_identifier)
                elif resource_type == "event_source_mapping":
                    delete_event_source_mapping(resource_identifier)
                elif resource_type == "eventbridge_pipe" or resource_type == "pipe":
                    delete_eventbridge_pipe(resource_identifier)
                else:
                    logger.warning(f"Unknown resource type: {resource_type}")
            except Exception as e:
                error_msg = f"Error cleaning up {resource_type} resource {resource_identifier}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

    # Delete the pipeline record
    try:
        table.delete_item(Key={"id": item["id"]})
        logger.info(f"Deleted pipeline record {item['id']}")
    except Exception as e:
        error_msg = f"Error deleting pipeline record: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    if errors:
        logger.error(
            f"Errors occurred while cleaning up pipeline {item['id']}: {errors}"
        )
    else:
        logger.info(f"Successfully cleaned up pipeline {item['id']}")


def delete_sqs_queue(queue_identifier):
    """
    Delete an SQS queue.

    Args:
        queue_identifier: Either a queue URL or queue ARN
    """
    try:
        # Check if the identifier is an ARN or URL
        if queue_identifier.startswith("arn:aws:sqs:"):
            # Extract queue URL from ARN
            # ARN format: arn:aws:sqs:region:account-id:queue-name
            parts = queue_identifier.split(":")
            if len(parts) >= 6:
                region = parts[3]
                account_id = parts[4]
                queue_name = parts[5]

                # Construct the queue URL
                queue_url = (
                    f"https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}"
                )
                logger.info(
                    f"Converting SQS ARN to URL: {queue_identifier} -> {queue_url}"
                )
            else:
                logger.error(f"Invalid SQS ARN format: {queue_identifier}")
                raise ValueError(f"Invalid SQS ARN format: {queue_identifier}")
        elif queue_identifier.startswith("https://sqs.") or queue_identifier.startswith(
            "http://sqs."
        ):
            # It's already a queue URL
            queue_url = queue_identifier
            logger.info(f"Using provided SQS queue URL: {queue_url}")
        else:
            # Backward compatibility: assume it might be a queue URL in a different format
            # or try to use it as-is
            queue_url = queue_identifier
            logger.info(
                f"Using queue identifier as-is (backward compatibility): {queue_url}"
            )

        sqs.delete_queue(QueueUrl=queue_url)
        logger.info(f"Successfully deleted SQS queue: {queue_url}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
            raise
        logger.warning(f"SQS queue {queue_identifier} already deleted or not found")
    except Exception as e:
        logger.error(f"Error deleting SQS queue {queue_identifier}: {str(e)}")
        raise


def delete_eventbridge_rule(rule_name, event_bus_name):
    try:
        events = boto3.client("events")
        # Remove targets from the rule
        targets = events.list_targets_by_rule(
            Rule=rule_name, EventBusName=event_bus_name
        )
        if targets["Targets"]:
            target_ids = [t["Id"] for t in targets["Targets"]]
            events.remove_targets(
                Rule=rule_name, EventBusName=event_bus_name, Ids=target_ids
            )

        # Delete the rule
        events.delete_rule(Name=rule_name, EventBusName=event_bus_name)
        logger.info(
            f"Deleted EventBridge rule {rule_name} from event bus {event_bus_name}"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"EventBridge rule {rule_name} already deleted")


def delete_event_bus_and_rules(event_bus_name):
    events = boto3.client("events")

    # List all rules for the event bus
    paginator = events.get_paginator("list_rules")
    for page in paginator.paginate(EventBusName=event_bus_name):
        for rule in page["Rules"]:
            delete_eventbridge_rule(rule["Name"], event_bus_name)

    # Delete the event bus
    try:
        events.delete_event_bus(Name=event_bus_name)
        logger.info(f"Deleted EventBridge event bus {event_bus_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"EventBridge event bus {event_bus_name} already deleted")


def delete_step_function(state_machine_arn):
    try:
        sfn = boto3.client("stepfunctions")

        # Check if there are any running executions
        try:
            # List executions
            paginator = sfn.get_paginator("list_executions")
            for page in paginator.paginate(stateMachineArn=state_machine_arn):
                for execution in page["executions"]:
                    if execution["status"] in ["RUNNING", "PENDING"]:
                        # Stop running executions
                        try:
                            logger.info(
                                f"Stopping execution {execution['executionArn']}"
                            )
                            sfn.stop_execution(
                                executionArn=execution["executionArn"],
                                cause="Cleanup during stack deletion",
                            )
                        except Exception as stop_error:
                            logger.warning(
                                f"Failed to stop execution {execution['executionArn']}: {str(stop_error)}"
                            )
        except Exception as list_error:
            logger.warning(
                f"Error listing executions for {state_machine_arn}: {str(list_error)}"
            )

        # Delete the state machine
        sfn.delete_state_machine(stateMachineArn=state_machine_arn)
        logger.info(f"Deleted Step Function {state_machine_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "StateMachineDoesNotExist":
            raise
        logger.warning(f"Step Function {state_machine_arn} already deleted")


def delete_event_source_mapping(uuid):
    max_retries = 30
    base_delay = 1  # Start with a 1-second delay

    for attempt in range(max_retries):
        try:
            lambda_client.delete_event_source_mapping(UUID=uuid)
            logger.info(f"Deleted event source mapping {uuid}")

            # Wait for the mapping to be fully deleted
            wait_attempts = 5
            for wait_attempt in range(wait_attempts):
                try:
                    # Check if the mapping still exists
                    lambda_client.get_event_source_mapping(UUID=uuid)
                    # If we get here, the mapping still exists, wait and try again
                    if wait_attempt < wait_attempts - 1:
                        time.sleep(2)
                    else:
                        logger.warning(
                            f"Event source mapping {uuid} still exists after waiting"
                        )
                except ClientError as wait_error:
                    if (
                        wait_error.response["Error"]["Code"]
                        == "ResourceNotFoundException"
                    ):
                        # Mapping is gone, we can return
                        logger.info(
                            f"Confirmed deletion of event source mapping {uuid}"
                        )
                        return
                    else:
                        # Some other error occurred
                        raise

            return
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning(f"Event source mapping {uuid} already deleted")
                return
            elif e.response["Error"]["Code"] == "ResourceInUseException":
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Event source mapping {uuid} in use. Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to delete event source mapping {uuid} after {max_retries} attempts"
                    )
                    raise
            else:
                raise

    logger.error(
        f"Failed to delete event source mapping {uuid} after {max_retries} attempts"
    )


def remove_eventbridge_rule(eventbridge: Any, connector_id: str) -> List[str]:
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


def remove_s3_bucket_notification(item):
    bucket_name = item["storageIdentifier"]
    integration_method = item.get("integrationMethod")
    try:
        logger.info(f"Removing notifications of type {integration_method}")
        if integration_method == "eventbridge":
            logger.info(f"Removing {integration_method}")
            remove_eventbridge_rule(eventbridge, item["id"])
        elif integration_method == "s3Notifications":
            logger.info(f"Removing {integration_method}")

            s3.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={},  # Empty config removes all notifications
            )
        else:
            logger.warning(f"Unknown integration method {integration_method}")

        logger.info(f"Removed notifications from bucket {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            raise
        logger.warning(f"S3 bucket {bucket_name} not found")


def delete_cloudwatch_log_groups(log_group_names):
    """Delete multiple CloudWatch log groups if they exist"""
    for log_group_name in log_group_names:
        try:
            cloudwatch_logs.delete_log_group(logGroupName=log_group_name)
            logger.info(f"Deleted CloudWatch log group {log_group_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            logger.warning(f"CloudWatch log group {log_group_name} not found")


def delete_eventbridge_pipe(pipe_arn):
    """Delete an EventBridge Pipe"""
    try:
        # Get the pipe name from ARN
        pipe_name = pipe_arn.split("/")[-1]

        # Check if pipe exists and get its current state
        try:
            pipe_info = pipes.describe_pipe(Name=pipe_name)
            current_state = pipe_info.get("CurrentState")

            # If pipe is running, stop it first
            if current_state == "RUNNING":
                pipes.stop_pipe(Name=pipe_name)
                logger.info(f"Stopped EventBridge Pipe {pipe_name}")

                # Wait for pipe to stop before deleting
                max_retries = 10
                for i in range(max_retries):
                    time.sleep(2)  # Wait 2 seconds between checks
                    pipe_info = pipes.describe_pipe(Name=pipe_name)
                    if pipe_info.get("CurrentState") != "RUNNING":
                        break
                    if i == max_retries - 1:
                        logger.warning(
                            f"Pipe {pipe_name} did not stop in time, attempting delete anyway"
                        )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        # Delete the pipe
        pipes.delete_pipe(Name=pipe_name)
        logger.info(f"Deleted EventBridge Pipe {pipe_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        logger.warning(f"EventBridge Pipe {pipe_arn} already deleted")


def delete_secrets_manager_secrets():
    """Delete secrets from Secrets Manager that match specific patterns"""
    try:
        # Define the patterns to match
        patterns = [
            "integration/",  # Matches integration/{uuid}/api-key
            "medialake/search/provider/",  # Matches medialake/search/provider/{uuid}
        ]

        logger.info("Starting cleanup of Secrets Manager secrets")

        # List all secrets
        paginator = secrets_manager.get_paginator("list_secrets")
        deleted_count = 0

        for page in paginator.paginate():
            for secret in page.get("SecretList", []):
                secret_name = secret["Name"]

                # Check if the secret matches any of our patterns
                should_delete = False
                for pattern in patterns:
                    if secret_name.startswith(pattern):
                        # Additional validation for integration pattern
                        if pattern == "integration/":
                            # Should match: integration/{uuid}/api-key
                            parts = secret_name.split("/")
                            if len(parts) == 3 and parts[2] == "api-key":
                                should_delete = True
                                break
                        elif pattern == "medialake/search/provider/":
                            # Should match: medialake/search/provider/{uuid}
                            parts = secret_name.split("/")
                            if len(parts) == 4:  # medialake/search/provider/{uuid}
                                should_delete = True
                                break

                if should_delete:
                    try:
                        # Delete the secret immediately (force delete without recovery window)
                        secrets_manager.delete_secret(
                            SecretId=secret_name, ForceDeleteWithoutRecovery=True
                        )
                        logger.info(f"Deleted secret: {secret_name}")
                        deleted_count += 1
                    except ClientError as e:
                        if e.response["Error"]["Code"] == "ResourceNotFoundException":
                            logger.warning(f"Secret {secret_name} already deleted")
                        elif e.response["Error"]["Code"] == "InvalidRequestException":
                            logger.warning(
                                f"Secret {secret_name} already scheduled for deletion"
                            )
                        else:
                            logger.error(
                                f"Error deleting secret {secret_name}: {str(e)}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Unexpected error deleting secret {secret_name}: {str(e)}"
                        )

        logger.info(
            f"Completed Secrets Manager cleanup. Deleted {deleted_count} secrets"
        )

    except Exception as e:
        logger.error(f"Error during Secrets Manager cleanup: {str(e)}")
        raise


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event: %s", event)
        request_type = event["RequestType"]

        if request_type == "Delete":
            connector_table_name = os.environ["CONNECTOR_TABLE"]
            pipeline_table_name = os.environ["PIPELINE_TABLE"]

            # Clean up pipeline resources
            logger.info("Starting cleanup of pipeline resources")
            clean_up_table_resources(pipeline_table_name, clean_up_pipeline)

            # Clean up connector resources
            logger.info("Starting cleanup of connector resources")
            clean_up_table_resources(connector_table_name, clean_up_connector)

            # Clean up CloudWatch log groups
            logger.info("Starting cleanup of CloudWatch log groups")
            delete_cloudwatch_log_groups(LOG_GROUPS_TO_CLEAN)

            # Clean up Secrets Manager secrets
            logger.info("Starting cleanup of Secrets Manager secrets")
            delete_secrets_manager_secrets()

            # Clean up S3 Vector Store resources
            logger.info("Starting cleanup of S3 Vector Store resources")
            cleanup_s3_vector_resources()

            # Additional cleanup for any orphaned resources
            try:
                # Check for orphaned EventBridge pipes
                logger.info("Checking for orphaned EventBridge pipes")
                pipes_paginator = pipes.get_paginator("list_pipes")
                for page in pipes_paginator.paginate():
                    for pipe in page.get("Pipes", []):
                        if "medialake" in pipe["Name"].lower():
                            try:
                                logger.info(
                                    f"Cleaning up orphaned EventBridge pipe: {pipe['Name']}"
                                )
                                delete_eventbridge_pipe(pipe["Arn"])
                            except Exception as e:
                                logger.error(
                                    f"Error cleaning up orphaned pipe {pipe['Name']}: {str(e)}"
                                )
            except Exception as e:
                logger.error(f"Error during orphaned resource cleanup: {str(e)}")

            logger.info("Cleanup completed successfully")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        else:
            # For Create/Update events, just respond success
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

    except Exception as e:
        logger.error("Error during cleanup: %s", str(e))
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
