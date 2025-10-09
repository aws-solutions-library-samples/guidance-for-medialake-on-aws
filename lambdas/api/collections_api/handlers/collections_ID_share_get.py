"""GET /collections/<collection_id>/share - List collection shares."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
)
from utils.formatting_utils import format_share

logger = Logger(
    service="collections-ID-share-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-share-get")
metrics = Metrics(namespace="medialake", service="collection-shares")

PERM_SK_PREFIX = "PERM#"


def register_route(app, dynamodb, table_name):
    """Register GET /collections/<collection_id>/share route"""

    @app.get("/collections/<collection_id>/share")
    @tracer.capture_method
    def collections_ID_share_get(collection_id: str):
        """Get collection shares"""
        try:
            table = dynamodb.Table(table_name)

            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": PERM_SK_PREFIX,
                },
            )

            items = response.get("Items", [])
            formatted_shares = [format_share(item) for item in items]

            return create_success_response(
                data=formatted_shares,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error listing collection shares", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
