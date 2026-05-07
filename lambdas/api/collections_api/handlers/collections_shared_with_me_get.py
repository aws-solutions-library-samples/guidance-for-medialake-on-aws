"""GET /collections/shared-with-me - Get collections shared with current user."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    USER_PK_PREFIX,
    create_error_response,
    create_success_response,
    format_collection_item,
)
from db_models import CollectionModel
from user_auth import extract_user_context

logger = Logger(
    service="collections-shared-with-me-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-shared-with-me-get")
metrics = Metrics(namespace="medialake", service="collections")

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
collections_table = dynamodb.Table(table_name)


def register_route(app):
    """Register GET /collections/shared-with-me route"""

    @app.get("/collections/shared-with-me")
    @tracer.capture_method
    def collections_shared_with_me_get():
        """Get collections shared with the current user"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            # Query user's shared collections via UserRelationshipModel
            # Using GSI1 (UserCollectionsGSI) to find all collections user has access to
            response = collections_table.query(
                IndexName="UserCollectionsGSI",
                KeyConditionExpression="GSI1_PK = :user_pk",
                FilterExpression="relationship <> :owner",
                ExpressionAttributeValues={
                    ":user_pk": f"{USER_PK_PREFIX}{user_id}",
                    ":owner": "OWNER",
                },
            )

            user_relationships = response.get("Items", [])

            logger.info(
                "Found shared collections for user",
                extra={
                    "user_id": user_id,
                    "shared_count": len(user_relationships),
                },
            )

            # Get collection details for each relationship
            shared_collections = []
            for relationship in user_relationships:
                # Extract collection ID from SK (format: COLL#{collection_id})
                collection_id = relationship.get("SK", "").replace(
                    COLLECTION_PK_PREFIX, ""
                )

                if not collection_id:
                    continue

                try:
                    # Get collection metadata
                    collection = CollectionModel.get(
                        f"{COLLECTION_PK_PREFIX}{collection_id}",
                        METADATA_SK,
                    )

                    # Format collection
                    collection_dict = {
                        "PK": collection.PK,
                        "SK": collection.SK,
                        "name": collection.name,
                        "description": collection.description,
                        "ownerId": collection.ownerId,
                        "status": collection.status,
                        "isPublic": collection.isPublic,
                        "itemCount": collection.itemCount,
                        "childCollectionCount": collection.childCollectionCount,
                        "collectionTypeId": collection.collectionTypeId,
                        "parentId": collection.parentId,
                        "tags": collection.tags,
                        "createdAt": collection.createdAt,
                        "updatedAt": collection.updatedAt,
                    }

                    formatted_item = format_collection_item(
                        collection_dict, user_context
                    )

                    # Add sharing metadata
                    formatted_item["sharedWithMe"] = True
                    formatted_item["myRole"] = relationship.get(
                        "relationship", "VIEWER"
                    )
                    formatted_item["sharedAt"] = relationship.get("addedAt")

                    shared_collections.append(formatted_item)

                except CollectionModel.DoesNotExist:
                    logger.warning(
                        f"Collection {collection_id} not found for shared relationship"
                    )
                    continue

            metrics.add_metric(
                name="SharedWithMeCollectionsReturned",
                unit=MetricUnit.Count,
                value=len(shared_collections),
            )

            return create_success_response(
                data=shared_collections,
                request_id=app.current_event.request_context.request_id,
            )

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error listing shared collections", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
