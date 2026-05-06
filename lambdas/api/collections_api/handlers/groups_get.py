"""GET /collections/groups - List collection groups with page-based pagination via OpenSearch."""

import math
import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError
from collection_groups_utils import format_collection_group_item
from collections_utils import create_error_response, create_success_response
from models import ListGroupsQueryParams
from user_auth import extract_user_context
from utils.collections_search import search_groups

logger = Logger(service="groups-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="groups-get")
metrics = Metrics(namespace="medialake", service="collection-groups")


def register_route(app):
    """Register GET /collections/groups route"""

    @app.get("/collections/groups")
    @tracer.capture_method
    def groups_get():
        """Get list of collection groups with page-based pagination via OpenSearch."""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required to list groups")

            # Parse and validate query parameters
            try:
                query_params_dict = {
                    "page": int(app.current_event.get_query_string_value("page", 1)),
                    "pageSize": int(
                        app.current_event.get_query_string_value("pageSize", 20)
                    ),
                }

                if sort_val := app.current_event.get_query_string_value("sort"):
                    query_params_dict["sort"] = sort_val
                if sort_dir := app.current_event.get_query_string_value(
                    "sortDirection"
                ):
                    query_params_dict["sortDirection"] = sort_dir
                if search_val := app.current_event.get_query_string_value("search"):
                    query_params_dict["search"] = search_val

                query_params = ListGroupsQueryParams(**query_params_dict)
            except (ValidationError, ValueError) as e:
                logger.warning(f"Query parameter validation error: {e}")
                raise BadRequestError(f"Invalid query parameters: {e}")

            logger.info(
                "Listing collection groups",
                extra={
                    "user_id": user_id,
                    "page": query_params.page,
                    "page_size": query_params.pageSize,
                    "search": query_params.search,
                },
            )

            # Query OpenSearch
            try:
                results, total_hits = search_groups(
                    user_id=user_id,
                    search_text=query_params.search,
                    page=query_params.page,
                    page_size=query_params.pageSize,
                    sort_field=query_params.sort or "name",
                    sort_direction=query_params.sortDirection or "asc",
                )
            except Exception as e:
                logger.error(
                    "OpenSearch groups listing failed", extra={"error": str(e)}
                )
                return create_error_response(
                    error_code="ServiceUnavailable",
                    error_message="Group listing service is temporarily unavailable",
                    status_code=503,
                    request_id=app.current_event.request_context.request_id,
                )

            # Format items
            formatted_items = [
                format_collection_group_item(item, user_context) for item in results
            ]

            # Compute pagination metadata
            page = query_params.page
            page_size = query_params.pageSize
            total_results = total_hits
            total_pages = math.ceil(total_results / page_size) if page_size > 0 else 0

            pagination = {
                "page": page,
                "pageSize": page_size,
                "totalResults": total_results,
                "totalPages": total_pages,
                "hasNextPage": page < total_pages,
                "hasPrevPage": page > 1,
            }

            metrics.add_metric(
                name="SuccessfulGroupRetrievals",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="GroupsReturned",
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
            logger.exception("Unexpected error listing groups", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
