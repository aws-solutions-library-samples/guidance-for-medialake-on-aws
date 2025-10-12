"""GET /collections/<collection_id> - Get collection details."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    create_success_response,
    format_collection_item,
)
from db_models import CollectionModel
from pynamodb.exceptions import DoesNotExist
from user_auth import extract_user_context

logger = Logger(service="collections-ID-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-ID-get")
metrics = Metrics(namespace="medialake", service="collection-detail")


def register_route(app):
    """Register GET /collections/<collection_id> route"""

    @app.get("/collections/<collection_id>")
    @tracer.capture_method
    def collections_ID_get(collection_id: str):
        """Get collection details with optional includes"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)

            # Get collection from DynamoDB using PynamoDB
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
            except DoesNotExist:
                raise NotFoundError(f"Collection '{collection_id}' not found")

            # Convert PynamoDB model to dict for formatting
            collection_dict = {
                "PK": collection.PK,
                "SK": collection.SK,
                "name": collection.name,
                "ownerId": collection.ownerId,
                "status": collection.status,
                "itemCount": collection.itemCount,
                "childCollectionCount": collection.childCollectionCount,
                "isPublic": collection.isPublic,
                "createdAt": collection.createdAt,
                "updatedAt": collection.updatedAt,
            }

            if collection.description:
                collection_dict["description"] = collection.description
            if collection.collectionTypeId:
                collection_dict["collectionTypeId"] = collection.collectionTypeId
            if collection.parentId:
                collection_dict["parentId"] = collection.parentId
            if collection.customMetadata:
                collection_dict["customMetadata"] = dict(collection.customMetadata)
            if collection.tags:
                collection_dict["tags"] = list(collection.tags)
            if collection.expiresAt:
                collection_dict["expiresAt"] = collection.expiresAt

            formatted_collection = format_collection_item(collection_dict, user_context)

            metrics.add_metric(
                name="SuccessfulCollectionRetrievals", unit=MetricUnit.Count, value=1
            )

            return create_success_response(
                data=formatted_collection,
                request_id=app.current_event.request_context.request_id,
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.exception("Error retrieving collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
