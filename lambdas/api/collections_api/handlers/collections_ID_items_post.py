"""POST /collections/<collection_id>/items - Add item to collection."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from db_models import CollectionItemModel, CollectionModel
from models import AddItemToCollectionRequest
from pynamodb.exceptions import PutError
from user_auth import extract_user_context
from utils.formatting_utils import format_collection_item
from utils.item_utils import generate_asset_sk
from utils.opensearch_utils import get_all_clips_for_asset

logger = Logger(
    service="collections-ID-items-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-items-post")
metrics = Metrics(namespace="medialake", service="collection-items")


def register_route(app):
    """Register POST /collections/<collection_id>/items route"""

    @app.post("/collections/<collection_id>/items")
    @tracer.capture_method
    def collections_ID_items_post(collection_id: str):
        """Add item(s) to collection with Pydantic validation and clip boundary support"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)

            # Parse and validate with Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=AddItemToCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error adding item: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            current_timestamp = datetime.utcnow().isoformat() + "Z"
            user_id = user_context.get("user_id")

            asset_id = request_data.assetId
            clip_boundary = request_data.clipBoundary or {}
            add_all_clips = request_data.addAllClips

            items_to_add = []

            # Determine what to add
            if add_all_clips and not clip_boundary.get("startTime"):
                logger.info(f"[ADD_ITEM] Adding all clips for asset {asset_id}")
                clips = get_all_clips_for_asset(asset_id)

                if clips:
                    for clip in clips:
                        sk = generate_asset_sk(asset_id, clip)
                        items_to_add.append(
                            {"SK": sk, "assetId": asset_id, "clipBoundary": clip}
                        )
                else:
                    logger.info(
                        f"[ADD_ITEM] No clips found, adding full file for asset {asset_id}"
                    )
                    sk = generate_asset_sk(asset_id, None)
                    items_to_add.append(
                        {"SK": sk, "assetId": asset_id, "clipBoundary": {}}
                    )
            else:
                sk = generate_asset_sk(
                    asset_id, clip_boundary if clip_boundary else None
                )
                items_to_add.append(
                    {
                        "SK": sk,
                        "assetId": asset_id,
                        "clipBoundary": clip_boundary if clip_boundary else {},
                    }
                )

            # Add all items to DynamoDB using PynamoDB
            added_items = []
            for item_data in items_to_add:
                item = CollectionItemModel()
                item.PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
                item.SK = item_data["SK"]
                item.itemType = "asset"
                item.assetId = item_data["assetId"]
                item.clipBoundary = item_data["clipBoundary"]
                item.addedAt = current_timestamp
                item.addedBy = user_id

                if request_data.sortOrder is not None:
                    item.sortOrder = request_data.sortOrder
                if request_data.metadata:
                    item.metadata = request_data.metadata

                # Set GSI2 for reverse lookup (item to collections)
                item.GSI2_PK = item_data["SK"]
                item.GSI2_SK = f"{COLLECTION_PK_PREFIX}{collection_id}"

                try:
                    item.save()

                    # Convert to dict for formatting
                    item_dict = {
                        "PK": item.PK,
                        "SK": item.SK,
                        "itemType": item.itemType,
                        "assetId": item.assetId,
                        "clipBoundary": (
                            item.clipBoundary.as_dict() if item.clipBoundary else {}
                        ),
                        "sortOrder": item.sortOrder if item.sortOrder else 0,
                        "metadata": item.metadata.as_dict() if item.metadata else {},
                        "addedAt": item.addedAt,
                        "addedBy": item.addedBy,
                    }
                    added_items.append(item_dict)
                    logger.info(f"[ADD_ITEM] Added item with SK: {item_data['SK']}")
                except PutError as e:
                    logger.error(f"[ADD_ITEM] Error adding item: {e}")

            # Update collection updatedAt timestamp
            # Note: itemCount is now computed dynamically
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
                collection.update(
                    actions=[
                        CollectionModel.updatedAt.set(current_timestamp),
                    ]
                )
            except Exception as e:
                logger.warning(f"[ADD_ITEM] Failed to update collection timestamp: {e}")

            logger.info(
                f"[ADD_ITEM] Added {len(added_items)} item(s) to collection {collection_id}"
            )
            metrics.add_metric(
                name="SuccessfulItemAdditions",
                unit=MetricUnit.Count,
                value=len(added_items),
            )

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "addedCount": len(added_items),
                            "items": [
                                format_collection_item(item) for item in added_items
                            ],
                        },
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error adding collection item", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
