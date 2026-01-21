"""
Collections utilities for MediaLake Lambda functions.

This module provides standardized collection-related utility functions
including access validation, pagination, and common operations that can
be used across all collections Lambda functions.
"""

import base64
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger(service="collections-utils")
tracer = Tracer(service="collections-utils")
metrics = Metrics(namespace="medialake", service="collections-utils")

# Collection constants
COLLECTION_PK_PREFIX = "COLL#"
METADATA_SK = "METADATA"
CHILD_SK_PREFIX = "CHILD#"
USER_PK_PREFIX = "USER#"
SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
COLLECTIONS_GSI5_PK = "COLLECTIONS"

# Item-related SK prefixes
ITEM_SK_PREFIX = "ITEM#"
ASSET_SK_PREFIX = "ASSET#"
RULE_SK_PREFIX = "RULE#"
PERM_SK_PREFIX = "PERM#"

# Valid collection statuses
VALID_COLLECTION_STATUSES = ["ACTIVE", "ARCHIVED", "DELETED"]
ACTIVE_STATUS = "ACTIVE"

# Valid item types for collections
VALID_ITEM_TYPES = ["asset", "workflow", "collection"]

# Access levels
ACCESS_LEVELS = {"READ": "read", "WRITE": "write", "DELETE": "delete", "SHARE": "share"}


