"""GET /collections/<collection_id>/items - List collection items."""

import os
import sys

from aws_lambda_powertools import Logger, Metrics, Tracer

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
)
from utils.formatting_utils import format_collection_item
from utils.item_utils import ASSET_SK_PREFIX, ITEM_SK_PREFIX

logger = Logger(
    service="collections-ID-items-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-get")
metrics = Metrics(namespace="medialake", service="collection-items")


def register_route(app, dynamodb, table_name):
    """Register GET /collections/<collection_id>/items route"""

    @app.get("/collections/<collection_id>/items")
    @tracer.capture_method
    def collections_ID_items_get(collection_id: str):
        """Get collection items"""
        try:
            table = dynamodb.Table(table_name)

            # Query for both old ITEM# and new ASSET# formats
            all_items = []

            # Query old format
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ITEM_SK_PREFIX,
                },
            )
            all_items.extend(response.get("Items", []))

            # Query new format
            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ASSET_SK_PREFIX,
                },
            )
            all_items.extend(response.get("Items", []))

            formatted_items = [format_collection_item(item) for item in all_items]

            return create_success_response(
                data=formatted_items,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error listing collection items", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
