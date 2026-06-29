"""
Portals API Lambda Handler.

Main entry point for the Upload Portals management API.
Routes all /settings/portals/* endpoints to their respective handlers.
"""

import json
import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from custom_exceptions import ForbiddenError

logger = Logger(service="portals-api", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-api")
metrics = Metrics(namespace="medialake", service="portals-api")

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

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

import portal_templates_get  # noqa: E402
import portal_templates_ID_delete  # noqa: E402
import portal_templates_ID_get  # noqa: E402
import portal_templates_ID_put  # noqa: E402
import portal_templates_post  # noqa: E402
import portal_themes_get  # noqa: E402
import portal_themes_ID_delete  # noqa: E402
import portal_themes_ID_get  # noqa: E402
import portal_themes_ID_put  # noqa: E402
import portal_themes_post  # noqa: E402
import portals_get  # noqa: E402
import portals_ID_banner_post  # noqa: E402
import portals_ID_delete  # noqa: E402
import portals_ID_favicon_post  # noqa: E402
import portals_ID_get  # noqa: E402
import portals_ID_logo_post  # noqa: E402
import portals_ID_put  # noqa: E402
import portals_ID_tokens_get  # noqa: E402
import portals_ID_tokens_ID_delete  # noqa: E402
import portals_ID_tokens_post  # noqa: E402
import portals_post  # noqa: E402
import portals_validate_post  # noqa: E402

portals_get.register_route(app)
portals_post.register_route(app)
portals_validate_post.register_route(app)
portals_ID_get.register_route(app)
portals_ID_put.register_route(app)
portals_ID_delete.register_route(app)
portals_ID_tokens_get.register_route(app)
portals_ID_tokens_post.register_route(app)
portals_ID_tokens_ID_delete.register_route(app)
portals_ID_logo_post.register_route(app)
portals_ID_banner_post.register_route(app)
portals_ID_favicon_post.register_route(app)

# Portal themes (reusable appearance) routes — task 16.2.
portal_themes_get.register_route(app)
portal_themes_post.register_route(app)
portal_themes_ID_get.register_route(app)
portal_themes_ID_put.register_route(app)
portal_themes_ID_delete.register_route(app)

# Portal templates (reusable full-structure snapshots) routes — task 16.3.
portal_templates_get.register_route(app)
portal_templates_post.register_route(app)
portal_templates_ID_get.register_route(app)
portal_templates_ID_put.register_route(app)
portal_templates_ID_delete.register_route(app)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Main Lambda handler for Portals API."""
    logger.info(
        "Portals API Lambda invoked",
        extra={
            "http_method": event.get("httpMethod"),
            "path": event.get("path"),
            "resource": event.get("resource"),
        },
    )

    try:
        return app.resolve(event, context)
    except ForbiddenError as e:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": e.message,
                    },
                    "meta": {
                        "request_id": event.get("requestContext", {}).get("requestId")
                    },
                }
            ),
        }
    except Exception as e:
        logger.exception("Unhandled exception in Portals API", exc_info=e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
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
