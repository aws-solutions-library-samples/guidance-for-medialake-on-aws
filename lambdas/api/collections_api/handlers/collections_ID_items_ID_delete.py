"""DELETE /collections/<collection_id>/items/<item_id> - Remove item from collection."""

import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    create_success_response,
)
from utils.item_utils import ASSET_SK_PREFIX, ITEM_SK_PREFIX

logger = Logger(
    service="collections-ID-items-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-items")


def register_route(app, dynamodb, table_name):
    """Register DELETE /collections/<collection_id>/items/<item_id> route"""

    @app.delete("/collections/<collection_id>/items/<item_id>")
    @tracer.capture_method
    def collections_ID_items_ID_delete(collection_id: str, item_id: str):
        """Remove item from collection"""
        try:
            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Support both old ITEM# and new ASSET# formats
            sk = (
                item_id
                if item_id.startswith(ASSET_SK_PREFIX)
                else f"{ITEM_SK_PREFIX}{item_id}"
            )

            table.delete_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": sk,
                }
            )

            # Update collection item count
            table.update_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
                UpdateExpression="ADD itemCount :dec SET updatedAt = :timestamp",
                ExpressionAttributeValues={":dec": -1, ":timestamp": current_timestamp},
            )

            logger.info(f"Item removed from collection {collection_id}")

            return create_success_response(
                data={"id": item_id, "removed": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error removing collection item", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