@tracer.capture_method
def get_collection_metadata(table, collection_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve collection metadata from DynamoDB.

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to retrieve

    Returns:
        Collection metadata dictionary or None if not found
    """
    try:
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        item = response.get("Item")
        if item:
            logger.debug(
                {
                    "message": "Collection metadata retrieved",
                    "collection_id": collection_id,
                    "operation": "get_collection_metadata",
                }
            )
        else:
            logger.debug(
                {
                    "message": "Collection not found",
                    "collection_id": collection_id,
                    "operation": "get_collection_metadata",
                }
            )

        return item

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to retrieve collection metadata",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_collection_metadata",
            }
        )
        return None


@tracer.capture_method
def get_collection_item_count(table, collection_pk: str) -> int:
    """
    Count the actual number of items in a collection by querying DynamoDB.

    This function queries for both ASSET# and ITEM# SK prefixes to count all
    items in a collection. It uses Select='COUNT' for efficiency, minimizing
    data transfer. Handles pagination for large collections.

    Args:
        table: DynamoDB table resource (boto3)
        collection_pk: Collection primary key (e.g., COLL#{collection_id})

    Returns:
        Integer count of items, or -1 if an error occurs
    """
    try:
        total_count = 0
        pk_value = collection_pk

        # Query for ASSET# prefix items
        asset_count = _count_items_with_prefix(table, pk_value, ASSET_SK_PREFIX)
        if asset_count < 0:
            # Error occurred, return -1
            return -1
        total_count += asset_count

        # Query for ITEM# prefix items
        item_count = _count_items_with_prefix(table, pk_value, ITEM_SK_PREFIX)
        if item_count < 0:
            # Error occurred, return -1
            return -1
        total_count += item_count

        logger.debug(
            {
                "message": "Collection item count retrieved",
                "collection_pk": collection_pk,
                "asset_count": asset_count,
                "item_count": item_count,
                "total_count": total_count,
                "operation": "get_collection_item_count",
            }
        )

        return total_count

    except ClientError as e:
        logger.error(
            {
                "message": "DynamoDB error counting collection items",
                "collection_pk": collection_pk,
                "error": str(e),
                "error_code": e.response.get("Error", {}).get("Code", "Unknown"),
                "operation": "get_collection_item_count",
            }
        )
        metrics.add_metric(
            name="CollectionItemCountQueryFailures", unit=MetricUnit.Count, value=1
        )
        return -1
    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error counting collection items",
                "collection_pk": collection_pk,
                "error": str(e),
                "operation": "get_collection_item_count",
            }
        )
        metrics.add_metric(
            name="CollectionItemCountQueryFailures", unit=MetricUnit.Count, value=1
        )
        return -1


@tracer.capture_method
def _count_items_with_prefix(table, pk_value: str, sk_prefix: str) -> int:
    """
    Count items with a specific SK prefix using DynamoDB query with Select='COUNT'.

    Handles pagination for large collections where count exceeds 1MB scan limit.

    Args:
        table: DynamoDB table resource (boto3)
        pk_value: Partition key value (e.g., COLL#{collection_id})
        sk_prefix: Sort key prefix to filter by (e.g., ASSET# or ITEM#)

    Returns:
        Integer count of items, or -1 if an error occurs
    """
    try:
        count = 0
        last_evaluated_key = None

        while True:
            query_params = {
                "KeyConditionExpression": Key("PK").eq(pk_value)
                & Key("SK").begins_with(sk_prefix),
                "Select": "COUNT",
            }

            if last_evaluated_key:
                query_params["ExclusiveStartKey"] = last_evaluated_key

            response = table.query(**query_params)
            count += response.get("Count", 0)

            # Check for pagination
            last_evaluated_key = response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break

        return count

    except ClientError as e:
        logger.error(
            {
                "message": "DynamoDB error in count query",
                "pk_value": pk_value,
                "sk_prefix": sk_prefix,
                "error": str(e),
                "error_code": e.response.get("Error", {}).get("Code", "Unknown"),
                "operation": "_count_items_with_prefix",
            }
        )
        metrics.add_metric(
            name="CollectionItemCountQueryFailures", unit=MetricUnit.Count, value=1
        )
        return -1
    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error in count query",
                "pk_value": pk_value,
                "sk_prefix": sk_prefix,
                "error": str(e),
                "operation": "_count_items_with_prefix",
            }
        )
        metrics.add_metric(
            name="CollectionItemCountQueryFailures", unit=MetricUnit.Count, value=1
        )
        return -1


@tracer.capture_method
def validate_collection_access(
    table,
    collection_id: str,
    user_id: Optional[str],
    required_access: str = ACCESS_LEVELS["READ"],
) -> Dict[str, Any]:
    """
    Validate that a collection exists and user has the required access level.

    This function provides standardized collection access validation across
    all collections Lambda functions with consistent return format.

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to validate
        user_id: User ID requesting access (None for anonymous)
        required_access: Required access level ('read', 'write', 'delete', 'share')

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "collection": dict (if valid),
            "error": str (if not valid),
            "error_code": str (if not valid)
        }
    """
    try:
        # Get collection metadata
        collection = get_collection_metadata(table, collection_id)

        if not collection:
            logger.warning(
                {
                    "message": "Collection not found",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return {
                "valid": False,
                "error": "Collection not found",
                "error_code": "COLLECTION_NOT_FOUND",
            }

        # Check if collection is active
        if collection.get("status") != ACTIVE_STATUS:
            logger.warning(
                {
                    "message": "Collection is not active",
                    "collection_id": collection_id,
                    "status": collection.get("status"),
                    "operation": "validate_collection_access",
                }
            )
            return {
                "valid": False,
                "error": "Collection is not active",
                "error_code": "COLLECTION_NOT_ACTIVE",
            }

        # Check access permissions
        access_granted = _check_collection_permissions(
            collection, user_id, required_access
        )

        if access_granted:
            logger.debug(
                {
                    "message": "Collection access granted",
                    "collection_id": collection_id,
                    "user_id": user_id,
                    "required_access": required_access,
                    "operation": "validate_collection_access",
                }
            )
            return {"valid": True, "collection": collection}
        else:
            logger.warning(
                {
                    "message": "Collection access denied",
                    "collection_id": collection_id,
                    "user_id": user_id,
                    "required_access": required_access,
                    "operation": "validate_collection_access",
                }
            )
            return {
                "valid": False,
                "error": "Insufficient permissions to access collection",
                "error_code": "ACCESS_DENIED",
            }

    except Exception as e:
        logger.error(
            {
                "message": "Failed to validate collection access",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "validate_collection_access",
            }
        )
        return {
            "valid": False,
            "error": "Internal error validating collection access",
            "error_code": "VALIDATION_ERROR",
        }


@tracer.capture_method
def _check_collection_permissions(
    collection: Dict[str, Any], user_id: Optional[str], required_access: str
) -> bool:
    """
    Internal function to check if user has required permissions for collection.

    Args:
        collection: Collection metadata
        user_id: User ID requesting access
        required_access: Required access level

    Returns:
        True if access is granted, False otherwise
    """
    # Public collections allow read access to everyone
    if required_access == ACCESS_LEVELS["READ"] and collection.get("isPublic", False):
        return True

    # No user ID provided - deny access for non-public collections
    if not user_id:
        return False

    # Owner has all permissions
    if collection.get("ownerId") == user_id:
        return True

    # TODO: Implement proper permission checking for shared collections
    # For now, authenticated users get read access to all collections
    # and only owners get write/delete/share access
    if required_access == ACCESS_LEVELS["READ"]:
        return True

    # Write, delete, and share access currently restricted to owners
    return False


@tracer.capture_method
def create_cursor(
    pk: str, sk: str, gsi_pk: Optional[str] = None, gsi_sk: Optional[str] = None
) -> str:
    """
    Create base64-encoded cursor for pagination.

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
        cursor_data["gsi_pk"] = gsi_pk
    if gsi_sk:
        cursor_data["gsi_sk"] = gsi_sk

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
def parse_cursor(cursor_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse base64-encoded cursor back to dictionary.

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
def format_collection_item(
    item: Dict[str, Any], user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format DynamoDB collection item to standardized API response format.

    Args:
        item: Raw DynamoDB item
        user_context: User context information

    Returns:
        Formatted collection object
    """
    # Extract collection ID from PK
    collection_id = item["PK"].replace(COLLECTION_PK_PREFIX, "")
    user_id = user_context.get("user_id") if user_context else None
    owner_id = item.get("ownerId", "")

    formatted_item = {
        "id": collection_id,
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "collectionTypeId": item.get("collectionTypeId", ""),
        "parentId": item.get("parentId"),
        "ownerId": owner_id,
        "metadata": item.get("customMetadata", {}),
        "tags": item.get("tags", {}),
        "status": item.get("status", ACTIVE_STATUS),
        "itemCount": item.get("itemCount", 0),
        "childCollectionCount": item.get("childCollectionCount", 0),
        "isPublic": item.get("isPublic", False),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        # Sharing metadata
        "isShared": item.get("isShared", False),
        "shareCount": item.get("shareCount", 0),
        "sharedWithMe": item.get("sharedWithMe", False),
    }

    # Add user-specific fields if user context available
    if user_id:
        formatted_item["isFavorite"] = False  # TODO: Query user collection relationship
        if owner_id == user_id:
            formatted_item["userRole"] = "owner"
        elif item.get("sharedWithMe"):
            # User has shared access to this collection
            formatted_item["userRole"] = item.get("myRole", "viewer").lower()
        else:
            formatted_item["userRole"] = "viewer"

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
def apply_field_selection(
    item: Dict[str, Any], fields: Optional[str]
) -> Dict[str, Any]:
    """
    Apply field selection to limit returned fields in API response.

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
def apply_sorting(
    items: List[Dict[str, Any]], sort_param: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Apply sorting to collections list.

    Args:
        items: List of collection items
        sort_param: Sort parameter (e.g., 'name', '-name', 'createdAt', etc.)

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
            "message": "Applying sort to collections",
            "sort_field": sort_field,
            "descending": descending,
            "item_count": len(items),
            "operation": "apply_sorting",
        }
    )

    # Define sorting key functions
    sort_key_map = {
        "name": lambda x: x.get("name", "").lower(),
        "createdAt": lambda x: x.get("createdAt", ""),
        "updatedAt": lambda x: x.get("updatedAt", ""),
    }

    sort_key_func = sort_key_map.get(sort_field, lambda x: x.get("updatedAt", ""))

    try:
        sorted_items = sorted(items, key=sort_key_func, reverse=descending)
        logger.info(
            {
                "message": "Collections sorted successfully",
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
                "message": "Failed to sort collections",
                "sort_field": sort_field,
                "error": str(e),
                "operation": "apply_sorting",
            }
        )
        return items


@tracer.capture_method
def build_filter_expression(
    filters: Dict[str, Any], expression_values: Dict[str, Any]
) -> Optional[str]:
    """
    Build DynamoDB filter expression from query parameters.

    Args:
        filters: Dictionary of filter parameters
        expression_values: Dictionary to store expression attribute values

    Returns:
        Filter expression string or None
    """
    filter_conditions = []

    # Status filter
    if filters.get("status"):
        filter_conditions.append("#status = :status")
        expression_values[":status"] = filters["status"]

    # Search filter (name or description contains search term)
    if filters.get("search"):
        filter_conditions.append(
            "(contains(#name, :search) OR contains(description, :search))"
        )
        expression_values[":search"] = filters["search"]

    # Collection type filter
    if filters.get("type"):
        filter_conditions.append("collectionTypeId = :collection_type")
        expression_values[":collection_type"] = filters["type"]

    return " AND ".join(filter_conditions) if filter_conditions else None


@tracer.capture_method
def create_error_response(
    error_code: str,
    error_message: str,
    status_code: int = 500,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized error response for collections API.

    Args:
        error_code: Error code identifier
        error_message: Human-readable error message
        status_code: HTTP status code
        request_id: Optional request ID for tracking

    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": error_message,
        },
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "v1",
        },
    }

    if request_id:
        response["meta"]["request_id"] = request_id

    return response, status_code


@tracer.capture_method
def create_success_response(
    data: Any,
    pagination: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized success response for collections API.

    Args:
        data: Response data
        pagination: Optional pagination information
        request_id: Optional request ID for tracking

    Returns:
        Standardized success response dictionary
    """
    response = {
        "success": True,
        "data": data,
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "v1",
        },
    }

    if pagination:
        response["pagination"] = pagination

    if request_id:
        response["meta"]["request_id"] = request_id

    return response
