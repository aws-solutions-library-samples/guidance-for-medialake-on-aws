"""
AWS Step Functions state machine builder for pipelines.

This module has been refactored into a more modular structure.
The implementation is now in the step_functions/ directory.
"""

from typing import Any, Dict


def build_step_function_definition(
    pipeline: Any, lambda_arns: Dict[str, str]
) -> Dict[str, Any]:
    """
    Build a Step Functions state machine definition from pipeline configuration.

    This is a wrapper around the implementation in step_functions/builders.py.

    Args:
        pipeline: Pipeline definition object
        lambda_arns: Dictionary mapping node IDs to Lambda ARNs

    Returns:
        Complete state machine definition
    """
    # Import here to avoid circular imports
    import os

    from builders import StateMachineBuilder

    resource_prefix = os.environ.get("RESOURCE_PREFIX", "")
    builder = StateMachineBuilder(pipeline, lambda_arns, resource_prefix)
    return builder.build()


def create_step_function(
    pipeline_name: str, definition: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a Step Functions state machine.

    This is a wrapper around the implementation in step_functions/aws_operations.py.

    Args:
        pipeline_name: Name of the pipeline
        definition: State machine definition

    Returns:
        Response from the create_state_machine API call
    """
    # Import here to avoid circular imports
    from aws_operations import create_step_function as create_sfn

    return create_sfn(pipeline_name, definition)
