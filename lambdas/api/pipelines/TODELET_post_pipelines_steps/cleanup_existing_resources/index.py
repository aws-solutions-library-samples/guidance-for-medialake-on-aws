"""
AWS Lambda function for cleaning up existing resources if a pipeline with the same name exists.
This step is executed only if the pipeline already exists.
"""

import os
from typing import Dict, Any, List, Tuple

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from eventbridge import delete_eventbridge_rule

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Clean up existing resources if a pipeline with the same name exists.
    
    Args:
        event: Input event containing the existing pipeline information
        context: Lambda context
        
    Returns:
        Event with cleanup status
    """
    logger.info("Cleaning up existing resources")
    
    # Check if the pipeline exists
    pipeline_exists = event.get("pipelineExists", False)
    if not pipeline_exists:
        logger.info("No existing pipeline to clean up")
        return event
    
    # Get the existing pipeline information
    existing_pipeline = event.get("existingPipeline", {})
    if not existing_pipeline:
        logger.error("Existing pipeline information not found in event")
        return {
            "error": "Existing pipeline information not found in event",
            "cleanupStatus": "FAILED",
            **event
        }
    
    pipeline_name = existing_pipeline.get("name")
    logger.info(f"Cleaning up resources for existing pipeline: {pipeline_name}")
    
    try:
        # Clean up existing EventBridge rules
        eventbridge_rules_cleaned = cleanup_eventbridge_rules(existing_pipeline)
        
        # Add cleanup status to the event
        return {
            "cleanupStatus": "SUCCESS",
            "cleanupDetails": {
                "eventbridgeRulesCleaned": eventbridge_rules_cleaned
            },
            **event
        }
    except Exception as e:
        logger.exception(f"Error cleaning up resources for pipeline '{pipeline_name}'")
        return {
            "error": str(e),
            "cleanupStatus": "FAILED",
            **event
        }

def cleanup_eventbridge_rules(existing_pipeline: Dict[str, Any]) -> List[str]:
    """
    Clean up existing EventBridge rules for a pipeline.
    
    Args:
        existing_pipeline: Existing pipeline information
        
    Returns:
        List of cleaned up EventBridge rule names
    """
    cleaned_rules = []
    
    # Get the dependent resources from the existing pipeline
    dependent_resources = existing_pipeline.get("dependentResources", [])
    
    # Clean up EventBridge rules
    for resource_type, resource_arn in dependent_resources:
        if resource_type == "eventbridge_rule":
            # Extract rule name from ARN
            rule_name = resource_arn.split("/")[-1]
            try:
                delete_eventbridge_rule(rule_name)
                logger.info(f"Deleted existing EventBridge rule: {rule_name}")
                cleaned_rules.append(rule_name)
            except Exception as e:
                logger.error(f"Failed to delete EventBridge rule {rule_name}: {e}")
    
    return cleaned_rules