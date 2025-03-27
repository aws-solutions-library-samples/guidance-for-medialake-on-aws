"""
AWS Lambda function for building the Step Function definition for the pipeline.
This step uses the Lambda ARNs created in the previous step.
"""

import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the Step Function builder from the original implementation
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from post_pipelines_v2.step_functions_builder import build_step_function_definition

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Build the Step Function definition for the pipeline.
    
    Args:
        event: Input event containing the pipeline definition and Lambda ARNs
        context: Lambda context
        
    Returns:
        Event with Step Function definition
    """
    logger.info("Building Step Function definition for pipeline")
    
    # Get the pipeline definition and Lambda ARNs from the event
    pipeline_def = event.get("pipeline", {})
    lambda_arns = event.get("lambdaArns", {})
    
    if not pipeline_def:
        logger.error("Pipeline definition not found in event")
        return {
            "error": "Pipeline definition not found in event",
            "stepFunctionDefinitionStatus": "FAILED",
            **event
        }
    
    if not lambda_arns:
        logger.error("Lambda ARNs not found in event")
        return {
            "error": "Lambda ARNs not found in event",
            "stepFunctionDefinitionStatus": "FAILED",
            **event
        }
    
    pipeline_name = pipeline_def.get("name")
    logger.info(f"Building Step Function definition for pipeline: {pipeline_name}")
    
    try:
        # Convert the pipeline definition to a PipelineDefinition object
        # This is a workaround since we're using the original build_step_function_definition function
        # which expects a PipelineDefinition object
        from post_pipelines_v2.models import PipelineDefinition
        pipeline = PipelineDefinition(**pipeline_def)
        
        # Build the Step Function definition
        state_machine_definition = build_step_function_definition(pipeline, lambda_arns)
        
        # Add the Step Function definition to the event
        return {
            "stepFunctionDefinitionStatus": "SUCCESS",
            "stateMachineDefinition": state_machine_definition,
            **event
        }
    except Exception as e:
        logger.exception(f"Error building Step Function definition for pipeline '{pipeline_name}'")
        return {
            "error": str(e),
            "stepFunctionDefinitionStatus": "FAILED",
            **event
        }