import time
from typing import Any, Dict, List, Tuple

import boto3
from aws_lambda_powertools import Logger

# Initialize logger
logger = Logger()


def delete_lambda_function(function_arn: str) -> bool:
    """
    Delete a Lambda function.

    Args:
        function_arn: ARN of the Lambda function to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Extract function name from ARN
        function_name = function_arn.split(":")[-1]
        logger.info(f"Deleting Lambda function: {function_name}")

        lambda_client = boto3.client("lambda")
        lambda_client.delete_function(FunctionName=function_name)
        logger.info(f"Successfully deleted Lambda function: {function_name}")
        return True
    except Exception as e:
        logger.error(f"Error deleting Lambda function {function_arn}: {e}")
        return False


def delete_step_function(state_machine_arn: str) -> bool:
    """
    Delete a Step Functions state machine.

    Args:
        state_machine_arn: ARN of the state machine to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        logger.info(f"Deleting Step Functions state machine: {state_machine_arn}")
        sfn_client = boto3.client("stepfunctions")
        sfn_client.delete_state_machine(stateMachineArn=state_machine_arn)
        logger.info(f"Successfully deleted state machine: {state_machine_arn}")
        return True
    except Exception as e:
        logger.error(f"Error deleting state machine {state_machine_arn}: {e}")
        return False


