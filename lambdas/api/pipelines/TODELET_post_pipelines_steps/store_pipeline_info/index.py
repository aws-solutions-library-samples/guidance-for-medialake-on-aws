"""
AWS Lambda function for storing pipeline information in DynamoDB.
This is the final step in the pipeline creation process.
"""

import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the pipeline info storage function from the original implementation
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from post_pipelines_v2.dynamodb_operations import store_pipeline_info

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Store pipeline information in DynamoDB.
    
    Args:
        event: Input event containing the pipeline definition, Step Function ARN, Lambda ARNs, and EventBridge rule ARNs
        context: Lambda context
        
    Returns:
        Event with storage status
    """
    logger.info("Storing pipeline information in DynamoDB")
    
    # Get the pipeline definition, Step Function ARN, Lambda ARNs, and EventBridge rule ARNs from the event
    pipeline_def = event.get("pipeline", {})
    state_machine_arn = event.get("stateMachineArn")
    lambda_arns = event.get("lambdaArns", {})
    eventbridge_rule_arns = event.get("eventBridgeRuleArns", {})
    
    if not pipeline_def:
        logger.error("Pipeline definition not found in event")
        return {
            "error": "Pipeline definition not found in event",
            "storageStatus": "FAILED",
            **event
        }
    
    if not state_machine_arn:
        logger.error("Step Function ARN not found in event")
        return {
            "error": "Step Function ARN not found in event",
            "storageStatus": "FAILED",
            **event
        }
    
    if not lambda_arns:
        logger.error("Lambda ARNs not found in event")
        return {
            "error": "Lambda ARNs not found in event",
            "storageStatus": "FAILED",
            **event
        }
    
    pipeline_name = pipeline_def.get("name")
    logger.info(f"Storing information for pipeline: {pipeline_name}")
    
    try:
        # Convert the pipeline definition to a PipelineDefinition object
        # This is a workaround since we're using the original store_pipeline_info function
        # which expects a PipelineDefinition object
        from post_pipelines_v2.models import PipelineDefinition
        pipeline = PipelineDefinition(**pipeline_def)
        
        # Store the pipeline information in DynamoDB
        store_pipeline_info(
            pipeline, state_machine_arn, lambda_arns, eventbridge_rule_arns
        )
        
        # Add the storage status to the event
        return {
            "storageStatus": "SUCCESS",
            "message": f"Pipeline '{pipeline_name}' created successfully",
            **event
        }
    except Exception as e:
        logger.exception(f"Error storing information for pipeline '{pipeline_name}'")
        return {
            "error": str(e),
            "storageStatus": "FAILED",
            **event
        }