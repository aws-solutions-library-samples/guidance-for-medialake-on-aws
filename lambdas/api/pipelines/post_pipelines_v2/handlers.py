import json
from typing import Dict, Any

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

from models import PipelineDefinition
from lambda_operations import create_lambda_function
from step_functions_builder import build_step_function_definition, create_step_function

from eventbridge import create_eventbridge_rule, delete_eventbridge_rule
from dynamodb_operations import (
    get_pipeline_by_name,
    get_pipeline_by_id,
    create_pipeline_record,
    update_pipeline_status,
    store_pipeline_info
)

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipeliNeV2")

def parse_pipeline_definition(event: Dict[str, Any]) -> PipelineDefinition:
    """
    Parse pipeline definition from event input.

    This function handles both direct pipeline definitions and those wrapped in a "body" field
    (like from API Gateway events).
    """
    logger.info("Parsing pipeline definition from event")
    
    # Check if the event has the required pipeline fields at the top level
    if all(key in event for key in ["name", "description", "configuration"]):
        logger.info("Pipeline definition found at top level of event")
        pipeline = PipelineDefinition(**event)
    else:
        # Try to extract from body field (API Gateway style)
        logger.info("Trying to extract pipeline definition from event body")
        body_str = event.get("body", "{}")
        body = body_str if isinstance(body_str, dict) else json.loads(body_str)
        pipeline = PipelineDefinition(**body)
    
    logger.debug(f"Parsed pipeline definition: {pipeline}")
    return pipeline

def create_pipeline(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create or update a pipeline based on the provided configuration.

    Args:
        event: Lambda event containing the pipeline definition

    Returns:
        A response dict with statusCode, headers, and body
    """
    try:
        logger.info("Received request to create/update a pipeline")
        # Use our helper to extract the pipeline configuration.
        pipeline = parse_pipeline_definition(event)
        logger.debug(f"Pipeline configuration: {pipeline}")

        pipeline_name = pipeline.name
        logger.info(f"Processing pipeline: {pipeline_name} - {pipeline.description}")
        
        # Check if pipeline_id is provided in the event
        pipeline_id = event.get("pipeline_id")
        
        # If pipeline_id is not provided, check if a pipeline with this name already exists
        if not pipeline_id:
            existing_pipeline = get_pipeline_by_name(pipeline_name)
            if existing_pipeline:
                # Clean up existing EventBridge rules if updating a pipeline
                for resource_type, resource_arn in existing_pipeline.get("dependentResources", []):
                    if resource_type == "eventbridge_rule":
                        rule_name = resource_arn.split("/")[-1]  # Extract rule name from ARN
                        try:
                            delete_eventbridge_rule(rule_name)
                            logger.info(f"Deleted existing EventBridge rule: {rule_name}")
                        except Exception as e:
                            logger.error(f"Failed to delete EventBridge rule {rule_name}: {e}")

                error_body = {
                    "error": "Pipeline name already exists",
                    "details": f"A pipeline with the name '{pipeline_name}' already exists. Please use a different name.",
                }
                logger.info(f"Rejecting pipeline creation - name already exists: {pipeline_name}")
                return {
                    "statusCode": 400,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps(error_body),
                }
        else:
            logger.info(f"Using provided pipeline_id: {pipeline_id}, skipping name check")
        
        # If pipeline_id is not provided, create a new pipeline record
        if not pipeline_id:
            # Create new pipeline record with initial status
            pipeline_id = create_pipeline_record(pipeline, None, "CREATING")
            logger.info(f"Created new pipeline record with ID: {pipeline_id}")
        
        try:
            # Create/update Lambda functions for each node
            update_pipeline_status(pipeline_id, "CREATING_RESOURCES")
            lambda_arns = {}
            for node in pipeline.configuration.nodes:
                logger.info(f"Processing node with id: {node.id}")
                logger.debug(f"Node details: {node}")
                lambda_arn = create_lambda_function(pipeline_name, node)
                
                # Create a specific key for Lambda ARN mapping that distinguishes methods/operations.
                lambda_key = node.data.id
                if node.data.type.lower() == "integration" and "method" in node.data.configuration:
                    lambda_key = f"{node.data.id}_{node.data.configuration['method']}"
                    if "operationId" in node.data.configuration and node.data.configuration["operationId"]:
                        lambda_key = f"{lambda_key}_{node.data.configuration['operationId']}"
                
                lambda_arns[lambda_key] = lambda_arn

            # Log edge processing (if any)
            for edge in pipeline.configuration.edges:
                logger.info(f"Processing edge: {edge.id} from {edge.source} to {edge.target}")

            settings = pipeline.configuration.settings
            logger.info(
                f"Pipeline settings: AutoStart={settings.autoStart}, RetryAttempts={settings.retryAttempts}, Timeout={settings.timeout}"
            )

            # Build and create/update the state machine
            update_pipeline_status(pipeline_id, "CREATING_STEP_FUNCTION")
            state_machine_definition = build_step_function_definition(pipeline, lambda_arns)
            sfn_response = create_step_function(pipeline_name, state_machine_definition)
            state_machine_arn = sfn_response.get("stateMachineArn")
            logger.info(f"State machine ARN: {state_machine_arn}")

            # Create EventBridge rules for trigger nodes
            update_pipeline_status(pipeline_id, "CREATING_EVENT_RULES")
            eventbridge_rule_arns = {}
            for node in pipeline.configuration.nodes:
                if node.data.type.lower() == "trigger":
                    try:
                        rule_arn = create_eventbridge_rule(pipeline_name, node, state_machine_arn)
                        if rule_arn:
                            eventbridge_rule_arns[node.data.id] = rule_arn
                            logger.info(f"Added EventBridge rule {rule_arn} for node {node.data.id}")
                    except Exception as e:
                        logger.error(f"Failed to create EventBridge rule for node {node.data.id}: {e}")

            # Update pipeline info in DynamoDB with DEPLOYED status
            pipeline_id = store_pipeline_info(pipeline, state_machine_arn, lambda_arns, eventbridge_rule_arns, pipeline_id)

            response_body = {
                "message": "Pipeline created successfully",
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
                "state_machine_arn": state_machine_arn,
                "deployment_status": "DEPLOYED"
            }
        except Exception as e:
            # Update pipeline status to FAILED if any error occurs
            update_pipeline_status(pipeline_id, "FAILED")
            raise e
        logger.info(f"Returning success response: {response_body}")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.exception("Error creating/updating pipeline")
        error_body = {"error": "Failed to create/update pipeline", "details": str(e)}
        logger.error(f"Returning error response: {error_body}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }

@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for processing pipeline creation/updating.

    Now a regular lambda function that directly invokes the create_pipeline route handler.
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = create_pipeline(event)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
