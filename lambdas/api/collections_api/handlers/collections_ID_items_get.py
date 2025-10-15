"""GET /collections/<collection_id>/items - List collection items."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
)
from db_models import CollectionItemModel
from utils.formatting_utils import format_collection_item
from utils.item_utils import ASSET_SK_PREFIX, ITEM_SK_PREFIX

logger = Logger(
    service="collections-ID-items-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-get")
metrics = Metrics(namespace="medialake", service="collection-items")


def register_route(app):
    """Register GET /collections/<collection_id>/items route"""

    @app.get("/collections/<collection_id>/items")
    @tracer.capture_method
    def collections_ID_items_get(collection_id: str):
        """Get collection items"""
        try:
            # Query for both old ITEM# and new ASSET# formats
            all_items = []

            # Query old format (ITEM#)
            try:
                for item in CollectionItemModel.query(
                    f"{COLLECTION_PK_PREFIX}{collection_id}",
                    CollectionItemModel.SK.startswith(ITEM_SK_PREFIX),
                ):
                    item_dict = {
                        "PK": item.PK,
                        "SK": item.SK,
                        "itemType": item.itemType,
                        "addedAt": item.addedAt,
                        "addedBy": item.addedBy,
                        "sortOrder": item.sortOrder if item.sortOrder else 0,
                    }
                    if item.assetId:
                        item_dict["assetId"] = item.assetId
                    if item.itemId:
                        item_dict["itemId"] = item.itemId
                    if item.clipBoundary:
                        item_dict["clipBoundary"] = dict(item.clipBoundary)
                    if item.metadata:
                        item_dict["metadata"] = dict(item.metadata)

                    all_items.append(item_dict)
            except Exception as e:
                logger.warning(f"Error querying ITEM# prefix: {e}")

            # Query new format (ASSET#)
            try:
                for item in CollectionItemModel.query(
                    f"{COLLECTION_PK_PREFIX}{collection_id}",
                    CollectionItemModel.SK.startswith(ASSET_SK_PREFIX),
                ):
                    item_dict = {
                        "PK": item.PK,
                        "SK": item.SK,
                        "itemType": item.itemType,
                        "addedAt": item.addedAt,
                        "addedBy": item.addedBy,
                        "sortOrder": item.sortOrder if item.sortOrder else 0,
                    }
                    if item.assetId:
                        item_dict["assetId"] = item.assetId
                    if item.itemId:
                        item_dict["itemId"] = item.itemId
                    if item.clipBoundary:
                        item_dict["clipBoundary"] = dict(item.clipBoundary)
                    if item.metadata:
                        item_dict["metadata"] = dict(item.metadata)

                    all_items.append(item_dict)
            except Exception as e:
                logger.warning(f"Error querying ASSET# prefix: {e}")

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
