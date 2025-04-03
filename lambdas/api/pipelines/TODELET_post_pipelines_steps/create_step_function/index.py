"""
AWS Lambda function for creating the Step Function state machine for the pipeline.
This step uses the Step Function definition created in the previous step.
"""

import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the Step Function creation function from the original implementation
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from post_pipelines_v2.step_functions.aws_operations import create_step_function

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Create the Step Function state machine for the pipeline.
    
    Args:
        event: Input event containing the pipeline definition and Step Function definition
        context: Lambda context
        
    Returns:
        Event with Step Function ARN
    """
    logger.info("Creating Step Function state machine for pipeline")
    
    # Get the pipeline definition and Step Function definition from the event
    pipeline_def = event.get("pipeline", {})
    state_machine_definition = event.get("stateMachineDefinition", {})
    
    if not pipeline_def:
        logger.error("Pipeline definition not found in event")
        return {
            "error": "Pipeline definition not found in event",
            "stepFunctionCreationStatus": "FAILED",
            **event
        }
    
    if not state_machine_definition:
        logger.error("Step Function definition not found in event")
        return {
            "error": "Step Function definition not found in event",
            "stepFunctionCreationStatus": "FAILED",
            **event
        }
    
    pipeline_name = pipeline_def.get("name")
    logger.info(f"Creating Step Function state machine for pipeline: {pipeline_name}")
    
    try:
        # Create the Step Function state machine
        sfn_response = create_step_function(pipeline_name, state_machine_definition)
        state_machine_arn = sfn_response.get("stateMachineArn")
        
        logger.info(f"Created Step Function state machine with ARN: {state_machine_arn}")
        
        # Add the Step Function ARN to the event
        return {
            "stepFunctionCreationStatus": "SUCCESS",
            "stateMachineArn": state_machine_arn,
            **event
        }
    except Exception as e:
        logger.exception(f"Error creating Step Function state machine for pipeline '{pipeline_name}'")
        return {
            "error": str(e),
            "stepFunctionCreationStatus": "FAILED",
            **event
        }