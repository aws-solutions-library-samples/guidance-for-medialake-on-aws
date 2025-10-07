"""
Collection Types Routes.

Handles all endpoints related to collection type management:
- GET /collection-types - List all collection types
- POST /collection-types - Create a new collection type
"""

import base64
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger(
    service="collection-types-routes", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collection-types-routes")
metrics = Metrics(namespace="medialake", service="collection-types")

# Constants
SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
ALLOWED_ITEM_TYPES = ["asset", "workflow", "collection"]
MAX_TYPE_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def register_routes(app, dynamodb, table_name):
    """
    Register collection type routes with the app resolver.

    Args:
        app: APIGatewayRestResolver instance
        dynamodb: DynamoDB resource
        table_name: Collections table name
    """

    @app.get("/collection-types")
    @tracer.capture_method
    def list_collection_types():
        """Get list of collection types with cursor-based pagination"""
        try:
            # Parse query parameters
            cursor = app.current_event.get_query_string_value("cursor")
            limit = int(
                app.current_event.get_query_string_value("limit", DEFAULT_LIMIT)
            )
            active_filter = app.current_event.get_query_string_value("filter[active]")
            sort_param = app.current_event.get_query_string_value("sort")

            # Validate limit
            limit = min(max(1, limit), MAX_LIMIT)

            logger.info(
                "Processing collection types retrieval request",
                extra={
                    "cursor": cursor,
                    "limit": limit,
                    "active_filter": active_filter,
                    "sort": sort_param,
                },
            )

            table = dynamodb.Table(table_name)

            # Parse cursor for pagination
            start_key = None
            parsed_cursor = _parse_cursor(cursor)
            if parsed_cursor:
                start_key = {
                    "PK": parsed_cursor.get("pk"),
                    "SK": parsed_cursor.get("sk"),
                }

            # Scan for collection types (PK=SYSTEM, SK begins with COLLTYPE#)
            scan_params = {
                "FilterExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "ExpressionAttributeValues": {
                    ":pk": SYSTEM_PK,
                    ":sk_prefix": COLLECTION_TYPE_SK_PREFIX,
                },
                "Limit": limit + 1,  # Get one extra to check if there are more results
            }

            if start_key:
                scan_params["ExclusiveStartKey"] = start_key

            response = table.scan(**scan_params)
            items = response.get("Items", [])

            logger.info(f"Retrieved {len(items)} collection types from DynamoDB")

            # Check if we have more results
            has_more = len(items) > limit
            if has_more:
                items = items[:limit]  # Remove the extra item

            # Apply active filter if specified
            if active_filter is not None:
                is_active = active_filter.lower() == "true"
                items = [
                    item for item in items if item.get("isActive", True) == is_active
                ]
                logger.info(
                    f"Applied active filter: {is_active}, {len(items)} items remaining"
                )

            # Format items for API response
            formatted_items = [_format_collection_type_item(item) for item in items]

            # Apply sorting
            sorted_items = _apply_sorting(formatted_items, sort_param)

            # Create pagination info
            pagination = {
                "has_next_page": has_more,
                "has_prev_page": cursor is not None,
                "limit": limit,
            }

            # Add next cursor if there are more results
            if has_more and sorted_items:
                last_item = items[-1]  # Use original DynamoDB item for cursor
                next_cursor = _create_cursor(
                    last_item["PK"], last_item["SK"], last_item.get("createdAt")
                )
                pagination["next_cursor"] = next_cursor

            # Log success metrics
            metrics.add_metric(
                name="SuccessfulCollectionTypeRetrievals",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="CollectionTypesReturned",
                unit=MetricUnit.Count,
                value=len(sorted_items),
            )

            # Create response
            response_data = {
                "success": True,
                "data": sorted_items,
                "pagination": pagination,
                "meta": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "v1",
                    "request_id": app.current_event.request_context.request_id,
                },
            }

            return {"statusCode": 200, "body": json.dumps(response_data)}

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            logger.error(
                "DynamoDB client error during collection types retrieval",
                extra={
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )

            metrics.add_metric(
                name="FailedCollectionTypeRetrievals", unit=MetricUnit.Count, value=1
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
            logger.exception(
                "Unexpected error during collection types retrieval", exc_info=e
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

    @app.post("/collection-types")
    @tracer.capture_method
    def create_collection_type():
        """Create a new collection type"""
        try:
            # Get request body from the event
            request_data = app.current_event.json_body
            logger.info("Processing collection type creation request")

            # Validate request data
            validation_errors = _validate_request_data(request_data)
            if validation_errors:
                logger.warning(
                    "Collection type creation request validation failed",
                    extra={"errors": validation_errors},
                )

                metrics.add_metric(
                    name="ValidationErrors", unit=MetricUnit.Count, value=1
                )

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

            table = dynamodb.Table(table_name)

            # Check if type name already exists
            type_name = request_data["typeName"]
            if not _check_type_name_uniqueness(table, type_name):
                logger.warning(
                    f"Collection type with name '{type_name}' already exists"
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
            type_id = _generate_collection_type_id()
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

            # Save collection type to DynamoDB
            table.put_item(Item=dynamodb_item)

            logger.info(f"Collection type created successfully: {type_id}")

            # Log success metrics
            metrics.add_metric(
                name="SuccessfulCollectionTypeCreations", unit=MetricUnit.Count, value=1
            )

            # Format response data
            response_data = _format_collection_type_response(dynamodb_item, type_id)

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
                "DynamoDB client error during collection type creation",
                extra={
                    "error_code": error_code,
                    "error_message": error_message,
                },
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
            logger.exception(
                "Unexpected error during collection type creation", exc_info=e
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


# Helper functions
@tracer.capture_method
def _parse_cursor(cursor_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse base64-encoded cursor back to dictionary"""
    if not cursor_str:
        return None

    try:
        decoded_bytes = base64.b64decode(cursor_str)
        cursor_data = json.loads(decoded_bytes.decode("utf-8"))
        return cursor_data
    except Exception as e:
        logger.warning(f"Failed to parse cursor: {e}")
        return None


@tracer.capture_method
def _create_cursor(pk: str, sk: str, sort_field: Optional[str] = None) -> str:
    """Create base64-encoded cursor for pagination"""
    cursor_data = {"pk": pk, "sk": sk, "timestamp": datetime.utcnow().isoformat() + "Z"}

    if sort_field:
        cursor_data["sort_field"] = sort_field

    cursor_json = json.dumps(cursor_data, default=str)
    cursor_b64 = base64.b64encode(cursor_json.encode("utf-8")).decode("utf-8")

    return cursor_b64


@tracer.capture_method
def _apply_sorting(items: list, sort_param: Optional[str]) -> list:
    """Apply sorting to collection types list"""
    if not sort_param or not items:
        return items

    # Parse sort direction and field
    descending = sort_param.startswith("-")
    sort_field = sort_param[1:] if descending else sort_param

    # Define sorting key functions
    sort_key_map = {
        "sortOrder": lambda x: x.get("sortOrder", 0),
        "typeName": lambda x: x.get("typeName", "").lower(),
        "createdAt": lambda x: x.get("createdAt", ""),
    }

    sort_key_func = sort_key_map.get(sort_field, lambda x: x.get("createdAt", ""))

    try:
        sorted_items = sorted(items, key=sort_key_func, reverse=descending)
        return sorted_items
    except Exception as e:
        logger.error(f"Failed to sort collection types: {e}")
        return items


@tracer.capture_method
def _format_collection_type_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format DynamoDB item to API response format"""
    # Extract type ID from SK
    type_id = item["SK"].replace(COLLECTION_TYPE_SK_PREFIX, "")

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


@tracer.capture_method
def _validate_request_data(request_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate collection type creation request data"""
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

    return errors


@tracer.capture_method
def _check_type_name_uniqueness(table, type_name: str) -> bool:
    """Check if a collection type name already exists"""
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

        return is_unique

    except ClientError as e:
        logger.error(f"Failed to check type name uniqueness: {e}")
        # On error, assume not unique to be safe
        return False


@tracer.capture_method
def _generate_collection_type_id() -> str:
    """Generate a unique collection type ID"""
    short_uuid = str(uuid.uuid4())[:8]
    type_id = f"type_{short_uuid}"
    return type_id


@tracer.capture_method
def _format_collection_type_response(
    item: Dict[str, Any], type_id: str
) -> Dict[str, Any]:
    """Format DynamoDB item to API response format"""
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
