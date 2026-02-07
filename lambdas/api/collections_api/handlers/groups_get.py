"""GET /collections/groups - List collection groups with pagination."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from collection_groups_utils import (
    GROUPS_GSI2_PK,
    format_collection_group_item,
)
from collections_utils import create_error_response, create_success_response
from user_auth import extract_user_context

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
groups_table = dynamodb.Table(table_name)

logger = Logger(service="groups-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="groups-get")
metrics = Metrics(namespace="medialake", service="collection-groups")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def register_route(app):
    """Register GET /collections/groups route"""

    @app.get("/collections/groups")
    @tracer.capture_method
    def groups_get():
        """Get list of collection groups with pagination and search"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required to list groups")

            # Parse query parameters
            limit = int(
                app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
            )
            limit = min(limit, MAX_LIMIT)

            search = app.current_event.get_query_string_value("search")
            cursor = app.current_event.get_query_string_value("cursor")

            logger.info(
                "Listing collection groups",
                extra={"user_id": user_id, "limit": limit, "search": search},
            )

            # Query all groups using GSI2 (all groups index)
            query_params = {
                "IndexName": "ItemCollectionsGSI",  # Reusing GSI2
                "KeyConditionExpression": "GSI2_PK = :groups_pk",
                "ExpressionAttributeValues": {":groups_pk": GROUPS_GSI2_PK},
                "Limit": limit + 1,
                "ScanIndexForward": False,  # Most recent first
            }

            # Add cursor for pagination
            if cursor:
                try:
                    import base64
                    import json

                    decoded = json.loads(base64.b64decode(cursor))
                    query_params["ExclusiveStartKey"] = {
                        "PK": decoded["pk"],
                        "SK": decoded["sk"],
                        "GSI2_PK": decoded.get("gsi2_pk", GROUPS_GSI2_PK),
                        "GSI2_SK": decoded.get("gsi2_sk"),
                    }
                except Exception as e:
                    logger.warning(f"Invalid cursor: {e}")

            response = groups_table.query(**query_params)
            items = response.get("Items", [])

            # Apply search filter if provided
            if search:
                search_lower = search.lower()
                items = [
                    item
                    for item in items
                    if search_lower in item.get("name", "").lower()
                    or search_lower in item.get("description", "").lower()
                ]

            # Check if there are more results
            has_more = len(items) > limit
            if has_more:
                items = items[:limit]

            # Format items
            formatted_items = [
                format_collection_group_item(item, user_context) for item in items
            ]

            # Create pagination
            pagination = {
                "has_next_page": has_more,
                "has_prev_page": cursor is not None,
                "limit": limit,
            }

            if has_more and items:
                import base64
                import json

                last_item = items[-1]
                next_cursor = base64.b64encode(
                    json.dumps(
                        {
                            "pk": last_item["PK"],
                            "sk": last_item["SK"],
                            "gsi2_pk": GROUPS_GSI2_PK,
                            "gsi2_sk": last_item.get("GSI2_SK"),
                        }
                    ).encode()
                ).decode()
                pagination["next_cursor"] = next_cursor

            metrics.add_metric(
                name="SuccessfulGroupRetrievals", unit=MetricUnit.Count, value=1
            )
            metrics.add_metric(
                name="GroupsReturned", unit=MetricUnit.Count, value=len(formatted_items)
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
