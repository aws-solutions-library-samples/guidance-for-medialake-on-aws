"""GET /collections/<collection_id> - Get collection details."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
    create_success_response,
    format_collection_item,
    get_collection_item_count,
)
from db_models import CollectionModel
from pynamodb.exceptions import DoesNotExist
from user_auth import extract_user_context

# Initialize DynamoDB resource for dynamic item count queries
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
collections_table = dynamodb.Table(table_name)

logger = Logger(service="collections-ID-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-ID-get")
metrics = Metrics(namespace="medialake", service="collection-detail")


def get_collection_ancestors(collection_id: str, max_depth: int = 10):
    """Get the ancestor chain for a collection (from root to current)"""
    ancestors = []
    current_id = collection_id
    depth = 0

    while current_id and depth < max_depth:
        try:
            collection = CollectionModel.get(
                f"{COLLECTION_PK_PREFIX}{current_id}", METADATA_SK
            )
        except DoesNotExist:
            logger.warning(f"[ANCESTORS] Collection not found: {current_id}")
            break

        parent_id = collection.parentId if collection.parentId else None
        ancestors.append(
            {
                "id": current_id,
                "name": collection.name,
                "parentId": parent_id,
            }
        )

        current_id = parent_id
        depth += 1

    # Reverse to get root -> current order
    ancestors.reverse()
    return ancestors


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

            # Get dynamic item count (returns -1 on error)
            dynamic_item_count = get_collection_item_count(
                collections_table, collection.PK
            )

            # Convert PynamoDB model to dict for formatting
            collection_dict = {
                "PK": collection.PK,
                "SK": collection.SK,
                "name": collection.name,
                "ownerId": collection.ownerId,
                "status": collection.status,
                "itemCount": dynamic_item_count,
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

            # Add ancestors to the response
            ancestors = get_collection_ancestors(collection_id)
            formatted_collection["ancestors"] = ancestors

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
