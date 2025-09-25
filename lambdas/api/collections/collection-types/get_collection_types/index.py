import base64
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-types-retrieval",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-types-retrieval")
metrics = Metrics(namespace="medialake", service="collection-types-retrieval")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")

# Get environment variables
TABLE_NAME = os.environ["COLLECTIONS_TABLE_NAME"]
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Constants
SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"


@tracer.capture_method
def parse_cursor(cursor_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse base64-encoded cursor back to dictionary

    Args:
        cursor_str: Base64-encoded cursor string

    Returns:
        Parsed cursor dictionary or None if invalid
    """
    if not cursor_str:
        return None

    try:
        decoded_bytes = base64.b64decode(cursor_str)
        cursor_data = json.loads(decoded_bytes.decode("utf-8"))
        logger.debug(
            {
                "message": "Cursor parsed successfully",
                "cursor_data": cursor_data,
                "operation": "parse_cursor",
            }
        )
        return cursor_data
    except Exception as e:
        logger.warning(
            {
                "message": "Failed to parse cursor",
                "cursor": cursor_str,
                "error": str(e),
                "operation": "parse_cursor",
            }
        )
        return None


@tracer.capture_method
def create_cursor(pk: str, sk: str, sort_field: Optional[str] = None) -> str:
    """
    Create base64-encoded cursor for pagination

    Args:
        pk: Primary key value
        sk: Sort key value
        sort_field: Optional sort field value

    Returns:
        Base64-encoded cursor string
    """
    cursor_data = {"pk": pk, "sk": sk, "timestamp": datetime.utcnow().isoformat() + "Z"}

    if sort_field:
        cursor_data["sort_field"] = sort_field

    cursor_json = json.dumps(cursor_data, default=str)
    cursor_b64 = base64.b64encode(cursor_json.encode("utf-8")).decode("utf-8")

    logger.debug(
        {
            "message": "Cursor created",
            "cursor_data": cursor_data,
            "operation": "create_cursor",
        }
    )

    return cursor_b64


@tracer.capture_method
def apply_sorting(items: list, sort_param: Optional[str]) -> list:
    """
    Apply sorting to collection types list

    Args:
        items: List of collection type items
        sort_param: Sort parameter (e.g., 'sortOrder', '-sortOrder', 'typeName', etc.)

    Returns:
        Sorted list of items
    """
    if not sort_param or not items:
        return items

    # Parse sort direction and field
    descending = sort_param.startswith("-")
    sort_field = sort_param[1:] if descending else sort_param

    logger.debug(
        {
            "message": "Applying sort to collection types",
            "sort_field": sort_field,
            "descending": descending,
            "item_count": len(items),
            "operation": "apply_sorting",
        }
    )

    # Define sorting key functions
    sort_key_map = {
        "sortOrder": lambda x: x.get("sortOrder", 0),
        "typeName": lambda x: x.get("typeName", "").lower(),
        "createdAt": lambda x: x.get("createdAt", ""),
    }

    sort_key_func = sort_key_map.get(sort_field, lambda x: x.get("createdAt", ""))

    try:
        sorted_items = sorted(items, key=sort_key_func, reverse=descending)
        logger.info(
            {
                "message": "Collection types sorted successfully",
                "sort_field": sort_field,
                "descending": descending,
                "sorted_count": len(sorted_items),
                "operation": "apply_sorting",
            }
        )
        return sorted_items
    except Exception as e:
        logger.error(
            {
                "message": "Failed to sort collection types",
                "sort_field": sort_field,
                "error": str(e),
                "operation": "apply_sorting",
            }
        )
        return items


@tracer.capture_method
def format_collection_type_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: Raw DynamoDB item

    Returns:
        Formatted collection type object
    """
    # Extract type ID from SK
    type_id = item["SK"].replace(COLLECTION_TYPE_SK_PREFIX, "")

    formatted_item = {
        "id": type_id,
        "typeName": item.get("typeName", ""),
        "description": item.get("description", ""),
        "allowedItemTypes": item.get("allowedItemTypes", []),
        "icon": item.get("icon", ""),
        "color": item.get("color", ""),
        "metadataSchema": item.get("metadataSchema", {}),
        "isActive": item.get("isActive", True),
        "sortOrder": item.get("sortOrder", 0),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }

    logger.debug(
        {
            "message": "Collection type item formatted",
            "type_id": type_id,
            "operation": "format_collection_type_item",
        }
    )

    return formatted_item


@app.get("/collection-types")
@tracer.capture_method
def list_collection_types():
    """Get list of collection types with cursor-based pagination"""
    try:
        # Parse query parameters
        cursor = app.current_event.get_query_string_value("cursor")
        limit = int(app.current_event.get_query_string_value("limit", DEFAULT_LIMIT))
        active_filter = app.current_event.get_query_string_value("filter[active]")
        sort_param = app.current_event.get_query_string_value("sort")

        # Validate limit
        limit = min(max(1, limit), MAX_LIMIT)

        logger.debug(
            {
                "message": "Processing collection types retrieval request",
                "cursor": cursor,
                "limit": limit,
                "active_filter": active_filter,
                "sort": sort_param,
                "operation": "list_collection_types",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Parse cursor for pagination
        start_key = None
        parsed_cursor = parse_cursor(cursor)
        if parsed_cursor:
            start_key = {"PK": parsed_cursor.get("pk"), "SK": parsed_cursor.get("sk")}

        # Scan for collection types (PK=SYSTEM, SK begins with COLLTYPE#)
        scan_params = {
            "FilterExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "ExpressionAttributeValues": {
                ":pk": SYSTEM_PK,
                ":sk_prefix": COLLECTION_TYPE_SK_PREFIX,
            },
            "Limit": limit + 1,  # Get one extra to check if there are more results
        }

        if start_key:
            scan_params["ExclusiveStartKey"] = start_key

        logger.info(
            {
                "message": "Scanning DynamoDB for collection types",
                "table_name": TABLE_NAME,
                "start_key": start_key,
                "limit": limit,
                "operation": "dynamodb_scan",
            }
        )

        response = table.scan(**scan_params)
        items = response.get("Items", [])

        logger.info(
            {
                "message": "Collection types retrieved from DynamoDB",
                "item_count": len(items),
                "has_more": len(items) > limit,
                "operation": "dynamodb_scan",
            }
        )

        # Check if we have more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]  # Remove the extra item

        # Apply active filter if specified
        if active_filter is not None:
            is_active = active_filter.lower() == "true"
            items = [item for item in items if item.get("isActive", True) == is_active]
            logger.info(
                {
                    "message": "Applied active filter to collection types",
                    "active_filter": is_active,
                    "filtered_count": len(items),
                    "operation": "apply_active_filter",
                }
            )

        # Format items for API response
        formatted_items = [format_collection_type_item(item) for item in items]

        # Apply sorting
        sorted_items = apply_sorting(formatted_items, sort_param)

        # Create pagination info
        pagination = {
            "has_next_page": has_more,
            "has_prev_page": cursor is not None,
            "limit": limit,
        }

        # Add next cursor if there are more results
        if has_more and sorted_items:
            last_item = items[-1]  # Use original DynamoDB item for cursor
            next_cursor = create_cursor(
                last_item["PK"], last_item["SK"], last_item.get("createdAt")
            )
            pagination["next_cursor"] = next_cursor

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionTypeRetrievals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="CollectionTypesReturned",
            unit=MetricUnit.Count,
            value=len(sorted_items),
        )

        # Create response
        response_data = {
            "success": True,
            "data": sorted_items,
            "pagination": pagination,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }

        logger.info(
            {
                "message": "Collection types retrieved successfully",
                "total_returned": len(sorted_items),
                "has_next_page": has_more,
                "operation": "list_collection_types",
            }
        )

        return {"statusCode": 200, "body": json.dumps(response_data)}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection types retrieval",
                "error_code": error_code,
                "error_message": error_message,
                "operation": "list_collection_types",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionTypeRetrievals", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "success": False,
                    "error": {"code": error_code, "message": error_message},
                    "meta": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "version": "v1",
                        "request_id": app.current_event.request_context.request_id,
                    },
                }
            ),
        }

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error during collection types retrieval",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "list_collection_types",
                "status": "failed",
            }
        )

        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

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
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "version": "v1",
                        "request_id": app.current_event.request_context.request_id,
                    },
                }
            ),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
