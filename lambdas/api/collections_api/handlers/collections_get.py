"""GET /collections - List collections with filtering and pagination."""

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError
from collections_utils import (
    CHILD_SK_PREFIX,
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    USER_PK_PREFIX,
    apply_field_selection,
    create_error_response,
    create_success_response,
    format_collection_item,
    get_collection_item_count,
)
from db_models import ChildReferenceModel, CollectionModel
from models import ListCollectionsQueryParams
from pynamodb.exceptions import QueryError
from user_auth import extract_user_context
from utils.pagination_utils import apply_sorting, create_cursor, parse_cursor

# Initialize DynamoDB resource for dynamic item count queries
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
collections_table = dynamodb.Table(table_name)

logger = Logger(service="collections-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-get")
metrics = Metrics(namespace="medialake", service="collections")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def register_route(app):
    """Register GET /collections route"""

    @app.get("/collections")
    @tracer.capture_method
    def collections_get():
        """Get list of collections with comprehensive filtering and pagination"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            # Parse and validate query parameters using Pydantic
            try:
                # Build query params dict - use field names, not aliases
                query_params_dict = {
                    "cursor": app.current_event.get_query_string_value("cursor"),
                    "limit": int(
                        app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
                    ),
                }

                # Add optional filter parameters if present
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
            except ValidationError as e:
                logger.warning(f"Query parameter validation error: {e}")
                raise BadRequestError(f"Invalid query parameters: {e}")

            logger.info(
                "Listing collections",
                extra={
                    "user_id": user_id,
                    "limit": query_params.limit,
                },
            )

            # Parse cursor for pagination
            start_key = None
            parsed_cursor = parse_cursor(query_params.cursor)
            if parsed_cursor:
                start_key = {
                    "PK": parsed_cursor.get("pk"),
                    "SK": parsed_cursor.get("sk"),
                }
                if parsed_cursor.get("gsi_pk"):
                    start_key["GSI1_PK"] = parsed_cursor.get("gsi_pk")
                if parsed_cursor.get("gsi_sk"):
                    start_key["GSI1_SK"] = parsed_cursor.get("gsi_sk")

            # Determine query strategy based on filters
            if query_params.filter_parentId:
                items = _query_child_collections(
                    query_params.filter_parentId, query_params.limit, start_key
                )
            elif query_params.filter_ownerId:
                items = _query_collections_by_owner(
                    query_params.filter_ownerId, query_params.limit, start_key
                )
            elif query_params.filter_type:
                items = _query_collections_by_type(
                    query_params.filter_type, query_params.limit, start_key
                )
            else:
                items = _query_all_collections(query_params.limit, start_key)

            # Filter collections based on privacy and ownership
            # This ensures:
            # - Public collections are visible to authenticated users only
            # - Private collections are only visible to their owners
            # - Unauthenticated users see no collections
            items = _filter_collections_by_access(items, user_id)

            # Apply group filtering if groupIds parameter provided (OR logic)
            if query_params.groupIds:
                from collection_groups_utils import get_collection_ids_by_group_ids

                group_id_list = [
                    gid.strip()
                    for gid in query_params.groupIds.split(",")
                    if gid.strip()
                ]
                if group_id_list:
                    # Get all collection IDs from specified groups
                    collection_ids_from_groups = set(
                        get_collection_ids_by_group_ids(
                            collections_table, group_id_list
                        )
                    )

                    # Filter items to only include collections in the groups (AND logic with other filters)
                    items = [
                        item
                        for item in items
                        if item.get("PK", "").replace(COLLECTION_PK_PREFIX, "")
                        in collection_ids_from_groups
                    ]

                    logger.debug(
                        {
                            "message": "Applied group filtering",
                            "group_count": len(group_id_list),
                            "collection_count": len(items),
                            "operation": "collections_get",
                        }
                    )

            has_more = len(items) > query_params.limit
            if has_more:
                items = items[: query_params.limit]

            # Apply post-query filters
            if query_params.filter_status or query_params.filter_search:
                items = _apply_post_filters(
                    items, query_params.filter_status, query_params.filter_search
                )

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

            # Apply sorting
            sorted_items = apply_sorting(formatted_items, query_params.sort)

            # Create pagination
            pagination = {
                "has_next_page": has_more,
                "has_prev_page": query_params.cursor is not None,
                "limit": query_params.limit,
            }

            if has_more and items:
                last_item = items[-1]
                gsi_pk = None
                gsi_sk = None

                if query_params.filter_ownerId:
                    gsi_pk = f"{USER_PK_PREFIX}{query_params.filter_ownerId}"
                    gsi_sk = last_item.get("lastAccessed", last_item.get("updatedAt"))
                elif query_params.filter_type:
                    gsi_pk = query_params.filter_type
                    gsi_sk = last_item["SK"]

                next_cursor = create_cursor(
                    last_item["PK"], last_item["SK"], gsi_pk, gsi_sk
                )
                pagination["next_cursor"] = next_cursor

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


# Helper functions
@tracer.capture_method
def _query_collections_by_owner(user_id, limit, start_key):
    """Query collections by owner using GSI1 - PynamoDB doesn't easily support GSI queries without index classes"""
    # For now, we'll use a workaround - query all and filter
    # In production, you'd want to define GSI index classes in db_models.py
    items = []
    try:
        # Query using the primary key pattern
        # This is a simplified version - ideally use GSI
        for collection in CollectionModel.query(
            f"{USER_PK_PREFIX}{user_id}",
            limit=limit + 1,
        ):
            if collection.ownerId == user_id:
                items.append(_model_to_dict(collection))
    except QueryError as e:
        logger.warning(f"Error querying collections by owner: {e}")
    except Exception as e:
        logger.warning(f"Query not supported, falling back to scan: {e}")
        # Fallback: query all collections and filter
        items = []
        for collection in _query_all_collections(limit, start_key):
            if collection.get("ownerId") == user_id:
                items.append(collection)
                if len(items) > limit:
                    break

    return items[: limit + 1]


