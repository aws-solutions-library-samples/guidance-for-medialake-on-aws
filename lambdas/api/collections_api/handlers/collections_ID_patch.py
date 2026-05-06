"""PATCH /collections/<collection_id> - Update collection."""

import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    get_user_collection_role,
)
from db_models import CollectionModel
from models import UpdateCollectionRequest
from pynamodb.exceptions import DoesNotExist, UpdateError
from user_auth import extract_user_context
from utils.collections_opensearch_write import update_collection_document

logger = Logger(
    service="collections-ID-patch", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-patch")
metrics = Metrics(namespace="medialake", service="collection-detail")


def register_route(app):
    """Register PATCH /collections/<collection_id> route"""

    @app.patch("/collections/<collection_id>")
    @tracer.capture_method
    def collections_ID_patch(collection_id: str):
        """Update collection with Pydantic validation"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            # Parse and validate with Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=UpdateCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error updating collection: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Get the collection
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
            except DoesNotExist:
                raise NotFoundError(f"Collection '{collection_id}' not found")

            # Check user's role on this collection
            user_role = get_user_collection_role(collection, user_id)

            if user_role is None or user_role == "VIEWER":
                raise BadRequestError(
                    "You do not have permission to update this collection"
                )

            is_owner = user_role == "OWNER"

            # Editors cannot change ownership-level settings
            if not is_owner:
                if request_data.isPublic is not None:
                    raise BadRequestError(
                        "Only the collection owner can change visibility settings"
                    )
                if request_data.status is not None:
                    raise BadRequestError(
                        "Only the collection owner can change the collection status"
                    )

            # Build update actions for PynamoDB
            actions = [
                CollectionModel.updatedAt.set(current_timestamp),
            ]

            if request_data.name is not None:
                actions.append(CollectionModel.name.set(request_data.name))

            if request_data.description is not None:
                actions.append(
                    CollectionModel.description.set(request_data.description)
                )

            if request_data.status is not None:
                actions.append(CollectionModel.status.set(request_data.status.value))

            if request_data.isPublic is not None:
                actions.append(CollectionModel.isPublic.set(request_data.isPublic))

            if request_data.metadata is not None:
                actions.append(
                    CollectionModel.customMetadata.set(request_data.metadata)
                )

            if request_data.tags is not None:
                actions.append(CollectionModel.tags.set(request_data.tags))

            # Handle thumbnail updates
            if request_data.thumbnailType is not None:
                actions.append(
                    CollectionModel.thumbnailType.set(request_data.thumbnailType.value)
                )
                # For icon type, just store the icon name
                if request_data.thumbnailType.value == "icon":
                    if request_data.thumbnailValue:
                        actions.append(
                            CollectionModel.thumbnailValue.set(
                                request_data.thumbnailValue
                            )
                        )
                    # Clear S3 key for icon type (no image stored)
                    actions.append(CollectionModel.thumbnailS3Key.remove())

            elif request_data.thumbnailValue is not None:
                # Only set thumbnailValue independently if thumbnailType wasn't also provided
                actions.append(
                    CollectionModel.thumbnailValue.set(request_data.thumbnailValue)
                )

            # Perform update
            try:
                collection.update(actions=actions)
            except UpdateError as e:
                logger.error(f"Error updating collection: {e}")
                raise BadRequestError("Failed to update collection")

            logger.info(f"Collection updated: {collection_id}")
            metrics.add_metric(
                name="SuccessfulCollectionUpdates", unit=MetricUnit.Count, value=1
            )

            # Write-through to OpenSearch so the update is immediately visible
            # in list/search results. Stream sync remains as safety net.
            os_updates = {"updatedAt": current_timestamp}
            if request_data.name is not None:
                os_updates["name"] = request_data.name
            if request_data.description is not None:
                os_updates["description"] = request_data.description
            if request_data.status is not None:
                os_updates["status"] = request_data.status.value
            if request_data.isPublic is not None:
                os_updates["isPublic"] = request_data.isPublic
            if request_data.metadata is not None:
                os_updates["customMetadata"] = request_data.metadata
            if request_data.tags is not None:
                os_updates["tags"] = list(request_data.tags)
            if request_data.thumbnailType is not None:
                os_updates["thumbnailType"] = request_data.thumbnailType.value
                if request_data.thumbnailType.value == "icon":
                    os_updates["thumbnailS3Key"] = None
            if request_data.thumbnailValue is not None:
                os_updates["thumbnailValue"] = request_data.thumbnailValue

            update_collection_document(collection_id, os_updates)

            return {
                "success": True,
                "data": {"id": collection_id, "updatedAt": current_timestamp},
                "meta": {
                    "timestamp": current_timestamp,
                    "version": "v1",
                    "request_id": app.current_event.request_context.request_id,
                },
            }

        except (BadRequestError, NotFoundError):
            raise
        except Exception as e:
            logger.exception("Error updating collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
