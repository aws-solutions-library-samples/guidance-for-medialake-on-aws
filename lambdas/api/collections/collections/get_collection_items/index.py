import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    apply_sorting,
    create_cursor,
    parse_cursor,
    validate_collection_access,
)

# Import centralized utilities
from user_auth import extract_user_context

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-items-retrieval",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-items-retrieval")
metrics = Metrics(namespace="medialake", service="collection-items-retrieval")

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
COLLECTION_PK_PREFIX = "COLL#"
ITEM_SK_PREFIX = "ITEM#"
METADATA_SK = "METADATA"
VALID_ITEM_TYPES = ["asset", "workflow", "collection"]
VALID_SORT_OPTIONS = ["sortOrder", "-sortOrder", "addedAt", "-addedAt"]


@tracer.capture_method
def extract_user_context(event: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Extract user information from JWT token in event context

    Args:
        event: Lambda event

    Returns:
        Dictionary with user_id and username
    """
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer.get("claims", {})

        user_id = claims.get("sub")
        username = claims.get("cognito:username")

        logger.debug(
            {
                "message": "User context extracted",
                "user_id": user_id,
                "username": username,
                "operation": "extract_user_context",
            }
        )

        return {"user_id": user_id, "username": username}
    except Exception as e:
        logger.warning(
            {
                "message": "Failed to extract user context",
                "error": str(e),
                "operation": "extract_user_context",
            }
        )
        return {"user_id": None, "username": None}


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
def create_cursor(pk: str, sk: str) -> str:
    """
    Create base64-encoded cursor for pagination

    Args:
        pk: Primary key value
        sk: Sort key value

    Returns:
        Base64-encoded cursor string
    """
    cursor_data = {"pk": pk, "sk": sk, "timestamp": datetime.utcnow().isoformat() + "Z"}

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
def format_collection_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: Raw DynamoDB item

    Returns:
        Formatted collection item object
    """
    # Extract item ID from SK
    item_id = item["SK"].replace(ITEM_SK_PREFIX, "")

    formatted_item = {
        "id": f"item_{item_id}",  # Generate item record ID
        "itemType": item.get("itemType", "").lower(),
        "itemId": item_id,
        "sortOrder": item.get("sortOrder", 0),
        "metadata": item.get("metadata", {}),
        "addedAt": item.get("addedAt", ""),
        "addedBy": item.get("addedBy", ""),
    }

    logger.debug(
        {
            "message": "Collection item formatted",
            "item_id": item_id,
            "operation": "format_collection_item",
        }
    )

    return formatted_item


@tracer.capture_method
def apply_sorting(
    items: List[Dict[str, Any]], sort_param: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Apply sorting to collection items list

    Args:
        items: List of collection items
        sort_param: Sort parameter (e.g., 'sortOrder', '-sortOrder', 'addedAt', '-addedAt')

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
            "message": "Applying sort to collection items",
            "sort_field": sort_field,
            "descending": descending,
            "item_count": len(items),
            "operation": "apply_sorting",
        }
    )

    # Define sorting key functions
    sort_key_map = {
        "sortOrder": lambda x: x.get("sortOrder", 0),
        "addedAt": lambda x: x.get("addedAt", ""),
    }

    sort_key_func = sort_key_map.get(sort_field, lambda x: x.get("sortOrder", 0))

    try:
        sorted_items = sorted(items, key=sort_key_func, reverse=descending)
        logger.info(
            {
                "message": "Collection items sorted successfully",
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
                "message": "Failed to sort collection items",
                "sort_field": sort_field,
                "error": str(e),
                "operation": "apply_sorting",
            }
        )
        return items


