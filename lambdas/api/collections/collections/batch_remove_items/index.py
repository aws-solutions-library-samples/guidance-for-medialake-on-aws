import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-batch-item-removal",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-batch-item-removal")
metrics = Metrics(namespace="medialake", service="collection-batch-item-removal")

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
MAX_BATCH_SIZE = 100
BATCH_WRITE_MAX_ITEMS = 25  # DynamoDB BatchWriteItem limit


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
def validate_batch_remove_request_data(
    request_data: Dict[str, Any],
) -> List[Dict[str, str]]:
    """
    Validate batch collection items removal request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate items array exists
    if not request_data.get("items"):
        errors.append(
            {
                "field": "items",
                "message": "Items array is required",
                "code": "REQUIRED_FIELD",
            }
        )
        return errors

    items = request_data["items"]

    # Validate items is an array
    if not isinstance(items, list):
        errors.append(
            {
                "field": "items",
                "message": "Items must be an array",
                "code": "INVALID_TYPE",
            }
        )
        return errors

    # Validate batch size
    if len(items) == 0:
        errors.append(
            {
                "field": "items",
                "message": "At least one item is required",
                "code": "INVALID_VALUE",
            }
        )
    elif len(items) > MAX_BATCH_SIZE:
        errors.append(
            {
                "field": "items",
                "message": f"Maximum {MAX_BATCH_SIZE} items allowed per batch",
                "code": "INVALID_VALUE",
            }
        )

    # Validate each item in the batch
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(
                {
                    "field": f"items[{index}]",
                    "message": "Each item must be an object",
                    "code": "INVALID_TYPE",
                }
            )
            continue

        # Validate required fields for each item
        if not item.get("type"):
            errors.append(
                {
                    "field": f"items[{index}].type",
                    "message": "Item type is required",
                    "code": "REQUIRED_FIELD",
                }
            )
        elif item["type"] not in VALID_ITEM_TYPES:
            errors.append(
                {
                    "field": f"items[{index}].type",
                    "message": f"Invalid item type. Valid options: {', '.join(VALID_ITEM_TYPES)}",
                    "code": "INVALID_VALUE",
                }
            )

        if not item.get("id"):
            errors.append(
                {
                    "field": f"items[{index}].id",
                    "message": "Item ID is required",
                    "code": "REQUIRED_FIELD",
                }
            )
        elif not isinstance(item["id"], str) or len(item["id"].strip()) == 0:
            errors.append(
                {
                    "field": f"items[{index}].id",
                    "message": "Item ID must be a non-empty string",
                    "code": "INVALID_VALUE",
                }
            )

    # Check for duplicate item IDs within the batch
    item_ids = [item.get("id") for item in items if item.get("id")]
    if len(item_ids) != len(set(item_ids)):
        errors.append(
            {
                "field": "items",
                "message": "Duplicate item IDs found within the batch",
                "code": "DUPLICATE_VALUES",
            }
        )

    logger.debug(
        {
            "message": "Batch remove request data validation completed",
            "item_count": len(items),
            "error_count": len(errors),
            "errors": errors,
            "operation": "validate_batch_remove_request_data",
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
def check_existing_items_for_removal(
    table, collection_id: str, item_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Check which items exist in the collection for removal

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        item_ids: List of item IDs to check

    Returns:
        Dictionary mapping item IDs to their full item data (if they exist)
    """
    existing_items = {}

    # Use batch_get_item for efficient checking
    batch_keys = []
    for item_id in item_ids:
        batch_keys.append(
            {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{ITEM_SK_PREFIX}{item_id}",
            }
        )

    # DynamoDB batch_get_item has a limit of 100 items, but we already validate batch size
    try:
        response = dynamodb.batch_get_item(
            RequestItems={TABLE_NAME: {"Keys": batch_keys}}
        )

        # Store found items with their full data
        for item in response.get("Responses", {}).get(TABLE_NAME, []):
            item_id = item["SK"].replace(ITEM_SK_PREFIX, "")
            existing_items[item_id] = item

        logger.debug(
            {
                "message": "Existing items check for removal completed",
                "collection_id": collection_id,
                "total_checked": len(item_ids),
                "existing_count": len(existing_items),
                "operation": "check_existing_items_for_removal",
            }
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to check existing items for removal",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "check_existing_items_for_removal",
            }
        )
        # In case of error, return empty dict
        existing_items = {}

    return existing_items


