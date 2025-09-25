import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="collection-type-creation",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="collection-type-creation")
metrics = Metrics(namespace="medialake", service="collection-type-creation")

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
SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
ALLOWED_ITEM_TYPES = ["asset", "workflow", "collection"]
MAX_TYPE_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500


@tracer.capture_method
def generate_collection_type_id() -> str:
    """
    Generate a unique collection type ID

    Returns:
        Unique type ID string
    """
    # Generate a short UUID-based ID with type prefix
    short_uuid = str(uuid.uuid4())[:8]
    type_id = f"type_{short_uuid}"

    logger.debug(
        {
            "message": "Generated collection type ID",
            "type_id": type_id,
            "operation": "generate_collection_type_id",
        }
    )

    return type_id


@tracer.capture_method
def validate_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Validate collection type creation request data

    Args:
        request_data: Request payload data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate required fields
    if not request_data.get("typeName"):
        errors.append(
            {
                "field": "typeName",
                "message": "Type name is required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif len(request_data["typeName"]) > MAX_TYPE_NAME_LENGTH:
        errors.append(
            {
                "field": "typeName",
                "message": f"Type name must be {MAX_TYPE_NAME_LENGTH} characters or less",
                "code": "INVALID_LENGTH",
            }
        )

    if not request_data.get("allowedItemTypes"):
        errors.append(
            {
                "field": "allowedItemTypes",
                "message": "Allowed item types are required",
                "code": "REQUIRED_FIELD",
            }
        )
    elif not isinstance(request_data["allowedItemTypes"], list):
        errors.append(
            {
                "field": "allowedItemTypes",
                "message": "Allowed item types must be an array",
                "code": "INVALID_TYPE",
            }
        )
    elif not request_data["allowedItemTypes"]:
        errors.append(
            {
                "field": "allowedItemTypes",
                "message": "At least one allowed item type is required",
                "code": "EMPTY_ARRAY",
            }
        )
    else:
        # Validate individual item types
        invalid_types = [
            item_type
            for item_type in request_data["allowedItemTypes"]
            if item_type not in ALLOWED_ITEM_TYPES
        ]
        if invalid_types:
            errors.append(
                {
                    "field": "allowedItemTypes",
                    "message": f"Invalid item types: {', '.join(invalid_types)}. Allowed types: {', '.join(ALLOWED_ITEM_TYPES)}",
                    "code": "INVALID_VALUE",
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

    # Validate metadataSchema if provided
    if request_data.get("metadataSchema"):
        if not isinstance(request_data["metadataSchema"], dict):
            errors.append(
                {
                    "field": "metadataSchema",
                    "message": "Metadata schema must be a valid JSON object",
                    "code": "INVALID_TYPE",
                }
            )
        else:
            # Basic JSON Schema validation - check for required structure
            schema = request_data["metadataSchema"]
            if schema.get("type") and schema["type"] not in [
                "object",
                "array",
                "string",
                "number",
                "boolean",
                "null",
            ]:
                errors.append(
                    {
                        "field": "metadataSchema.type",
                        "message": "Invalid JSON Schema type",
                        "code": "INVALID_SCHEMA",
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
def check_type_name_uniqueness(table, type_name: str) -> bool:
    """
    Check if a collection type name already exists

    Args:
        table: DynamoDB table resource
        type_name: Type name to check

    Returns:
        True if name is unique, False if it already exists
    """
    try:
        response = table.scan(
            FilterExpression="PK = :pk AND begins_with(SK, :sk_prefix) AND typeName = :type_name",
            ExpressionAttributeValues={
                ":pk": SYSTEM_PK,
                ":sk_prefix": COLLECTION_TYPE_SK_PREFIX,
                ":type_name": type_name,
            },
            ProjectionExpression="SK",
        )

        existing_items = response.get("Items", [])
        is_unique = len(existing_items) == 0

        logger.debug(
            {
                "message": "Type name uniqueness check completed",
                "type_name": type_name,
                "is_unique": is_unique,
                "existing_count": len(existing_items),
                "operation": "check_type_name_uniqueness",
            }
        )

        return is_unique

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to check type name uniqueness",
                "type_name": type_name,
                "error": str(e),
                "operation": "check_type_name_uniqueness",
            }
        )
        # On error, assume not unique to be safe
        return False


@tracer.capture_method
def format_collection_type_response(
    item: Dict[str, Any], type_id: str
) -> Dict[str, Any]:
    """
    Format DynamoDB item to API response format

    Args:
        item: DynamoDB item
        type_id: Collection type ID

    Returns:
        Formatted collection type object
    """
    return {
        "id": type_id,
        "typeName": item.get("typeName", ""),
        "description": item.get("description", ""),
        "allowedItemTypes": item.get("allowedItemTypes", []),
        "icon": item.get("icon", ""),
        "color": item.get("color", ""),
        "metadataSchema": item.get("metadataSchema", {}),
        "isActive": item.get("isActive", True),
        "sortOrder": item.get("sortOrder", 0),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }


@app.post("/collection-types")
@tracer.capture_method
def create_collection_type():
    """Create a new collection type"""
    try:
        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing collection type creation request",
                "request_data": request_data,
                "operation": "create_collection_type",
            }
        )

        # Validate request data
        validation_errors = validate_request_data(request_data)
        if validation_errors:
            logger.warning(
                {
                    "message": "Collection type creation request validation failed",
                    "errors": validation_errors,
                    "operation": "create_collection_type",
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

        # Check if type name already exists
        type_name = request_data["typeName"]
        if not check_type_name_uniqueness(table, type_name):
            logger.warning(
                {
                    "message": "Collection type with same name already exists",
                    "type_name": type_name,
                    "operation": "create_collection_type",
                }
            )

            metrics.add_metric(
                name="DuplicateTypeNames", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "DUPLICATE_TYPE_NAME",
                            "message": f"Collection type with name '{type_name}' already exists",
                        },
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        # Generate unique type ID
        type_id = generate_collection_type_id()
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        # Prepare DynamoDB item
        dynamodb_item = {
            "PK": SYSTEM_PK,
            "SK": f"{COLLECTION_TYPE_SK_PREFIX}{type_id}",
            "typeName": request_data["typeName"],
            "allowedItemTypes": request_data["allowedItemTypes"],
            "isActive": True,
            "sortOrder": request_data.get("sortOrder", 0),
            "createdAt": current_timestamp,
            "updatedAt": current_timestamp,
        }

        # Add optional fields if provided
        if request_data.get("description"):
            dynamodb_item["description"] = request_data["description"]

        if request_data.get("icon"):
            dynamodb_item["icon"] = request_data["icon"]

        if request_data.get("color"):
            dynamodb_item["color"] = request_data["color"]

        if request_data.get("metadataSchema"):
            dynamodb_item["metadataSchema"] = request_data["metadataSchema"]

        logger.debug(
            {
                "message": "Prepared DynamoDB item for collection type",
                "type_id": type_id,
                "item_keys": list(dynamodb_item.keys()),
                "operation": "create_collection_type",
            }
        )

        # Save collection type to DynamoDB
        table.put_item(Item=dynamodb_item)

        logger.info(
            {
                "message": "Collection type created successfully in DynamoDB",
                "type_id": type_id,
                "type_name": request_data["typeName"],
                "operation": "create_collection_type",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulCollectionTypeCreations", unit=MetricUnit.Count, value=1
        )

        # Format response data
        response_data = format_collection_type_response(dynamodb_item, type_id)

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
                "message": "DynamoDB client error during collection type creation",
                "error_code": error_code,
                "error_message": error_message,
                "type_name": request_data.get("typeName"),
                "operation": "create_collection_type",
                "status": "failed",
            }
        )

        metrics.add_metric(
            name="FailedCollectionTypeCreations", unit=MetricUnit.Count, value=1
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
                "message": "Unexpected error during collection type creation",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "type_name": request_data.get("typeName"),
                "operation": "create_collection_type",
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
