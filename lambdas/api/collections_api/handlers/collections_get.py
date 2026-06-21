"""GET /collections - List collections with page-based pagination via OpenSearch."""

import math
import os
from concurrent.futures import ThreadPoolExecutor

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError
from collections_utils import (
    COLLECTION_PK_PREFIX,
    apply_field_selection,
    create_error_response,
    create_success_response,
    format_collection_item,
    get_collection_item_count,
)
from models import ListCollectionsQueryParams
from user_auth import extract_user_context
from utils.collections_search import search_collections
from utils.metadata_filter_parser import parse_metadata_filter_params

logger = Logger(service="collections-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-get")
metrics = Metrics(namespace="medialake", service="collections")

# DynamoDB table for dynamic item-count queries. itemCount stored on the
# METADATA row (and mirrored into OpenSearch) is deprecated and drifts, so the
# list endpoint recomputes counts the same way the detail endpoint does.
_dynamodb = boto3.resource("dynamodb")
_collections_table = _dynamodb.Table(
    os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
)

# Upper bound on how many collections we'll recompute counts for in a single
# request. Realistic UI page sizes are <= 100; this guards against pathological
# large pages (pageSize can be up to 5000) causing a flood of COUNT queries.
_MAX_DYNAMIC_COUNT_ITEMS = int(os.environ.get("MAX_DYNAMIC_COUNT_ITEMS", "200"))