@tracer.capture_method
def _query_all_collections(limit, start_key):
    """Query all collections using GSI5"""
    items = []
    try:
        # Query all collections - simplified without GSI for now
        # In production, define GSI5 index class in db_models.py
        for collection in CollectionModel.scan(
            limit=limit + 1,
            filter_condition=(CollectionModel.SK == METADATA_SK),
        ):
            items.append(_model_to_dict(collection))
    except Exception as e:
        logger.warning(f"Error querying all collections: {e}")

    return items


@tracer.capture_method
def _query_collections_by_type(collection_type_id, limit, start_key):
    """Query collections by type using GSI3"""
    items = []
    try:
        # Simplified - scan and filter by type
        for collection in CollectionModel.scan(
            limit=limit + 1,
            filter_condition=(
                (CollectionModel.SK == METADATA_SK)
                & (CollectionModel.collectionTypeId == collection_type_id)
            ),
        ):
            items.append(_model_to_dict(collection))
    except Exception as e:
        logger.warning(f"Error querying collections by type: {e}")

    return items


@tracer.capture_method
def _query_child_collections(parent_id, limit, start_key):
    """Query child collections by parent ID using CHILD# references"""
    logger.info(f"Querying child collections for parent: {parent_id}")

    child_items = []
    try:
        # Query for child references using PynamoDB
        for child_ref in ChildReferenceModel.query(
            f"{COLLECTION_PK_PREFIX}{parent_id}",
            ChildReferenceModel.SK.startswith(CHILD_SK_PREFIX),
            limit=limit + 1,
        ):
            child_id = child_ref.childCollectionId
            if child_id:
                try:
                    # Get full collection data
                    collection = CollectionModel.get(
                        f"{COLLECTION_PK_PREFIX}{child_id}", METADATA_SK
                    )
                    child_items.append(_model_to_dict(collection))
                except Exception as e:
                    logger.warning(f"Failed to get child collection {child_id}: {e}")
    except Exception as e:
        logger.warning(f"Error querying child collections: {e}")

    logger.info(f"Found {len(child_items)} child collections")
    return child_items


