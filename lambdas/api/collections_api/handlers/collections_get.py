"""GET /collections - List collections with filtering and pagination."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError
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

logger = Logger(service="collections-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-get")
metrics = Metrics(namespace="medialake", service="collections")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def register_route(app, dynamodb, table_name):
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
                query_params = ListCollectionsQueryParams(
                    cursor=app.current_event.get_query_string_value("cursor"),
                    limit=int(
                        app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
                    ),
                    filter_type=app.current_event.get_query_string_value(
                        "filter[type]"
                    ),
                    filter_ownerId=app.current_event.get_query_string_value(
                        "filter[ownerId]"
                    ),
                    filter_parentId=app.current_event.get_query_string_value(
                        "filter[parentId]"
                    ),
                    filter_status=app.current_event.get_query_string_value(
                        "filter[status]"
                    ),
                    filter_search=app.current_event.get_query_string_value(
                        "filter[search]"
                    ),
                    sort=app.current_event.get_query_string_value("sort"),
                    fields=app.current_event.get_query_string_value("fields"),
                )
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

            table = dynamodb.Table(table_name)

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
                response = _query_child_collections(
                    table, query_params.filter_parentId, query_params.limit, start_key
                )
            elif query_params.filter_ownerId:
                response = _query_collections_by_owner(
                    table, query_params.filter_ownerId, query_params.limit, start_key
                )
            elif query_params.filter_type:
                response = _query_collections_by_type(
                    table, query_params.filter_type, query_params.limit, start_key
                )
            else:
                response = _query_all_collections(table, query_params.limit, start_key)

            items = response.get("Items", [])
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
def _query_collections_by_owner(table, user_id, limit, start_key):
    """Query collections by owner using GSI1"""
    query_params = {
        "IndexName": "UserCollectionsGSI",
        "KeyConditionExpression": "GSI1_PK = :gsi1_pk AND begins_with(GSI1_SK, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":gsi1_pk": f"{USER_PK_PREFIX}{user_id}",
            ":sk_prefix": COLLECTION_PK_PREFIX,
        },
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key
    return table.query(**query_params)


@tracer.capture_method
def _query_all_collections(table, limit, start_key):
    """Query all collections using GSI5"""
    query_params = {
        "IndexName": "RecentlyModifiedGSI",
        "KeyConditionExpression": "GSI5_PK = :gsi5_pk",
        "ExpressionAttributeValues": {":gsi5_pk": COLLECTIONS_GSI5_PK},
        "ScanIndexForward": False,
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key
    return table.query(**query_params)


@tracer.capture_method
def _query_collections_by_type(table, collection_type_id, limit, start_key):
    """Query collections by type using GSI3"""
    query_params = {
        "IndexName": "CollectionTypeGSI",
        "KeyConditionExpression": "GSI3_PK = :gsi3_pk",
        "ExpressionAttributeValues": {":gsi3_pk": collection_type_id},
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key
    return table.query(**query_params)


@tracer.capture_method
def _query_child_collections(table, parent_id, limit, start_key):
    """Query child collections by parent ID"""
    query_params = {
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": f"{COLLECTION_PK_PREFIX}{parent_id}",
            ":sk_prefix": CHILD_SK_PREFIX,
        },
        "Limit": limit + 1,
    }
    if start_key:
        query_params["ExclusiveStartKey"] = start_key

    response = table.query(**query_params)

    # Get full collection data for each child
    child_items = []
    for child_ref in response.get("Items", []):
        child_id = child_ref.get("childCollectionId")
        if child_id:
            try:
                child_response = table.get_item(
                    Key={"PK": f"{COLLECTION_PK_PREFIX}{child_id}", "SK": METADATA_SK}
                )
                if "Item" in child_response:
                    child_items.append(child_response["Item"])
            except Exception as e:
                logger.warning(f"Failed to get child collection {child_id}: {e}")

    return {"Items": child_items, "LastEvaluatedKey": response.get("LastEvaluatedKey")}


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
