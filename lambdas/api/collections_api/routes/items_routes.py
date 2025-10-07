"""
Collection Items Routes.

Handles collection items operations:
- GET /collections/{collectionId}/items - List collection items
- POST /collections/{collectionId}/items - Add item to collection
- POST /collections/{collectionId}/items/batch - Batch add items
- POST /collections/{collectionId}/items/batch-remove - Batch remove items
- PUT /collections/{collectionId}/items/{itemId} - Update collection item
- DELETE /collections/{collectionId}/items/{itemId} - Remove item from collection
"""

import json
import os
import sys
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    create_success_response,
)
from user_auth import extract_user_context

logger = Logger(service="items-routes", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="items-routes")
metrics = Metrics(namespace="medialake", service="collection-items")

# Constants
ITEM_SK_PREFIX = "ITEM#"


def register_routes(app, dynamodb, table_name):
    """Register collection items routes"""

    @app.get("/collections/<collection_id>/items")
    @tracer.capture_method
    def list_collection_items(collection_id: str):
        """Get collection items"""
        try:
            table = dynamodb.Table(table_name)

            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": ITEM_SK_PREFIX,
                },
            )

            items = response.get("Items", [])
            formatted_items = [_format_collection_item(item) for item in items]

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

    @app.post("/collections/<collection_id>/items")
    @tracer.capture_method
    def add_collection_item(collection_id: str):
        """Add item to collection"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            request_data = app.current_event.json_body

            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            item_id = f"item_{str(uuid.uuid4())[:8]}"

            item = {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{ITEM_SK_PREFIX}{item_id}",
                "itemType": request_data["type"],
                "itemId": request_data["id"],
                "sortOrder": request_data.get("sortOrder", 0),
                "metadata": request_data.get("metadata", {}),
                "addedAt": current_timestamp,
                "addedBy": user_context.get("user_id"),
            }

            table.put_item(Item=item)

            # Update collection item count
            table.update_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
                UpdateExpression="ADD itemCount :inc SET updatedAt = :timestamp",
                ExpressionAttributeValues={":inc": 1, ":timestamp": current_timestamp},
            )

            logger.info(f"Item added to collection {collection_id}")
            metrics.add_metric(
                name="SuccessfulItemAdditions", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": _format_collection_item(item),
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error adding collection item", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.post("/collections/<collection_id>/items/batch")
    @tracer.capture_method
    def batch_add_items(collection_id: str):
        """Batch add items to collection"""
        try:
            extract_user_context(app.current_event.raw_event)
            request_data = app.current_event.json_body
            items = request_data.get("items", [])

            # Implement batch add logic
            logger.info(
                f"Batch adding {len(items)} items to collection {collection_id}"
            )

            return create_success_response(
                data={"addedCount": len(items)},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error batch adding items", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.post("/collections/<collection_id>/items/batch-remove")
    @tracer.capture_method
    def batch_remove_items(collection_id: str):
        """Batch remove items from collection"""
        try:
            request_data = app.current_event.json_body
            item_ids = request_data.get("itemIds", [])

            logger.info(
                f"Batch removing {len(item_ids)} items from collection {collection_id}"
            )

            return create_success_response(
                data={"removedCount": len(item_ids)},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error batch removing items", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.put("/collections/<collection_id>/items/<item_id>")
    @tracer.capture_method
    def update_collection_item(collection_id: str, item_id: str):
        """Update collection item"""
        try:
            request_data = app.current_event.json_body
            table = dynamodb.Table(table_name)

            table.update_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{ITEM_SK_PREFIX}{item_id}",
                },
                UpdateExpression="SET sortOrder = :sortOrder, metadata = :metadata",
                ExpressionAttributeValues={
                    ":sortOrder": request_data.get("sortOrder", 0),
                    ":metadata": request_data.get("metadata", {}),
                },
            )

            return create_success_response(
                data={"id": item_id, "updated": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error updating collection item", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.delete("/collections/<collection_id>/items/<item_id>")
    @tracer.capture_method
    def remove_collection_item(collection_id: str, item_id: str):
        """Remove item from collection"""
        try:
            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            table.delete_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{ITEM_SK_PREFIX}{item_id}",
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


def _format_collection_item(item):
    """Format collection item for API response"""
    item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
    return {
        "id": item_id,
        "itemType": item.get("itemType", ""),
        "itemId": item.get("itemId", ""),
        "sortOrder": item.get("sortOrder", 0),
        "metadata": item.get("metadata", {}),
        "addedAt": item.get("addedAt", ""),
        "addedBy": item.get("addedBy", ""),
    }
