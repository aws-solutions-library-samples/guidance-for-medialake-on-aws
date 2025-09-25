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
    service="collection-deletion",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-deletion")
metrics = Metrics(namespace="medialake", service="collection-deletion")

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
VERSION_SK_PREFIX = "VERSION#"
USER_PK_PREFIX = "USER#"
COLLECTIONS_GSI5_PK = "COLLECTIONS"


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
def check_user_permissions(table, collection_id: str, user_id: str) -> bool:
    """
    Check if user has permission to delete the collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        user_id: User ID

    Returns:
        True if user has permission, False otherwise
    """
    try:
        # Get collection metadata to check owner
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        )

        if "Item" not in response:
            return False  # Collection doesn't exist

        collection = response["Item"]

        # Owner has full permissions
        if collection.get("ownerId") == user_id:
            return True

        # TODO: Check explicit permissions when permission system is implemented
        # For now, only owners can delete collections
        logger.debug(
            {
                "message": "Permission check completed",
                "collection_id": collection_id,
                "user_id": user_id,
                "is_owner": collection.get("ownerId") == user_id,
                "operation": "check_user_permissions",
            }
        )

        return False

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to check user permissions",
                "collection_id": collection_id,
                "user_id": user_id,
                "error": str(e),
                "operation": "check_user_permissions",
            }
        )
        return False


@tracer.capture_method
def get_child_collections(table, collection_id: str) -> List[str]:
    """
    Get list of child collection IDs

    Args:
        table: DynamoDB table resource
        collection_id: Parent collection ID

    Returns:
        List of child collection IDs
    """
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                ":sk_prefix": CHILD_SK_PREFIX,
            },
        )

        children = []
        for item in response.get("Items", []):
            child_id = item.get("childCollectionId")
            if child_id:
                children.append(child_id)

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
def collect_collection_items(table, collection_id: str) -> List[Dict[str, Any]]:
    """
    Collect all items that need to be deleted for a collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID

    Returns:
        List of items to delete
    """
    items_to_delete = []

    try:
        # Get all items related to this collection
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"{COLLECTION_PK_PREFIX}{collection_id}"},
        )

        for item in response.get("Items", []):
            items_to_delete.append({"PK": item["PK"], "SK": item["SK"]})

        # Get user relationship records
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression="SK = :sk",
            ExpressionAttributeValues={":sk": f"{COLLECTION_PK_PREFIX}{collection_id}"},
        )

        for item in response.get("Items", []):
            if item["PK"].startswith(USER_PK_PREFIX):
                items_to_delete.append({"PK": item["PK"], "SK": item["SK"]})

        logger.debug(
            {
                "message": "Collection items collected for deletion",
                "collection_id": collection_id,
                "item_count": len(items_to_delete),
                "operation": "collect_collection_items",
            }
        )

        return items_to_delete

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to collect collection items",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "collect_collection_items",
            }
        )
        return []


@tracer.capture_method
def delete_collection_cascade(table, collection_id: str, user_id: str) -> List[str]:
    """
    Recursively delete collection and all its children

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to delete
        user_id: User performing the deletion

    Returns:
        List of deleted collection IDs
    """
    deleted_collections = []

    try:
        # Get child collections first
        children = get_child_collections(table, collection_id)

        # Recursively delete children first
        for child_id in children:
            child_deleted = delete_collection_cascade(table, child_id, user_id)
            deleted_collections.extend(child_deleted)

        # Now delete this collection
        items_to_delete = collect_collection_items(table, collection_id)

        # Delete items in batches
        batch_size = 25  # DynamoDB batch write limit
        for i in range(0, len(items_to_delete), batch_size):
            batch = items_to_delete[i : i + batch_size]

            delete_requests = [{"DeleteRequest": {"Key": item}} for item in batch]

            dynamodb.meta.client.batch_write_item(
                RequestItems={TABLE_NAME: delete_requests}
            )

        deleted_collections.append(collection_id)

        logger.info(
            {
                "message": "Collection deleted with cascade",
                "collection_id": collection_id,
                "items_deleted": len(items_to_delete),
                "children_deleted": len(children),
                "operation": "delete_collection_cascade",
            }
        )

        return deleted_collections

    except Exception as e:
        logger.error(
            {
                "message": "Failed to delete collection with cascade",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "delete_collection_cascade",
            }
        )
        raise


@tracer.capture_method
def soft_delete_collection(table, collection_id: str, user_id: str) -> None:
    """
    Soft delete collection by setting status to DELETED

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to soft delete
        user_id: User performing the deletion
    """
    try:
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Update collection status to DELETED
        table.update_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
            UpdateExpression="SET #status = :status, updatedAt = :timestamp, deletedAt = :timestamp, deletedBy = :user_id",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "DELETED",
                ":timestamp": current_timestamp,
                ":user_id": user_id,
            },
            ConditionExpression="attribute_exists(PK)",
        )

        logger.info(
            {
                "message": "Collection soft deleted",
                "collection_id": collection_id,
                "user_id": user_id,
                "operation": "soft_delete_collection",
            }
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to soft delete collection",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "soft_delete_collection",
            }
        )
        raise


