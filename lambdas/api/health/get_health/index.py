"""
Health check Lambda function for MediaLake API.

This function provides a simple health check endpoint that returns the service status
and basic system information. It follows AWS Power Tools best practices for monitoring,
security, and logging.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import Metrics
from aws_lambda_powertools.utilities.validation import validate

# Initialize AWS Power Tools
logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()


# Request schema for validation
health_request_schema = {
    "type": "object",
    "properties": {
        "include_details": {
            "type": "boolean",
            "description": "Whether to include detailed system information",
        }
    },
    "additionalProperties": False,
}


@app.get("/health")
@tracer.capture_method
def get_health():
    """
    Health check endpoint that returns service status.

    Returns:
        dict: Health status response with service information
    """
    logger.info("Health check endpoint called")

    # Add custom metrics
    metrics.add_metric(name="HealthCheckRequested", unit="Count", value=1)

    try:
        # Basic health response
        health_response = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "MediaLake API",
            "version": "1.0.0",
        }

        # Check for query parameters
        query_params = app.current_event.query_string_parameters or {}
        include_details = query_params.get("include_details", "false").lower() == "true"

        if include_details:
            health_response["details"] = {
                "lambda_function": {
                    "memory_limit": app.lambda_context.memory_limit_in_mb,
                    "time_remaining": app.lambda_context.get_remaining_time_in_millis(),
                    "request_id": app.lambda_context.aws_request_id,
                },
                "environment": {
                    "aws_region": app.lambda_context.invoked_function_arn.split(":")[3],
                    "function_name": app.lambda_context.function_name,
                    "function_version": app.lambda_context.function_version,
                },
            }

        logger.info("Health check completed successfully", extra={"status": "healthy"})
        metrics.add_metric(name="HealthCheckSuccess", unit="Count", value=1)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
            "body": json.dumps(health_response),
        }

    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        metrics.add_metric(name="HealthCheckError", unit="Count", value=1)

        error_response = {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "MediaLake API",
            "error": "Internal service error",
        }

        return {
            "statusCode": 503,
            "headers": {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
            "body": json.dumps(error_response),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        dict: HTTP response
    """
    logger.info("Processing health check request", extra={"event": event})

    try:
        # Validate the request if it has a body
        if event.get("body"):
            validate(event=json.loads(event["body"]), schema=health_request_schema)

        return app.resolve(event, context)

    except Exception as e:
        logger.error("Unhandled error in health check handler", extra={"error": str(e)})

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
            "body": json.dumps(
                {
                    "status": "error",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Internal server error",
                }
            ),
        }
