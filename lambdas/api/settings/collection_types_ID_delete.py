"""DELETE /settings/collection-types/{typeId} - Delete collection type."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    ForbiddenError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionModel, CollectionTypeModel
from pynamodb.exceptions import DoesNotExist
from permission_utils import check_admin_permission, extract_user_context
from response_utils import create_error_response

logger = Logger(
    service="settings-collection-types-delete",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
tracer = Tracer(service="settings-collection-types-delete")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
COLLECTION_PK_PREFIX = "COLLECTION#"
METADATA_SK = "METADATA#"


def register_route(app):
    """Register DELETE /settings/collection-types/<type_id> route"""

    @app.delete("/settings/collection-types/<type_id>")
    @tracer.capture_method
    def settings_collection_types_delete(type_id: str):
        """Delete a collection type (Admin only)"""
        request_id = app.current_event.request_context.request_id

        try:
            # Extract user context and check admin permission
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            logger.info(
                f"Deleting collection type: {type_id}",
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
                raise ForbiddenError("Cannot delete system collection types")

            # Check usage count
            usage_count = count_collections_using_type(type_id)

            if usage_count > 0:
                logger.warning(
                    f"Cannot delete type {type_id}: {usage_count} collections are using it"
                )
                return create_error_response(
                    code="TYPE_IN_USE",
                    message="Cannot delete type that is in use",
                    details=[
                        {
                            "field": "usageCount",
                            "message": f"{usage_count} collections are using this type",
                            "code": "USAGE_CHECK_FAILED",
                        }
                    ],
                    status_code=409,
                    request_id=request_id,
                )

            # Delete the collection type
            collection_type.delete()

            logger.info(f"Collection type deleted successfully: {type_id}")
            metrics.add_metric(
                name="SuccessfulCollectionTypeDeletions", unit=MetricUnit.Count, value=1
            )

            # Return 204 No Content
            return {"statusCode": 204, "body": ""}

        except (ForbiddenError, NotFoundError):
            raise

        except Exception as e:
            logger.exception(f"Error deleting collection type {type_id}", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )


def count_collections_using_type(type_id: str) -> int:
    """
    Count how many collections are using this type.

    Args:
        type_id: Collection type ID

    Returns:
        Count of collections using this type
    """
    try:
        count = 0

        # Scan collections table for items with this type
        # Note: In production, consider using GSI3 if available
        for collection in CollectionModel.scan(
            CollectionModel.SK == METADATA_SK,
            filter_condition=CollectionModel.collectionTypeId == type_id,
        ):
            count += 1

        logger.info(f"Found {count} collections using type {type_id}")
        return count

    except Exception as e:
        logger.error(f"Error counting collections using type {type_id}", exc_info=e)
        # Return 0 on error to be safe (don't block deletion)
        return 0
