"""
AWS-specific operations for Step Functions state machines.
"""

import json
import time
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger
from iam_operations import create_sfn_role
from sanitizers import sanitize_role_name, sanitize_state_machine_name

logger = Logger()


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


def create_step_function(
    pipeline_name: str, definition: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a Step Functions state machine.

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

        # Create new state machine
        logger.info(f"Creating new Step Function: {sanitized_state_machine_name}")
        response = sfn_client.create_state_machine(
            name=sanitized_state_machine_name,
            definition=json.dumps(definition),
            roleArn=role_arn,
        )
        logger.info(
            f"Created state machine for pipeline '{pipeline_name}' with name '{sanitized_state_machine_name}': {response}"
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
