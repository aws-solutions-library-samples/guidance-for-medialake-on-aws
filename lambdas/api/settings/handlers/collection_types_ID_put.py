"""PUT /settings/collection-types/{typeId} - Update collection type."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionTypeModel
from pynamodb.exceptions import DoesNotExist
from utils.permission_utils import check_admin_permission, extract_user_context
from utils.response_utils import (
    create_error_response,
    create_success_response,
    now_iso,
)
from utils.validation_utils import validate_collection_type_data

logger = Logger(
    service="settings-collection-types-put", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="settings-collection-types-put")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"


def register_route(app):
    """Register PUT /settings/collection-types/<type_id> route"""

    @app.put("/settings/collection-types/<type_id>")
    @tracer.capture_method
    def settings_collection_types_put(type_id: str):
        """Update a collection type (Admin only)"""
        request_id = app.current_event.request_context.request_id

        try:
            # Extract user context and check admin permission
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            # Get and validate request data
            request_data = app.current_event.json_body

            if not request_data:
                raise BadRequestError("Request body is required")

            # Validate collection type data (update mode)
            validation_errors = validate_collection_type_data(
                request_data, is_update=True
            )
            if validation_errors:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details=validation_errors,
                    status_code=422,
                    request_id=request_id,
                )

            logger.info(
                f"Updating collection type: {type_id}",
                extra={"user_id": user_context["user_id"], "type_id": type_id},
            )

            # Get existing collection type
            sk = f"{COLLECTION_TYPE_SK_PREFIX}{type_id}"
            try:
                collection_type = CollectionTypeModel.get(SYSTEM_PK, sk)
            except DoesNotExist:
                raise NotFoundError(f"Collection type '{type_id}' not found")

            # Check if system type
            if collection_type.isSystem:
                raise ForbiddenError("Cannot edit system collection types")

            # Update fields
            if "name" in request_data:
                collection_type.name = request_data["name"]
            if "description" in request_data:
                collection_type.description = request_data["description"]
            if "color" in request_data:
                collection_type.color = request_data["color"]
            if "icon" in request_data:
                collection_type.icon = request_data["icon"]
            if "isActive" in request_data:
                collection_type.isActive = request_data["isActive"]

            collection_type.updatedAt = now_iso()

            # Save to DynamoDB
            collection_type.save()

            logger.info(f"Collection type updated successfully: {type_id}")
            metrics.add_metric(
                name="SuccessfulCollectionTypeUpdates", unit=MetricUnit.Count, value=1
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

            return create_success_response(
                data=response_data, status_code=200, request_id=request_id
            )

        except (BadRequestError, ForbiddenError, NotFoundError):
            raise

        except Exception as e:
            logger.exception(f"Error updating collection type {type_id}", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
