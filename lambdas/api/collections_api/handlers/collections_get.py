"""GET /collections - List collections with filtering and pagination."""

import os

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
)
from db_models import ChildReferenceModel, CollectionModel
from models import ListCollectionsQueryParams
from pynamodb.exceptions import QueryError
from user_auth import extract_user_context
from utils.pagination_utils import apply_sorting, create_cursor, parse_cursor

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


def _model_to_dict(collection):
    """Convert PynamoDB model to dict for formatting"""
    item_dict = {
        "PK": collection.PK,
        "SK": collection.SK,
        "name": collection.name,
        "ownerId": collection.ownerId,
        "status": collection.status,
        "itemCount": collection.itemCount,
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
