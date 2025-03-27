"""
AWS Lambda function for creating Lambda functions for each node in the pipeline.
This is a key step in the pipeline creation process.
"""

import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the Lambda creation function from the original implementation
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from post_pipelines_v2.lambda_operations import create_lambda_function

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Create Lambda functions for each node in the pipeline.
    
    Args:
        event: Input event containing the pipeline definition
        context: Lambda context
        
    Returns:
        Event with Lambda ARNs
    """
    logger.info("Creating Lambda functions for pipeline nodes")
    
    # Get the pipeline definition from the event
    pipeline_def = event.get("pipeline", {})
    if not pipeline_def:
        logger.error("Pipeline definition not found in event")
        return {
            "error": "Pipeline definition not found in event",
            "lambdaCreationStatus": "FAILED",
            **event
        }
    
    pipeline_name = pipeline_def.get("name")
    logger.info(f"Creating Lambda functions for pipeline: {pipeline_name}")
    
    try:
        # Create Lambda functions for each node
        lambda_arns = {}
        
        # Convert the pipeline definition to a PipelineDefinition object
        # This is a workaround since we're using the original create_lambda_function function
        # which expects a PipelineDefinition object
        from post_pipelines_v2.models import PipelineDefinition
        pipeline = PipelineDefinition(**pipeline_def)
        
        for node in pipeline.configuration.nodes:
            logger.info(f"Processing node with id: {node.id}")
            lambda_arn = create_lambda_function(pipeline_name, node)
            
            # Create a more specific key for Lambda ARN mapping that includes the method
            # This ensures different operations (GET, POST) for the same node type get different Lambda functions
            lambda_key = node.data.id
            if node.data.type.lower() == "integration" and "method" in node.data.configuration:
                lambda_key = f"{node.data.id}_{node.data.configuration['method']}"
                # Add operationId to the key if available
                if "operationId" in node.data.configuration and node.data.configuration["operationId"]:
                    lambda_key = f"{lambda_key}_{node.data.configuration['operationId']}"
            
            lambda_arns[lambda_key] = lambda_arn
        
        # Add Lambda ARNs to the event
        return {
            "lambdaCreationStatus": "SUCCESS",
            "lambdaArns": lambda_arns,
            **event
        }
    except Exception as e:
        logger.exception(f"Error creating Lambda functions for pipeline '{pipeline_name}'")
        return {
            "error": str(e),
            "lambdaCreationStatus": "FAILED",
            **event
        }