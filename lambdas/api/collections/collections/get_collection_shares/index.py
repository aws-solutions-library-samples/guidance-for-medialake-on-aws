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
    service="collection-shares-retrieval",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-shares-retrieval")
metrics = Metrics(namespace="medialake", service="collection-shares-retrieval")

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
GROUP_PK_PREFIX = "GROUP#"
VALID_ROLES = ["viewer", "editor", "admin"]
ROLE_HIERARCHY = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


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
def check_collection_access(table, collection_id: str, user_id: str) -> Dict[str, Any]:
    """
    Check if user has access to view collection shares

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        user_id: User ID

    Returns:
        Dictionary with access info and user role
    """
    try:
        # Get collection metadata
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        if "Item" not in response:
            return {"has_access": False, "reason": "COLLECTION_NOT_FOUND"}

        collection = response["Item"]

        # Check if collection is active
        if collection.get("status") == "DELETED":
            return {"has_access": False, "reason": "COLLECTION_NOT_FOUND"}

        # Check if user is owner
        if collection.get("ownerId") == user_id:
            return {"has_access": True, "user_role": "owner", "collection": collection}

        # Check if user has explicit permissions
        try:
            perm_response = table.get_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{PERM_SK_PREFIX}{user_id}",
                }
            )

            if "Item" in perm_response:
                perm_item = perm_response["Item"]
                user_role = perm_item.get("role", "viewer")

                # Only admin and owner can view shares
                if user_role in ["admin"]:
                    return {
                        "has_access": True,
                        "user_role": user_role,
                        "collection": collection,
                    }

        except ClientError:
            pass  # Permission not found, continue to deny access

        return {"has_access": False, "reason": "INSUFFICIENT_PERMISSIONS"}

    except ClientError as e:
        logger.error(
            {
                "message": "Error checking collection access",
                "collection_id": collection_id,
                "user_id": user_id,
                "error": str(e),
                "operation": "check_collection_access",
            }
        )
        return {"has_access": False, "reason": "DATABASE_ERROR"}


@tracer.capture_method
def format_share_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB share item to API response format

    Args:
        item: Raw DynamoDB share item

    Returns:
        Formatted share object
    """
    # Extract target ID from SK
    target_id = item["SK"].replace(PERM_SK_PREFIX, "")

    formatted_item = {
        "id": f"share_{target_id}",
        "targetType": item.get("targetType", "user"),
        "targetId": item.get("targetId", target_id),
        "role": item.get("role", "viewer"),
        "sharedAt": item.get("sharedAt", ""),
        "sharedBy": item.get("sharedBy", ""),
    }

    # Add expiration if present
    if item.get("expiresAt"):
        # Convert Unix timestamp to ISO format
        expires_timestamp = item["expiresAt"]
        expires_dt = datetime.fromtimestamp(expires_timestamp)
        formatted_item["expiresAt"] = expires_dt.isoformat() + "Z"

    logger.debug(
        {
            "message": "Share item formatted",
            "target_id": target_id,
            "operation": "format_share_item",
        }
    )

    return formatted_item


@app.get("/collections/<collection_id>/share")
@tracer.capture_method
def get_collection_shares(collection_id: str):
    """Get list of users and groups with access to collection"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection shares retrieval attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "get_collection_shares",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to view collection shares",
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

        # Validate limit
        limit = min(max(1, limit), MAX_LIMIT)

        logger.debug(
            {
                "message": "Processing collection shares retrieval request",
                "collection_id": collection_id,
                "cursor": cursor,
                "limit": limit,
                "user_id": user_id,
                "operation": "get_collection_shares",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Check if user has access to view shares
        access_check = check_collection_access(table, collection_id, user_id)
        if not access_check["has_access"]:
            error_code = (
                "COLLECTION_NOT_FOUND"
                if access_check["reason"] == "COLLECTION_NOT_FOUND"
                else "INSUFFICIENT_PERMISSIONS"
            )
            status_code = (
                404 if access_check["reason"] == "COLLECTION_NOT_FOUND" else 403
            )

            logger.warning(
                {
                    "message": "Access denied for collection shares retrieval",
                    "collection_id": collection_id,
                    "user_id": user_id,
                    "reason": access_check["reason"],
                    "operation": "get_collection_shares",
                }
            )

            return {
                "statusCode": status_code,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": error_code,
                            "message": (
                                f"Collection '{collection_id}' not found"
                                if status_code == 404
                                else "You don't have permission to view collection shares"
                            ),
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

        # Query collection shares
        query_params = {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "ExpressionAttributeValues": {
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": PERM_SK_PREFIX,
            },
            "Limit": limit + 1,  # Get one extra to check if there are more results
        }

        if start_key:
            query_params["ExclusiveStartKey"] = start_key

        response = table.query(**query_params)
        items = response.get("Items", [])

        logger.info(
            {
                "message": "Collection shares retrieved from DynamoDB",
                "collection_id": collection_id,
                "item_count": len(items),
                "has_more": len(items) > limit,
                "operation": "get_collection_shares",
            }
        )

        # Check if we have more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]  # Remove the extra item

        # Format items for API response
        formatted_items = [format_share_item(item) for item in items]

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
            name="SuccessfulCollectionSharesRetrievals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="CollectionSharesReturned",
            unit=MetricUnit.Count,
            value=len(formatted_items),
        )

        # Create response
        response_data = {
            "success": True,
            "data": formatted_items,
            "pagination": pagination,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }

        logger.info(
            {
                "message": "Collection shares retrieved successfully",
                "collection_id": collection_id,
                "total_returned": len(formatted_items),
                "has_next_page": has_more,
                "operation": "get_collection_shares",
            }
        )

        return {"statusCode": 200, "body": json.dumps(response_data)}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection shares retrieval",
                "error_code": error_code,
                "error_message": error_message,
                "collection_id": collection_id,
                "operation": "get_collection_shares",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionSharesRetrievals", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection shares retrieval",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_id": collection_id,
                "operation": "get_collection_shares",
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
