import json
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from dynamodb_operations import (
    delete_pipeline_from_dynamodb,
    get_pipeline_by_id,
    get_pipeline_by_name,
)
from models import DeletePipelineRequest
from resource_cleanup import cleanup_pipeline_resources

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="DeletePipeline")

# Configure CORS and API Gateway resolver
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])
app = APIGatewayRestResolver(cors=cors_config)


# --------
# Route Handler
# --------
@app.delete("/pipelines/<pipeline_id>")
@tracer.capture_method
def delete_pipeline_by_id(pipeline_id: str) -> Dict[str, Any]:
    """
    Delete a pipeline by ID.

    Args:
        pipeline_id: ID of the pipeline to delete

    Returns:
        API Gateway response
    """
    try:
        logger.info(f"Received request to delete pipeline with ID: {pipeline_id}")

        # Get pipeline details
        pipeline = get_pipeline_by_id(pipeline_id)
        if not pipeline:
            error_body = {
                "error": "Pipeline not found",
                "details": f"No pipeline found with ID: {pipeline_id}",
            }
            logger.info(f"Pipeline not found with ID: {pipeline_id}")
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        # Get dependent resources
        dependent_resources = pipeline.get("dependentResources", [])
        logger.info(f"Found {len(dependent_resources)} dependent resources to clean up")
        logger.info(f"Dependent resources details: {dependent_resources}")

        # Clean up resources
        cleanup_results = cleanup_pipeline_resources(dependent_resources)
        logger.info(f"Cleanup results: {cleanup_results}")

        # Delete pipeline from DynamoDB
        delete_success = delete_pipeline_from_dynamodb(pipeline_id)

        # Prepare response
        response_body = {
            "message": (
                "Pipeline deleted successfully"
                if delete_success
                else "Pipeline deletion partially successful"
            ),
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline.get("name"),
            "cleanup_results": cleanup_results,
            "database_deletion": "success" if delete_success else "failed",
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
        logger.exception("Error deleting pipeline")
        error_body = {"error": "Failed to delete pipeline", "details": str(e)}
        logger.error(f"Returning error response: {error_body}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


@app.delete("/pipelines")
@tracer.capture_method
def delete_pipeline() -> Dict[str, Any]:
    """
    Delete a pipeline by name or ID from request body.

    Returns:
        API Gateway response
    """
    try:
        logger.info("Received request to delete a pipeline")
        request_data = app.current_event.json_body
        delete_request = DeletePipelineRequest(**request_data)

        if not delete_request.validate_request():
            error_body = {
                "error": "Invalid request",
                "details": "Either pipeline_id or pipeline_name must be provided",
            }
            logger.info("Invalid delete request - missing identifiers")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        # Get pipeline by ID or name
        pipeline = None
        if delete_request.pipeline_id:
            pipeline = get_pipeline_by_id(delete_request.pipeline_id)
            if not pipeline:
                logger.info(f"Pipeline not found with ID: {delete_request.pipeline_id}")

        if not pipeline and delete_request.pipeline_name:
            pipeline = get_pipeline_by_name(delete_request.pipeline_name)
            if not pipeline:
                logger.info(
                    f"Pipeline not found with name: {delete_request.pipeline_name}"
                )

        if not pipeline:
            error_body = {
                "error": "Pipeline not found",
                "details": "No pipeline found with the provided ID or name",
            }
            logger.info("Pipeline not found with provided identifiers")
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        # Get pipeline ID and dependent resources
        pipeline_id = pipeline["id"]
        dependent_resources = pipeline.get("dependentResources", [])
        logger.info(
            f"Found pipeline with ID {pipeline_id} and {len(dependent_resources)} dependent resources"
        )
        logger.info(f"Dependent resources details: {dependent_resources}")

        # Clean up resources
        cleanup_results = cleanup_pipeline_resources(dependent_resources)
        logger.info(f"Cleanup results: {cleanup_results}")

        # Delete pipeline from DynamoDB
        delete_success = delete_pipeline_from_dynamodb(pipeline_id)

        # Prepare response
        response_body = {
            "message": (
                "Pipeline deleted successfully"
                if delete_success
                else "Pipeline deletion partially successful"
            ),
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline.get("name"),
            "cleanup_results": cleanup_results,
            "database_deletion": "success" if delete_success else "failed",
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
        logger.exception("Error deleting pipeline")
        error_body = {"error": "Failed to delete pipeline", "details": str(e)}
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