@tracer.capture_method
def _get_shared_collection_ids(user_id):
    """
    Get IDs of collections shared with the user.

    Args:
        user_id: User ID to check

    Returns:
        Dictionary mapping collection_id to relationship info
    """
    shared_collections = {}

    try:
        # Query UserCollectionsGSI for user's relationships
        response = collections_table.query(
            IndexName="UserCollectionsGSI",
            KeyConditionExpression="GSI1_PK = :user_pk",
            FilterExpression="relationship <> :owner",
            ExpressionAttributeValues={
                ":user_pk": f"{USER_PK_PREFIX}{user_id}",
                ":owner": "OWNER",
            },
        )

        for item in response.get("Items", []):
            # Extract collection ID from SK (format: COLL#{collection_id})
            collection_id = item.get("SK", "").replace(COLLECTION_PK_PREFIX, "")
            if collection_id:
                shared_collections[collection_id] = {
                    "role": item.get("relationship", "VIEWER"),
                    "sharedAt": item.get("addedAt"),
                }

        logger.debug(
            {
                "message": "Found shared collections for user",
                "user_id": user_id,
                "shared_count": len(shared_collections),
                "operation": "_get_shared_collection_ids",
            }
        )

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
def _filter_collections_by_access(items, user_id):
    """
    Filter collections based on privacy, ownership, and sharing.

    Returns:
        - Public collections (isPublic = True) - visible to authenticated users
        - Private collections if user_id matches ownerId
        - Private collections shared with the user
        - Unauthenticated users (user_id = None) see no collections

    Args:
        items: List of collection dictionaries
        user_id: User ID from JWT token, or None if unauthenticated

    Returns:
        Filtered list of collections with sharing metadata
    """
    filtered_items = []

    # Unauthenticated users cannot see any collections
    if not user_id:
        logger.debug(
            {
                "message": "Unauthenticated user - no collections visible",
                "original_count": len(items),
                "filtered_count": 0,
                "operation": "_filter_collections_by_access",
            }
        )
        return filtered_items

    # Get collections shared with this user
    shared_collection_info = _get_shared_collection_ids(user_id)

    for item in items:
        is_public = item.get("isPublic", False)
        owner_id = item.get("ownerId")
        collection_id = item.get("PK", "").replace(COLLECTION_PK_PREFIX, "")

        # Public collections are accessible to authenticated users
        if is_public:
            # Check if owner has shared this collection (for isShared flag)
            if owner_id == user_id:
                item["isShared"] = _check_collection_has_shares(collection_id)
            filtered_items.append(item)
        # Private collections: accessible to owner
        elif owner_id == user_id:
            # Check if this collection has any shares
            item["isShared"] = _check_collection_has_shares(collection_id)
            filtered_items.append(item)
        # Private collections shared with this user
        elif collection_id in shared_collection_info:
            share_info = shared_collection_info[collection_id]
            item["sharedWithMe"] = True
            item["myRole"] = share_info.get("role", "VIEWER")
            item["sharedAt"] = share_info.get("sharedAt")
            filtered_items.append(item)
        # Private collections owned by others and not shared are excluded

    logger.debug(
        {
            "message": "Filtered collections by access",
            "original_count": len(items),
            "filtered_count": len(filtered_items),
            "user_id": user_id,
            "shared_access_count": len(shared_collection_info),
            "operation": "_filter_collections_by_access",
        }
    )

    return filtered_items


@tracer.capture_method
def _check_collection_has_shares(collection_id):
    """
    Check if a collection has any shares.

    Args:
        collection_id: Collection ID to check

    Returns:
        True if collection has shares, False otherwise
    """
    try:
        response = collections_table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :perm_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":perm_prefix": "PERM#",
            },
            Select="COUNT",
            Limit=1,
        )
        return response.get("Count", 0) > 0
    except Exception as e:
        logger.warning(
            {
                "message": "Error checking collection shares",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "_check_collection_has_shares",
            }
        )
        return False


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

    Args:
        collection: PynamoDB CollectionModel instance

    Returns:
        Dictionary representation of the collection
    """
    # Get dynamic item count (returns -1 on error)
    dynamic_item_count: int = get_collection_item_count(
        collections_table, collection.PK
    )

    item_dict = {
        "PK": collection.PK,
        "SK": collection.SK,
        "name": collection.name,
        "ownerId": collection.ownerId,
        "status": collection.status,
        "itemCount": dynamic_item_count,
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

    return item_dict
