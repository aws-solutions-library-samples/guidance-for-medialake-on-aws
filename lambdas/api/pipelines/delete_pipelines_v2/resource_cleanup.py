import boto3
from typing import Dict, Any, List, Tuple
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
        region = parts[3]
        account_id = parts[4]
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


def cleanup_pipeline_resources(
    dependent_resources: List[Tuple[str, str]]
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
        "other_resources": {"success": [], "failed": []},
    }

    for resource_type, resource_arn in dependent_resources:
        try:
            if resource_type == "lambda":
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

            else:
                logger.warning(
                    f"Unknown resource type: {resource_type} with ARN: {resource_arn}"
                )
                results["other_resources"]["failed"].append(resource_arn)

        except Exception as e:
            logger.error(
                f"Error cleaning up resource {resource_type} - {resource_arn}: {e}"
            )
            results[f"{resource_type}s"]["failed"].append(resource_arn)

    return results
