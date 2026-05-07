"""
Integrations API Lambda Handler.

This is the main entry point for the unified Integrations API Lambda function.
It uses AWS Lambda Powertools APIGatewayRestResolver with Pydantic V2 validation
for routing all integrations-related endpoints to their respective handlers.

All handlers are defined in the handlers/ directory with resource-path-based naming:
- integrations_get.py: GET /integrations
- integrations_post.py: POST /integrations
- integrations_ID_put.py: PUT /integrations/<id>
- integrations_ID_delete.py: DELETE /integrations/<id>

All request validation is handled by Pydantic V2 models in the models/ directory.
"""

import json
import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize PowerTools
logger = Logger(service="integrations-api", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="integrations-api")
metrics = Metrics(namespace="medialake", service="integrations-api")

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

# Register all routes - import handlers after PowerTools initialization
import integrations_get  # noqa: E402
import integrations_ID_delete  # noqa: E402
import integrations_ID_put  # noqa: E402
import integrations_post  # noqa: E402

# Register all routes
integrations_get.register_route(app)
integrations_post.register_route(app)
integrations_ID_put.register_route(app)
integrations_ID_delete.register_route(app)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for Integrations API.

    Uses Lambda Powertools to route requests to appropriate handlers
    based on the HTTP method and path.

    Args:
        event: API Gateway Lambda proxy integration event
        context: Lambda context object

    Returns:
        API Gateway Lambda proxy integration response
    """
    logger.info(
        "Integrations API Lambda invoked",
        extra={
            "http_method": event.get("httpMethod"),
            "path": event.get("path"),
            "resource": event.get("resource"),
        },
    )

    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled exception in Integrations API", exc_info=e)
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
