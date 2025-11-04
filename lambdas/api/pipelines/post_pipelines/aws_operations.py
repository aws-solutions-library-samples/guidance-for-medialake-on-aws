"""
AWS-specific operations for Step Functions state machines.
"""

import json
import os
import time
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger
from iam_operations import create_sfn_role
from sanitizers import sanitize_role_name, sanitize_state_machine_name

logger = Logger()

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")


def check_step_function_exists(state_machine_name: str) -> bool:
    """
    Check if a Step Function state machine exists.

    Args:
        state_machine_name: Name of the state machine

    Returns:
        True if the state machine exists, False otherwise
    """
    sfn_client = boto3.client("stepfunctions")
    try:
        paginator = sfn_client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for state_machine in page["stateMachines"]:
                if state_machine["name"] == state_machine_name:
                    return True
        return False
    except Exception as e:
        logger.error(f"Error checking Step Function existence: {e}")
        return False


def delete_step_function(state_machine_name: str) -> None:
    """
    Delete a Step Function state machine if it exists.

    Args:
        state_machine_name: Name of the state machine
    """
    sfn_client = boto3.client("stepfunctions")
    try:
        # First get the ARN
        paginator = sfn_client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for state_machine in page["stateMachines"]:
                if state_machine["name"] == state_machine_name:
                    sfn_client.delete_state_machine(
                        stateMachineArn=state_machine["stateMachineArn"]
                    )
                    logger.info(f"Deleted existing Step Function: {state_machine_name}")
                    return
    except Exception as e:
        logger.error(f"Error deleting Step Function: {e}")


def wait_for_state_machine_deletion(
    state_machine_name: str, max_attempts: int = 40
) -> None:
    """
    Wait for a state machine to be fully deleted.

    Args:
        state_machine_name: Name of the state machine
        max_attempts: Maximum number of attempts to check
    """
    sfn_client = boto3.client("stepfunctions")
    attempt = 0

    while attempt < max_attempts:
        try:
            paginator = sfn_client.get_paginator("list_state_machines")
            exists = False
            for page in paginator.paginate():
                for state_machine in page["stateMachines"]:
                    if state_machine["name"] == state_machine_name:
                        exists = True
                        break
                if exists:
                    break

            if not exists:
                logger.info(f"State machine {state_machine_name} has been deleted")
                return

            attempt += 1
            logger.info(
                f"State machine {state_machine_name} is still being deleted, waiting... (attempt {attempt}/{max_attempts})"
            )
            time.sleep(5)  # Wait 5 seconds between checks

        except Exception as e:
            logger.error(f"Error checking state machine status: {e}")
            attempt += 1
            time.sleep(5)

    raise TimeoutError(
        f"State machine {state_machine_name} deletion timed out after {max_attempts} attempts"
    )


def create_or_get_log_group(log_group_name: str) -> str:
    """
    Create a CloudWatch Log Group for Step Functions logging if it doesn't exist.

    Args:
        log_group_name: Name of the log group

    Returns:
        ARN of the log group
    """
    logs_client = boto3.client("logs")

    try:
        # Check if log group exists
        response = logs_client.describe_log_groups(
            logGroupNamePrefix=log_group_name, limit=1
        )

        if response.get("logGroups"):
            for log_group in response["logGroups"]:
                if log_group["logGroupName"] == log_group_name:
                    logger.info(f"Log group {log_group_name} already exists")
                    return log_group["arn"]

        # Create log group if it doesn't exist
        logs_client.create_log_group(logGroupName=log_group_name)
        logger.info(f"Created log group: {log_group_name}")

        # Set retention policy to 30 days
        logs_client.put_retention_policy(
            logGroupName=log_group_name, retentionInDays=30
        )
        logger.info(f"Set retention policy for log group {log_group_name} to 30 days")

        # Get the ARN of the newly created log group
        response = logs_client.describe_log_groups(
            logGroupNamePrefix=log_group_name, limit=1
        )

        if response.get("logGroups"):
            return response["logGroups"][0]["arn"]

        # Construct ARN if describe fails
        log_group_arn = (
            f"arn:aws:logs:{AWS_REGION}:{ACCOUNT_ID}:log-group:{log_group_name}:*"
        )
        return log_group_arn

    except Exception as e:
        logger.error(f"Error creating/getting log group {log_group_name}: {e}")
        # Return constructed ARN as fallback
        return f"arn:aws:logs:{AWS_REGION}:{ACCOUNT_ID}:log-group:{log_group_name}:*"


