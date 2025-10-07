"""
Collections API Lambda Handler.

This is the main entry point for the unified Collections API Lambda function.
It uses AWS Lambda Powertools APIGatewayRestResolver for routing all
collections-related endpoints to their respective handlers.

All routes are defined in the routes/ directory and imported here.
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize PowerTools
logger = Logger(service="collections-api", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-api")
metrics = Metrics(namespace="medialake", service="collections-api")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
    expose_headers=["X-Request-Id"],
    max_age=300,
)

# Initialize API Gateway resolver with CORS
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize DynamoDB client (shared across routes)
dynamodb = boto3.resource("dynamodb")

# Get environment variables
TABLE_NAME = os.environ.get("COLLECTIONS_TABLE_NAME")

# Import all route handlers
# These imports will register their routes with the app resolver
from routes import (
    assets_routes,
    collection_detail_routes,
    collection_types_routes,
    collections_routes,
    items_routes,
    rules_routes,
    shares_routes,
)

# Register route modules with the app
collection_types_routes.register_routes(app, dynamodb, TABLE_NAME)
collections_routes.register_routes(app, dynamodb, TABLE_NAME)
collection_detail_routes.register_routes(app, dynamodb, TABLE_NAME)
items_routes.register_routes(app, dynamodb, TABLE_NAME)
rules_routes.register_routes(app, dynamodb, TABLE_NAME)
shares_routes.register_routes(app, dynamodb, TABLE_NAME)
assets_routes.register_routes(app, dynamodb, TABLE_NAME)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for Collections API.

    Uses Lambda Powertools to route requests to appropriate handlers
    based on the HTTP method and path.

    Args:
        event: API Gateway Lambda proxy integration event
        context: Lambda context object

    Returns:
        API Gateway Lambda proxy integration response
    """
    logger.info(
        "Collections API Lambda invoked",
        extra={
            "http_method": event.get("httpMethod"),
            "path": event.get("path"),
            "resource": event.get("resource"),
        },
    )

    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled exception in Collections API", exc_info=e)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "success": False,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred",
                    },
                    "meta": {
                        "request_id": event.get("requestContext", {}).get("requestId")
                    },
                }
            ),
        }
