"""GET /collection-types - List collection types."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from db_models import CollectionTypeModel
from pynamodb.exceptions import QueryError
from utils.formatting_utils import format_collection_type
from utils.pagination_utils import apply_sorting, create_cursor, parse_cursor

logger = Logger(
    service="collection-types-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collection-types-get")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def register_route(app):
    """Register GET /collection-types route"""

    @app.get("/collection-types")
    @tracer.capture_method
    def collection_types_get():
        """Get list of collection types with cursor-based pagination"""
        try:
            cursor = app.current_event.get_query_string_value("cursor")
            limit = int(
                app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
            )
            active_filter = app.current_event.get_query_string_value("filter[active]")
            sort_param = app.current_event.get_query_string_value("sort")

            limit = min(max(1, limit), MAX_LIMIT)

            logger.info(
                "Processing collection types retrieval request",
                extra={
                    "cursor": cursor,
                    "limit": limit,
                    "active_filter": active_filter,
                    "sort": sort_param,
                },
            )

            # Parse cursor for pagination
            start_key = None
            parsed_cursor = parse_cursor(cursor)
            if parsed_cursor:
                start_key = parsed_cursor.get("pk"), parsed_cursor.get("sk")

            # Query for collection types using PynamoDB
            items = []
            try:
                query_kwargs = {}
                if start_key:
                    query_kwargs["last_evaluated_key"] = {
                        "PK": start_key[0],
                        "SK": start_key[1],
                    }

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
                            "name": item.name,
                            "description": (
                                item.description if item.description else None
                            ),
                            "isActive": item.isActive,
                            "allowedItemTypes": (
                                list(item.allowedItemTypes)
                                if item.allowedItemTypes
                                else []
                            ),
                            "schema": dict(item.schema) if item.schema else None,
                            "createdAt": item.createdAt,
                            "updatedAt": item.updatedAt,
                        }
                    )

            except QueryError as e:
                logger.error("PynamoDB query error", exc_info=e)
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "QUERY_ERROR",
                                "message": "Error querying collection types",
                            },
                            "meta": {
                                "request_id": app.current_event.request_context.request_id
                            },
                        }
                    ),
                }

            logger.info(f"Retrieved {len(items)} collection types from DynamoDB")

            # Apply active filter if specified
            if active_filter is not None:
                is_active = active_filter.lower() in ["true", "1", "yes"]
                items = [item for item in items if item.get("isActive") == is_active]

            # Check if there are more results
            has_more = len(items) > limit
            if has_more:
                items = items[:limit]

            # Format items
            formatted_items = [format_collection_type(item) for item in items]

            # Apply sorting if specified
            if sort_param:
                formatted_items = apply_sorting(formatted_items, sort_param)

            # Create pagination info
            pagination = {
                "hasMore": has_more,
                "limit": limit,
            }

            if has_more and items:
                last_item = items[-1]
                next_cursor = create_cursor(last_item["PK"], last_item["SK"])
                pagination["nextCursor"] = next_cursor

            logger.info(f"Returning {len(formatted_items)} collection types")
            metrics.add_metric(
                name="SuccessfulCollectionTypeRetrievals",
                unit=MetricUnit.Count,
                value=1,
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": formatted_items,
                        "pagination": pagination,
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except ClientError as e:
            logger.error("DynamoDB error", exc_info=e)
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": e.response["Error"]["Code"],
                            "message": e.response["Error"]["Message"],
                        },
                        "meta": {
                            "request_id": app.current_event.request_context.request_id
                        },
                    }
                ),
            }

        except Exception as e:
            logger.exception("Unexpected error", exc_info=e)
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "InternalServerError",
                            "message": "An unexpected error occurred",
                        },
                        "meta": {
                            "request_id": app.current_event.request_context.request_id
                        },
                    }
                ),
            }
