import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from dynamodb_operations import (
    conditionally_set_deleting_status,
    get_pipeline_by_id,
    get_pipeline_by_name,
    update_pipeline_deployment_status,
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
# Async worker — invoked by the API handler via Lambda async invoke
# --------
def _execute_async_delete(pipeline_id: str) -> None:
    """
    Perform the actual resource cleanup and mark the pipeline as DELETED.

    This runs inside an async Lambda invocation so there is no API Gateway
    timeout to worry about.
    """
    logger.info(f"Async delete worker started for pipeline {pipeline_id}")

    pipeline = get_pipeline_by_id(pipeline_id)
    if not pipeline:
        logger.error(f"Pipeline {pipeline_id} not found during async delete")
        return

    dependent_resources = pipeline.get("dependentResources", [])
    logger.info(f"Cleaning up {len(dependent_resources)} dependent resources")

    try:
        cleanup_results = cleanup_pipeline_resources(dependent_resources)
        logger.info(f"Cleanup results: {cleanup_results}")

        # Check if any resources failed to delete
        all_failed = []
        for category, results in cleanup_results.items():
            if isinstance(results, dict) and results.get("failed"):
                all_failed.extend(results["failed"])

        if all_failed:
            logger.warning(f"Some resources failed to delete: {all_failed}")
            update_pipeline_deployment_status(
                pipeline_id,
                "DELETE_FAILED",
                cleanup_results=cleanup_results,
            )
        else:
            update_pipeline_deployment_status(
                pipeline_id,
                "DELETED",
                cleanup_results=cleanup_results,
            )
            logger.info(f"Pipeline {pipeline_id} marked as DELETED")

    except Exception as e:
        logger.exception(f"Async delete failed for pipeline {pipeline_id}: {e}")
        try:
            update_pipeline_deployment_status(
                pipeline_id,
                "DELETE_FAILED",
                error_details=str(e),
            )
        except Exception:
            logger.exception("Failed to update pipeline status to DELETE_FAILED")


# --------
# Helper — kick off the async worker
# --------
def _invoke_async_delete(pipeline_id: str) -> None:
    """Invoke this same Lambda asynchronously to perform the heavy cleanup.

    If the invocation fails, rolls the pipeline status back to DELETE_FAILED
    so it doesn't stay stuck in DELETING permanently.
    """
    lambda_client = boto3.client("lambda")
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")

    payload = json.dumps(
        {
            "async_delete": True,
            "pipeline_id": pipeline_id,
        }
    )

    try:
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",  # async — returns immediately
            Payload=payload,
        )
        logger.info(
            f"Invoked async delete for pipeline {pipeline_id} on {function_name}"
        )
    except Exception as e:
        logger.exception(
            f"Failed to invoke async delete for pipeline {pipeline_id}: {e}"
        )
        try:
            update_pipeline_deployment_status(
                pipeline_id,
                "DELETE_FAILED",
                error_details=f"Failed to start async cleanup: {e}",
            )
        except Exception:
            logger.exception(
                f"Failed to rollback pipeline {pipeline_id} status from DELETING"
            )
        raise


# --------
# Route Handlers
# --------
@app.delete("/pipelines/<pipeline_id>")
@tracer.capture_method
def delete_pipeline_by_id(pipeline_id: str) -> Dict[str, Any]:
    """
    Validate and accept a pipeline deletion request, then hand off to an
    async worker.  Returns 202 Accepted immediately.
    """
    try:
        logger.info(f"Received request to delete pipeline with ID: {pipeline_id}")

        # Validate pipeline exists
        pipeline = get_pipeline_by_id(pipeline_id)
        if not pipeline:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "error": "Pipeline not found",
                        "details": f"No pipeline found with ID: {pipeline_id}",
                    }
                ),
            }

        # Atomically mark as DELETING — the ConditionExpression ensures
        # only one request wins when concurrent deletes arrive.
        try:
            conditionally_set_deleting_status(pipeline_id)
            logger.info(f"Pipeline {pipeline_id} marked as DELETING")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                current_status = pipeline.get("deploymentStatus", "DELETING")
                return {
                    "statusCode": 409,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps(
                        {
                            "error": "Pipeline is already being deleted",
                            "details": f"Current status: {current_status}",
                            "pipeline_id": pipeline_id,
                        }
                    ),
                }
            raise

        # Fire-and-forget the heavy cleanup
        _invoke_async_delete(pipeline_id)

        return {
            "statusCode": 202,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "message": "Pipeline deletion started",
                    "pipeline_id": pipeline_id,
                    "pipeline_name": pipeline.get("name"),
                    "deployment_status": "DELETING",
                }
            ),
        }

    except Exception as e:
        logger.exception("Error initiating pipeline deletion")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "error": "Failed to initiate pipeline deletion",
                    "details": str(e),
                }
            ),
        }


@app.delete("/pipelines")
@tracer.capture_method
def delete_pipeline() -> Dict[str, Any]:
    """
    Delete a pipeline by name or ID from request body.
    Validates and returns 202 Accepted, then cleans up asynchronously.
    """
    try:
        logger.info("Received request to delete a pipeline")
        request_data = app.current_event.json_body
        delete_request = DeletePipelineRequest(**request_data)

        if not delete_request.validate_request():
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "error": "Invalid request",
                        "details": "Either pipeline_id or pipeline_name must be provided",
                    }
                ),
            }

        # Resolve pipeline
        pipeline = None
        if delete_request.pipeline_id:
            pipeline = get_pipeline_by_id(delete_request.pipeline_id)
        if not pipeline and delete_request.pipeline_name:
            pipeline = get_pipeline_by_name(delete_request.pipeline_name)

        if not pipeline:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "error": "Pipeline not found",
                        "details": "No pipeline found with the provided ID or name",
                    }
                ),
            }

        pipeline_id = pipeline["id"]

        # Reject if already being deleted
        current_status = pipeline.get("deploymentStatus", "")
        if current_status in ("DELETING", "DELETED"):
            return {
                "statusCode": 409,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "error": "Pipeline is already being deleted",
                        "details": f"Current status: {current_status}",
                        "pipeline_id": pipeline_id,
                    }
                ),
            }

        # Mark as DELETING
        update_pipeline_deployment_status(pipeline_id, "DELETING")
        logger.info(f"Pipeline {pipeline_id} marked as DELETING")

        # Fire-and-forget
        _invoke_async_delete(pipeline_id)

        return {
            "statusCode": 202,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "message": "Pipeline deletion started",
                    "pipeline_id": pipeline_id,
                    "pipeline_name": pipeline.get("name"),
                    "deployment_status": "DELETING",
                }
            ),
        }

    except Exception as e:
        logger.exception("Error initiating pipeline deletion")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "error": "Failed to initiate pipeline deletion",
                    "details": str(e),
                }
            ),
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

    Routes between:
    - API Gateway requests (normal DELETE endpoint)
    - Async delete worker (self-invoked with async_delete=True)
    """
    # Check if this is an async delete invocation
    if isinstance(event, dict) and event.get("async_delete"):
        pipeline_id = event.get("pipeline_id")
        if not pipeline_id or not isinstance(pipeline_id, str):
            logger.error(
                f"Missing or invalid pipeline_id in async delete event: {pipeline_id}"
            )
            return {"statusCode": 400, "body": "Missing or invalid pipeline_id"}
        logger.info(f"Handling async delete for pipeline {pipeline_id}")
        _execute_async_delete(pipeline_id)
        return {"statusCode": 200, "body": "Async delete completed"}

    # Otherwise, handle as API Gateway request
    logger.info("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
