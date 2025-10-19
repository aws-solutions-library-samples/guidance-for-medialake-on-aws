"""POST /settings/collection-types/{typeId}/migrate - Migrate collections to another type."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from db_models import CollectionModel, CollectionTypeModel
from pynamodb.exceptions import DoesNotExist
from permission_utils import check_admin_permission, extract_user_context
from response_utils import (
    create_error_response,
    create_success_response,
    now_iso,
)

logger = Logger(
    service="settings-collection-types-migrate",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
tracer = Tracer(service="settings-collection-types-migrate")
metrics = Metrics(namespace="medialake", service="collection-types")

SYSTEM_PK = "SYSTEM"
COLLECTION_TYPE_SK_PREFIX = "COLLTYPE#"
METADATA_SK = "METADATA#"


def register_route(app):
    """Register POST /settings/collection-types/<type_id>/migrate route"""

    @app.post("/settings/collection-types/<type_id>/migrate")
    @tracer.capture_method
    def settings_collection_types_migrate(type_id: str):
        """Migrate collections from one type to another (Admin only)"""
        request_id = app.current_event.request_context.request_id

        try:
            # Extract user context and check admin permission
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            # Get and validate request data
            request_data = app.current_event.json_body

            if not request_data:
                raise BadRequestError("Request body is required")

            target_type_id = request_data.get("targetTypeId")
            if not target_type_id:
                raise BadRequestError("targetTypeId is required")

            logger.info(
                f"Migrating collections from type {type_id} to {target_type_id}",
                extra={
                    "user_id": user_context["user_id"],
                    "source_type": type_id,
                    "target_type": target_type_id,
                },
            )

            # Validate source type exists
            source_sk = f"{COLLECTION_TYPE_SK_PREFIX}{type_id}"
            try:
                CollectionTypeModel.get(SYSTEM_PK, source_sk)
            except DoesNotExist:
                raise NotFoundError(f"Source collection type '{type_id}' not found")

            # Validate target type exists
            target_sk = f"{COLLECTION_TYPE_SK_PREFIX}{target_type_id}"
            try:
                target_type = CollectionTypeModel.get(SYSTEM_PK, target_sk)
                if not target_type.isActive:
                    raise BadRequestError("Target collection type is not active")
            except DoesNotExist:
                raise NotFoundError(
                    f"Target collection type '{target_type_id}' not found"
                )

            # Perform migration
            migrated_count = migrate_collections(type_id, target_type_id)

            logger.info(f"Successfully migrated {migrated_count} collections")
            metrics.add_metric(
                name="SuccessfulCollectionTypeMigrations",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="CollectionsMigrated", unit=MetricUnit.Count, value=migrated_count
            )

            # Return success response
            response_data = {"migratedCount": migrated_count}

            return create_success_response(
                data=response_data, status_code=200, request_id=request_id
            )

        except (BadRequestError, NotFoundError):
            raise

        except Exception as e:
            logger.exception(
                f"Error migrating collections from type {type_id}", exc_info=e
            )
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )


def migrate_collections(source_type_id: str, target_type_id: str) -> int:
    """
    Migrate all collections from source type to target type.

    Args:
        source_type_id: Source collection type ID
        target_type_id: Target collection type ID

    Returns:
        Count of migrated collections
    """
    try:
        migrated_count = 0
        current_timestamp = now_iso()

        # Get all collections using the source type
        collections_to_migrate = []
        for collection in CollectionModel.scan(
            CollectionModel.SK == METADATA_SK,
            filter_condition=CollectionModel.collectionTypeId == source_type_id,
        ):
            collections_to_migrate.append(collection)

        logger.info(f"Found {len(collections_to_migrate)} collections to migrate")

        # Batch update collections
        # PynamoDB doesn't have batch_write for updates, so we'll update individually
        # In production, consider using DynamoDB batch_write_item directly for better performance
        for collection in collections_to_migrate:
            try:
                collection.collectionTypeId = target_type_id
                collection.updatedAt = current_timestamp
                collection.save()
                migrated_count += 1

                if migrated_count % 10 == 0:
                    logger.info(
                        f"Migration progress: {migrated_count}/{len(collections_to_migrate)}"
                    )

            except Exception as e:
                logger.error(f"Error migrating collection {collection.PK}", exc_info=e)
                # Continue with other collections
                continue

        logger.info(
            f"Migration complete: {migrated_count} collections migrated",
            extra={"count": migrated_count},
        )
        return migrated_count

    except Exception as e:
        logger.error("Error during migration", exc_info=e)
        raise
