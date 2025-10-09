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
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

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
ASSET_SK_PREFIX = "ASSET#"

# Environment variables
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "")

# Cache for OpenSearch client
_opensearch_client = None


def get_opensearch_client() -> Optional[OpenSearch]:
    """Create and return a cached OpenSearch client"""
    global _opensearch_client

    if not OPENSEARCH_ENDPOINT or not OPENSEARCH_INDEX:
        logger.warning("[OPENSEARCH] OpenSearch not configured")
        return None

    if _opensearch_client is None:
        try:
            host = OPENSEARCH_ENDPOINT.replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ.get("SCOPE", "es")

            auth = RequestsAWSV4SignerAuth(
                boto3.Session().get_credentials(), region, service_scope
            )

            _opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                region=region,
                timeout=30,
                max_retries=2,
                retry_on_timeout=True,
            )

            logger.info("[OPENSEARCH] OpenSearch client initialized")
        except Exception as e:
            logger.error(f"[OPENSEARCH] Failed to initialize client: {str(e)}")
            return None

    return _opensearch_client


def get_all_clips_for_asset(asset_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all clips for a specific asset from OpenSearch.

    Args:
        asset_id: The ID of the asset to retrieve clips for

    Returns:
        List of clip objects with startTime and endTime
    """
    try:
        client = get_opensearch_client()
        if not client:
            logger.warning(
                f"[CLIPS] OpenSearch client not available for asset {asset_id}"
            )
            return []

        # Query for clips associated with this asset
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"InventoryID": asset_id}},
                        {"term": {"embedding_scope": "clip"}},
                    ]
                }
            },
            "size": 1000,  # Get all clips
            "_source": ["start_timecode", "end_timecode", "score"],
            "sort": [{"start_timecode": {"order": "asc"}}],
        }

        response = client.search(body=query, index=OPENSEARCH_INDEX)

        clips = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            start_time = source.get("start_timecode")
            end_time = source.get("end_timecode")

            if start_time and end_time:
                clips.append(
                    {
                        "startTime": start_time,
                        "endTime": end_time,
                    }
                )

        logger.info(f"[CLIPS] Retrieved {len(clips)} clips for asset {asset_id}")
        return clips

    except Exception as e:
        logger.error(f"[CLIPS] Error retrieving clips for asset {asset_id}: {str(e)}")
        return []


def generate_asset_sk(
    asset_id: str, clip_boundary: Optional[Dict[str, str]] = None
) -> str:
    """
    Generate SK for an asset item based on clip boundary.

    Args:
        asset_id: The asset ID
        clip_boundary: Optional dict with startTime and endTime

    Returns:
        SK string like ASSET#id#FULL or ASSET#id#CLIP#start-end
    """
    if not clip_boundary or (
        not clip_boundary.get("startTime") and not clip_boundary.get("endTime")
    ):
        # Full file
        return f"{ASSET_SK_PREFIX}{asset_id}#FULL"

    start_time = clip_boundary.get("startTime", "")
    end_time = clip_boundary.get("endTime", "")

    # Sanitize timecodes for use in SK (replace : with -)
    start_sanitized = start_time.replace(":", "-")
    end_sanitized = end_time.replace(":", "-")

    return f"{ASSET_SK_PREFIX}{asset_id}#CLIP#{start_sanitized}_{end_sanitized}"


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
        """
        Add item(s) to collection with clip boundary support.

        Request body:
        {
            "assetId": "12345",
            "clipBoundary": {"startTime": "HH:MM:SS:FF", "endTime": "HH:MM:SS:FF"}, # Optional
            "addAllClips": true  # Optional - if true and no clipBoundary, adds all clips
        }
        """
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            request_data = app.current_event.json_body

            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"
            user_id = user_context.get("user_id")

            asset_id = request_data.get("assetId")
            if not asset_id:
                return create_error_response(
                    error_code="ValidationError",
                    error_message="assetId is required",
                    status_code=400,
                    request_id=app.current_event.request_context.request_id,
                )

            clip_boundary = request_data.get("clipBoundary", {})
            add_all_clips = request_data.get("addAllClips", False)

            items_to_add = []

            # Determine what to add
            if add_all_clips and not clip_boundary.get("startTime"):
                # Add all clips for this asset
                logger.info(f"[ADD_ITEM] Adding all clips for asset {asset_id}")
                clips = get_all_clips_for_asset(asset_id)

                if clips:
                    for clip in clips:
                        sk = generate_asset_sk(asset_id, clip)
                        items_to_add.append(
                            {
                                "SK": sk,
                                "assetId": asset_id,
                                "clipBoundary": clip,
                            }
                        )
                else:
                    # No clips found, add full file
                    logger.info(
                        f"[ADD_ITEM] No clips found, adding full file for asset {asset_id}"
                    )
                    sk = generate_asset_sk(asset_id, None)
                    items_to_add.append(
                        {
                            "SK": sk,
                            "assetId": asset_id,
                            "clipBoundary": {},
                        }
                    )
            else:
                # Add single item (either specific clip or full file)
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

            # Add all items to DynamoDB
            added_items = []
            for item_data in items_to_add:
                item = {
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": item_data["SK"],
                    "itemType": "asset",
                    "assetId": item_data["assetId"],
                    "clipBoundary": item_data["clipBoundary"],
                    "addedAt": current_timestamp,
                    "addedBy": user_id,
                }

                table.put_item(Item=item)
                added_items.append(item)
                logger.info(f"[ADD_ITEM] Added item with SK: {item_data['SK']}")

            # Update collection item count
            table.update_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
                UpdateExpression="ADD itemCount :inc SET updatedAt = :timestamp",
                ExpressionAttributeValues={
                    ":inc": len(added_items),
                    ":timestamp": current_timestamp,
                },
            )

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
                                _format_collection_item(item) for item in added_items
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
    # For backward compatibility, support both old ITEM# format and new ASSET# format
    sk = item["SK"]

    if sk.startswith(ASSET_SK_PREFIX):
        # New format - extract assetId from SK
        item_id = sk
    else:
        # Old format - use ITEM# prefix
        item_id = sk.replace(ITEM_SK_PREFIX, "")

    return {
        "id": item_id,
        "itemType": item.get("itemType", ""),
        "assetId": item.get(
            "assetId", item.get("itemId", "")
        ),  # Support both old and new formats
        "clipBoundary": item.get("clipBoundary", {}),
        "sortOrder": item.get("sortOrder", 0),
        "metadata": item.get("metadata", {}),
        "addedAt": item.get("addedAt", ""),
        "addedBy": item.get("addedBy", ""),
    }
