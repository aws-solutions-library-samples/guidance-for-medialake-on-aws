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
from db_models import CollectionItemModel, CollectionModel
from pynamodb.exceptions import DeleteError, DoesNotExist
from utils.item_utils import ASSET_SK_PREFIX, ITEM_SK_PREFIX

logger = Logger(
    service="collections-ID-items-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-items")


def register_route(app):
    """Register DELETE /collections/<collection_id>/items/<item_id> route"""

    @app.delete("/collections/<collection_id>/items/<item_id>")
    @tracer.capture_method
    def collections_ID_items_ID_delete(collection_id: str, item_id: str):
        """Remove item from collection"""
        try:
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Support both old ITEM# and new ASSET# formats
            sk = (
                item_id
                if item_id.startswith(ASSET_SK_PREFIX)
                else f"{ITEM_SK_PREFIX}{item_id}"
            )

            # Delete the item using PynamoDB
            try:
                item = CollectionItemModel(f"{COLLECTION_PK_PREFIX}{collection_id}", sk)
                item.delete()
            except DoesNotExist:
                logger.warning(
                    f"Item not found: {item_id} in collection {collection_id}"
                )
            except DeleteError as e:
                logger.error(f"Error deleting item: {e}")
                raise

            # Update collection item count
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
                collection.update(
                    actions=[
                        CollectionModel.itemCount.add(-1),
                        CollectionModel.updatedAt.set(current_timestamp),
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to update item count: {e}")

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
