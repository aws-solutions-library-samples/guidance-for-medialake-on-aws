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
    service="collection-item-update",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-item-update")
metrics = Metrics(namespace="medialake", service="collection-item-update")

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
MAX_SORT_ORDER = 999999


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
def validate_update_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection item update request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # At least one field must be provided for update
    if not request_data.get("sortOrder") and not request_data.get("metadata"):
        errors.append(
            {
                "field": "request",
                "message": "At least one of 'sortOrder' or 'metadata' must be provided",
                "code": "REQUIRED_FIELD",
            }
        )

    # Validate optional sortOrder field
    if request_data.get("sortOrder") is not None:
        sort_order = request_data["sortOrder"]
        if (
            not isinstance(sort_order, int)
            or sort_order < 0
            or sort_order > MAX_SORT_ORDER
        ):
            errors.append(
                {
                    "field": "sortOrder",
                    "message": f"Sort order must be an integer between 0 and {MAX_SORT_ORDER}",
                    "code": "INVALID_VALUE",
                }
            )

    # Validate optional metadata field
    if request_data.get("metadata"):
        if not isinstance(request_data["metadata"], dict):
            errors.append(
                {
                    "field": "metadata",
                    "message": "Metadata must be a valid JSON object",
                    "code": "INVALID_TYPE",
                }
            )

    logger.debug(
        {
            "message": "Update request data validation completed",
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_update_request_data",
        }
    )

    return errors


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
def update_collection_item_data(
    table, collection_id: str, item_id: str, update_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update collection item with new data

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        item_id: Item ID
        update_data: Data to update

    Returns:
        Dictionary with 'success' boolean and optional updated 'item' data
    """
    try:
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Build update expression dynamically
        update_expressions = []
        expression_values = {}
        expression_names = {}

        # Always update the updatedAt timestamp
        update_expressions.append("#updatedAt = :timestamp")
        expression_names["#updatedAt"] = "updatedAt"
        expression_values[":timestamp"] = current_timestamp

        # Add sortOrder if provided
        if "sortOrder" in update_data:
            update_expressions.append("sortOrder = :sortOrder")
            expression_values[":sortOrder"] = update_data["sortOrder"]

        # Add metadata if provided
        if "metadata" in update_data:
            update_expressions.append("metadata = :metadata")
            expression_values[":metadata"] = update_data["metadata"]

        update_expression = "SET " + ", ".join(update_expressions)

        # Perform conditional update
        response = table.update_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{ITEM_SK_PREFIX}{item_id}",
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ConditionExpression="attribute_exists(PK)",
            ReturnValues="ALL_NEW",
        )

        updated_item = response.get("Attributes", {})

        logger.info(
            {
                "message": "Collection item updated successfully",
                "collection_id": collection_id,
                "item_id": item_id,
                "updated_fields": list(update_data.keys()),
                "operation": "update_collection_item_data",
            }
        )

        return {"success": True, "item": updated_item}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")

        if error_code == "ConditionalCheckFailedException":
            logger.warning(
                {
                    "message": "Collection item not found for update",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "update_collection_item_data",
                }
            )
            return {"success": False, "error": "ITEM_NOT_FOUND"}

        logger.error(
            {
                "message": "Failed to update collection item",
                "collection_id": collection_id,
                "item_id": item_id,
                "error_code": error_code,
                "error": str(e),
                "operation": "update_collection_item_data",
            }
        )
        return {"success": False, "error": error_code or "UPDATE_FAILED"}


@tracer.capture_method
def format_item_response(item: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: DynamoDB item
        item_id: Item ID

    Returns:
        Formatted collection item object
    """
    formatted_item = {
        "id": f"item_{item_id}",  # Generate item record ID
        "itemType": item.get("itemType", "").lower(),
        "itemId": item_id,
        "sortOrder": item.get("sortOrder", 0),
        "metadata": item.get("metadata", {}),
        "addedAt": item.get("addedAt", ""),
        "addedBy": item.get("addedBy", ""),
        "updatedAt": item.get("updatedAt", ""),
    }

    logger.debug(
        {
            "message": "Collection item formatted for response",
            "item_id": item_id,
            "operation": "format_item_response",
        }
    )

    return formatted_item


@app.put("/collections/<collection_id>/items/<item_id>")
@tracer.capture_method
def update_collection_item(collection_id: str, item_id: str):
    """Update item metadata within collection"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection item update attempted without valid user context",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "update_collection_item",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to update collection items",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing collection item update request",
                "collection_id": collection_id,
                "item_id": item_id,
                "request_data": request_data,
                "user_id": user_id,
                "operation": "update_collection_item",
            }
        )

        # Validate request data
        validation_errors = validate_update_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Collection item update request validation failed",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "errors": validation_errors,
                    "operation": "update_collection_item",
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
                    "operation": "update_collection_item",
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

        # Check if item exists in collection
        existing_result = get_existing_item(table, collection_id, item_id)
        if not existing_result["exists"]:
            logger.warning(
                {
                    "message": "Collection item not found for update",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "update_collection_item",
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

        # Prepare update data (only include fields that are provided)
        update_data = {}
        if "sortOrder" in request_data:
            update_data["sortOrder"] = request_data["sortOrder"]
        if "metadata" in request_data:
            update_data["metadata"] = request_data["metadata"]

        # Update the item
        update_result = update_collection_item_data(
            table, collection_id, item_id, update_data
        )
        if not update_result["success"]:
            error_code = update_result.get("error", "UPDATE_FAILED")

            if error_code == "ITEM_NOT_FOUND":
                status_code = 404
                message = f"Item '{item_id}' not found in collection"
            else:
                status_code = 500
                message = "Failed to update collection item"

            logger.error(
                {
                    "message": "Failed to update collection item",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "error_code": error_code,
                    "operation": "update_collection_item",
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

        updated_item = update_result["item"]

        logger.info(
            {
                "message": "Collection item updated successfully",
                "collection_id": collection_id,
                "item_id": item_id,
                "updated_fields": list(update_data.keys()),
                "user_id": user_id,
                "operation": "update_collection_item",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionItemUpdates", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_item_response(updated_item, item_id)

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
                "message": "DynamoDB client error during collection item update",
                "collection_id": collection_id,
                "item_id": item_id,
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_context.get("user_id"),
                "operation": "update_collection_item",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionItemUpdates", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection item update",
                "collection_id": collection_id,
                "item_id": item_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_id": user_context.get("user_id"),
                "operation": "update_collection_item",
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
