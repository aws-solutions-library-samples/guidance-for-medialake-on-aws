"""
Collections API Lambda Handler.

This is the main entry point for the unified Collections API Lambda function.
It uses AWS Lambda Powertools APIGatewayRestResolver with Pydantic V2 validation
for routing all collections-related endpoints to their respective handlers.

All handlers are defined in the handlers/ directory with resource-path-based naming:
- collections.py: GET/POST /collections
- collections_ID.py: GET/PATCH/DELETE /collections/<id>
- collections_ID_items.py: GET/POST/DELETE /collections/<id>/items
- collections_ID_assets.py: GET /collections/<id>/assets
- collections_ID_share.py: GET/POST/DELETE /collections/<id>/share
- collections_ID_rules.py: GET/POST/PUT/DELETE /collections/<id>/rules
- collection_types.py: GET/POST /collection-types

All request validation is handled by Pydantic V2 models in the models/ directory.
"""

import json
import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import PynamoDB models
from db_models import (
    ChildReferenceModel,
    CollectionItemModel,
    CollectionModel,
    CollectionTypeModel,
    RuleModel,
    ShareModel,
    UserRelationshipModel,
)

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

# Initialize PynamoDB models with environment configuration
table_name = os.environ.get("COLLECTIONS_TABLE_NAME")
region = os.environ.get("AWS_REGION", "us-east-1")

# Set table name and region for all models
for model in [
    CollectionModel,
    ChildReferenceModel,
    UserRelationshipModel,
    CollectionItemModel,
    ShareModel,
    RuleModel,
    CollectionTypeModel,
]:
    model.Meta.table_name = table_name
    model.Meta.region = region

logger.info(f"PynamoDB models initialized for table: {table_name} in region: {region}")

# Register all routes - import is done after model initialization
from handlers import register_all_routes  # noqa: E402

register_all_routes(app)


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