@tracer.capture_method
def validate_collection_access(
    table, collection_id: str, user_id: Optional[str]
) -> bool:
    """
    Validate that the collection exists and user has access

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to validate
        user_id: User ID requesting access

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if collection exists
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        item = response.get("Item")
        if not item:
            logger.warning(
                {
                    "message": "Collection not found",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return False

        # Check if collection is active
        if item.get("status") != "ACTIVE":
            logger.warning(
                {
                    "message": "Collection is not active",
                    "collection_id": collection_id,
                    "status": item.get("status"),
                    "operation": "validate_collection_access",
                }
            )
            return False

        # Check if user has access (owner, public, or has permissions)
        if item.get("isPublic", False):
            logger.debug(
                {
                    "message": "Collection access granted - public collection",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return True

        if user_id and item.get("ownerId") == user_id:
            logger.debug(
                {
                    "message": "Collection access granted - user is owner",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return True

        # TODO: Check user permissions for non-owned, non-public collections
        # For now, allow access for authenticated users (simplified logic)
        if user_id:
            logger.debug(
                {
                    "message": "Collection access granted - authenticated user",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return True

        logger.warning(
            {
                "message": "Collection access denied - no permission",
                "collection_id": collection_id,
                "operation": "validate_collection_access",
            }
        )
        return False

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate collection access",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "validate_collection_access",
            }
        )
        return False


@app.get("/collections/<collection_id>/items")
@tracer.capture_method
def list_collection_items(collection_id: str):
    """Get list of items in a collection with filtering and pagination"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        # Parse query parameters
        cursor = app.current_event.get_query_string_value("cursor")
        limit = int(app.current_event.get_query_string_value("limit", DEFAULT_LIMIT))
        type_filter = app.current_event.get_query_string_value("filter[type]")
        sort_param = app.current_event.get_query_string_value("sort")

        # Validate limit
        limit = min(max(1, limit), MAX_LIMIT)

        # Validate sort parameter
        if sort_param and sort_param not in VALID_SORT_OPTIONS:
            logger.warning(
                {
                    "message": "Invalid sort parameter",
                    "sort_param": sort_param,
                    "valid_options": VALID_SORT_OPTIONS,
                    "operation": "list_collection_items",
                }
            )
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_SORT_PARAMETER",
                            "message": f"Invalid sort parameter. Valid options: {', '.join(VALID_SORT_OPTIONS)}",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Validate type filter
        if type_filter and type_filter not in VALID_ITEM_TYPES:
            logger.warning(
                {
                    "message": "Invalid type filter",
                    "type_filter": type_filter,
                    "valid_types": VALID_ITEM_TYPES,
                    "operation": "list_collection_items",
                }
            )
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_TYPE_FILTER",
                            "message": f"Invalid type filter. Valid options: {', '.join(VALID_ITEM_TYPES)}",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        logger.debug(
            {
                "message": "Processing collection items retrieval request",
                "collection_id": collection_id,
                "cursor": cursor,
                "limit": limit,
                "type_filter": type_filter,
                "sort": sort_param,
                "user_id": user_id,
                "operation": "list_collection_items",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Validate collection access
        if not validate_collection_access(table, collection_id, user_id):
            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "COLLECTION_NOT_FOUND",
                            "message": "Collection not found or access denied",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Parse cursor for pagination
        start_key = None
        parsed_cursor = parse_cursor(cursor)
        if parsed_cursor:
            start_key = {"PK": parsed_cursor.get("pk"), "SK": parsed_cursor.get("sk")}

        # Build query parameters
        query_params = {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "ExpressionAttributeValues": {
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": ITEM_SK_PREFIX,
            },
            "Limit": limit + 1,  # Get one extra to determine if there are more results
        }

        # Add type filter if specified
        if type_filter:
            query_params["FilterExpression"] = "itemType = :item_type"
            query_params["ExpressionAttributeValues"][
                ":item_type"
            ] = type_filter.upper()

        if start_key:
            query_params["ExclusiveStartKey"] = start_key

        # Execute query
        response = table.query(**query_params)
        items = response.get("Items", [])

        logger.info(
            {
                "message": "Collection items retrieved from DynamoDB",
                "collection_id": collection_id,
                "item_count": len(items),
                "has_more": len(items) > limit,
                "operation": "list_collection_items",
            }
        )

        # Check if we have more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]  # Remove the extra item

        # Format items for API response
        formatted_items = [format_collection_item(item) for item in items]

        # Apply sorting
        sorted_items = apply_sorting(formatted_items, sort_param)

        # Create pagination info
        pagination = {
            "has_next_page": has_more,
            "has_prev_page": cursor is not None,
            "limit": limit,
        }

        # Add next cursor if there are more results
        if has_more and items:
            last_item = items[-1]  # Use original DynamoDB item for cursor
            next_cursor = create_cursor(last_item["PK"], last_item["SK"])
            pagination["next_cursor"] = next_cursor

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionItemRetrievals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="CollectionItemsReturned",
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
                "message": "Collection items retrieved successfully",
                "collection_id": collection_id,
                "total_returned": len(sorted_items),
                "has_next_page": has_more,
                "operation": "list_collection_items",
            }
        )

        return {"statusCode": 200, "body": json.dumps(response_data)}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection items retrieval",
                "collection_id": collection_id,
                "error_code": error_code,
                "error_message": error_message,
                "operation": "list_collection_items",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionItemRetrievals", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection items retrieval",
                "collection_id": collection_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "list_collection_items",
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
