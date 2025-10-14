"""GET /settings/collection-types - List collection types."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionTypeModel
from pynamodb.exceptions import QueryError
from utils.response_utils import (
    create_error_response,
    create_pagination_response,
    create_success_response,
    decode_cursor,
    encode_cursor,
)

logger = Logger(
    service="settings-collection-types-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="settings-collection-types-get")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def register_route(app):
    """Register GET /settings/collection-types route"""

    @app.get("/settings/collection-types")
    @tracer.capture_method
    def settings_collection_types_get():
        """Get list of collection types with cursor-based pagination"""
        request_id = app.current_event.request_context.request_id

        try:
            cursor = app.current_event.get_query_string_value("cursor")
            limit_str = app.current_event.get_query_string_value("limit") or str(
                DEFAULT_LIMIT
            )
            active_filter = app.current_event.get_query_string_value("filter[active]")

            try:
                limit = int(limit_str)
            except ValueError:
                raise BadRequestError("Limit must be a valid integer")

            limit = min(max(1, limit), MAX_LIMIT)

            logger.info(
                "Processing collection types retrieval request",
                extra={
                    "cursor": cursor,
                    "limit": limit,
                    "active_filter": active_filter,
                },
            )

            # Parse cursor for pagination
            parsed_cursor = decode_cursor(cursor) if cursor else None

            # Query for collection types using PynamoDB
            items = []
            last_evaluated_key = None

            try:
                query_kwargs = {}

                if parsed_cursor:
                    query_kwargs["last_evaluated_key"] = parsed_cursor

                results = CollectionTypeModel.query(
                    SYSTEM_PK,
                    CollectionTypeModel.SK.startswith(COLLECTION_TYPE_SK_PREFIX),
                    limit=limit + 1,
                    **query_kwargs,
                )

                for item in results:
                    items.append(
                        {
                            "PK": item.PK,
                            "SK": item.SK,
                            "id": item.SK.replace(COLLECTION_TYPE_SK_PREFIX, ""),
                            "name": item.name,
                            "description": (
                                item.description if item.description else None
                            ),
                            "color": (
                                item.color if hasattr(item, "color") else "#1976d2"
                            ),
                            "icon": item.icon if hasattr(item, "icon") else "Folder",
                            "isActive": item.isActive,
                            "isSystem": (
                                item.isSystem if hasattr(item, "isSystem") else False
                            ),
                            "createdAt": item.createdAt,
                            "updatedAt": item.updatedAt,
                        }
                    )
                    last_evaluated_key = {"PK": item.PK, "SK": item.SK}

            except QueryError as e:
                logger.error("PynamoDB query error", exc_info=e)
                return create_error_response(
                    code="QUERY_ERROR",
                    message="Error querying collection types",
                    status_code=500,
                    request_id=request_id,
                )

            logger.info(f"Retrieved {len(items)} collection types from DynamoDB")

            # Apply active filter if specified
            if active_filter is not None:
                is_active = active_filter.lower() in ["true", "1", "yes"]
                items = [item for item in items if item.get("isActive") == is_active]

            # Check if there are more results
            has_next = len(items) > limit
            if has_next:
                items = items[:limit]
                # Set last_evaluated_key to the last item we're returning
                last_evaluated_key = {"PK": items[-1]["PK"], "SK": items[-1]["SK"]}
            else:
                last_evaluated_key = None

            # Format items (remove PK/SK from response)
            formatted_items = []
            for item in items:
                formatted_item = {
                    k: v for k, v in item.items() if k not in ["PK", "SK"]
                }
                formatted_items.append(formatted_item)

            # Create pagination response following API standards
            next_cursor = (
                encode_cursor(last_evaluated_key)
                if last_evaluated_key and has_next
                else None
            )

            pagination = create_pagination_response(
                has_next=has_next,
                has_prev=cursor is not None,
                limit=limit,
                next_cursor=next_cursor,
                prev_cursor=None,  # Prev cursor not implemented for now
            )

            logger.info(f"Returning {len(formatted_items)} collection types")
            metrics.add_metric(
                name="SuccessfulCollectionTypeRetrievals",
                unit=MetricUnit.Count,
                value=1,
            )

            return create_success_response(
                data=formatted_items,
                pagination=pagination,
                status_code=200,
                request_id=request_id,
            )

        except BadRequestError:
            raise

        except Exception as e:
            logger.exception("Unexpected error", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