@tracer.capture_method
def process_batch_remove_items(
    table,
    collection_id: str,
    items: List[Dict[str, Any]],
    user_id: str,
    existing_items: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """
    Process batch items for removal from collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        items: List of items to remove
        user_id: User ID removing the items
        existing_items: Dictionary mapping item IDs to their full data

    Returns:
        Tuple of (successful_items, error_items, successful_count)
    """
    successful_items = []
    error_items = []

    # Prepare items for batch delete
    delete_requests = []

    for index, item_data in enumerate(items):
        item_id = item_data.get("id")
        item_type = item_data.get("type")

        try:
            # Check if item exists in collection
            if item_id not in existing_items:
                error_items.append(
                    {
                        "index": index,
                        "id": item_id,
                        "error": "NOT_FOUND",
                        "detail": f"Item '{item_id}' not found in this collection",
                    }
                )
                continue

            existing_item = existing_items[item_id]

            # Verify item type matches (optional validation)
            if existing_item.get("itemType", "").upper() != item_type.upper():
                error_items.append(
                    {
                        "index": index,
                        "id": item_id,
                        "error": "TYPE_MISMATCH",
                        "detail": f"Item type mismatch. Expected '{existing_item.get('itemType', '')}', got '{item_type}'",
                    }
                )
                continue

            # Prepare delete request
            delete_requests.append(
                {
                    "DeleteRequest": {
                        "Key": {
                            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                            "SK": f"{ITEM_SK_PREFIX}{item_id}",
                        }
                    }
                }
            )

            # Add to successful items list for response (using existing item data)
            successful_items.append(
                {
                    "id": f"item_{item_id}",
                    "itemType": existing_item.get("itemType", "").lower(),
                    "itemId": item_id,
                    "sortOrder": existing_item.get("sortOrder", 0),
                    "metadata": existing_item.get("metadata", {}),
                    "addedAt": existing_item.get("addedAt", ""),
                    "addedBy": existing_item.get("addedBy", ""),
                    "removedAt": datetime.utcnow().isoformat() + "Z",
                    "removedBy": user_id,
                }
            )

        except Exception as e:
            logger.error(
                {
                    "message": "Failed to process batch remove item",
                    "collection_id": collection_id,
                    "item_id": item_id,
                    "index": index,
                    "error": str(e),
                    "operation": "process_batch_remove_items",
                }
            )
            error_items.append(
                {
                    "index": index,
                    "id": item_id,
                    "error": "PROCESSING_ERROR",
                    "detail": f"Failed to process item removal: {str(e)}",
                }
            )

    # Execute batch deletes in chunks
    successful_count = 0
    if delete_requests:
        successful_count = execute_batch_deletes(table, delete_requests, error_items)

    logger.debug(
        {
            "message": "Batch items removal processing completed",
            "collection_id": collection_id,
            "total_items": len(items),
            "successful_count": successful_count,
            "error_count": len(error_items),
            "operation": "process_batch_remove_items",
        }
    )

    return successful_items[:successful_count], error_items, successful_count


@tracer.capture_method
def execute_batch_deletes(
    table, delete_requests: List[Dict], error_items: List[Dict]
) -> int:
    """
    Execute batch deletes from DynamoDB in chunks

    Args:
        table: DynamoDB table resource
        delete_requests: List of delete requests
        error_items: List to append errors to

    Returns:
        Number of successfully deleted items
    """
    successful_count = 0

    # Split delete requests into chunks of 25 (DynamoDB limit)
    for i in range(0, len(delete_requests), BATCH_WRITE_MAX_ITEMS):
        chunk = delete_requests[i : i + BATCH_WRITE_MAX_ITEMS]

        try:
            response = dynamodb.batch_write_item(RequestItems={TABLE_NAME: chunk})

            # Handle unprocessed items
            unprocessed = response.get("UnprocessedItems", {}).get(TABLE_NAME, [])
            successful_in_chunk = len(chunk) - len(unprocessed)
            successful_count += successful_in_chunk

            # Retry unprocessed items (simplified - in production might want exponential backoff)
            if unprocessed:
                logger.warning(
                    {
                        "message": "Some items were unprocessed in batch delete",
                        "unprocessed_count": len(unprocessed),
                        "chunk_start_index": i,
                        "operation": "execute_batch_deletes",
                    }
                )

                # Try once more for unprocessed items
                try:
                    retry_response = dynamodb.batch_write_item(
                        RequestItems={TABLE_NAME: unprocessed}
                    )

                    retry_unprocessed = retry_response.get("UnprocessedItems", {}).get(
                        TABLE_NAME, []
                    )
                    successful_count += len(unprocessed) - len(retry_unprocessed)

                    # Log remaining unprocessed items as errors
                    for unprocessed_item in retry_unprocessed:
                        item_sk = unprocessed_item["DeleteRequest"]["Key"]["SK"]
                        item_id = item_sk.replace(ITEM_SK_PREFIX, "")
                        error_items.append(
                            {
                                "index": i + chunk.index(unprocessed_item),
                                "id": item_id,
                                "error": "DELETE_FAILED",
                                "detail": "Failed to delete item after retry",
                            }
                        )

                except ClientError as retry_e:
                    logger.error(
                        {
                            "message": "Retry batch delete failed",
                            "error": str(retry_e),
                            "operation": "execute_batch_deletes",
                        }
                    )
                    # Mark all retry items as failed
                    for unprocessed_item in unprocessed:
                        item_sk = unprocessed_item["DeleteRequest"]["Key"]["SK"]
                        item_id = item_sk.replace(ITEM_SK_PREFIX, "")
                        error_items.append(
                            {
                                "index": i + chunk.index(unprocessed_item),
                                "id": item_id,
                                "error": "DELETE_FAILED",
                                "detail": f"Batch delete failed: {str(retry_e)}",
                            }
                        )

        except ClientError as e:
            logger.error(
                {
                    "message": "Batch delete failed",
                    "chunk_start_index": i,
                    "chunk_size": len(chunk),
                    "error": str(e),
                    "operation": "execute_batch_deletes",
                }
            )

            # Mark all items in this chunk as failed
            for j, request in enumerate(chunk):
                item_sk = request["DeleteRequest"]["Key"]["SK"]
                item_id = item_sk.replace(ITEM_SK_PREFIX, "")
                error_items.append(
                    {
                        "index": i + j,
                        "id": item_id,
                        "error": "DELETE_FAILED",
                        "detail": f"Batch delete failed: {str(e)}",
                    }
                )

    return successful_count


@tracer.capture_method
def update_collection_item_count(table, collection_id: str, decrement: int) -> bool:
    """
    Update collection item count by decrementing

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        decrement: Number to subtract from item count

    Returns:
        True if successful, False otherwise
    """
    if decrement == 0:
        return True

    try:
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        table.update_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
            UpdateExpression="ADD itemCount :dec SET updatedAt = :timestamp",
            ExpressionAttributeValues={
                ":dec": -decrement,  # Negative value to decrement
                ":timestamp": current_timestamp,
            },
            ConditionExpression="attribute_exists(PK)",
        )

        logger.debug(
            {
                "message": "Collection item count decremented",
                "collection_id": collection_id,
                "decrement": decrement,
                "operation": "update_collection_item_count",
            }
        )

        return True

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to update collection item count",
                "collection_id": collection_id,
                "decrement": decrement,
                "error": str(e),
                "operation": "update_collection_item_count",
            }
        )
        return False


