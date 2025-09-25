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

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-detail-retrieval",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-detail-retrieval")
metrics = Metrics(namespace="medialake", service="collection-detail-retrieval")

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

# Constants
COLLECTION_PK_PREFIX = "COLL#"
METADATA_SK = "METADATA"
ITEM_SK_PREFIX = "ITEM#"
CHILD_SK_PREFIX = "CHILD#"
RULE_SK_PREFIX = "RULE#"
PERM_SK_PREFIX = "PERM#"
USER_PK_PREFIX = "USER#"
SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"


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
def apply_field_selection(
    item: Dict[str, Any], fields: Optional[str]
) -> Dict[str, Any]:
    """
    Apply field selection to limit returned fields

    Args:
        item: Collection item
        fields: Comma-separated list of fields to return

    Returns:
        Filtered item dictionary
    """
    if not fields:
        return item

    field_list = [field.strip() for field in fields.split(",")]
    return {key: value for key, value in item.items() if key in field_list}


@tracer.capture_method
def format_collection_item(
    item: Dict[str, Any], user_context: Dict[str, Optional[str]]
) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: Raw DynamoDB item
        user_context: User context information

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

    # Add user-specific fields if user context available
    if user_context.get("user_id"):
        formatted_item["isFavorite"] = False  # TODO: Query user collection relationship
        if formatted_item["ownerId"] == user_context["user_id"]:
            formatted_item["userRole"] = "owner"
        else:
            formatted_item["userRole"] = "viewer"  # TODO: Query actual permissions

    # Add TTL if present
    if item.get("expiresAt"):
        formatted_item["expiresAt"] = item["expiresAt"]

    logger.debug(
        {
            "message": "Collection item formatted",
            "collection_id": collection_id,
            "operation": "format_collection_item",
        }
    )

    return formatted_item


@tracer.capture_method
def format_collection_item_simple(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB collection item to simple API response format

    Args:
        item: Raw DynamoDB item

    Returns:
        Formatted collection item object
    """
    # Extract item ID from SK
    item_id = item["SK"].replace(ITEM_SK_PREFIX, "")

    return {
        "id": item_id,
        "itemType": item.get("itemType", ""),
        "itemId": item.get("itemId", ""),
        "sortOrder": item.get("sortOrder", 0),
        "metadata": item.get("metadata", {}),
        "addedAt": item.get("addedAt", ""),
        "addedBy": item.get("addedBy", ""),
    }


@tracer.capture_method
def format_collection_rule(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB rule item to API response format

    Args:
        item: Raw DynamoDB rule item

    Returns:
        Formatted rule object
    """
    # Extract rule ID from the end of SK after the priority
    sk_parts = item["SK"].split("#")
    rule_id = sk_parts[-1] if len(sk_parts) > 2 else item.get("ruleId", "")

    return {
        "id": rule_id,
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "ruleType": item.get("ruleType", ""),
        "criteria": item.get("criteria", {}),
        "isActive": item.get("isActive", True),
        "priority": item.get("priority", 0),
        "matchCount": item.get("matchCount", 0),
        "lastEvaluatedAt": item.get("lastEvaluatedAt"),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }


@tracer.capture_method
def format_permission_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB permission item to API response format

    Args:
        item: Raw DynamoDB permission item

    Returns:
        Formatted permission object
    """
    # Extract target ID from SK
    target_id = item["SK"].replace(PERM_SK_PREFIX, "")

    return {
        "id": f"perm_{target_id}",
        "targetType": item.get("targetType", ""),
        "targetId": item.get("targetId", ""),
        "permissions": item.get("permissions", {}),
        "grantedBy": item.get("grantedBy", ""),
        "grantedAt": item.get("grantedAt", ""),
        "expiresAt": item.get("expiresAt"),
    }


@tracer.capture_method
def get_collection_items(
    table, collection_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get items from a collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        limit: Maximum number of items to return

    Returns:
        List of formatted collection items
    """
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": ITEM_SK_PREFIX,
            },
            Limit=limit,
        )

        items = response.get("Items", [])
        formatted_items = [format_collection_item_simple(item) for item in items]

        logger.debug(
            {
                "message": "Collection items retrieved",
                "collection_id": collection_id,
                "item_count": len(formatted_items),
                "operation": "get_collection_items",
            }
        )

        return formatted_items

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get collection items",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_collection_items",
            }
        )
        return []


@tracer.capture_method
def get_child_collections(
    table, collection_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get child collections

    Args:
        table: DynamoDB table resource
        collection_id: Parent collection ID
        limit: Maximum number of children to return

    Returns:
        List of formatted child collections
    """
    try:
        # Get child collection references
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": CHILD_SK_PREFIX,
            },
            Limit=limit,
        )

        child_refs = response.get("Items", [])

        # Get full collection data for each child
        children = []
        for child_ref in child_refs:
            child_id = child_ref.get("childCollectionId")
            if child_id:
                try:
                    child_response = table.get_item(
                        Key={
                            "PK": f"{COLLECTION_PK_PREFIX}{child_id}",
                            "SK": METADATA_SK,
                        }
                    )
                    if "Item" in child_response:
                        # Format as basic collection info
                        child_item = child_response["Item"]
                        children.append(
                            {
                                "id": child_id,
                                "name": child_item.get("name", ""),
                                "collectionTypeId": child_item.get(
                                    "collectionTypeId", ""
                                ),
                                "status": child_item.get("status", "ACTIVE"),
                                "itemCount": child_item.get("itemCount", 0),
                                "childCollectionCount": child_item.get(
                                    "childCollectionCount", 0
                                ),
                                "createdAt": child_item.get("createdAt", ""),
                                "updatedAt": child_item.get("updatedAt", ""),
                            }
                        )
                except Exception as e:
                    logger.warning(
                        {
                            "message": "Failed to get child collection metadata",
                            "child_id": child_id,
                            "error": str(e),
                            "operation": "get_child_collections",
                        }
                    )

        logger.debug(
            {
                "message": "Child collections retrieved",
                "collection_id": collection_id,
                "child_count": len(children),
                "operation": "get_child_collections",
            }
        )

        return children

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get child collections",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_child_collections",
            }
        )
        return []


@tracer.capture_method
def get_collection_rules(
    table, collection_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get rules for a collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        limit: Maximum number of rules to return

    Returns:
        List of formatted collection rules
    """
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": RULE_SK_PREFIX,
            },
            Limit=limit,
        )

        items = response.get("Items", [])
        formatted_rules = [format_collection_rule(item) for item in items]

        logger.debug(
            {
                "message": "Collection rules retrieved",
                "collection_id": collection_id,
                "rule_count": len(formatted_rules),
                "operation": "get_collection_rules",
            }
        )

        return formatted_rules

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get collection rules",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_collection_rules",
            }
        )
        return []