def delete_eventbridge_rule(rule_arn: str) -> bool:
    """
    Delete an EventBridge rule.

    Args:
        rule_arn: ARN of the EventBridge rule to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Extract rule name and event bus name from ARN
        # ARN format: arn:aws:events:region:account-id:rule/event-bus-name/rule-name
        parts = rule_arn.split(":")
        parts[3]
        parts[4]
        rule_path = parts[5].split("/")

        if len(rule_path) > 2:
            # Format with event bus: rule/event-bus-name/rule-name
            event_bus_name = rule_path[1]
            rule_name = rule_path[2]
        else:
            # Format without event bus: rule/rule-name (default event bus)
            event_bus_name = "default"
            rule_name = rule_path[1]

        logger.info(
            f"Deleting EventBridge rule: {rule_name} from bus: {event_bus_name}"
        )

        events_client = boto3.client("events")

        # List all targets for the rule
        targets_response = events_client.list_targets_by_rule(
            Rule=rule_name, EventBusName=event_bus_name
        )

        # Remove all targets from the rule
        if targets_response.get("Targets"):
            target_ids = [target["Id"] for target in targets_response["Targets"]]
            events_client.remove_targets(
                Rule=rule_name, EventBusName=event_bus_name, Ids=target_ids
            )
            logger.info(f"Removed {len(target_ids)} targets from rule {rule_name}")

        # Delete the rule
        events_client.delete_rule(Name=rule_name, EventBusName=event_bus_name)

        logger.info(f"Successfully deleted EventBridge rule: {rule_name}")
        return True
    except Exception as e:
        logger.error(f"Error deleting EventBridge rule {rule_arn}: {e}")
        return False


def delete_iam_role(role_arn: str) -> bool:
    """
    Delete an IAM role.

    Args:
        role_arn: ARN of the IAM role to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Extract role name from ARN
        role_name = role_arn.split("/")[-1]
        logger.info(f"Deleting IAM role: {role_name}")

        iam_client = boto3.client("iam")

        # First detach all managed policies
        paginator = iam_client.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy in page["AttachedPolicies"]:
                logger.info(
                    f"Detaching policy {policy['PolicyArn']} from role {role_name}"
                )
                iam_client.detach_role_policy(
                    RoleName=role_name, PolicyArn=policy["PolicyArn"]
                )

        # Delete all inline policies
        paginator = iam_client.get_paginator("list_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy_name in page["PolicyNames"]:
                logger.info(
                    f"Deleting inline policy {policy_name} from role {role_name}"
                )
                iam_client.delete_role_policy(
                    RoleName=role_name, PolicyName=policy_name
                )

        # Delete the role
        iam_client.delete_role(RoleName=role_name)
        logger.info(f"Successfully deleted IAM role: {role_name}")
        return True
    except Exception as e:
        logger.error(f"Error deleting IAM role {role_arn}: {e}")
        return False


def delete_sqs_queue(queue_arn: str) -> bool:
    """
    Delete an SQS queue.

    Args:
        queue_arn: ARN of the SQS queue to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Extract queue URL from ARN
        # ARN format: arn:aws:sqs:region:account-id:queue-name
        parts = queue_arn.split(":")
        region = parts[3]
        account_id = parts[4]
        queue_name = parts[5]

        logger.info(f"Deleting SQS queue: {queue_name}")

        sqs_client = boto3.client("sqs")

        # Get the queue URL
        queue_url = f"https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}"

        # Delete the queue
        sqs_client.delete_queue(QueueUrl=queue_url)
        logger.info(f"Successfully deleted SQS queue: {queue_name}")
        return True
    except Exception as e:
        logger.error(f"Error deleting SQS queue {queue_arn}: {e}")
        return False


def delete_event_source_mapping(mapping_uuid: str) -> bool:
    """
    Delete a Lambda event source mapping.

    Args:
        mapping_uuid: UUID of the event source mapping to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        logger.info(f"Deleting event source mapping: {mapping_uuid}")

        lambda_client = boto3.client("lambda")
        lambda_client.delete_event_source_mapping(UUID=mapping_uuid)

        # Wait for the event source mapping to be deleted
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                lambda_client.get_event_source_mapping(UUID=mapping_uuid)
                logger.info(
                    f"Event source mapping {mapping_uuid} is still being deleted, waiting... (attempt {attempt+1}/{max_attempts})"
                )
                time.sleep(2)
            except lambda_client.exceptions.ResourceNotFoundException:
                logger.info(
                    f"Successfully deleted event source mapping: {mapping_uuid}"
                )
                return True

        logger.warning(
            f"Event source mapping {mapping_uuid} deletion timed out after {max_attempts} attempts"
        )
        return False
    except Exception as e:
        logger.error(f"Error deleting event source mapping {mapping_uuid}: {e}")
        return False


def cleanup_pipeline_resources(
    dependent_resources: List[Tuple[str, str]],
) -> Dict[str, Any]:
    """
    Clean up all AWS resources associated with a pipeline.

    Args:
        dependent_resources: List of tuples containing resource type and ARN

    Returns:
        Dictionary with cleanup results
    """
    logger.info(f"Cleaning up pipeline resources: {dependent_resources}")
    results = {
        "lambda_functions": {"success": [], "failed": []},
        "step_functions": {"success": [], "failed": []},
        "eventbridge_rules": {"success": [], "failed": []},
        "iam_roles": {"success": [], "failed": []},
        "sqs_queues": {"success": [], "failed": []},
        "event_source_mappings": {"success": [], "failed": []},
        "other_resources": {"success": [], "failed": []},
    }

    for resource_type, resource_arn in dependent_resources:
        try:
            if resource_type == "lambda" or resource_type == "trigger_lambda":
                success = delete_lambda_function(resource_arn)
                if success:
                    results["lambda_functions"]["success"].append(resource_arn)
                else:
                    results["lambda_functions"]["failed"].append(resource_arn)

            elif resource_type == "step_function":
                success = delete_step_function(resource_arn)
                if success:
                    results["step_functions"]["success"].append(resource_arn)
                else:
                    results["step_functions"]["failed"].append(resource_arn)

            elif resource_type == "eventbridge_rule":
                success = delete_eventbridge_rule(resource_arn)
                if success:
                    results["eventbridge_rules"]["success"].append(resource_arn)
                else:
                    results["eventbridge_rules"]["failed"].append(resource_arn)

            elif (
                resource_type == "iam_role"
                or resource_type == "lambda_role"
                or resource_type == "sfn_role"
                or resource_type == "events_role"
                or resource_type == "service_role"
            ):
                success = delete_iam_role(resource_arn)
                if success:
                    results["iam_roles"]["success"].append(resource_arn)
                else:
                    results["iam_roles"]["failed"].append(resource_arn)

            elif resource_type == "sqs_queue":
                success = delete_sqs_queue(resource_arn)
                if success:
                    results["sqs_queues"]["success"].append(resource_arn)
                else:
                    results["sqs_queues"]["failed"].append(resource_arn)

            elif resource_type == "event_source_mapping":
                success = delete_event_source_mapping(resource_arn)
                if success:
                    results["event_source_mappings"]["success"].append(resource_arn)
                else:
                    results["event_source_mappings"]["failed"].append(resource_arn)

            else:
                logger.warning(
                    f"Unknown resource type: {resource_type} with ARN: {resource_arn}"
                )
                results["other_resources"]["failed"].append(resource_arn)

        except Exception as e:
            logger.error(
                f"Error cleaning up resource {resource_type} - {resource_arn}: {e}"
            )
            # Use a default category if the resource type doesn't match any known category
            category = (
                f"{resource_type}s"
                if resource_type in ["lambda", "step_function", "eventbridge_rule"]
                else "other_resources"
            )
            results[category]["failed"].append(resource_arn)

    return results