@app.post("/collections/<collection_id>/items/batch-remove")
@tracer.capture_method
def batch_remove_items(collection_id: str):
    """Remove multiple items from collection in batch operation"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Batch collection items removal attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "batch_remove_items",
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

        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing batch collection items removal request",
                "collection_id": collection_id,
                "item_count": len(request_data.get("items", [])),
                "user_id": user_id,
                "operation": "batch_remove_items",
            }
        )

        # Validate request data
        validation_errors = validate_batch_remove_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Batch collection items removal request validation failed",
                    "collection_id": collection_id,
                    "errors": validation_errors,
                    "operation": "batch_remove_items",
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
        items = request_data["items"]

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
                    "operation": "batch_remove_items",
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

        # Check for existing items
        item_ids = [item["id"] for item in items]
        existing_items = check_existing_items_for_removal(
            table, collection_id, item_ids
        )

        # Process batch items for removal
        successful_items, error_items, successful_count = process_batch_remove_items(
            table, collection_id, items, user_id, existing_items
        )

        # Update collection item count
        if successful_count > 0:
            update_collection_item_count(table, collection_id, successful_count)

        logger.info(
            {
                "message": "Batch collection items removal completed",
                "collection_id": collection_id,
                "total_processed": len(items),
                "successful_count": successful_count,
                "failed_count": len(error_items),
                "user_id": user_id,
                "operation": "batch_remove_items",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulBatchItemRemovals", unit=MetricUnit.Count, value=1
        )
        metrics.add_metric(
            name="BatchItemsProcessedForRemoval",
            unit=MetricUnit.Count,
            value=len(items),
        )
        metrics.add_metric(
            name="BatchItemsRemovedSuccessfully",
            unit=MetricUnit.Count,
            value=successful_count,
        )
        metrics.add_metric(
            name="BatchItemRemovalsFailed",
            unit=MetricUnit.Count,
            value=len(error_items),
        )

        # Create response
        response_data = {
            "success": True,
            "data": successful_items,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "v1",
                "request_id": app.current_event.request_context.request_id,
                "processed": len(items),
                "successful": successful_count,
                "failed": len(error_items),
            },
        }

        # Add errors array if there were any failures
        if error_items:
            response_data["errors"] = error_items

        return {"statusCode": 200, "body": json.dumps(response_data)}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during batch collection items removal",
                "collection_id": collection_id,
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_context.get("user_id"),
                "operation": "batch_remove_items",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedBatchItemRemovals", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during batch collection items removal",
                "collection_id": collection_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_id": user_context.get("user_id"),
                "operation": "batch_remove_items",
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