def create_step_function(
    pipeline_name: str, definition: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a Step Functions state machine with logging enabled.

    Args:
        pipeline_name: Name of the pipeline
        definition: State machine definition

    Returns:
        Dictionary containing:
        - response: Response from the create_state_machine API call
        - role_arn: ARN of the IAM role created for the state machine
    """
    logger.info(f"Creating Step Functions state machine for pipeline: {pipeline_name}")
    sfn_client = boto3.client("stepfunctions")

    # Sanitize the pipeline name for use in the IAM role name and state machine name
    sanitized_role_name_str = sanitize_role_name(pipeline_name)
    sanitized_state_machine_name = sanitize_state_machine_name(pipeline_name)

    role_name = f"{sanitized_role_name_str}_sfn_role"
    logger.info(f"Using sanitized role name: {role_name}")
    logger.info(f"Using sanitized state machine name: {sanitized_state_machine_name}")
    role_arn = create_sfn_role(role_name)

    # Create CloudWatch Log Group for Step Functions logging
    log_group_name = f"/aws/vendedlogs/states/{sanitized_state_machine_name}"
    log_group_arn = create_or_get_log_group(log_group_name)
    logger.info(f"Using log group: {log_group_name} with ARN: {log_group_arn}")

    try:
        # Check if state machine exists
        if check_step_function_exists(sanitized_state_machine_name):
            logger.info(
                f"Found existing Step Function {sanitized_state_machine_name}, deleting it"
            )
            delete_step_function(sanitized_state_machine_name)
            wait_for_state_machine_deletion(sanitized_state_machine_name)

        # Print the definition for debugging
        definition_json = json.dumps(definition, indent=2)
        logger.info(f"Step Function Definition for {pipeline_name}:\n{definition_json}")

        # Create new state machine with logging enabled
        logger.info(f"Creating new Step Function: {sanitized_state_machine_name}")
        response = sfn_client.create_state_machine(
            name=sanitized_state_machine_name,
            definition=json.dumps(definition),
            roleArn=role_arn,
            loggingConfiguration={
                "level": "ALL",
                "includeExecutionData": True,
                "destinations": [
                    {"cloudWatchLogsLogGroup": {"logGroupArn": log_group_arn}}
                ],
            },
        )
        logger.info(
            f"Created state machine for pipeline '{pipeline_name}' with name '{sanitized_state_machine_name}' and logging enabled: {response}"
        )
        return {"response": response, "role_arn": role_arn}
    except Exception as e:
        logger.exception(
            f"Failed to create/update state machine for pipeline '{pipeline_name}': {e}"
        )
        raise


def get_state_machine_execution_history(
    state_machine_arn: str, execution_arn: str
) -> Dict[str, Any]:
    """
    Get the execution history of a state machine execution.

    Args:
        state_machine_arn: ARN of the state machine
        execution_arn: ARN of the execution

    Returns:
        Execution history
    """
    sfn_client = boto3.client("stepfunctions")
    try:
        paginator = sfn_client.get_paginator("get_execution_history")
        events = []
        for page in paginator.paginate(executionArn=execution_arn):
            events.extend(page["events"])
        return {"events": events}
    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        raise


def start_state_machine_execution(
    state_machine_arn: str, input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Start a state machine execution.

    Args:
        state_machine_arn: ARN of the state machine
        input_data: Input data for the execution

    Returns:
        Response from the start_execution API call
    """
    sfn_client = boto3.client("stepfunctions")
    try:
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(input_data),
        )
        logger.info(
            f"Started execution of state machine {state_machine_arn}: {response}"
        )
        return response
    except Exception as e:
        logger.error(f"Error starting state machine execution: {e}")
        raise
