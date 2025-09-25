import json
import os
import uuid
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
    service="collection-creation",
    level=os.environ.get("LOG_LEVEL", "DEBUG"),
    json_default=str,
)
tracer = Tracer(service="collection-creation")
metrics = Metrics(namespace="medialake", service="collection-creation")

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
USER_PK_PREFIX = "USER#"
CHILD_SK_PREFIX = "CHILD#"
SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
COLLECTIONS_GSI5_PK = "COLLECTIONS"
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
VALID_STATUSES = ["ACTIVE", "ARCHIVED"]


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
def generate_collection_id() -> str:
    """
    Generate a unique collection ID

    Returns:
        Unique collection ID string
    """
    # Generate a short UUID-based ID with collection prefix
    short_uuid = str(uuid.uuid4())[:8]
    collection_id = f"col_{short_uuid}"

    logger.debug(
        {
            "message": "Generated collection ID",
            "collection_id": collection_id,
            "operation": "generate_collection_id",
        }
    )

    return collection_id


@tracer.capture_method
def validate_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection creation request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate required fields
    if not request_data.get("name"):
        errors.append(
            {
                "field": "name",
                "message": "Collection name is required",
                "code": "REQUIRED_FIELD",
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

    # Validate optional fields
    if (
        request_data.get("description")
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
    if request_data.get("metadata"):
        if not isinstance(request_data["metadata"], dict):
            errors.append(
                {
                    "field": "metadata",
                    "message": "Metadata must be a valid JSON object",
                    "code": "INVALID_TYPE",
                }
            )

    # Validate tags if provided
    if request_data.get("tags"):
        if not isinstance(request_data["tags"], dict):
            errors.append(
                {
                    "field": "tags",
                    "message": "Tags must be a valid JSON object",
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

    # Validate expiresAt if provided
    if request_data.get("expiresAt"):
        try:
            # Parse the datetime string to validate format
            datetime.fromisoformat(request_data["expiresAt"].replace("Z", "+00:00"))
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
def validate_collection_type(table, collection_type_id: str) -> bool:
    """
    Validate that the collection type exists and is active

    Args:
        table: DynamoDB table resource
        collection_type_id: Collection type ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not collection_type_id:
        return True  # Collection type is optional

    try:
        response = table.get_item(
            Key={
                "PK": SYSTEM_PK,
                "SK": f"{COLLECTION_TYPE_SK_PREFIX}{collection_type_id}",
            }
        )

        item = response.get("Item")
        if not item:
            logger.warning(
                {
                    "message": "Collection type not found",
                    "collection_type_id": collection_type_id,
                    "operation": "validate_collection_type",
                }
            )
            return False

        if not item.get("isActive", True):
            logger.warning(
                {
                    "message": "Collection type is not active",
                    "collection_type_id": collection_type_id,
                    "operation": "validate_collection_type",
                }
            )
            return False

        logger.debug(
            {
                "message": "Collection type validated successfully",
                "collection_type_id": collection_type_id,
                "operation": "validate_collection_type",
            }
        )

        return True

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate collection type",
                "collection_type_id": collection_type_id,
                "error": str(e),
                "operation": "validate_collection_type",
            }
        )
        return False


@tracer.capture_method
def validate_parent_collection(table, parent_id: str, user_id: str) -> bool:
    """
    Validate that the parent collection exists and user has access

    Args:
        table: DynamoDB table resource
        parent_id: Parent collection ID to validate
        user_id: User ID requesting access

    Returns:
        True if valid, False otherwise
    """
    if not parent_id:
        return True  # Parent is optional

    try:
        # Check if parent collection exists
        response = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{parent_id}", "SK": METADATA_SK}
        )

        item = response.get("Item")
        if not item:
            logger.warning(
                {
                    "message": "Parent collection not found",
                    "parent_id": parent_id,
                    "operation": "validate_parent_collection",
                }
            )
            return False

        # Check if parent is active
        if item.get("status") != "ACTIVE":
            logger.warning(
                {
                    "message": "Parent collection is not active",
                    "parent_id": parent_id,
                    "status": item.get("status"),
                    "operation": "validate_parent_collection",
                }
            )
            return False

        # Check if user has access (owner or has permissions)
        if item.get("ownerId") == user_id:
            logger.debug(
                {
                    "message": "Parent collection validated - user is owner",
                    "parent_id": parent_id,
                    "operation": "validate_parent_collection",
                }
            )
            return True

        # TODO: Check user permissions for non-owned collections
        # For now, allow if user is not the owner (simplified logic)
        logger.debug(
            {
                "message": "Parent collection validated - user has access",
                "parent_id": parent_id,
                "operation": "validate_parent_collection",
            }
        )

        return True

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate parent collection",
                "parent_id": parent_id,
                "error": str(e),
                "operation": "validate_parent_collection",
            }
        )
        return False


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
        formatted_item["isFavorite"] = (
            False  # Default, will be updated when user relationships are queried
        )
        formatted_item["userRole"] = (
            "owner"
            if formatted_item["ownerId"] == user_context["user_id"]
            else "viewer"
        )

    # Add TTL if present
    if item.get("expiresAt"):
        formatted_item["expiresAt"] = item["expiresAt"]

    return formatted_item


@app.post("/collections")
@tracer.capture_method
def create_collection():
    """Create a new collection"""
    try:
        # Log the full event for debugging
        logger.debug(
            {
                "message": "Full event received",
                "raw_event": app.current_event.raw_event,
                "operation": "create_collection_debug",
            }
        )

        # Also log the current_event object structure
        logger.debug(
            {
                "message": "Current event object details",
                "current_event_type": type(app.current_event).__name__,
                "current_event_attributes": [
                    attr for attr in dir(app.current_event) if not attr.startswith("_")
                ],
                "operation": "create_collection_debug",
            }
        )

        # Extract user context
        user_context = extract_user_context(app.current_event.raw_event)
        user_id = user_context.get("user_id")

        if not user_id:
            logger.warning(
                {
                    "message": "Collection creation attempted without valid user context",
                    "operation": "create_collection",
                }
            )
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AUTHENTICATION_REQUIRED",
                            "message": "Valid authentication is required to create collections",
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
                "message": "Processing collection creation request",
                "request_data": request_data,
                "user_id": user_id,
                "operation": "create_collection",
            }
        )

        # Validate request data
        validation_errors = validate_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Collection creation request validation failed",
                    "errors": validation_errors,
                    "operation": "create_collection",
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

        # Validate collection type if provided
        collection_type_id = request_data.get("collectionTypeId")
        if collection_type_id and not validate_collection_type(
            table, collection_type_id
        ):
            logger.warning(
                {
                    "message": "Invalid collection type specified",
                    "collection_type_id": collection_type_id,
                    "operation": "create_collection",
                }
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_COLLECTION_TYPE",
                            "message": f"Collection type '{collection_type_id}' does not exist or is not active",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Validate parent collection if provided
        parent_id = request_data.get("parentId")
        if parent_id and not validate_parent_collection(table, parent_id, user_id):
            logger.warning(
                {
                    "message": "Invalid parent collection specified",
                    "parent_id": parent_id,
                    "operation": "create_collection",
                }
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_PARENT_COLLECTION",
                            "message": f"Parent collection '{parent_id}' does not exist, is not active, or you don't have access",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Generate unique collection ID
        collection_id = generate_collection_id()
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Calculate TTL timestamp if expires_at is provided
        ttl_timestamp = None
        if request_data.get("expiresAt"):
            expires_dt = datetime.fromisoformat(
                request_data["expiresAt"].replace("Z", "+00:00")
            )
            ttl_timestamp = int(expires_dt.timestamp())

        # Prepare collection metadata item
        collection_item = {
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": METADATA_SK,
            "name": request_data["name"],
            "ownerId": user_id,
            "status": "ACTIVE",
            "itemCount": 0,
            "childCollectionCount": 0,
            "isPublic": bool(request_data.get("isPublic", False)),
            "createdAt": current_timestamp,
            "updatedAt": current_timestamp,
            # GSI attributes
            "GSI5_PK": COLLECTIONS_GSI5_PK,
            "GSI5_SK": current_timestamp,
        }

        # Add optional fields if provided
        if request_data.get("description"):
            collection_item["description"] = request_data["description"]

        if collection_type_id:
            collection_item["collectionTypeId"] = collection_type_id
            # Add GSI3 attributes for collection type queries
            collection_item["GSI3_PK"] = collection_type_id
            collection_item["GSI3_SK"] = f"{COLLECTION_PK_PREFIX}{collection_id}"

        if parent_id:
            collection_item["parentId"] = parent_id

        if request_data.get("metadata"):
            collection_item["customMetadata"] = request_data["metadata"]

        if request_data.get("tags"):
            collection_item["tags"] = request_data["tags"]

        if ttl_timestamp:
            collection_item["expiresAt"] = ttl_timestamp

        # Prepare user relationship item
        user_relationship_item = {
            "PK": f"{USER_PK_PREFIX}{user_id}",
            "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "relationship": "OWNER",
            "addedAt": current_timestamp,
            "lastAccessed": current_timestamp,
            "isFavorite": False,
            # GSI1 attributes for user collection queries
            "GSI1_PK": f"{USER_PK_PREFIX}{user_id}",
            "GSI1_SK": current_timestamp,
        }

        # Prepare items for transactional write
        transact_items = [
            {
                "Put": {
                    "TableName": TABLE_NAME,
                    "Item": collection_item,
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            },
            {
                "Put": {
                    "TableName": TABLE_NAME,
                    "Item": user_relationship_item,
                    "ConditionExpression": "attribute_not_exists(PK) OR attribute_not_exists(SK)",
                }
            },
        ]

        # Add parent-child relationship if parent specified
        if parent_id:
            child_relationship_item = {
                "PK": f"{COLLECTION_PK_PREFIX}{parent_id}",
                "SK": f"{CHILD_SK_PREFIX}{collection_id}",
                "childCollectionId": collection_id,
                "addedAt": current_timestamp,
                "addedBy": user_id,
                # GSI4 attributes for child-parent queries
                "GSI4_PK": f"CHILD#{collection_id}",
                "GSI4_SK": f"{COLLECTION_PK_PREFIX}{parent_id}",
            }

            transact_items.append(
                {"Put": {"TableName": TABLE_NAME, "Item": child_relationship_item}}
            )

            # Update parent collection's child count
            transact_items.append(
                {
                    "Update": {
                        "TableName": TABLE_NAME,
                        "Key": {
                            "PK": f"{COLLECTION_PK_PREFIX}{parent_id}",
                            "SK": METADATA_SK,
                        },
                        "UpdateExpression": "ADD childCollectionCount :inc SET updatedAt = :timestamp",
                        "ExpressionAttributeValues": {
                            ":inc": 1,
                            ":timestamp": current_timestamp,
                        },
                    }
                }
            )

        logger.debug(
            {
                "message": "Prepared transactional items for collection creation",
                "collection_id": collection_id,
                "transaction_item_count": len(transact_items),
                "operation": "create_collection",
            }
        )

        # Execute transactional write
        try:
            dynamodb.meta.client.transact_write_items(TransactItems=transact_items)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    {
                        "message": "Collection creation failed - conditional check failed",
                        "collection_id": collection_id,
                        "error": str(e),
                        "operation": "create_collection",
                    }
                )
                return {
                    "statusCode": 409,
                    "body": json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "COLLECTION_ALREADY_EXISTS",
                                "message": "Collection with this ID already exists",
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
                "message": "Collection created successfully in DynamoDB",
                "collection_id": collection_id,
                "collection_name": request_data["name"],
                "user_id": user_id,
                "parent_id": parent_id,
                "operation": "create_collection",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionCreations", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_collection_response(
            collection_item, collection_id, user_context
        )

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
                "message": "DynamoDB client error during collection creation",
                "error_code": error_code,
                "error_message": error_message,
                "collection_name": request_data.get("name"),
                "user_id": user_context.get("user_id"),
                "operation": "create_collection",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionCreations", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection creation",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "collection_name": request_data.get("name"),
                "user_id": user_context.get("user_id"),
                "operation": "create_collection",
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
