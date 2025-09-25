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
    service="shared-collections-retrieval",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="shared-collections-retrieval")
metrics = Metrics(namespace="medialake", service="shared-collections-retrieval")

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
METADATA_SK = "METADATA"
PERM_SK_PREFIX = "PERM#"
USER_PK_PREFIX = "USER#"
VALID_ROLES = ["viewer", "editor", "admin"]


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
def create_cursor(
    pk: str, sk: str, gsi_pk: Optional[str] = None, gsi_sk: Optional[str] = None
) -> str:
    """
    Create base64-encoded cursor for pagination

    Args:
        pk: Primary key value
        sk: Sort key value
        gsi_pk: Optional GSI partition key
        gsi_sk: Optional GSI sort key

    Returns:
        Base64-encoded cursor string
    """
    cursor_data = {"pk": pk, "sk": sk, "timestamp": datetime.utcnow().isoformat() + "Z"}

    if gsi_pk:
        cursor_data["gsi1_pk"] = gsi_pk
    if gsi_sk:
        cursor_data["gsi1_sk"] = gsi_sk

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
def get_user_permission(table, collection_id: str, user_id: str) -> Optional[str]:
    """
    Get user's permission role for a collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        user_id: User ID

    Returns:
        User's role or None if no explicit permission
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{PERM_SK_PREFIX}{user_id}",
            }
        )

        if "Item" in response:
            return response["Item"].get("role", "viewer")

        return None

    except ClientError as e:
        logger.error(
            {
                "message": "Error getting user permission",
                "collection_id": collection_id,
                "user_id": user_id,
                "error": str(e),
                "operation": "get_user_permission",
            }
        )
        return None


@tracer.capture_method
def format_shared_collection_item(
    item: Dict[str, Any], user_id: str, user_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format DynamoDB collection item to API response format for shared collections

    Args:
        item: Raw DynamoDB item
        user_id: User ID for context
        user_role: User's role in the collection

    Returns:
        Formatted collection object
    """
    # Extract collection ID from PK
    collection_id = item["PK"].replace(COLLECTION_PK_PREFIX, "")

    formatted_item = {
        "id": collection_id,
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "collectionTypeId": item.get("collectionTypeId", ""),
        "parentId": item.get("parentId"),
        "ownerId": item.get("ownerId", ""),
        "metadata": item.get("customMetadata", {}),
        "tags": item.get("tags", {}),
        "status": item.get("status", "ACTIVE"),
        "itemCount": item.get("itemCount", 0),
        "childCollectionCount": item.get("childCollectionCount", 0),
        "isPublic": item.get("isPublic", False),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }

    # Add user-specific fields
    formatted_item["isFavorite"] = False  # TODO: Query user collection relationship
    formatted_item["userRole"] = user_role or "viewer"

    # Add TTL if present
    if item.get("expiresAt"):
        formatted_item["expiresAt"] = item["expiresAt"]

    logger.debug(
        {
            "message": "Shared collection item formatted",
            "collection_id": collection_id,
            "user_role": user_role,
            "operation": "format_shared_collection_item",
        }
    )

    return formatted_item