@tracer.capture_method
def update_parent_child_count(table, parent_id: str, collection_id: str) -> None:
    """
    Update parent collection's child count and remove child relationship

    Args:
        table: DynamoDB table resource
        parent_id: Parent collection ID
        collection_id: Child collection ID that was deleted
    """
    try:
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Remove child relationship record
        table.delete_item(
            Key={
                "PK": f"{COLLECTION_PK_PREFIX}{parent_id}",
                "SK": f"{CHILD_SK_PREFIX}{collection_id}",
            }
        )

        # Decrease parent's child count
        table.update_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{parent_id}", "SK": METADATA_SK},
            UpdateExpression="ADD childCollectionCount :dec SET updatedAt = :timestamp",
            ExpressionAttributeValues={":dec": -1, ":timestamp": current_timestamp},
            ConditionExpression="attribute_exists(PK) AND childCollectionCount > :zero",
            ExpressionAttributeValues={
                ":dec": -1,
                ":timestamp": current_timestamp,
                ":zero": 0,
            },
        )

        logger.debug(
            {
                "message": "Parent collection child count updated",
                "parent_id": parent_id,
                "deleted_child_id": collection_id,
                "operation": "update_parent_child_count",
            }
        )

    except ClientError as e:
        # Don't fail deletion if parent update fails
        logger.warning(
            {
                "message": "Failed to update parent collection child count",
                "parent_id": parent_id,
                "collection_id": collection_id,
                "error": str(e),
                "operation": "update_parent_child_count",
            }
        )


@app.delete("/collections/<collection_id>")
@tracer.capture_method
def delete_collection(collection_id: str):
    """Delete a collection with optional cascade"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection deletion attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "delete_collection",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to delete collections",
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
        cascade_param = app.current_event.get_query_string_value("cascade")
        cascade = cascade_param and cascade_param.lower() == "true"

        logger.debug(
            {
                "message": "Processing collection deletion request",
                "collection_id": collection_id,
                "cascade": cascade,
                "user_id": user_id,
                "operation": "delete_collection",
            }
        )

        table = dynamodb.Table(TABLE_NAME)

        # Check if user has permission to delete this collection
        if not check_user_permissions(table, collection_id, user_id):
            logger.warning(
                {
                    "message": "User does not have permission to delete collection",
                    "collection_id": collection_id,
                    "user_id": user_id,
                    "operation": "delete_collection",
                }
            )

            return {
                "statusCode": 403,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": "You don't have permission to delete this collection",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Get collection metadata to check if it exists and get parent info
        try:
            response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )
        except ClientError as e:
            logger.error(
                {
                    "message": "DynamoDB error retrieving collection for deletion",
                    "collection_id": collection_id,
                    "error": str(e),
                    "operation": "delete_collection",
                }
            )
            raise

        if "Item" not in response:
            logger.info(
                {
                    "message": "Collection not found for deletion",
                    "collection_id": collection_id,
                    "operation": "delete_collection",
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

        collection_item = response["Item"]
        current_status = collection_item.get("status", "ACTIVE")
        parent_id = collection_item.get("parentId")

        # Check if collection is already deleted
        if current_status == "DELETED":
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

        # Check for child collections if cascade is not enabled
        if not cascade:
            children = get_child_collections(table, collection_id)
            if children:
                logger.warning(
                    {
                        "message": "Cannot delete collection with children when cascade=false",
                        "collection_id": collection_id,
                        "child_count": len(children),
                        "operation": "delete_collection",
                    }
                )

                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "COLLECTION_HAS_CHILDREN",
                                "message": f"Collection has {len(children)} child collections. Use cascade=true to delete children or remove them first.",
                            },
                            "meta": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "version": "v1",
                                "request_id": app.current_event.request_context.request_id,
                            },
                        }
                    ),
                }

        # Perform deletion based on cascade option
        deleted_collections = []

        if cascade:
            # Hard delete with cascade
            deleted_collections = delete_collection_cascade(
                table, collection_id, user_id
            )
        else:
            # Soft delete single collection
            soft_delete_collection(table, collection_id, user_id)
            deleted_collections = [collection_id]

        # Update parent collection if this collection has a parent
        if parent_id:
            update_parent_child_count(table, parent_id, collection_id)

        logger.info(
            {
                "message": "Collection deletion completed successfully",
                "collection_id": collection_id,
                "cascade": cascade,
                "deleted_count": len(deleted_collections),
                "user_id": user_id,
                "operation": "delete_collection",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionDeletions", unit=MetricUnit.Count, value=1
        )

        if cascade:
            metrics.add_metric(
                name="CascadeCollectionDeletions",
                unit=MetricUnit.Count,
                value=len(deleted_collections),
            )

        # Return 204 No Content for successful deletion
        return {"statusCode": 204, "body": ""}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "DynamoDB client error during collection deletion",
                "error_code": error_code,
                "error_message": error_message,
                "collection_id": collection_id,
                "user_id": user_context.get("user_id"),
                "operation": "delete_collection",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionDeletions", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection deletion",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_id": collection_id,
                "user_id": user_context.get("user_id"),
                "operation": "delete_collection",
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
