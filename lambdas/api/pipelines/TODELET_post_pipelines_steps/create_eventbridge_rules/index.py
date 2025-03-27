"""
AWS Lambda function for creating EventBridge rules for trigger nodes in the pipeline.
This step uses the Step Function ARN created in the previous step.
"""

import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the EventBridge rule creation function from the original implementation
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from post_pipelines_v2.eventbridge import create_eventbridge_rule

# Initialize logger
logger = Logger()

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Create EventBridge rules for trigger nodes in the pipeline.
    
    Args:
        event: Input event containing the pipeline definition and Step Function ARN
        context: Lambda context
        
    Returns:
        Event with EventBridge rule ARNs
    """
    logger.info("Creating EventBridge rules for pipeline trigger nodes")
    
    # Get the pipeline definition and Step Function ARN from the event
    pipeline_def = event.get("pipeline", {})
    state_machine_arn = event.get("stateMachineArn")
    
    if not pipeline_def:
        logger.error("Pipeline definition not found in event")
        return {
            "error": "Pipeline definition not found in event",
            "eventBridgeRulesCreationStatus": "FAILED",
            **event
        }
    
    if not state_machine_arn:
        logger.error("Step Function ARN not found in event")
        return {
            "error": "Step Function ARN not found in event",
            "eventBridgeRulesCreationStatus": "FAILED",
            **event
        }
    
    pipeline_name = pipeline_def.get("name")
    logger.info(f"Creating EventBridge rules for pipeline: {pipeline_name}")
    
    try:
        # Convert the pipeline definition to a PipelineDefinition object
        # This is a workaround since we're using the original create_eventbridge_rule function
        # which expects a PipelineDefinition object
        from post_pipelines_v2.models import PipelineDefinition
        pipeline = PipelineDefinition(**pipeline_def)
        
        # Create EventBridge rules for trigger nodes
        eventbridge_rule_arns = {}
        for node in pipeline.configuration.nodes:
            if node.data.type.lower() == "trigger":
                try:
                    rule_arn = create_eventbridge_rule(
                        pipeline_name, node, state_machine_arn
                    )
                    if rule_arn:
                        eventbridge_rule_arns[node.data.id] = rule_arn
                        logger.info(
                            f"Added EventBridge rule {rule_arn} for node {node.data.id}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to create EventBridge rule for node {node.data.id}: {e}"
                    )
        
        # Add the EventBridge rule ARNs to the event
        return {
            "eventBridgeRulesCreationStatus": "SUCCESS",
            "eventBridgeRuleArns": eventbridge_rule_arns,
            **event
        }
    except Exception as e:
        logger.exception(f"Error creating EventBridge rules for pipeline '{pipeline_name}'")
        return {
            "error": str(e),
            "eventBridgeRulesCreationStatus": "FAILED",
            **event
        }