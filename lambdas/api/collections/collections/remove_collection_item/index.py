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
    service="collection-item-removal",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-item-removal")
metrics = Metrics(namespace="medialake", service="collection-item-removal")

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
ITEM_SK_PREFIX = "ITEM#"
METADATA_SK = "METADATA"


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
def validate_collection_access(
    table, collection_id: str, user_id: Optional[str]
) -> Dict[str, Any]:
    """
    Validate that the collection exists and user has write access

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to validate
        user_id: User ID requesting access

    Returns:
        Dictionary with 'valid' boolean and optional 'collection' data
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
            return {"valid": False, "error": "COLLECTION_NOT_FOUND"}

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
            return {"valid": False, "error": "COLLECTION_NOT_ACTIVE"}

        # Check if user has write access (owner or has write permissions)
        if user_id and item.get("ownerId") == user_id:
            logger.debug(
                {
                    "message": "Collection write access granted - user is owner",
                    "collection_id": collection_id,
                    "operation": "validate_collection_access",
                }
            )
            return {"valid": True, "collection": item}

        # TODO: Check user permissions for non-owned collections
        # For now, deny write access for non-owners (simplified logic)
        logger.warning(
            {
                "message": "Collection write access denied - user is not owner",
                "collection_id": collection_id,
                "user_id": user_id,
                "owner_id": item.get("ownerId"),
                "operation": "validate_collection_access",
            }
        )
        return {"valid": False, "error": "INSUFFICIENT_PERMISSIONS"}

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate collection access",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "validate_collection_access",
            }
        )
        return {"valid": False, "error": "VALIDATION_FAILED"}


@tracer.capture_method
def get_existing_item(table, collection_id: str, item_id: str) -> Dict[str, Any]:
    """
    Get existing collection item

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        item_id: Item ID

    Returns:
        Dictionary with 'exists' boolean and optional 'item' data
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{ITEM_SK_PREFIX}{item_id}",
            }
        )

        item = response.get("Item")
        if not item:
            logger.debug(
                {
                    "message": "Collection item not found",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "get_existing_item",
                }
            )
            return {"exists": False}

        logger.debug(
            {
                "message": "Collection item found",
                "collection_id": collection_id,
                "item_id": item_id,
                "operation": "get_existing_item",
            }
        )

        return {"exists": True, "item": item}

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get existing collection item",
                "collection_id": collection_id,
                "item_id": item_id,
                "error": str(e),
                "operation": "get_existing_item",
            }
        )
        return {"exists": False, "error": str(e)}


@tracer.capture_method
def remove_collection_item_data(
    table, collection_id: str, item_id: str
) -> Dict[str, Any]:
    """
    Remove collection item and update collection item count

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        item_id: Item ID

    Returns:
        Dictionary with 'success' boolean and optional error information
    """
    try:
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Prepare transactional write items
        transact_items = [
            {
                "Delete": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                        "SK": f"{ITEM_SK_PREFIX}{item_id}",
                    },
                    "ConditionExpression": "attribute_exists(PK)",
                }
            },
            {
                "Update": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                        "SK": METADATA_SK,
                    },
                    "UpdateExpression": "ADD itemCount :dec SET updatedAt = :timestamp",
                    "ExpressionAttributeValues": {
                        ":dec": -1,  # Decrement by 1
                        ":timestamp": current_timestamp,
                    },
                    "ConditionExpression": "attribute_exists(PK)",
                }
            },
        ]

        # Execute transactional write
        dynamodb.meta.client.transact_write_items(TransactItems=transact_items)

        logger.info(
            {
                "message": "Collection item removed successfully",
                "collection_id": collection_id,
                "item_id": item_id,
                "operation": "remove_collection_item_data",
            }
        )

        return {"success": True}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")

        if error_code == "ConditionalCheckFailedException":
            logger.warning(
                {
                    "message": "Collection item not found for removal",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "remove_collection_item_data",
                }
            )
            return {"success": False, "error": "ITEM_NOT_FOUND"}

        logger.error(
            {
                "message": "Failed to remove collection item",
                "collection_id": collection_id,
                "item_id": item_id,
                "error_code": error_code,
                "error": str(e),
                "operation": "remove_collection_item_data",
            }
        )
        return {"success": False, "error": error_code or "REMOVAL_FAILED"}


@app.delete("/collections/<collection_id>/items/<item_id>")
@tracer.capture_method
def remove_collection_item(collection_id: str, item_id: str):
    """Remove single item from collection"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection item removal attempted without valid user context",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "remove_collection_item",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to remove items from collections",
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
                "message": "Processing collection item removal request",
                "collection_id": collection_id,
                "item_id": item_id,
                "user_id": user_id,
                "operation": "remove_collection_item",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Validate collection access
        access_result = validate_collection_access(table, collection_id, user_id)
        if not access_result["valid"]:
            error_code = access_result["error"]

            if error_code == "COLLECTION_NOT_FOUND":
                status_code = 404
                message = "Collection not found"
            elif error_code == "COLLECTION_NOT_ACTIVE":
                status_code = 400
                message = "Collection is not active"
            elif error_code == "INSUFFICIENT_PERMISSIONS":
                status_code = 403
                message = "Insufficient permissions to modify this collection"
            else:
                status_code = 500
                message = "Failed to validate collection access"

            logger.warning(
                {
                    "message": "Collection access validation failed",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "error_code": error_code,
                    "operation": "remove_collection_item",
                }
            )

            return {
                "statusCode": status_code,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {"code": error_code, "message": message},
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Check if item exists in collection before attempting removal
        existing_result = get_existing_item(table, collection_id, item_id)
        if not existing_result["exists"]:
            logger.warning(
                {
                    "message": "Collection item not found for removal",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "remove_collection_item",
                }
            )

            return {
                "statusCode": 404,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "ITEM_NOT_FOUND",
                            "message": f"Item '{item_id}' not found in collection '{collection_id}'",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Remove the item and update collection count
        removal_result = remove_collection_item_data(table, collection_id, item_id)
        if not removal_result["success"]:
            error_code = removal_result.get("error", "REMOVAL_FAILED")

            if error_code == "ITEM_NOT_FOUND":
                status_code = 404
                message = f"Item '{item_id}' not found in collection"
            else:
                status_code = 500
                message = "Failed to remove collection item"

            logger.error(
                {
                    "message": "Failed to remove collection item",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "error_code": error_code,
                    "operation": "remove_collection_item",
                }
            )

            return {
                "statusCode": status_code,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {"code": error_code, "message": message},
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        logger.info(
            {
                "message": "Collection item removed successfully",
                "collection_id": collection_id,
                "item_id": item_id,
                "user_id": user_id,
                "operation": "remove_collection_item",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionItemRemovals", unit=MetricUnit.Count, value=1
        )

        # Return 204 No Content for successful deletion
        return {"statusCode": 204, "body": ""}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection item removal",
                "collection_id": collection_id,
                "item_id": item_id,
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_context.get("user_id"),
                "operation": "remove_collection_item",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionItemRemovals", unit=MetricUnit.Count, value=1
        )

        # Map specific DynamoDB errors to appropriate HTTP status codes
        status_code = 500
        if error_code in ["ValidationException", "ConditionalCheckFailedException"]:
            status_code = 400

        return {
            "statusCode": status_code,
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
                "message": "Unexpected error during collection item removal",
                "collection_id": collection_id,
                "item_id": item_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_id": user_context.get("user_id"),
                "operation": "remove_collection_item",
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
