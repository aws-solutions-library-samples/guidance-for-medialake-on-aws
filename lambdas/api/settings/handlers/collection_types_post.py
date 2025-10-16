"""POST /settings/collection-types - Create collection type."""

import json
import os
import uuid

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionTypeModel
from utils.permission_utils import check_admin_permission, extract_user_context
from utils.response_utils import (
    create_error_response,
    now_iso,
)
from utils.validation_utils import validate_collection_type_data

logger = Logger(
    service="settings-collection-types-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="settings-collection-types-post")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"


def register_route(app):
    """Register POST /settings/collection-types route"""

    @app.post("/settings/collection-types")
    @tracer.capture_method
    def settings_collection_types_post():
        """Create a new collection type (Admin only)"""
        request_id = app.current_event.request_context.request_id

        try:
            # Extract user context and check admin permission
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            # Get and validate request data
            request_data = app.current_event.json_body

            if not request_data:
                raise BadRequestError("Request body is required")

            # Validate collection type data
            validation_errors = validate_collection_type_data(
                request_data, is_update=False
            )
            if validation_errors:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details=validation_errors,
                    status_code=422,
                    request_id=request_id,
                )

            current_timestamp = now_iso()
            type_id = f"colltype_{str(uuid.uuid4())[:8]}"

            logger.info(
                f"Creating collection type: {type_id}",
                extra={
                    "user_id": user_context["user_id"],
                    "type_name": request_data["name"],
                },
            )

            # Create collection type model instance
            collection_type = CollectionTypeModel()
            collection_type.PK = SYSTEM_PK
            collection_type.SK = f"{COLLECTION_TYPE_SK_PREFIX}{type_id}"
            collection_type.name = request_data["name"]
            collection_type.color = request_data["color"]
            collection_type.icon = request_data["icon"]
            collection_type.isActive = request_data.get("isActive", True)
            collection_type.isSystem = (
                False  # User-created types are never system types
            )
            collection_type.createdAt = current_timestamp
            collection_type.updatedAt = current_timestamp

            if request_data.get("description"):
                collection_type.description = request_data["description"]

            # Save to DynamoDB
            collection_type.save()

            logger.info(f"Collection type created successfully: {type_id}")
            metrics.add_metric(
                name="SuccessfulCollectionTypeCreations", unit=MetricUnit.Count, value=1
            )

            # Format response data
            response_data = {
                "id": type_id,
                "name": collection_type.name,
                "description": (
                    collection_type.description if collection_type.description else None
                ),
                "color": collection_type.color,
                "icon": collection_type.icon,
                "isActive": collection_type.isActive,
                "isSystem": collection_type.isSystem,
                "createdAt": collection_type.createdAt,
                "updatedAt": collection_type.updatedAt,
            }

            # Return raw Lambda proxy format for 201 status code
            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": response_data,
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": request_id,
                        },
                    }
                ),
            }

        except BadRequestError:
            raise

        except Exception as e:
            logger.exception("Error creating collection type", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
