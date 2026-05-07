"""GET /collections - List collections with cursor-based pagination."""

import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError
from boto3.dynamodb.conditions import Key
from collections_utils import (
    CHILD_SK_PREFIX,
    COLLECTION_PK_PREFIX,
    COLLECTIONS_GSI5_PK,
    METADATA_SK,
    USER_PK_PREFIX,
    apply_field_selection,
    create_error_response,
    create_success_response,
    format_collection_item,
)
from models import ListCollectionsQueryParams
from user_auth import extract_user_context
from utils.pagination_utils import apply_sorting, create_cursor, parse_cursor

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
collections_table = dynamodb.Table(table_name)

logger = Logger(service="collections-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-get")
metrics = Metrics(namespace="medialake", service="collections")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def register_route(app):
    """Register GET /collections route"""

    @app.get("/collections")
    @tracer.capture_method
    def collections_get():
        """Get list of collections with cursor-based pagination."""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            # Parse and validate query parameters using Pydantic
            try:
                query_params_dict = {
                    "limit": int(
                        app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
                    ),
                }

                if cursor := app.current_event.get_query_string_value("cursor"):
                    query_params_dict["cursor"] = cursor
                if filter_type := app.current_event.get_query_string_value(
                    "filter[type]"
                ):
                    query_params_dict["filter_type"] = filter_type
                if filter_owner := app.current_event.get_query_string_value(
                    "filter[ownerId]"
                ):
                    query_params_dict["filter_ownerId"] = filter_owner
                if filter_parent := app.current_event.get_query_string_value(
                    "filter[parentId]"
                ):
                    query_params_dict["filter_parentId"] = filter_parent
                if filter_status := app.current_event.get_query_string_value(
                    "filter[status]"
                ):
                    query_params_dict["filter_status"] = filter_status
                if filter_search := app.current_event.get_query_string_value(
                    "filter[search]"
                ):
                    query_params_dict["filter_search"] = filter_search
                if group_ids := app.current_event.get_query_string_value("groupIds"):
                    query_params_dict["groupIds"] = group_ids
                if sort_val := app.current_event.get_query_string_value("sort"):
                    query_params_dict["sort"] = sort_val
                if fields_val := app.current_event.get_query_string_value("fields"):
                    query_params_dict["fields"] = fields_val

                query_params = ListCollectionsQueryParams(**query_params_dict)
                # Cap limit to MAX_LIMIT to prevent excessive reads
                if query_params.limit > MAX_LIMIT:
                    query_params.limit = MAX_LIMIT
            except ValidationError as e:
                logger.warning(f"Query parameter validation error: {e}")
                raise BadRequestError(f"Invalid query parameters: {e}")

            logger.info(
                "Listing collections",
                extra={
                    "user_id": user_id,
                    "limit": query_params.limit,
                    "has_cursor": query_params.cursor is not None,
                },
            )

            # Parse cursor for pagination
            exclusive_start_key = _parse_pagination_cursor(query_params.cursor)

            # Pre-fetch group IDs once if needed (avoid re-querying in the loop)
            collection_ids_from_groups = None
            if query_params.groupIds:
                from collection_groups_utils import get_collection_ids_by_group_ids

                group_id_list = [
                    gid.strip()
                    for gid in query_params.groupIds.split(",")
                    if gid.strip()
                ]
                if group_id_list:
                    collection_ids_from_groups = set(
                        get_collection_ids_by_group_ids(
                            collections_table, group_id_list
                        )
                    )

            # Over-fetch to compensate for items removed by access/post filtering.
            # We loop up to MAX_FETCH_ITERATIONS to fill the requested page size.
            desired = query_params.limit
            fetch_limit = desired * 3  # 3x over-fetch per DynamoDB call
            accumulated_items: List[Dict[str, Any]] = []
            last_key = exclusive_start_key
            MAX_FETCH_ITERATIONS = 5

            for _iteration in range(MAX_FETCH_ITERATIONS):
                # Determine query strategy based on filters
                if query_params.filter_parentId:
                    raw_items, last_key = _query_child_collections(
                        query_params.filter_parentId, fetch_limit, last_key
                    )
                elif query_params.filter_ownerId:
                    raw_items, last_key = _query_collections_by_owner(
                        query_params.filter_ownerId, fetch_limit, last_key
                    )
                elif query_params.filter_type:
                    raw_items, last_key = _query_collections_by_type(
                        query_params.filter_type, fetch_limit, last_key
                    )
                else:
                    raw_items, last_key = _query_all_collections(fetch_limit, last_key)

                # Apply access filtering
                filtered = _filter_collections_by_access(raw_items, user_id)

                # Apply group filtering
                if collection_ids_from_groups is not None:
                    filtered = [
                        item
                        for item in filtered
                        if item.get("PK", "").replace(COLLECTION_PK_PREFIX, "")
                        in collection_ids_from_groups
                    ]

                # Apply status/search post-filters
                if query_params.filter_status or query_params.filter_search:
                    filtered = _apply_post_filters(
                        filtered,
                        query_params.filter_status,
                        query_params.filter_search,
                    )

                accumulated_items.extend(filtered)

                # Stop if we have enough or there's no more data
                if len(accumulated_items) >= desired or not last_key:
                    break

            # Remember whether DynamoDB had more pages before we rewrite last_key
            last_key_from_dynamo = last_key

            # Trim to the requested limit
            items = accumulated_items[:desired]

            # Derive last_key from the last returned item so the cursor
            # points to the correct position after trimming, rather than
            # the over-fetched DynamoDB page boundary.
            if items:
                last_item = items[-1]
                last_key = {"PK": last_item["PK"], "SK": last_item["SK"]}
                # Preserve GSI key attributes if present on the item
                for gsi_key in (
                    "GSI5_PK",
                    "GSI5_SK",
                    "GSI3_PK",
                    "GSI3_SK",
                    "GSI1_PK",
                    "GSI1_SK",
                ):
                    if gsi_key in last_item:
                        last_key[gsi_key] = last_item[gsi_key]
                # If we consumed everything and DynamoDB had no more pages,
                # there's genuinely no next page.
                if len(accumulated_items) <= desired and not last_key_from_dynamo:
                    last_key = None
            else:
                last_key = None

            # Format items
            formatted_items = [
                format_collection_item(item, user_context) for item in items
            ]

            # Apply field selection
            if query_params.fields:
                formatted_items = [
                    apply_field_selection(item, query_params.fields)
                    for item in formatted_items
                ]

            # Apply sorting only when not using cursor-based pagination,
            # since cursor pagination relies on GSI ordering (e.g. GSI5_SK/timestamp)
            # and re-sorting a single page would break cross-page ordering.
            if query_params.cursor:
                sorted_items = formatted_items
            else:
                sorted_items = apply_sorting(formatted_items, query_params.sort)

            # Build pagination response with cursor
            next_cursor = None
            if last_key:
                next_cursor = _build_pagination_cursor(last_key)

            pagination = {
                "has_next_page": next_cursor is not None,
                "has_prev_page": query_params.cursor is not None,
                "next_cursor": next_cursor,
                "limit": query_params.limit,
            }

            metrics.add_metric(
                name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
            )
            metrics.add_metric(
                name="CollectionsReturned",
                unit=MetricUnit.Count,
                value=len(sorted_items),
            )

            return create_success_response(
                data=sorted_items,
                pagination=pagination,
                request_id=app.current_event.request_context.request_id,
            )

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Unexpected error listing collections", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )


