import time
import os
import boto3
import cfnresponse
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from lambda_utils import lambda_handler_decorator, logger, metrics, tracer, handle_error
from typing import List, Any


# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
iam = boto3.client("iam")
s3 = boto3.client("s3")
sqs = boto3.client("sqs")
cloudwatch_logs = boto3.client("logs")
eventbridge = boto3.client("events")
pipes = boto3.client("pipes")

# Define log groups to clean up
LOG_GROUPS_TO_CLEAN = ["/aws/apigateway/medialake-access-logs"]


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
                    logger.warning(f"Invalid resource format: {resource}. Expected [type, identifier]")
                    continue
                
                resource_type = resource[0]
                resource_identifier = resource[1]
                
                logger.info(f"Cleaning up resource of type {resource_type}: {resource_identifier}")
                
                if resource_type == "sqs":
                    delete_sqs_queue(resource_identifier)
                elif resource_type == "eventbridge_rule":
                    # Handle the new format where resource_identifier is an ARN string
                    # Format: arn:aws:events:region:account-id:rule/event-bus-name/rule-name
                    if isinstance(resource_identifier, str) and resource_identifier.startswith("arn:aws:events:"):
                        # Parse the ARN to extract rule name and event bus name
                        parts = resource_identifier.split(":")
                        if len(parts) >= 6:
                            rule_path = parts[5]
                            if rule_path.startswith("rule/"):
                                path_parts = rule_path[5:].split("/", 1)  # Remove 'rule/' prefix and split
                                if len(path_parts) == 2:
                                    event_bus_name = path_parts[0]
                                    rule_name = path_parts[1]
                                    delete_eventbridge_rule(rule_name, event_bus_name)
                                else:
                                    # Default event bus
                                    rule_name = path_parts[0]
                                    delete_eventbridge_rule(rule_name, "default")
                            else:
                                logger.warning(f"Invalid EventBridge rule ARN format: {resource_identifier}")
                    # Handle the old format where resource_identifier is a dictionary
                    elif isinstance(resource_identifier, dict) and "rule_name" in resource_identifier and "eventbus_name" in resource_identifier:
                        delete_eventbridge_rule(
                            resource_identifier["rule_name"],
                            resource_identifier["eventbus_name"],
                        )
                    else:
                        logger.warning(f"Unrecognized EventBridge rule format: {resource_identifier}")
                elif resource_type in ["iam_stepfunction_role", "iam_lambda_trigger_role"]:
                    delete_iam_role(resource_identifier)
                elif resource_type == "step_function":
                    delete_step_function(resource_identifier)
                elif resource_type == "lambda":
                    delete_lambda_function(resource_identifier)
                elif resource_type == "event_source_mapping":
                    delete_event_source_mapping(resource_identifier)
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
        logger.error(f"Errors occurred while cleaning up pipeline {item['id']}: {errors}")
    else:
        logger.info(f"Successfully cleaned up pipeline {item['id']}")


def delete_sqs_queue(queue_url):
    try:
        sqs.delete_queue(QueueUrl=queue_url)
        logger.info(f"Deleted SQS queue {queue_url}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
            raise
        logger.warning(f"SQS queue {queue_url} already deleted")


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
            current_state = pipe_info.get('CurrentState')
            
            # If pipe is running, stop it first
            if current_state == 'RUNNING':
                pipes.stop_pipe(Name=pipe_name)
                logger.info(f"Stopped EventBridge Pipe {pipe_name}")
                
                # Wait for pipe to stop before deleting
                max_retries = 10
                for i in range(max_retries):
                    time.sleep(2)  # Wait 2 seconds between checks
                    pipe_info = pipes.describe_pipe(Name=pipe_name)
                    if pipe_info.get('CurrentState') != 'RUNNING':
                        break
                    if i == max_retries - 1:
                        logger.warning(f"Pipe {pipe_name} did not stop in time, attempting delete anyway")
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


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event: %s", event)
        request_type = event["RequestType"]

        if request_type == "Delete":
            connector_table_name = os.environ["CONNECTOR_TABLE"]
            pipeline_table_name = os.environ["PIPELINE_TABLE"]

            # Clean up pipeline resources
            clean_up_table_resources(pipeline_table_name, clean_up_pipeline)

            # Clean up connector resources
            clean_up_table_resources(connector_table_name, clean_up_connector)

            # Clean up CloudWatch log groups
            delete_cloudwatch_log_groups(LOG_GROUPS_TO_CLEAN)

            logger.info("Cleanup completed successfully")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        else:
            # For Create/Update events, just respond success
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

    except Exception as e:
        logger.error("Error during cleanup: %s", str(e))
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
