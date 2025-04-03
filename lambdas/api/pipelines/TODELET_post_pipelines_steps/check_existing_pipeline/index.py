"""
AWS Lambda function for checking if a pipeline with the same name already exists.
This is the second step in the pipeline creation process.
"""

import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize logger
logger = Logger()

# Get the DynamoDB table name from environment variables
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Check if a pipeline with the same name already exists.
    
    Args:
        event: Input event containing the validated pipeline definition
        context: Lambda context
        
    Returns:
        Event with a flag indicating if the pipeline exists
    """
    logger.info("Checking if pipeline already exists")
    
    # Extract the pipeline name from the event
    pipeline_name = event.get("pipelineName")
    if not pipeline_name:
        pipeline_name = event.get("pipeline", {}).get("name")
    
    if not pipeline_name:
        logger.error("Pipeline name not found in event")
        return {
            "error": "Pipeline name not found in event",
            "pipelineExists": False
        }
    
    logger.info(f"Checking if pipeline '{pipeline_name}' already exists")
    
    try:
        # Check if a pipeline with the same name already exists
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(PIPELINES_TABLE)
        
        # Scan for items with matching name
        response = table.scan(
            FilterExpression="#n = :name",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": pipeline_name},
        )
        
        items = response.get("Items", [])
        pipeline_exists = len(items) > 0
        
        if pipeline_exists:
            logger.info(f"Pipeline '{pipeline_name}' already exists")
            # Include the existing pipeline data in the response
            existing_pipeline = items[0]
            return {
                "pipelineExists": True,
                "existingPipeline": existing_pipeline,
                "pipeline": event.get("pipeline", {}),
                "pipelineName": pipeline_name
            }
        else:
            logger.info(f"Pipeline '{pipeline_name}' does not exist")
            return {
                "pipelineExists": False,
                "pipeline": event.get("pipeline", {}),
                "pipelineName": pipeline_name
            }
    except Exception as e:
        logger.exception(f"Error checking if pipeline '{pipeline_name}' exists")
        return {
            "error": str(e),
            "pipelineExists": False,
            "pipeline": event.get("pipeline", {}),
            "pipelineName": pipeline_name
        }