# --- Pagination cursor helpers ---


def _parse_pagination_cursor(cursor_str: Optional[str]) -> Optional[Dict[str, str]]:
    """Parse a pagination cursor into a DynamoDB ExclusiveStartKey.

    Uses the embedded gsi_name to reconstruct the correct GSI key attributes.
    """
    if not cursor_str:
        return None
    parsed = parse_cursor(cursor_str)
    if not parsed:
        logger.warning("Invalid pagination cursor, ignoring")
        return None
    if "pk" not in parsed or "sk" not in parsed:
        logger.warning("Pagination cursor missing pk/sk, ignoring")
        return None
    # Reconstruct the ExclusiveStartKey from cursor data
    start_key = {"PK": parsed["pk"], "SK": parsed["sk"]}

    gsi_name = parsed.get("gsi_name")
    gsi_pk = parsed.get("gsi_pk")
    gsi_sk = parsed.get("gsi_sk")

    if gsi_name and gsi_pk:
        start_key[f"{gsi_name}_PK"] = gsi_pk
    if gsi_name and gsi_sk:
        start_key[f"{gsi_name}_SK"] = gsi_sk

    # Backwards compatibility: cursors without gsi_name fall back to GSI5
    if not gsi_name:
        if gsi_pk:
            start_key["GSI5_PK"] = gsi_pk
        if gsi_sk:
            start_key["GSI5_SK"] = gsi_sk
        # Also honour legacy gsi3_ fields if present
        if parsed.get("gsi3_pk"):
            start_key["GSI3_PK"] = parsed["gsi3_pk"]
        if parsed.get("gsi3_sk"):
            start_key["GSI3_SK"] = parsed["gsi3_sk"]

    return start_key


