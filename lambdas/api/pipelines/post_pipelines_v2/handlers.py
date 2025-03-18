import json
from typing import Dict, Any

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)

from models import PipelineDefinition
from lambda_operations import create_lambda_function
from step_functions_builder import build_step_function_definition, create_step_function

from eventbridge import create_eventbridge_rule, delete_eventbridge_rule
from dynamodb_operations import get_pipeline_by_name, store_pipeline_info

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipeliNeV2")

# Configure CORS and API Gateway resolver
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])
app = APIGatewayRestResolver(cors=cors_config)


def parse_pipeline_definition(event: Dict[str, Any]) -> PipelineDefinition:
    """
    Parse pipeline definition from API Gateway event body.

    Args:
        event: API Gateway event

    Returns:
        Parsed PipelineDefinition object
    """
    logger.info("Parsing pipeline definition from event body")
    body = json.loads(event.get("body", "{}"))
    pipeline = PipelineDefinition(**body)
    logger.debug(f"Parsed pipeline definition: {pipeline}")
    return pipeline


# --------
# Route Handler
# --------
@app.post("/pipelinesv2")
@tracer.capture_method
def create_pipeline() -> Dict[str, Any]:
    """
    Create or update a pipeline based on the provided configuration.

    Returns:
        API Gateway response
    """
    try:
        logger.info("Received request to create/update a pipeline")
        request_data = app.current_event.json_body
        pipeline = PipelineDefinition(**request_data)
        logger.debug(f"Pipeline configuration: {pipeline}")

        pipeline_name = pipeline.name
        logger.info(f"Processing pipeline: {pipeline_name} - {pipeline.description}")

        # Check if a pipeline with this name already exists
        existing_pipeline = get_pipeline_by_name(pipeline_name)
        if existing_pipeline:
            # Clean up existing EventBridge rules if updating a pipeline
            for resource_type, resource_arn in existing_pipeline.get(
                "dependentResources", []
            ):
                if resource_type == "eventbridge_rule":
                    rule_name = resource_arn.split("/")[
                        -1
                    ]  # Extract rule name from ARN
                    try:
                        delete_eventbridge_rule(rule_name)
                        logger.info(f"Deleted existing EventBridge rule: {rule_name}")
                    except Exception as e:
                        logger.error(
                            f"Failed to delete EventBridge rule {rule_name}: {e}"
                        )

            error_body = {
                "error": "Pipeline name already exists",
                "details": f"A pipeline with the name '{pipeline_name}' already exists. Please use a different name.",
            }
            logger.info(
                f"Rejecting pipeline creation - name already exists: {pipeline_name}"
            )
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        # Create/update Lambda functions for each node
        lambda_arns = {}
        for node in pipeline.configuration.nodes:
            logger.info(f"Processing node with id: {node.id}")
            logger.info(node)
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

        # Log edge processing (if any)
        for edge in pipeline.configuration.edges:
            logger.info(
                f"Processing edge: {edge.id} from {edge.source} to {edge.target}"
            )

        settings = pipeline.configuration.settings
        logger.info(
            f"Pipeline settings: AutoStart={settings.autoStart}, RetryAttempts={settings.retryAttempts}, Timeout={settings.timeout}"
        )

        # Build and create/update the state machine
        state_machine_definition = build_step_function_definition(pipeline, lambda_arns)
        sfn_response = create_step_function(pipeline_name, state_machine_definition)
        state_machine_arn = sfn_response.get("stateMachineArn")
        logger.info(f"State machine ARN: {state_machine_arn}")

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

        # Store/update pipeline info in DynamoDB
        store_pipeline_info(
            pipeline, state_machine_arn, lambda_arns, eventbridge_rule_arns
        )

        # If we found an existing pipeline with identical name and definition,
        # we still recreated all resources but didn't create a new DB record
        action = "recreated" if existing_pipeline else "created"
        response_body = {
            "message": f"Pipeline {action} successfully",
            "pipeline_name": pipeline_name,
            "state_machine_arn": state_machine_arn,
        }
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


# --------
# Lambda Handler
# --------
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    AWS Lambda handler entry point.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
