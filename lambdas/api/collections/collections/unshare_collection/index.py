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
    service="collection-unsharing",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-unsharing")
metrics = Metrics(namespace="medialake", service="collection-unsharing")

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
def check_unsharing_permissions(
    table, collection_id: str, requester_id: str
) -> Dict[str, Any]:
    """
    Check if user has permission to unshare the collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        requester_id: User ID requesting to unshare

    Returns:
        Dictionary with permission info and user role
    """
    try:
        # Get collection metadata
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        if "Item" not in response:
            return {"can_unshare": False, "reason": "COLLECTION_NOT_FOUND"}

        collection = response["Item"]

        # Check if collection is active
        if collection.get("status") == "DELETED":
            return {"can_unshare": False, "reason": "COLLECTION_NOT_FOUND"}

        # Check if user is owner
        if collection.get("ownerId") == requester_id:
            return {"can_unshare": True, "user_role": "owner", "collection": collection}

        # Check if user has admin permissions
        try:
            perm_response = table.get_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{PERM_SK_PREFIX}{requester_id}",
                }
            )

            if "Item" in perm_response:
                perm_item = perm_response["Item"]
                user_role = perm_item.get("role", "viewer")

                # Only admin and owner can unshare collections
                if user_role == "admin":
                    return {
                        "can_unshare": True,
                        "user_role": user_role,
                        "collection": collection,
                    }

        except ClientError:
            pass  # Permission not found, continue to deny access

        return {"can_unshare": False, "reason": "INSUFFICIENT_PERMISSIONS"}

    except ClientError as e:
        logger.error(
            {
                "message": "Error checking unsharing permissions",
                "collection_id": collection_id,
                "requester_id": requester_id,
                "error": str(e),
                "operation": "check_unsharing_permissions",
            }
        )
        return {"can_unshare": False, "reason": "DATABASE_ERROR"}


@tracer.capture_method
def get_existing_share(
    table, collection_id: str, target_user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get existing share for the target user

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        target_user_id: Target user ID to check

    Returns:
        Existing share item if found, None otherwise
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{PERM_SK_PREFIX}{target_user_id}",
            }
        )

        return response.get("Item")

    except ClientError as e:
        logger.error(
            {
                "message": "Error getting existing share",
                "collection_id": collection_id,
                "target_user_id": target_user_id,
                "error": str(e),
                "operation": "get_existing_share",
            }
        )
        return None


@app.delete("/collections/<collection_id>/share/<user_id>")
@tracer.capture_method
def unshare_collection(collection_id: str, user_id: str):
    """Remove user's access to collection"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        requester_id = user_context.get("user_id")

        if not requester_id:
            logger.warning(
                {
                    "message": "Collection unsharing attempted without valid user context",
                    "collection_id": collection_id,
                    "target_user_id": user_id,
                    "operation": "unshare_collection",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to unshare collections",
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
                "message": "Processing collection unsharing request",
                "collection_id": collection_id,
                "target_user_id": user_id,
                "requester_id": requester_id,
                "operation": "unshare_collection",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Check if requester has permission to unshare
        permission_check = check_unsharing_permissions(
            table, collection_id, requester_id
        )
        if not permission_check["can_unshare"]:
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
                    "message": "Access denied for collection unsharing",
                    "collection_id": collection_id,
                    "requester_id": requester_id,
                    "reason": permission_check["reason"],
                    "operation": "unshare_collection",
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
                                else "You don't have permission to manage collection shares"
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

        # Check if trying to unshare with collection owner
        collection = permission_check["collection"]
        if user_id == collection.get("ownerId"):
            logger.warning(
                {
                    "message": "Attempt to unshare collection with owner",
                    "collection_id": collection_id,
                    "target_user_id": user_id,
                    "operation": "unshare_collection",
                }
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_OPERATION",
                            "message": "Cannot remove access from collection owner",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Check if share exists
        existing_share = get_existing_share(table, collection_id, user_id)
        if not existing_share:
            logger.warning(
                {
                    "message": "No existing share found for user",
                    "collection_id": collection_id,
                    "target_user_id": user_id,
                    "operation": "unshare_collection",
                }
            )

            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "SHARE_NOT_FOUND",
                            "message": "User does not have access to this collection",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Check role hierarchy - can only remove shares for roles at or below your level
        requester_role = permission_check["user_role"]
        target_role = existing_share.get("role", "viewer")

        requester_level = ROLE_HIERARCHY.get(requester_role, 0)
        target_level = ROLE_HIERARCHY.get(target_role, 0)

        if requester_level < target_level:
            logger.warning(
                {
                    "message": "Role hierarchy violation in unsharing",
                    "collection_id": collection_id,
                    "requester_role": requester_role,
                    "target_role": target_role,
                    "operation": "unshare_collection",
                }
            )

            return {
                "statusCode": 403,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": f"Cannot remove access for user with '{target_role}' role with your current permissions",
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
                "message": "Removing collection share",
                "collection_id": collection_id,
                "target_user_id": user_id,
                "target_role": target_role,
                "requester_id": requester_id,
                "operation": "unshare_collection",
            }
        )

        # Remove the share
        try:
            table.delete_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{PERM_SK_PREFIX}{user_id}",
                },
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Share was already removed by another request
                logger.warning(
                    {
                        "message": "Share removal failed - item no longer exists",
                        "collection_id": collection_id,
                        "target_user_id": user_id,
                        "error": str(e),
                        "operation": "unshare_collection",
                    }
                )
                return {
                    "statusCode": 404,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "SHARE_NOT_FOUND",
                                "message": "User does not have access to this collection",
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
                "message": "Collection unshared successfully",
                "collection_id": collection_id,
                "target_user_id": user_id,
                "target_role": target_role,
                "removed_by": requester_id,
                "operation": "unshare_collection",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionUnshares", unit=MetricUnit.Count, value=1
        )

        return {"statusCode": 204, "body": ""}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection unsharing",
                "error_code": error_code,
                "error_message": error_message,
                "collection_id": collection_id,
                "target_user_id": user_id,
                "operation": "unshare_collection",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionUnshares", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection unsharing",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_id": collection_id,
                "target_user_id": user_id,
                "operation": "unshare_collection",
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