def _build_pagination_cursor(last_evaluated_key: Dict[str, str]) -> str:
    """Build a pagination cursor from a DynamoDB LastEvaluatedKey.

    Embeds the GSI origin so the decoder can reconstruct the correct
    ExclusiveStartKey attributes (GSI5_PK/SK vs GSI3_PK/SK vs GSI1_PK/SK).
    """
    gsi_pk = None
    gsi_sk = None
    gsi_name = None

    if "GSI5_PK" in last_evaluated_key:
        gsi_name = "GSI5"
        gsi_pk = last_evaluated_key.get("GSI5_PK")
        gsi_sk = last_evaluated_key.get("GSI5_SK")
    elif "GSI3_PK" in last_evaluated_key:
        gsi_name = "GSI3"
        gsi_pk = last_evaluated_key.get("GSI3_PK")
        gsi_sk = last_evaluated_key.get("GSI3_SK")
    elif "GSI1_PK" in last_evaluated_key:
        gsi_name = "GSI1"
        gsi_pk = last_evaluated_key.get("GSI1_PK")
        gsi_sk = last_evaluated_key.get("GSI1_SK")

    return create_cursor(
        pk=last_evaluated_key.get("PK", ""),
        sk=last_evaluated_key.get("SK", ""),
        gsi_pk=gsi_pk,
        gsi_sk=gsi_sk,
        gsi_name=gsi_name,
    )


# --- Query functions ---


