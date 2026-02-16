"""DELETE /collections/<collection_id>/items/<item_id> - Remove item from collection."""

import os
from datetime import datetime
from urllib.parse import unquote

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    COLLECTIONS_GSI5_PK,
    METADATA_SK,
    create_error_response,
    create_success_response,
)
from db_models import CollectionItemModel, CollectionModel
from pynamodb.exceptions import DeleteError, DoesNotExist, UpdateError
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

            # URL decode the item_id (API Gateway doesn't auto-decode path parameters)
            decoded_item_id = unquote(item_id)

            logger.info(f"[DELETE] Received item_id (raw): {item_id}")
            logger.info(f"[DELETE] Decoded item_id: {decoded_item_id}")
            logger.info(f"[DELETE] Collection: {collection_id}")

            # Support both old ITEM# and new ASSET# formats
            sk = (
                decoded_item_id
                if decoded_item_id.startswith(ASSET_SK_PREFIX)
                or decoded_item_id.startswith(ITEM_SK_PREFIX)
                else f"{ITEM_SK_PREFIX}{decoded_item_id}"
            )

            logger.info(f"[DELETE] Final SK to delete: {sk}")
            logger.info(f"[DELETE] PK: {COLLECTION_PK_PREFIX}{collection_id}")

            # Delete the item using PynamoDB
            try:
                item = CollectionItemModel(f"{COLLECTION_PK_PREFIX}{collection_id}", sk)
                logger.info(
                    f"[DELETE] Attempting to delete item with PK={item.PK}, SK={item.SK}"
                )
                item.delete()
                logger.info(f"[DELETE] Successfully deleted item")
            except DoesNotExist:
                logger.warning(
                    f"[DELETE] Item not found: {decoded_item_id} (SK: {sk}) in collection {collection_id}"
                )
            except DeleteError as e:
                logger.error(f"[DELETE] Error deleting item: {e}")
                raise

            # Update collection: decrement itemCount atomically and refresh timestamps
            # Note: itemCount is maintained as a stored counter for efficient listing.
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
                # Decrement itemCount only when it's > 0 to prevent negatives.
                try:
                    collection.update(
                        actions=[
                            CollectionModel.updatedAt.set(current_timestamp),
                            CollectionModel.itemCount.set(
                                (CollectionModel.itemCount - 1)
                            ),
                            CollectionModel.GSI5_PK.set(COLLECTIONS_GSI5_PK),
                            CollectionModel.GSI5_SK.set(current_timestamp),
                        ],
                        condition=(CollectionModel.itemCount > 0),
                    )
                except UpdateError:
                    # itemCount is already 0 — still update timestamps.
                    logger.warning(
                        f"[DELETE] itemCount already 0 for collection {collection_id}, "
                        "skipping decrement"
                    )
                    collection.update(
                        actions=[
                            CollectionModel.updatedAt.set(current_timestamp),
                            CollectionModel.GSI5_PK.set(COLLECTIONS_GSI5_PK),
                            CollectionModel.GSI5_SK.set(current_timestamp),
                        ]
                    )
                logger.info(f"[DELETE] Updated collection updatedAt timestamp")
            except Exception as e:
                logger.warning(f"[DELETE] Failed to update collection timestamp: {e}")

            logger.info(f"[DELETE] Item removed from collection {collection_id}")

            return create_success_response(
                data={"id": decoded_item_id, "removed": True},
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
