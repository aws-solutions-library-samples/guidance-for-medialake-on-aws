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
    service="collection-sharing",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-sharing")
metrics = Metrics(namespace="medialake", service="collection-sharing")

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
PERM_SK_PREFIX = "PERM#"
USER_PK_PREFIX = "USER#"
GROUP_PK_PREFIX = "GROUP#"
VALID_ROLES = ["viewer", "editor", "admin"]
VALID_TARGET_TYPES = ["user", "group"]
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
def validate_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection sharing request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate required fields
    if not request_data.get("targetType"):
        errors.append(
            {
                "field": "targetType",
                "message": "Target type is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif request_data["targetType"] not in VALID_TARGET_TYPES:
        errors.append(
            {
                "field": "targetType",
                "message": f"Target type must be one of: {', '.join(VALID_TARGET_TYPES)}",
                "code": "INVALID_VALUE",
            }
        )

    if not request_data.get("targetId"):
        errors.append(
            {
                "field": "targetId",
                "message": "Target ID is required",
                "code": "REQUIRED_FIELD",
            }
        )

    if not request_data.get("role"):
        errors.append(
            {"field": "role", "message": "Role is required", "code": "REQUIRED_FIELD"}
        )
    elif request_data["role"] not in VALID_ROLES:
        errors.append(
            {
                "field": "role",
                "message": f"Role must be one of: {', '.join(VALID_ROLES)}",
                "code": "INVALID_VALUE",
            }
        )

    # Validate expiresAt if provided
    if request_data.get("expiresAt"):
        try:
            expires_dt = datetime.fromisoformat(
                request_data["expiresAt"].replace("Z", "+00:00")
            )
            if expires_dt <= datetime.now(expires_dt.tzinfo):
                errors.append(
                    {
                        "field": "expiresAt",
                        "message": "Expiration date must be in the future",
                        "code": "INVALID_VALUE",
                    }
                )
        except ValueError:
            errors.append(
                {
                    "field": "expiresAt",
                    "message": "Invalid date format. Use ISO 8601 format",
                    "code": "INVALID_FORMAT",
                }
            )

    logger.debug(
        {
            "message": "Request data validation completed",
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_request_data",
        }
    )

    return errors


@tracer.capture_method
def check_sharing_permissions(
    table, collection_id: str, user_id: str
) -> Dict[str, Any]:
    """
    Check if user has permission to share the collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        user_id: User ID

    Returns:
        Dictionary with permission info and user role
    """
    try:
        # Get collection metadata
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        if "Item" not in response:
            return {"can_share": False, "reason": "COLLECTION_NOT_FOUND"}

        collection = response["Item"]

        # Check if collection is active
        if collection.get("status") == "DELETED":
            return {"can_share": False, "reason": "COLLECTION_NOT_FOUND"}

        # Check if user is owner
        if collection.get("ownerId") == user_id:
            return {"can_share": True, "user_role": "owner", "collection": collection}

        # Check if user has admin permissions
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

                # Only admin and owner can share collections
                if user_role == "admin":
                    return {
                        "can_share": True,
                        "user_role": user_role,
                        "collection": collection,
                    }

        except ClientError:
            pass  # Permission not found, continue to deny access

        return {"can_share": False, "reason": "INSUFFICIENT_PERMISSIONS"}

    except ClientError as e:
        logger.error(
            {
                "message": "Error checking sharing permissions",
                "collection_id": collection_id,
                "user_id": user_id,
                "error": str(e),
                "operation": "check_sharing_permissions",
            }
        )
        return {"can_share": False, "reason": "DATABASE_ERROR"}


@tracer.capture_method
def validate_target_exists(target_type: str, target_id: str) -> bool:
    """
    Validate that the target user or group exists

    Args:
        target_type: Type of target (user or group)
        target_id: Target ID

    Returns:
        True if target exists, False otherwise
    """
    # TODO: Implement actual user/group validation when user management is available
    # For now, assume all targets exist
    logger.debug(
        {
            "message": "Target validation (placeholder implementation)",
            "target_type": target_type,
            "target_id": target_id,
            "operation": "validate_target_exists",
        }
    )

    return True


@tracer.capture_method
def check_role_hierarchy(granter_role: str, requested_role: str) -> bool:
    """
    Check if user can grant the requested role based on hierarchy

    Args:
        granter_role: Role of the user granting permission
        requested_role: Role being requested to grant

    Returns:
        True if role can be granted, False otherwise
    """
    granter_level = ROLE_HIERARCHY.get(granter_role, 0)
    requested_level = ROLE_HIERARCHY.get(requested_role, 0)

    # User can only grant roles lower than or equal to their own (except owner which cannot be granted)
    can_grant = granter_level >= requested_level and requested_role != "owner"

    logger.debug(
        {
            "message": "Role hierarchy check",
            "granter_role": granter_role,
            "requested_role": requested_role,
            "can_grant": can_grant,
            "operation": "check_role_hierarchy",
        }
    )

    return can_grant


@tracer.capture_method
def check_existing_share(
    table, collection_id: str, target_id: str
) -> Optional[Dict[str, Any]]:
    """
    Check if target already has access to collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        target_id: Target user/group ID

    Returns:
        Existing share item if found, None otherwise
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{PERM_SK_PREFIX}{target_id}",
            }
        )

        return response.get("Item")

    except ClientError as e:
        logger.error(
            {
                "message": "Error checking existing share",
                "collection_id": collection_id,
                "target_id": target_id,
                "error": str(e),
                "operation": "check_existing_share",
            }
        )
        return None


@tracer.capture_method
def format_share_response(item: Dict[str, Any], target_id: str) -> Dict[str, Any]:
    """
    Format DynamoDB share item to API response format

    Args:
        item: DynamoDB share item
        target_id: Target ID

    Returns:
        Formatted share object
    """
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

    return formatted_item


@app.post("/collections/<collection_id>/share")
@tracer.capture_method
def share_collection(collection_id: str):
    """Share collection with users or groups"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection sharing attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "share_collection",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to share collections",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Get request body
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing collection sharing request",
                "collection_id": collection_id,
                "request_data": request_data,
                "user_id": user_id,
                "operation": "share_collection",
            }
        )

        # Validate request data
        validation_errors = validate_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Collection sharing request validation failed",
                    "errors": validation_errors,
                    "operation": "share_collection",
                }
            )

            metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)

            return {
                "statusCode": 422,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "The request could not be processed due to validation errors",
                            "details": validation_errors,
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        table = dynamodb.Table(TABLE_NAME)
        target_type = request_data["targetType"]
        target_id = request_data["targetId"]
        requested_role = request_data["role"]

        # Check if user has permission to share
        permission_check = check_sharing_permissions(table, collection_id, user_id)
        if not permission_check["can_share"]:
            error_code = (
                "COLLECTION_NOT_FOUND"
                if permission_check["reason"] == "COLLECTION_NOT_FOUND"
                else "INSUFFICIENT_PERMISSIONS"
            )
            status_code = (
                404 if permission_check["reason"] == "COLLECTION_NOT_FOUND" else 403
            )

            logger.warning(
                {
                    "message": "Access denied for collection sharing",
                    "collection_id": collection_id,
                    "user_id": user_id,
                    "reason": permission_check["reason"],
                    "operation": "share_collection",
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
                                else "You don't have permission to share this collection"
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

        # Check if trying to share with collection owner
        collection = permission_check["collection"]
        if target_type == "user" and target_id == collection.get("ownerId"):
            logger.warning(
                {
                    "message": "Attempt to share collection with owner",
                    "collection_id": collection_id,
                    "target_id": target_id,
                    "operation": "share_collection",
                }
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_TARGET",
                            "message": "Cannot share collection with the owner",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Validate role hierarchy
        user_role = permission_check["user_role"]
        if not check_role_hierarchy(user_role, requested_role):
            logger.warning(
                {
                    "message": "Role hierarchy violation",
                    "collection_id": collection_id,
                    "user_role": user_role,
                    "requested_role": requested_role,
                    "operation": "share_collection",
                }
            )

            return {
                "statusCode": 403,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": f"Cannot grant '{requested_role}' role with your current permissions",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Validate target exists
        if not validate_target_exists(target_type, target_id):
            logger.warning(
                {
                    "message": "Target does not exist",
                    "collection_id": collection_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "operation": "share_collection",
                }
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_TARGET",
                            "message": f"Target {target_type} '{target_id}' does not exist",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Check for existing share
        existing_share = check_existing_share(table, collection_id, target_id)
        if existing_share:
            logger.warning(
                {
                    "message": "Target already has access to collection",
                    "collection_id": collection_id,
                    "target_id": target_id,
                    "existing_role": existing_share.get("role"),
                    "operation": "share_collection",
                }
            )

            return {
                "statusCode": 409,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "ALREADY_SHARED",
                            "message": f"Target already has access to this collection with role '{existing_share.get('role')}'",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Create share item
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        share_item = {
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": f"{PERM_SK_PREFIX}{target_id}",
            "targetType": target_type,
            "targetId": target_id,
            "role": requested_role,
            "sharedAt": current_timestamp,
            "sharedBy": user_id,
        }

        # Add TTL if expiration is specified
        if request_data.get("expiresAt"):
            expires_dt = datetime.fromisoformat(
                request_data["expiresAt"].replace("Z", "+00:00")
            )
            ttl_timestamp = int(expires_dt.timestamp())
            share_item["expiresAt"] = ttl_timestamp

        logger.debug(
            {
                "message": "Creating share item",
                "collection_id": collection_id,
                "target_type": target_type,
                "target_id": target_id,
                "role": requested_role,
                "operation": "share_collection",
            }
        )

        # Put the share item
        try:
            table.put_item(
                Item=share_item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Race condition - share was created by another request
                logger.warning(
                    {
                        "message": "Share creation failed - conditional check failed",
                        "collection_id": collection_id,
                        "target_id": target_id,
                        "error": str(e),
                        "operation": "share_collection",
                    }
                )
                return {
                    "statusCode": 409,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "ALREADY_SHARED",
                                "message": "Target already has access to this collection",
                            },
                            "meta": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "version": "v1",
                                "request_id": app.current_event.request_context.request_id,
                            },
                        }
                    ),
                }
            else:
                raise  # Re-raise other ClientErrors

        logger.info(
            {
                "message": "Collection shared successfully",
                "collection_id": collection_id,
                "target_type": target_type,
                "target_id": target_id,
                "role": requested_role,
                "shared_by": user_id,
                "operation": "share_collection",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionShares", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_share_response(share_item, target_id)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "success": True,
                    "data": response_data,
                    "meta": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "version": "v1",
                        "request_id": app.current_event.request_context.request_id,
                    },
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection sharing",
                "error_code": error_code,
                "error_message": error_message,
                "collection_id": collection_id,
                "operation": "share_collection",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionShares", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection sharing",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_id": collection_id,
                "operation": "share_collection",
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