@tracer.capture_method
def _query_collections_by_owner(
    user_id: str, limit: int, exclusive_start_key: Optional[Dict] = None
) -> Tuple[List[Dict[str, Any]], Optional[Dict]]:
    """Query collections by owner using GSI1 (UserCollectionsGSI)."""
    items = []
    last_key = None
    try:
        query_kwargs = {
            "IndexName": "UserCollectionsGSI",
            "KeyConditionExpression": Key("GSI1_PK").eq(f"{USER_PK_PREFIX}{user_id}"),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key

        response = collections_table.query(**query_kwargs)
        # Filter to only METADATA items for collections (not groups, etc.)
        for item in response.get("Items", []):
            if item.get("SK") == METADATA_SK and item.get("PK", "").startswith(
                COLLECTION_PK_PREFIX
            ):
                items.append(item)

        last_key = response.get("LastEvaluatedKey")

    except Exception as e:
        logger.warning(f"Error querying collections by owner via GSI1: {e}")
        # Fallback to GSI5 scan filtered by owner.
        # Reset start key — the GSI1-shaped key is incompatible with GSI5.
        items, last_key = _query_all_collections(limit, exclusive_start_key=None)
        items = [item for item in items if item.get("ownerId") == user_id]
        last_key = None  # Can't reliably continue pagination after a fallback switch

    return items, last_key


@tracer.capture_method
def _query_all_collections(
    limit: int, exclusive_start_key: Optional[Dict] = None
) -> Tuple[List[Dict[str, Any]], Optional[Dict]]:
    """Query all collections using GSI5 (RecentlyModifiedGSI) instead of scanning."""
    items = []
    last_key = None
    try:
        query_kwargs = {
            "IndexName": "RecentlyModifiedGSI",
            "KeyConditionExpression": Key("GSI5_PK").eq(COLLECTIONS_GSI5_PK),
            "ScanIndexForward": False,  # Most recently updated first
            "Limit": limit,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key

        response = collections_table.query(**query_kwargs)
        items = response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")

    except Exception as e:
        logger.warning(f"Error querying GSI5, falling back to scan: {e}")
        # Fallback: scan with filter (original behavior)
        # Reset start key — the GSI5-shaped key is incompatible with a base table scan.
        scan_kwargs = {
            "FilterExpression": "SK = :sk AND begins_with(PK, :pk_prefix)",
            "ExpressionAttributeValues": {
                ":sk": METADATA_SK,
                ":pk_prefix": COLLECTION_PK_PREFIX,
            },
            "Limit": limit,
        }
        response = collections_table.scan(**scan_kwargs)
        items = response.get("Items", [])
        last_key = None  # Can't reliably continue pagination after a fallback switch

    return items, last_key


@tracer.capture_method
def _query_collections_by_type(
    collection_type_id: str, limit: int, exclusive_start_key: Optional[Dict] = None
) -> Tuple[List[Dict[str, Any]], Optional[Dict]]:
    """Query collections by type using GSI3 (CollectionTypeGSI) instead of scanning."""
    items = []
    last_key = None
    try:
        query_kwargs = {
            "IndexName": "CollectionTypeGSI",
            "KeyConditionExpression": Key("GSI3_PK").eq(collection_type_id),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key

        response = collections_table.query(**query_kwargs)
        items = response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")

    except Exception as e:
        logger.warning(f"Error querying GSI3, falling back to scan: {e}")
        # Reset start key — the GSI3-shaped key is incompatible with a base table scan.
        scan_kwargs = {
            "FilterExpression": (
                "SK = :sk AND collectionTypeId = :type_id"
                " AND begins_with(PK, :pk_prefix)"
            ),
            "ExpressionAttributeValues": {
                ":sk": METADATA_SK,
                ":type_id": collection_type_id,
                ":pk_prefix": COLLECTION_PK_PREFIX,
            },
            "Limit": limit,
        }
        response = collections_table.scan(**scan_kwargs)
        items = response.get("Items", [])
        last_key = None  # Can't reliably continue pagination after a fallback switch

    return items, last_key


@tracer.capture_method
def _query_child_collections(
    parent_id: str, limit: int, exclusive_start_key: Optional[Dict] = None
) -> Tuple[List[Dict[str, Any]], Optional[Dict]]:
    """Query child collections using BatchGetItem instead of N+1 GetItem calls."""
    logger.info(f"Querying child collections for parent: {parent_id}")

    child_items = []
    last_key = None
    try:
        # Step 1: Query child references from the parent collection
        query_kwargs = {
            "KeyConditionExpression": (
                Key("PK").eq(f"{COLLECTION_PK_PREFIX}{parent_id}")
                & Key("SK").begins_with(CHILD_SK_PREFIX)
            ),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key

        response = collections_table.query(**query_kwargs)
        child_refs = response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")

        # Step 2: Batch-fetch all child collection metadata
        child_ids = [
            ref.get("childCollectionId")
            for ref in child_refs
            if ref.get("childCollectionId")
        ]

        if child_ids:
            child_items = _batch_get_collection_metadata(child_ids)

    except Exception as e:
        logger.warning(f"Error querying child collections: {e}")

    logger.info(f"Found {len(child_items)} child collections")
    return child_items, last_key


@tracer.capture_method
def _batch_get_collection_metadata(
    collection_ids: List[str],
) -> List[Dict[str, Any]]:
    """Fetch multiple collection metadata records using BatchGetItem (max 100 per batch)."""
    all_items = []
    # DynamoDB BatchGetItem supports max 100 keys per request
    batch_size = 100

    for i in range(0, len(collection_ids), batch_size):
        batch_ids = collection_ids[i : i + batch_size]
        keys = [
            {"PK": f"{COLLECTION_PK_PREFIX}{cid}", "SK": METADATA_SK}
            for cid in batch_ids
        ]

        try:
            response = dynamodb.batch_get_item(
                RequestItems={table_name: {"Keys": keys}}
            )
            items = response.get("Responses", {}).get(table_name, [])
            all_items.extend(items)

            # Handle unprocessed keys (throttling) with exponential backoff
            unprocessed = response.get("UnprocessedKeys", {}).get(table_name)
            max_retries = 5
            retry = 0
            while unprocessed and retry < max_retries:
                delay = min(2**retry * 0.1, 5)  # 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                time.sleep(delay + random.uniform(0, delay * 0.5))  # jitter
                response = dynamodb.batch_get_item(
                    RequestItems={table_name: unprocessed}
                )
                items = response.get("Responses", {}).get(table_name, [])
                all_items.extend(items)
                unprocessed = response.get("UnprocessedKeys", {}).get(table_name)
                retry += 1
            if unprocessed:
                unprocessed_count = len(unprocessed.get("Keys", []))
                logger.error(
                    f"Partial data: {unprocessed_count} unprocessed keys remain "
                    f"after {max_retries} retries for batch starting at {i}. "
                    f"Results may be incomplete."
                )

        except Exception as e:
            logger.warning(f"BatchGetItem error for batch starting at {i}: {e}")

    return all_items


@tracer.capture_method
def _get_shared_collection_ids(user_id):
    """
    Get IDs of collections shared with the user.
    Paginates through all results to handle users with many shared collections.

    Returns:
        Dictionary mapping collection_id to relationship info
    """
    shared_collections = {}

    try:
        query_kwargs = {
            "IndexName": "UserCollectionsGSI",
            "KeyConditionExpression": "GSI1_PK = :user_pk",
            "FilterExpression": "relationship <> :owner",
            "ExpressionAttributeValues": {
                ":user_pk": f"{USER_PK_PREFIX}{user_id}",
                ":owner": "OWNER",
            },
        }

        while True:
            response = collections_table.query(**query_kwargs)

            for item in response.get("Items", []):
                collection_id = item.get("SK", "").replace(COLLECTION_PK_PREFIX, "")
                if collection_id:
                    shared_collections[collection_id] = {
                        "role": item.get("relationship", "VIEWER"),
                        "sharedAt": item.get("addedAt"),
                    }

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

    except Exception as e:
        logger.warning(
            {
                "message": "Error querying shared collections",
                "user_id": user_id,
                "error": str(e),
                "operation": "_get_shared_collection_ids",
            }
        )

    return shared_collections


@tracer.capture_method
def _batch_check_collections_have_shares(
    collection_ids: List[str],
) -> Dict[str, bool]:
    """
    Check which collections have shares.
    Returns a dict mapping collection_id -> has_shares (bool).

    Note: This still issues one COUNT query per collection. At the current
    page size (max 200), this is bounded and acceptable. For further
    optimization, consider storing an isShared boolean on the metadata
    record and maintaining it on share create/delete.
    """
    result = {cid: False for cid in collection_ids}
    if not collection_ids:
        return result

    for cid in collection_ids:
        try:
            response = collections_table.query(
                KeyConditionExpression=(
                    Key("PK").eq(f"{COLLECTION_PK_PREFIX}{cid}")
                    & Key("SK").begins_with("PERM#")
                ),
                Select="COUNT",
                Limit=1,
            )
            result[cid] = response.get("Count", 0) > 0
        except Exception as e:
            logger.warning(f"Error checking shares for {cid}: {e}")

    return result


@tracer.capture_method
def _filter_collections_by_access(
    items: List[Dict[str, Any]], user_id: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Filter collections based on privacy, ownership, and sharing.
    Uses batched share-checking instead of per-item queries.
    """
    if not user_id:
        return []

    # Get collections shared with this user (single query)
    shared_collection_info = _get_shared_collection_ids(user_id)

    # Collect IDs of collections owned by the user to batch-check shares
    owned_collection_ids = []
    for item in items:
        pk = item.get("PK", "")
        if not pk.startswith(COLLECTION_PK_PREFIX):
            continue
        if item.get("ownerId") == user_id:
            collection_id = pk.replace(COLLECTION_PK_PREFIX, "")
            owned_collection_ids.append(collection_id)

    # Batch check shares for all owned collections at once
    shares_map = _batch_check_collections_have_shares(owned_collection_ids)

    filtered_items = []
    for item in items:
        pk = item.get("PK", "")
        if not pk.startswith(COLLECTION_PK_PREFIX):
            continue

        is_public = item.get("isPublic", False)
        owner_id = item.get("ownerId")
        collection_id = pk.replace(COLLECTION_PK_PREFIX, "")

        if is_public:
            if owner_id == user_id:
                item["isShared"] = shares_map.get(collection_id, False)
            filtered_items.append(item)
        elif owner_id == user_id:
            item["isShared"] = shares_map.get(collection_id, False)
            filtered_items.append(item)
        elif collection_id in shared_collection_info:
            share_info = shared_collection_info[collection_id]
            item["sharedWithMe"] = True
            item["myRole"] = share_info.get("role", "VIEWER")
            item["sharedAt"] = share_info.get("sharedAt")
            filtered_items.append(item)

    logger.debug(
        {
            "message": "Filtered collections by access",
            "original_count": len(items),
            "filtered_count": len(filtered_items),
            "user_id": user_id,
            "operation": "_filter_collections_by_access",
        }
    )

    return filtered_items


@tracer.capture_method
def _apply_post_filters(items, status_filter, search_filter):
    """Apply post-query filters"""
    filtered_items = []
    for item in items:
        if status_filter and item.get("status") != status_filter:
            continue
        if search_filter:
            search_term = search_filter.lower()
            name_match = search_term in item.get("name", "").lower()
            desc_match = search_term in item.get("description", "").lower()
            if not (name_match or desc_match):
                continue
        filtered_items.append(item)
    return filtered_items


def _model_to_dict(collection) -> dict[str, Any]:
    """Convert PynamoDB model to dict for formatting.

    Uses the stored itemCount instead of dynamically querying per collection.
    """
    item_dict = {
        "PK": collection.PK,
        "SK": collection.SK,
        "name": collection.name,
        "ownerId": collection.ownerId,
        "status": collection.status,
        "itemCount": collection.itemCount or 0,
        "childCollectionCount": collection.childCollectionCount,
        "isPublic": collection.isPublic,
        "createdAt": collection.createdAt,
        "updatedAt": collection.updatedAt,
    }

    if collection.description:
        item_dict["description"] = collection.description
    if collection.collectionTypeId:
        item_dict["collectionTypeId"] = collection.collectionTypeId
    if collection.parentId:
        item_dict["parentId"] = collection.parentId
    if collection.customMetadata:
        item_dict["customMetadata"] = dict(collection.customMetadata)
    if collection.tags:
        item_dict["tags"] = list(collection.tags)
    if collection.expiresAt:
        item_dict["expiresAt"] = collection.expiresAt
    if collection.thumbnailType:
        item_dict["thumbnailType"] = collection.thumbnailType
    if collection.thumbnailValue:
        item_dict["thumbnailValue"] = collection.thumbnailValue
    if collection.thumbnailS3Key:
        item_dict["thumbnailS3Key"] = collection.thumbnailS3Key

    return item_dict
