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
    validate_collection_access,
)

# Import centralized utilities
from user_auth import extract_user_context

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-item-addition",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-item-addition")
metrics = Metrics(namespace="medialake", service="collection-item-addition")

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
VALID_ITEM_TYPES = ["asset", "workflow", "collection"]
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
        request_context = event.get("requestContext")
        if not isinstance(request_context, dict):
            logger.debug(
                {
                    "message": "No valid requestContext found",
                    "request_context_type": type(request_context).__name__,
                    "operation": "extract_user_context",
                }
            )
            return {"user_id": None, "username": None}

        authorizer = request_context.get("authorizer")
        if not isinstance(authorizer, dict):
            logger.debug(
                {
                    "message": "No valid authorizer found",
                    "authorizer_type": type(authorizer).__name__,
                    "operation": "extract_user_context",
                }
            )
            return {"user_id": None, "username": None}

        claims = authorizer.get("claims")

        # Handle claims as either dict or JSON string
        if isinstance(claims, str):
            try:
                import json

                claims = json.loads(claims)
                logger.debug(
                    {
                        "message": "Parsed claims from JSON string",
                        "operation": "extract_user_context",
                    }
                )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    {
                        "message": "Failed to parse claims JSON string",
                        "error": str(e),
                        "claims_preview": (
                            claims[:200]
                            if isinstance(claims, str)
                            else str(claims)[:200]
                        ),
                        "operation": "extract_user_context",
                    }
                )
                return {"user_id": None, "username": None}
        elif not isinstance(claims, dict):
            logger.debug(
                {
                    "message": "Claims is neither dict nor string",
                    "claims_type": type(claims).__name__,
                    "operation": "extract_user_context",
                }
            )
            return {"user_id": None, "username": None}

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
                "event_keys": (
                    list(event.keys()) if isinstance(event, dict) else "event_not_dict"
                ),
            }
        )
        return {"user_id": None, "username": None}


@tracer.capture_method
def validate_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection item addition request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate required fields
    if not request_data.get("type"):
        errors.append(
            {
                "field": "type",
                "message": "Item type is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif request_data["type"] not in VALID_ITEM_TYPES:
        errors.append(
            {
                "field": "type",
                "message": f"Invalid item type. Valid options: {', '.join(VALID_ITEM_TYPES)}",
                "code": "INVALID_VALUE",
            }
        )

    if not request_data.get("id"):
        errors.append(
            {"field": "id", "message": "Item ID is required", "code": "REQUIRED_FIELD"}
        )
    elif (
        not isinstance(request_data["id"], str) or len(request_data["id"].strip()) == 0
    ):
        errors.append(
            {
                "field": "id",
                "message": "Item ID must be a non-empty string",
                "code": "INVALID_VALUE",
            }
        )

    # Validate optional fields
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

    # Validate metadata if provided
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
            "message": "Request data validation completed",
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_request_data",
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
def check_item_duplicate(table, collection_id: str, item_id: str) -> bool:
    """
    Check if item already exists in the collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        item_id: Item ID to check

    Returns:
        True if item already exists, False otherwise
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{ITEM_SK_PREFIX}{item_id}",
            }
        )

        exists = "Item" in response
        logger.debug(
            {
                "message": "Item duplicate check completed",
                "collection_id": collection_id,
                "item_id": item_id,
                "exists": exists,
                "operation": "check_item_duplicate",
            }
        )

        return exists

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to check item duplicate",
                "collection_id": collection_id,
                "item_id": item_id,
                "error": str(e),
                "operation": "check_item_duplicate",
            }
        )
        return False


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
    }

    logger.debug(
        {
            "message": "Collection item formatted for response",
            "item_id": item_id,
            "operation": "format_item_response",
        }
    )

    return formatted_item


@app.post("/collections/<collection_id>/items")
@tracer.capture_method
def add_collection_item(collection_id: str):
    """Add a single item to collection"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection item addition attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "add_collection_item",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to add items to collections",
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
                "message": "Processing collection item addition request",
                "collection_id": collection_id,
                "request_data": request_data,
                "user_id": user_id,
                "operation": "add_collection_item",
            }
        )

        # Validate request data
        validation_errors = validate_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Collection item addition request validation failed",
                    "collection_id": collection_id,
                    "errors": validation_errors,
                    "operation": "add_collection_item",
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
                    "error_code": error_code,
                    "operation": "add_collection_item",
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

        access_result["collection"]
        item_id = request_data["id"]
        item_type = request_data["type"]

        # Check for duplicate item
        if check_item_duplicate(table, collection_id, item_id):
            logger.warning(
                {
                    "message": "Item already exists in collection",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "operation": "add_collection_item",
                }
            )

            return {
                "statusCode": 409,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "ITEM_ALREADY_EXISTS",
                            "message": f"Item '{item_id}' already exists in this collection",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Prepare item data
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        collection_item = {
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": f"{ITEM_SK_PREFIX}{item_id}",
            "itemType": item_type.upper(),
            "addedAt": current_timestamp,
            "addedBy": user_id,
            "sortOrder": request_data.get("sortOrder", 0),
            # GSI2 attributes for reverse lookup (item -> collections)
            "GSI2PK": f"ITEM#{item_id}",
            "GSI2SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
        }

        # Add optional metadata if provided
        if request_data.get("metadata"):
            collection_item["metadata"] = request_data["metadata"]

        # Prepare transactional write items
        transact_items = [
            {
                "Put": {
                    "TableName": TABLE_NAME,
                    "Item": collection_item,
                    "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
                }
            },
            {
                "Update": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                        "SK": METADATA_SK,
                    },
                    "UpdateExpression": "ADD itemCount :inc SET updatedAt = :timestamp",
                    "ExpressionAttributeValues": {
                        ":inc": 1,
                        ":timestamp": current_timestamp,
                    },
                    "ConditionExpression": "attribute_exists(PK)",
                }
            },
        ]

        logger.debug(
            {
                "message": "Prepared transactional items for collection item addition",
                "collection_id": collection_id,
                "item_id": item_id,
                "transaction_item_count": len(transact_items),
                "operation": "add_collection_item",
            }
        )

        # Execute transactional write
        try:
            dynamodb.meta.client.transact_write_items(TransactItems=transact_items)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    {
                        "message": "Collection item addition failed - conditional check failed",
                        "collection_id": collection_id,
                        "item_id": item_id,
                        "error": str(e),
                        "operation": "add_collection_item",
                    }
                )
                return {
                    "statusCode": 409,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "ITEM_ALREADY_EXISTS",
                                "message": "Item already exists in collection or collection was modified",
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
                "message": "Collection item added successfully",
                "collection_id": collection_id,
                "item_id": item_id,
                "item_type": item_type,
                "user_id": user_id,
                "operation": "add_collection_item",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionItemAdditions", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_item_response(collection_item, item_id)

        return {
            "statusCode": 201,
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
                "message": "DynamoDB client error during collection item addition",
                "collection_id": collection_id,
                "error_code": error_code,
                "error_message": error_message,
                "item_data": request_data.get("id"),
                "user_id": user_context.get("user_id"),
                "operation": "add_collection_item",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionItemAdditions", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection item addition",
                "collection_id": collection_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "item_data": request_data.get("id"),
                "user_id": user_context.get("user_id"),
                "operation": "add_collection_item",
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
