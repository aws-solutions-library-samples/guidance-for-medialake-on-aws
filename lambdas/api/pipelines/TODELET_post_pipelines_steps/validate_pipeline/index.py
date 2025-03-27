"""
AWS Lambda function for validating pipeline definitions.
This is the first step in the pipeline creation process.
"""

import json
from typing import Dict, Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the PipelineDefinition model
import sys
import os

# Add the parent directory to the path so we can import the models
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from post_pipelines_async.models import PipelineDefinition

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Validate the pipeline definition.
    
    Args:
        event: Input event containing the pipeline definition
        context: Lambda context
        
    Returns:
        Validated pipeline definition
    """
    logger.info("Validating pipeline definition")
    
    try:
        # Parse and validate the pipeline definition
        pipeline = PipelineDefinition(**event)
        logger.info(f"Pipeline definition validated: {pipeline.name}")
        
        # Return the validated pipeline definition and a flag indicating it's valid
        return {
            "pipeline": pipeline.dict(),
            "isValid": True,
            "pipelineName": pipeline.name
        }
    except Exception as e:
        logger.exception("Error validating pipeline definition")
        # Return an error response
        return {
            "isValid": False,
            "error": str(e)
        }