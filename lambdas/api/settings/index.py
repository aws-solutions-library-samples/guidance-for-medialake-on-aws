"""
Settings API Lambda Handler.

This is the main entry point for the unified Settings API Lambda function.
It uses AWS Lambda Powertools APIGatewayRestResolver for routing all
settings-related endpoints to their respective handlers.

Handles:
- Collection types: GET/POST/PUT/DELETE /settings/collection-types
- System settings: GET/POST/PUT/DELETE /settings/system
- API keys: GET/POST/PUT/DELETE /settings/api-keys
- Search providers: GET/POST/PUT/DELETE /settings/system/search
- Users: GET /settings/users

All handlers are defined in the handlers/ directory following resource-path naming.
"""

import json
import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize PowerTools
logger = Logger(service="settings-api", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="settings-api")
metrics = Metrics(namespace="medialake", service="settings-api")

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

# Register all routes from handlers
from handlers import register_all_routes  # noqa: E402

register_all_routes(app)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for Settings API.

    Uses Lambda Powertools to route requests to appropriate handlers
    based on the HTTP method and path.

    Args:
        event: API Gateway Lambda proxy integration event
        context: Lambda context object

    Returns:
        API Gateway Lambda proxy integration response
    """
    logger.info(
        "Settings API Lambda invoked",
        extra={
            "http_method": event.get("httpMethod"),
            "path": event.get("path"),
            "resource": event.get("resource"),
        },
    )

    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled exception in Settings API", exc_info=e)
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