@tracer.capture_method
def get_collection_permissions(
    table, collection_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get permissions for a collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        limit: Maximum number of permissions to return

    Returns:
        List of formatted collection permissions
    """
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": PERM_SK_PREFIX,
            },
            Limit=limit,
        )

        items = response.get("Items", [])
        formatted_permissions = [format_permission_item(item) for item in items]

        logger.debug(
            {
                "message": "Collection permissions retrieved",
                "collection_id": collection_id,
                "permission_count": len(formatted_permissions),
                "operation": "get_collection_permissions",
            }
        )

        return formatted_permissions

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get collection permissions",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_collection_permissions",
            }
        )
        return []


@tracer.capture_method
def get_owner_info(table, owner_id: str) -> Optional[Dict[str, Any]]:
    """
    Get owner information (placeholder implementation)

    Args:
        table: DynamoDB table resource
        owner_id: Owner user ID

    Returns:
        Owner information dictionary or None
    """
    # TODO: Implement actual user lookup when user management is available
    # For now, return basic user info structure
    logger.debug(
        {
            "message": "Owner info requested (placeholder implementation)",
            "owner_id": owner_id,
            "operation": "get_owner_info",
        }
    )

    return {
        "id": owner_id,
        "username": f"user_{owner_id}",
        "displayName": f"User {owner_id}",
        "email": f"{owner_id}@example.com",
    }


@app.get("/collections/<collection_id>")
@tracer.capture_method
def get_collection(collection_id: str):
    """Get collection details with optional includes"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)

        # Parse query parameters
        include_param = app.current_event.get_query_string_value("include")
        fields_param = app.current_event.get_query_string_value("fields")

        # Parse includes
        includes = []
        if include_param:
            includes = [include.strip() for include in include_param.split(",")]

        logger.debug(
            {
                "message": "Processing collection detail request",
                "collection_id": collection_id,
                "includes": includes,
                "fields": fields_param,
                "operation": "get_collection",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Get collection metadata
        try:
            response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )
        except ClientError as e:
            logger.error(
                {
                    "message": "DynamoDB error retrieving collection",
                    "collection_id": collection_id,
                    "error": str(e),
                    "operation": "get_collection",
                }
            )
            raise

        if "Item" not in response:
            logger.info(
                {
                    "message": "Collection not found",
                    "collection_id": collection_id,
                    "operation": "get_collection",
                }
            )

            metrics.add_metric(
                name="CollectionNotFound", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "COLLECTION_NOT_FOUND",
                            "message": f"Collection '{collection_id}' not found",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        collection_item = response["Item"]

        # Check if collection is deleted
        if collection_item.get("status") == "DELETED":
            logger.info(
                {
                    "message": "Collection is deleted",
                    "collection_id": collection_id,
                    "operation": "get_collection",
                }
            )

            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "COLLECTION_NOT_FOUND",
                            "message": f"Collection '{collection_id}' not found",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # TODO: Add permission check - user must have read access to collection

        logger.info(
            {
                "message": "Collection metadata retrieved",
                "collection_id": collection_id,
                "collection_name": collection_item.get("name"),
                "operation": "get_collection",
            }
        )

        # Format collection data
        formatted_collection = format_collection_item(collection_item, user_context)

        # Handle includes
        if "items" in includes:
            formatted_collection["items"] = get_collection_items(table, collection_id)

        if "children" in includes:
            formatted_collection["children"] = get_child_collections(
                table, collection_id
            )

        if "rules" in includes:
            formatted_collection["rules"] = get_collection_rules(table, collection_id)

        if "permissions" in includes:
            formatted_collection["permissions"] = get_collection_permissions(
                table, collection_id
            )

        if "owner" in includes:
            owner_id = formatted_collection.get("ownerId")
            if owner_id:
                formatted_collection["owner"] = get_owner_info(table, owner_id)

        # Apply field selection if specified
        if fields_param:
            formatted_collection = apply_field_selection(
                formatted_collection, fields_param
            )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
        )

        # Create response
        response_data = {
            "success": True,
            "data": formatted_collection,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
            },
        }

        logger.info(
            {
                "message": "Collection details retrieved successfully",
                "collection_id": collection_id,
                "includes_applied": includes,
                "operation": "get_collection",
            }
        )

        return {"statusCode": 200, "body": json.dumps(response_data)}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection retrieval",
                "error_code": error_code,
                "error_message": error_message,
                "collection_id": collection_id,
                "operation": "get_collection",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionRetrievals", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection retrieval",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_id": collection_id,
                "operation": "get_collection",
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
