"""GET /collections/shared-by-me - Get collections shared by current user."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
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
from user_auth import extract_user_context

logger = Logger(
    service="collections-shared-by-me-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-shared-by-me-get")
metrics = Metrics(namespace="medialake", service="collections")

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
collections_table = dynamodb.Table(table_name)

GRANTOR_PREFIX = "GRANTOR#"


def register_route(app):
    """Register GET /collections/shared-by-me route"""

    @app.get("/collections/shared-by-me")
    @tracer.capture_method
    def collections_shared_by_me_get():
        """Get collections shared by the current user"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError("Authentication required")

            # Query GSI6 to find all shares granted by this user. Paginate so
            # users who have granted more than one page (>1MB) of shares get a
            # complete list rather than a silently truncated one.
            query_kwargs = {
                "IndexName": "SharesGrantedByGSI",
                "KeyConditionExpression": "GSI6_PK = :grantor_pk",
                "ExpressionAttributeValues": {
                    ":grantor_pk": f"{GRANTOR_PREFIX}{user_id}",
                },
            }

            shares = []
            while True:
                response = collections_table.query(**query_kwargs)
                shares.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key

            logger.info(
                "Found shares granted by user",
                extra={
                    "user_id": user_id,
                    "share_count": len(shares),
                },
            )

            # Get unique collection IDs from shares
            collection_ids = list(
                set(share["PK"].replace(COLLECTION_PK_PREFIX, "") for share in shares)
            )

            # Batch get collection details
            collections_with_shares = []
            for collection_id in collection_ids:
                try:
                    # Get collection metadata
                    collection = CollectionModel.get(
                        f"{COLLECTION_PK_PREFIX}{collection_id}",
                        METADATA_SK,
                    )

                    # Get all shares for this collection
                    collection_shares = [
                        s
                        for s in shares
                        if s["PK"] == f"{COLLECTION_PK_PREFIX}{collection_id}"
                    ]

                    # Compute live item count (deprecated stored itemCount drifts);
                    # fall back to the stored value if the count query errors (-1).
                    dynamic_count = get_collection_item_count(
                        collections_table, collection.PK
                    )
                    item_count = (
                        dynamic_count if dynamic_count >= 0 else collection.itemCount
                    )

                    # Format collection with share info
                    collection_dict = {
                        "PK": collection.PK,
                        "SK": collection.SK,
                        "name": collection.name,
                        "description": collection.description,
                        "ownerId": collection.ownerId,
                        "status": collection.status,
                        "isPublic": collection.isPublic,
                        "itemCount": item_count,
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

                    # Add share information
                    formatted_item["shareCount"] = len(collection_shares)
                    formatted_item["isShared"] = True
                    formatted_item["sharedWith"] = [
                        {
                            "targetId": s.get("targetId"),
                            "targetType": s.get("targetType"),
                            "role": s.get("role"),
                            "grantedAt": s.get("grantedAt"),
                        }
                        for s in collection_shares
                    ]

                    collections_with_shares.append(formatted_item)

                except CollectionModel.DoesNotExist:
                    logger.warning(f"Collection {collection_id} not found for share")
                    continue

            metrics.add_metric(
                name="SharedByMeCollectionsReturned",
                unit=MetricUnit.Count,
                value=len(collections_with_shares),
            )

            return create_success_response(
                data=collections_with_shares,
                request_id=app.current_event.request_context.request_id,
            )

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error listing collections shared by user", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
