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
    service="collection-update",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-update")
metrics = Metrics(namespace="medialake", service="collection-update")

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
VERSION_SK_PREFIX = "VERSION#"
USER_PK_PREFIX = "USER#"
COLLECTIONS_GSI5_PK = "COLLECTIONS"
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
VALID_STATUSES = ["ACTIVE", "ARCHIVED"]
ALLOWED_UPDATE_FIELDS = ["name", "description", "metadata", "tags", "status"]


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
    Validate collection update request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check if any invalid fields are provided
    invalid_fields = set(request_data.keys()) - set(ALLOWED_UPDATE_FIELDS)
    if invalid_fields:
        for field in invalid_fields:
            errors.append(
                {
                    "field": field,
                    "message": f"Field '{field}' cannot be updated",
                    "code": "INVALID_FIELD",
                }
            )

    # Validate name if provided
    if "name" in request_data:
        if not request_data["name"]:
            errors.append(
                {
                    "field": "name",
                    "message": "Collection name cannot be empty",
                    "code": "INVALID_VALUE",
                }
            )
        elif len(request_data["name"]) > MAX_NAME_LENGTH:
            errors.append(
                {
                    "field": "name",
                    "message": f"Collection name must be {MAX_NAME_LENGTH} characters or less",
                    "code": "INVALID_LENGTH",
                }
            )

    # Validate description if provided
    if "description" in request_data:
        if (
            request_data["description"]
            and len(request_data["description"]) > MAX_DESCRIPTION_LENGTH
        ):
            errors.append(
                {
                    "field": "description",
                    "message": f"Description must be {MAX_DESCRIPTION_LENGTH} characters or less",
                    "code": "INVALID_LENGTH",
                }
            )

    # Validate metadata if provided
    if "metadata" in request_data:
        if request_data["metadata"] is not None and not isinstance(
            request_data["metadata"], dict
        ):
            errors.append(
                {
                    "field": "metadata",
                    "message": "Metadata must be a valid JSON object or null",
                    "code": "INVALID_TYPE",
                }
            )

    # Validate tags if provided
    if "tags" in request_data:
        if request_data["tags"] is not None:
            if not isinstance(request_data["tags"], dict):
                errors.append(
                    {
                        "field": "tags",
                        "message": "Tags must be a valid JSON object or null",
                        "code": "INVALID_TYPE",
                    }
                )
            else:
                # Validate tag values are strings
                for key, value in request_data["tags"].items():
                    if not isinstance(value, str):
                        errors.append(
                            {
                                "field": f"tags.{key}",
                                "message": "Tag values must be strings",
                                "code": "INVALID_TYPE",
                            }
                        )

    # Validate status if provided
    if "status" in request_data:
        if request_data["status"] not in VALID_STATUSES:
            errors.append(
                {
                    "field": "status",
                    "message": f"Status must be one of: {', '.join(VALID_STATUSES)}",
                    "code": "INVALID_VALUE",
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
def validate_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if status transition is allowed

    Args:
        current_status: Current collection status
        new_status: Requested new status

    Returns:
        True if transition is allowed, False otherwise
    """
    # Define allowed transitions
    allowed_transitions = {"ACTIVE": ["ARCHIVED"], "ARCHIVED": ["ACTIVE"]}

    if current_status == new_status:
        return True  # No change is always allowed

    if current_status == "DELETED":
        return False  # Cannot change status of deleted collections

    return new_status in allowed_transitions.get(current_status, [])


@tracer.capture_method
def check_user_permissions(
    table, collection_id: str, user_id: str, required_permission: str = "update"
) -> bool:
    """
    Check if user has permission to update the collection

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        user_id: User ID
        required_permission: Required permission level

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
        # For now, only owners can update collections
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
def build_update_expression(
    request_data: Dict[str, Any], current_item: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build DynamoDB update expression from request data

    Args:
        request_data: Request payload with updates
        current_item: Current collection item

    Returns:
        Dictionary with UpdateExpression and ExpressionAttributeValues
    """
    update_expressions = []
    expression_values = {}
    expression_names = {}
    changes = []
    current_timestamp = datetime.utcnow().isoformat() + "Z"

    # Always update the timestamp
    update_expressions.append("updatedAt = :updated_at")
    expression_values[":updated_at"] = current_timestamp

    # Update GSI5 sort key for recent collections queries
    update_expressions.append("GSI5SK = :gsi5_sk")
    expression_values[":gsi5_sk"] = current_timestamp

    # Handle each field that can be updated
    if "name" in request_data:
        update_expressions.append("#name = :name")
        expression_names["#name"] = "name"
        expression_values[":name"] = request_data["name"]
        changes.append(
            {
                "field": "name",
                "old_value": current_item.get("name"),
                "new_value": request_data["name"],
            }
        )

    if "description" in request_data:
        if request_data["description"]:
            update_expressions.append("description = :description")
            expression_values[":description"] = request_data["description"]
        else:
            # Remove description if empty string or null
            update_expressions.append("REMOVE description")
        changes.append(
            {
                "field": "description",
                "old_value": current_item.get("description"),
                "new_value": request_data["description"],
            }
        )

    if "metadata" in request_data:
        if request_data["metadata"]:
            update_expressions.append("customMetadata = :metadata")
            expression_values[":metadata"] = request_data["metadata"]
        else:
            # Remove metadata if null
            update_expressions.append("REMOVE customMetadata")
        changes.append(
            {
                "field": "metadata",
                "old_value": current_item.get("customMetadata"),
                "new_value": request_data["metadata"],
            }
        )

    if "tags" in request_data:
        if request_data["tags"]:
            update_expressions.append("tags = :tags")
            expression_values[":tags"] = request_data["tags"]
        else:
            # Remove tags if null
            update_expressions.append("REMOVE tags")
        changes.append(
            {
                "field": "tags",
                "old_value": current_item.get("tags"),
                "new_value": request_data["tags"],
            }
        )

    if "status" in request_data:
        update_expressions.append("#status = :status")
        expression_names["#status"] = "status"
        expression_values[":status"] = request_data["status"]
        changes.append(
            {
                "field": "status",
                "old_value": current_item.get("status"),
                "new_value": request_data["status"],
            }
        )

    # Combine SET and REMOVE expressions
    set_expressions = [
        expr for expr in update_expressions if not expr.startswith("REMOVE")
    ]
    remove_expressions = [
        expr.replace("REMOVE ", "")
        for expr in update_expressions
        if expr.startswith("REMOVE")
    ]

    update_expression_parts = []
    if set_expressions:
        update_expression_parts.append("SET " + ", ".join(set_expressions))
    if remove_expressions:
        update_expression_parts.append("REMOVE " + ", ".join(remove_expressions))

    return {
        "UpdateExpression": " ".join(update_expression_parts),
        "ExpressionAttributeValues": expression_values,
        "ExpressionAttributeNames": expression_names if expression_names else None,
        "changes": changes,
    }


@tracer.capture_method
def create_version_record(
    table, collection_id: str, user_id: str, changes: List[Dict[str, Any]]
) -> None:
    """
    Create a version record for tracking collection changes

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID
        user_id: User making the changes
        changes: List of changes made
    """
    try:
        # Get current version count (simplified - in reality would query existing versions)
        version_number = 1  # TODO: Implement actual version counting
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        version_item = {
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": f"{VERSION_SK_PREFIX}{version_number:04d}",
            "changedBy": user_id,
            "changedAt": current_timestamp,
            "changes": [change["field"] for change in changes],
            "previousValues": {
                change["field"]: change["old_value"]
                for change in changes
                if change["old_value"] is not None
            },
        }

        table.put_item(Item=version_item)

        logger.debug(
            {
                "message": "Version record created",
                "collection_id": collection_id,
                "version_number": version_number,
                "change_count": len(changes),
                "operation": "create_version_record",
            }
        )

    except Exception as e:
        # Don't fail the update if version recording fails
        logger.warning(
            {
                "message": "Failed to create version record",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "create_version_record",
            }
        )


@tracer.capture_method
def format_collection_response(
    item: Dict[str, Any], collection_id: str, user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: DynamoDB item
        collection_id: Collection ID
        user_context: User context information

    Returns:
        Formatted collection object
    """
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

    # Add user-specific fields
    if user_context.get("user_id"):
        formatted_item["isFavorite"] = False  # TODO: Query user relationship
        formatted_item["userRole"] = (
            "owner"
            if formatted_item["ownerId"] == user_context["user_id"]
            else "viewer"
        )

    # Add TTL if present
    if item.get("expiresAt"):
        formatted_item["expiresAt"] = item["expiresAt"]

    return formatted_item


@app.patch("/collections/<collection_id>")
@tracer.capture_method
def update_collection(collection_id: str):
    """Update collection attributes or metadata"""
    try:
        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection update attempted without valid user context",
                    "collection_id": collection_id,
                    "operation": "update_collection",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to update collections",
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

        if not request_data:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "EMPTY_REQUEST_BODY",
                            "message": "Request body cannot be empty",
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
                "message": "Processing collection update request",
                "collection_id": collection_id,
                "request_data": request_data,
                "user_id": user_id,
                "operation": "update_collection",
            }
        )

        # Validate request data
        validation_errors = validate_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Collection update request validation failed",
                    "collection_id": collection_id,
                    "errors": validation_errors,
                    "operation": "update_collection",
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

        # Check if user has permission to update this collection
        if not check_user_permissions(table, collection_id, user_id):
            logger.warning(
                {
                    "message": "User does not have permission to update collection",
                    "collection_id": collection_id,
                    "user_id": user_id,
                    "operation": "update_collection",
                }
            )

            return {
                "statusCode": 403,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": "You don't have permission to update this collection",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Get current collection to validate status transitions and build update
        try:
            response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )
        except ClientError as e:
            logger.error(
                {
                    "message": "DynamoDB error retrieving collection for update",
                    "collection_id": collection_id,
                    "error": str(e),
                    "operation": "update_collection",
                }
            )
            raise

        if "Item" not in response:
            logger.info(
                {
                    "message": "Collection not found for update",
                    "collection_id": collection_id,
                    "operation": "update_collection",
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

        current_item = response["Item"]
        current_status = current_item.get("status", "ACTIVE")

        # Check if collection is deleted
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

        # Validate status transition if status is being changed
        if "status" in request_data:
            new_status = request_data["status"]
            if not validate_status_transition(current_status, new_status):
                logger.warning(
                    {
                        "message": "Invalid status transition",
                        "collection_id": collection_id,
                        "current_status": current_status,
                        "new_status": new_status,
                        "operation": "update_collection",
                    }
                )

                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "INVALID_STATUS_TRANSITION",
                                "message": f"Cannot change status from '{current_status}' to '{new_status}'",
                            },
                            "meta": {
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "version": "v1",
                                "request_id": app.current_event.request_context.request_id,
                            },
                        }
                    ),
                }

        # Build update expression
        update_params = build_update_expression(request_data, current_item)

        # Prepare update parameters
        update_kwargs = {
            "Key": {"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
            "UpdateExpression": update_params["UpdateExpression"],
            "ExpressionAttributeValues": update_params["ExpressionAttributeValues"],
            "ReturnValues": "ALL_NEW",
            "ConditionExpression": "attribute_exists(PK)",  # Ensure collection still exists
        }

        if update_params["ExpressionAttributeNames"]:
            update_kwargs["ExpressionAttributeNames"] = update_params[
                "ExpressionAttributeNames"
            ]

        logger.debug(
            {
                "message": "Prepared update parameters",
                "collection_id": collection_id,
                "update_expression": update_params["UpdateExpression"],
                "change_count": len(update_params["changes"]),
                "operation": "update_collection",
            }
        )

        # Execute update
        try:
            response = table.update_item(**update_kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
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
            else:
                raise  # Re-raise other ClientErrors

        updated_item = response["Attributes"]

        # Create version record for significant changes
        if update_params["changes"]:
            create_version_record(
                table, collection_id, user_id, update_params["changes"]
            )

        logger.info(
            {
                "message": "Collection updated successfully",
                "collection_id": collection_id,
                "user_id": user_id,
                "changes_made": len(update_params["changes"]),
                "operation": "update_collection",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionUpdates", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_collection_response(
            updated_item, collection_id, user_context
        )

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
                "message": "DynamoDB client error during collection update",
                "error_code": error_code,
                "error_message": error_message,
                "collection_id": collection_id,
                "user_id": user_context.get("user_id"),
                "operation": "update_collection",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionUpdates", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection update",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_id": collection_id,
                "user_id": user_context.get("user_id"),
                "operation": "update_collection",
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
