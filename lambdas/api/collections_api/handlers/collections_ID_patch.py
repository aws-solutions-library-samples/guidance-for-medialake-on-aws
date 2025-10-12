"""PATCH /collections/<collection_id> - Update collection."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from db_models import CollectionModel
from models import UpdateCollectionRequest
from pynamodb.exceptions import DoesNotExist, UpdateError
from user_auth import extract_user_context

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
            user_context.get("user_id")

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

            # Build update actions for PynamoDB
            actions = [CollectionModel.updatedAt.set(current_timestamp)]

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

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {"id": collection_id, "updatedAt": current_timestamp},
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
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