@tracer.capture_method
def _apply_dynamic_item_counts(formatted_items: list) -> None:
    """Override each item's stale stored itemCount with a live DynamoDB count.

    Counts are computed in parallel (bounded) for the page of results. On a
    per-item error (count returns -1) the existing stored value is kept so the
    listing never surfaces -1 on a card. Mutates ``formatted_items`` in place.
    """
    if not formatted_items:
        return

    if len(formatted_items) > _MAX_DYNAMIC_COUNT_ITEMS:
        logger.info(
            "Skipping dynamic item-count recompute for large page",
            extra={
                "item_count": len(formatted_items),
                "max": _MAX_DYNAMIC_COUNT_ITEMS,
            },
        )
        return

    def _count_for(item: dict) -> tuple[dict, int]:
        pk = f"{COLLECTION_PK_PREFIX}{item.get('id', '')}"
        return item, get_collection_item_count(_collections_table, pk)

    max_workers = min(16, len(formatted_items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for item, count in executor.map(_count_for, formatted_items):
            # -1 signals a query error — keep the stored value as a fallback.
            if count >= 0:
                item["itemCount"] = count


def register_route(app):
    """Register GET /collections route"""

    @app.get("/collections")
    @tracer.capture_method
    def collections_get():
        """Get list of collections with page-based pagination via OpenSearch."""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            # Parse and validate query parameters using Pydantic
            try:
                try:
                    page = int(app.current_event.get_query_string_value("page", 1))
                    page_size = int(
                        app.current_event.get_query_string_value("pageSize", 50)
                    )
                except (ValueError, TypeError):
                    raise BadRequestError("page and pageSize must be integers")

                query_params_dict = {
                    "page": page,
                    "pageSize": page_size,
                }

                if sort_val := app.current_event.get_query_string_value("sort"):
                    query_params_dict["sort"] = sort_val
                if sort_dir := app.current_event.get_query_string_value(
                    "sortDirection"
                ):
                    query_params_dict["sortDirection"] = sort_dir
                if include_children := app.current_event.get_query_string_value(
                    "includeChildren"
                ):
                    query_params_dict["includeChildren"] = include_children.lower() in (
                        "true",
                        "1",
                        "yes",
                    )
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
                if fields_val := app.current_event.get_query_string_value("fields"):
                    query_params_dict["fields"] = fields_val

                # Extract metadata filters from filter[metadata.KEY]=VALUE params
                all_params = app.current_event.query_string_parameters or {}
                metadata_filters = parse_metadata_filter_params(all_params)

                if metadata_filters:
                    query_params_dict["metadata_filters"] = metadata_filters

                # Multi-valued filter[tag] — API Gateway REST collapses repeated
                # query params to the last value in queryStringParameters, so we
                # read multiValueQueryStringParameters for the full list.
                multi_value_params = (
                    app.current_event.multi_value_query_string_parameters or {}
                )
                tag_values = multi_value_params.get("filter[tag]") or []
                # Fall back to single-value form so a client sending one tag still works
                if not tag_values:
                    single_tag = app.current_event.get_query_string_value("filter[tag]")
                    if single_tag:
                        tag_values = [single_tag]
                # Split comma-separated single values too so clients can shortcut
                flattened_tags: list = []
                for raw in tag_values:
                    flattened_tags.extend(
                        [v.strip() for v in raw.split(",") if v.strip()]
                    )
                if flattened_tags:
                    query_params_dict["filter_tag"] = flattened_tags

                # Multi-valued filter[visibility] — same multi-value handling as tags
                visibility_values = multi_value_params.get("filter[visibility]") or []
                if not visibility_values:
                    single_vis = app.current_event.get_query_string_value(
                        "filter[visibility]"
                    )
                    if single_vis:
                        visibility_values = [single_vis]
                flattened_vis: list = []
                for raw in visibility_values:
                    flattened_vis.extend(
                        [v.strip() for v in raw.split(",") if v.strip()]
                    )
                if flattened_vis:
                    query_params_dict["filter_visibility"] = flattened_vis

                if updated_within := app.current_event.get_query_string_value(
                    "filter[updatedWithin]"
                ):
                    query_params_dict["filter_updated_within"] = updated_within

                query_params = ListCollectionsQueryParams(**query_params_dict)
            except ValidationError as e:
                logger.warning(f"Query parameter validation error: {e}")
                raise BadRequestError(f"Invalid query parameters: {e}")

            logger.info(
                "Listing collections",
                extra={
                    "user_id": user_id,
                    "page": query_params.page,
                    "page_size": query_params.pageSize,
                    "include_children": query_params.includeChildren,
                },
            )

            # Determine parent_id_filter
            if query_params.includeChildren:
                parent_id_filter = "__all__"
            elif query_params.filter_parentId:
                parent_id_filter = query_params.filter_parentId
            else:
                parent_id_filter = "__root__"

            # Pre-fetch group IDs once if needed
            collection_ids_from_groups = None
            if query_params.groupIds:
                import boto3
                from collection_groups_utils import get_collection_ids_by_group_ids

                dynamodb = boto3.resource("dynamodb")
                table_name = os.environ.get(
                    "COLLECTIONS_TABLE_NAME", "collections_table_dev"
                )
                collections_table = dynamodb.Table(table_name)

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

            # --- OpenSearch only path — no DynamoDB fallback ---
            try:
                results, total_hits = search_collections(
                    user_id=user_id,
                    search_text=query_params.filter_search,
                    status_filter=(
                        query_params.filter_status.value
                        if query_params.filter_status
                        else None
                    ),
                    collection_type_filter=query_params.filter_type,
                    owner_filter=query_params.filter_ownerId,
                    parent_id_filter=parent_id_filter,
                    metadata_filters=query_params.metadata_filters,
                    tag_filter=query_params.filter_tag,
                    visibility_filter=query_params.filter_visibility,
                    updated_within=query_params.filter_updated_within,
                    collection_ids_filter=collection_ids_from_groups,
                    page=query_params.page,
                    page_size=query_params.pageSize,
                    sort_field=query_params.sort or "name",
                    sort_direction=query_params.sortDirection or "asc",
                )
            except Exception as e:
                logger.error("OpenSearch listing failed", extra={"error": str(e)})
                return create_error_response(
                    error_code="ServiceUnavailable",
                    error_message="Collection listing service is temporarily unavailable",
                    status_code=503,
                    request_id=app.current_event.request_context.request_id,
                )

            # Format items
            formatted_items = [
                format_collection_item(item, user_context) for item in results
            ]

            # Replace stale stored itemCount (from OpenSearch) with live DynamoDB
            # counts so the list matches the detail view when items are added/removed.
            _apply_dynamic_item_counts(formatted_items)

            # Apply field selection
            if query_params.fields:
                formatted_items = [
                    apply_field_selection(item, query_params.fields)
                    for item in formatted_items
                ]

            # Compute pagination metadata
            page = query_params.page
            page_size = query_params.pageSize
            total_results = total_hits
            total_pages = math.ceil(total_results / page_size) if page_size > 0 else 0
            has_next_page = page < total_pages
            has_prev_page = page > 1

            pagination = {
                "page": page,
                "pageSize": page_size,
                "totalResults": total_results,
                "totalPages": total_pages,
                "hasNextPage": has_next_page,
                "hasPrevPage": has_prev_page,
            }

            metrics.add_metric(
                name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
            )
            metrics.add_metric(
                name="CollectionsReturned",
                unit=MetricUnit.Count,
                value=len(formatted_items),
            )

            return create_success_response(
                data=formatted_items,
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
