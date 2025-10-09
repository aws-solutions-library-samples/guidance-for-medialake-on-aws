"""DELETE /collections/<collection_id> - Delete collection (hard delete)."""

import json
import os
import sys
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit

sys.path.insert(0, "/opt/python")
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from user_auth import extract_user_context

logger = Logger(
    service="collections-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-detail")


def register_route(app, dynamodb, table_name):
    """Register DELETE /collections/<collection_id> route"""

    @app.delete("/collections/<collection_id>")
    @tracer.capture_method
    def collections_ID_delete(collection_id: str):
        """Delete collection and all its items (hard delete)"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")
            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            logger.info(
                f"[DELETE] Starting hard delete for collection: {collection_id}"
            )

            # Step 1: Verify collection exists and user has permission
            collection_response = table.get_item(
                Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
            )
            if "Item" not in collection_response:
                logger.warning(f"[DELETE] Collection not found: {collection_id}")
                raise NotFoundError(f"Collection '{collection_id}' not found")

            collection = collection_response["Item"]
            if collection.get("ownerId") != user_id:
                logger.warning(
                    f"[DELETE] User {user_id} is not owner of collection {collection_id}"
                )
                raise BadRequestError(
                    "You do not have permission to delete this collection"
                )

            # Step 2: Query all items in the collection
            items_to_delete = []
            paginator_kwargs = {
                "KeyConditionExpression": "PK = :pk",
                "ExpressionAttributeValues": {
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}"
                },
            }
            while True:
                response = table.query(**paginator_kwargs)
                items_to_delete.extend(response.get("Items", []))
                if "LastEvaluatedKey" not in response:
                    break
                paginator_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            logger.info(
                f"[DELETE] Found {len(items_to_delete)} items in collection partition"
            )

            # Step 3: Query user relationships (GSI2)
            user_relationships = []
            gsi_kwargs = {
                "IndexName": "ItemCollectionsGSI",
                "KeyConditionExpression": "GSI2_PK = :collection_pk",
                "ExpressionAttributeValues": {
                    ":collection_pk": f"{COLLECTION_PK_PREFIX}{collection_id}"
                },
            }
            while True:
                response = table.query(**gsi_kwargs)
                user_relationships.extend(response.get("Items", []))
                if "LastEvaluatedKey" not in response:
                    break
                gsi_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            logger.info(f"[DELETE] Found {len(user_relationships)} user relationships")

            # Combine and deduplicate
            all_items_to_delete = items_to_delete + user_relationships
            seen = set()
            unique_items = []
            for item in all_items_to_delete:
                key = (item["PK"], item["SK"])
                if key not in seen:
                    seen.add(key)
                    unique_items.append(item)
            logger.info(f"[DELETE] Total unique items to delete: {len(unique_items)}")

            # Step 4: Delete all items in batches
            if unique_items:
                batch_size = 25
                deleted_count = 0
                for i in range(0, len(unique_items), batch_size):
                    batch = unique_items[i : i + batch_size]
                    with table.batch_writer() as batch_writer:
                        for item in batch:
                            batch_writer.delete_item(
                                Key={"PK": item["PK"], "SK": item["SK"]}
                            )
                            deleted_count += 1
                    logger.info(
                        f"[DELETE] Deleted batch {i//batch_size + 1}: {len(batch)} items"
                    )
                logger.info(f"[DELETE] Successfully deleted {deleted_count} items")

            logger.info(f"[DELETE] Collection hard delete complete: {collection_id}")
            metrics.add_metric(
                name="SuccessfulCollectionDeletions", unit=MetricUnit.Count, value=1
            )
            metrics.add_metric(
                name="CollectionItemsDeleted",
                unit=MetricUnit.Count,
                value=len(unique_items),
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "id": collection_id,
                            "status": "DELETED",
                            "itemsDeleted": len(unique_items),
                        },
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
            logger.exception(
                f"[DELETE] Error deleting collection {collection_id}", exc_info=e
            )
            metrics.add_metric(
                name="FailedCollectionDeletions", unit=MetricUnit.Count, value=1
            )
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