@tracer.capture_method
def query_shared_collections(
    table,
    user_id: str,
    limit: int,
    start_key: Optional[Dict],
    role_filter: Optional[str] = None,
) -> Dict:
    """
    Query collections shared with user using a scan approach since we need to find all collections
    where the user has permissions but is not the owner

    Args:
        table: DynamoDB table resource
        user_id: User ID
        limit: Query limit
        start_key: Pagination start key
        role_filter: Optional role filter

    Returns:
        Query response with shared collections
    """
    shared_collections = []
    processed_count = 0

    try:
        # Scan for permissions where the user is the target
        scan_params = {
            "FilterExpression": "begins_with(SK, :perm_prefix) AND targetId = :user_id",
            "ExpressionAttributeValues": {
                ":perm_prefix": PERM_SK_PREFIX,
                ":user_id": user_id,
            },
            "Limit": limit * 5,  # Get more items to account for filtering
        }

        if start_key:
            scan_params["ExclusiveStartKey"] = start_key

        response = table.scan(**scan_params)
        permission_items = response.get("Items", [])

        logger.debug(
            {
                "message": "Permission items found",
                "count": len(permission_items),
                "operation": "query_shared_collections",
            }
        )

        # For each permission, get the collection metadata
        for perm_item in permission_items:
            if len(shared_collections) >= limit:
                break

            collection_id = perm_item["PK"].replace(COLLECTION_PK_PREFIX, "")
            user_role = perm_item.get("role", "viewer")

            # Apply role filter if specified
            if role_filter and user_role != role_filter:
                continue

            # Get collection metadata
            try:
                coll_response = table.get_item(
                    Key={
                        "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                        "SK": METADATA_SK,
                    }
                )

                if "Item" in coll_response:
                    collection_item = coll_response["Item"]

                    # Skip if user is the owner (this is not a "shared" collection for them)
                    if collection_item.get("ownerId") == user_id:
                        continue

                    # Skip if collection is deleted
                    if collection_item.get("status") == "DELETED":
                        continue

                    formatted_collection = format_shared_collection_item(
                        collection_item, user_id, user_role
                    )
                    shared_collections.append(formatted_collection)

            except ClientError as e:
                logger.warning(
                    {
                        "message": "Failed to get collection metadata",
                        "collection_id": collection_id,
                        "error": str(e),
                        "operation": "query_shared_collections",
                    }
                )
                continue

            processed_count += 1

        # Construct response similar to DynamoDB query response
        result = {
            "Items": shared_collections,
            "Count": len(shared_collections),
            "ScannedCount": processed_count,
        }

        # Add LastEvaluatedKey if there might be more results
        if response.get("LastEvaluatedKey") and len(permission_items) >= limit * 5:
            result["LastEvaluatedKey"] = response["LastEvaluatedKey"]

        return result

    except ClientError as e:
        logger.error(
            {
                "message": "Error querying shared collections",
                "user_id": user_id,
                "error": str(e),
                "operation": "query_shared_collections",
            }
        )
        return {"Items": [], "Count": 0, "ScannedCount": 0}


@app.get("/collections/shared-with-me")
@tracer.capture_method
def get_shared_collections():
    """Get list of collections shared with current user"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Shared collections retrieval attempted without valid user context",
                    "operation": "get_shared_collections",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to view shared collections",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Parse query parameters
        cursor = app.current_event.get_query_string_value("cursor")
        limit = int(app.current_event.get_query_string_value("limit", DEFAULT_LIMIT))
        role_filter = app.current_event.get_query_string_value("filter[role]")

        # Validate limit
        limit = min(max(1, limit), MAX_LIMIT)

        # Validate role filter
        if role_filter and role_filter not in VALID_ROLES:
            logger.warning(
                {
                    "message": "Invalid role filter specified",
                    "role_filter": role_filter,
                    "valid_roles": VALID_ROLES,
                    "operation": "get_shared_collections",
                }
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_FILTER",
                            "message": f"Role filter must be one of: {', '.join(VALID_ROLES)}",
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
                "message": "Processing shared collections retrieval request",
                "cursor": cursor,
                "limit": limit,
                "role_filter": role_filter,
                "user_id": user_id,
                "operation": "get_shared_collections",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Parse cursor for pagination
        start_key = None
        parsed_cursor = parse_cursor(cursor)
        if parsed_cursor:
            start_key = {"PK": parsed_cursor.get("pk"), "SK": parsed_cursor.get("sk")}

        # Query shared collections
        response = query_shared_collections(
            table, user_id, limit, start_key, role_filter
        )
        items = response.get("Items", [])

        logger.info(
            {
                "message": "Shared collections retrieved",
                "user_id": user_id,
                "item_count": len(items),
                "has_more": "LastEvaluatedKey" in response,
                "operation": "get_shared_collections",
            }
        )

        # Check if we have more results
        has_more = "LastEvaluatedKey" in response

        # Create pagination info
        pagination = {
            "has_next_page": has_more,
            "has_prev_page": cursor is not None,
            "limit": limit,
        }

        # Add next cursor if there are more results
        if has_more and response.get("LastEvaluatedKey"):
            last_key = response["LastEvaluatedKey"]
            next_cursor = create_cursor(last_key["PK"], last_key["SK"])
            pagination["next_cursor"] = next_cursor

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulSharedCollectionsRetrievals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="SharedCollectionsReturned", unit=MetricUnit.Count, value=len(items)
        )

        # Create response
        response_data = {
            "success": True,
            "data": items,
            "pagination": pagination,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }

        logger.info(
            {
                "message": "Shared collections retrieved successfully",
                "user_id": user_id,
                "total_returned": len(items),
                "has_next_page": has_more,
                "role_filter": role_filter,
                "operation": "get_shared_collections",
            }
        )

        return {"statusCode": 200, "body": json.dumps(response_data)}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during shared collections retrieval",
                "error_code": error_code,
                "error_message": error_message,
                "operation": "get_shared_collections",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedSharedCollectionsRetrievals", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during shared collections retrieval",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "get_shared_collections",
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
