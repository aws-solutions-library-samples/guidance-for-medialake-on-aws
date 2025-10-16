"""DELETE /collections/<collection_id> - Delete collection (hard delete)."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import (
    CHILD_SK_PREFIX,
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    create_error_response,
)
from db_models import (
    ChildReferenceModel,
    CollectionItemModel,
    CollectionModel,
    UserRelationshipModel,
)
from pynamodb.exceptions import DoesNotExist
from user_auth import extract_user_context

logger = Logger(
    service="collections-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-detail")


def _delete_collection_recursive(collection_id, user_id, current_timestamp):
    """Recursively delete a collection and all its children using PynamoDB"""
    logger.info(f"[CASCADE] Deleting collection: {collection_id}")

    # Step 1: Query for child collections using CHILD# references
    child_refs = []
    try:
        for child_ref in ChildReferenceModel.query(
            f"{COLLECTION_PK_PREFIX}{collection_id}",
            ChildReferenceModel.SK.startswith(CHILD_SK_PREFIX),
        ):
            child_refs.append(child_ref)
    except Exception as e:
        logger.warning(f"[CASCADE] Error querying child references: {e}")

    logger.info(f"[CASCADE] Found {len(child_refs)} children for {collection_id}")

    # Step 2: Recursively delete each child first
    for child_ref in child_refs:
        child_id = child_ref.childCollectionId
        if child_id:
            logger.info(f"[CASCADE] Recursively deleting child: {child_id}")
            _delete_collection_recursive(child_id, user_id, current_timestamp)

    # Step 3: Delete this collection's items (query all items in partition)
    deleted_count = 0
    items_to_delete = []

    # Query all items for this collection (different SK prefixes: METADATA, ITEM#, ASSET#, PERM#, RULE#, CHILD#)
    # We need to scan the partition
    try:
        # Use scan on the partition key to get all items
        for item in CollectionModel.query(f"{COLLECTION_PK_PREFIX}{collection_id}"):
            items_to_delete.append((item.PK, item.SK))
            deleted_count += 1
    except Exception as e:
        logger.warning(f"[CASCADE] Error querying collection items: {e}")

    # Step 4: Query user relationships (GSI2) - users who have access to this collection
    try:
        # UserRelationshipModel has GSI2_PK = COLL#{collection_id}
        # We need to query the GSI to find all user relationships
        for user_rel in UserRelationshipModel.GSI2_PK_index.query(
            f"{COLLECTION_PK_PREFIX}{collection_id}"
        ):
            items_to_delete.append((user_rel.PK, user_rel.SK))
            deleted_count += 1
    except AttributeError:
        # GSI2 index not defined, query directly
        logger.warning("[CASCADE] GSI2 index not available for user relationships")
    except Exception as e:
        logger.warning(f"[CASCADE] Error querying user relationships: {e}")

    # Step 5: Delete all items in batches
    if items_to_delete:
        # PynamoDB batch delete
        batch_size = 25
        for i in range(0, len(items_to_delete), batch_size):
            batch = items_to_delete[i : i + batch_size]
            with CollectionModel.batch_write() as batch_writer:
                for pk, sk in batch:
                    # Determine which model to use based on SK prefix
                    if sk == METADATA_SK:
                        batch_writer.delete(CollectionModel(pk, sk))
                    elif sk.startswith("USER#"):
                        batch_writer.delete(UserRelationshipModel(pk, sk))
                    elif sk.startswith(CHILD_SK_PREFIX):
                        batch_writer.delete(ChildReferenceModel(pk, sk))
                    elif sk.startswith("ASSET#") or sk.startswith("ITEM#"):
                        batch_writer.delete(CollectionItemModel(pk, sk))
                    elif sk.startswith("PERM#"):
                        # ShareModel would be here
                        try:
                            from db_models import ShareModel

                            batch_writer.delete(ShareModel(pk, sk))
                        except Exception:
                            pass
                    elif sk.startswith("RULE#"):
                        # RuleModel would be here
                        try:
                            from db_models import RuleModel

                            batch_writer.delete(RuleModel(pk, sk))
                        except Exception:
                            pass

    logger.info(
        f"[CASCADE] Deleted {deleted_count} items from collection {collection_id}"
    )
    return deleted_count


def register_route(app):
    """Register DELETE /collections/<collection_id> route"""

    @app.delete("/collections/<collection_id>")
    @tracer.capture_method
    def collections_ID_delete(collection_id: str):
        """Delete collection and all its children (cascade delete)"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            logger.info(
                f"[DELETE] Starting cascade delete for collection: {collection_id}"
            )

            # Step 1: Verify collection exists and user has permission
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
            except DoesNotExist:
                logger.warning(f"[DELETE] Collection not found: {collection_id}")
                raise NotFoundError(f"Collection '{collection_id}' not found")

            if collection.ownerId != user_id:
                logger.warning(
                    f"[DELETE] User {user_id} is not owner of collection {collection_id}"
                )
                raise BadRequestError(
                    "You do not have permission to delete this collection"
                )

            # Step 2: Recursively delete this collection and all children
            total_deleted = _delete_collection_recursive(
                collection_id, user_id, current_timestamp
            )

            # Step 3: If this is a child collection, remove CHILD# reference from parent
            parent_id = (
                collection.parentId
                if hasattr(collection, "parentId") and collection.parentId
                else None
            )
            if parent_id:
                logger.info(
                    f"[DELETE] Removing CHILD# reference from parent: {parent_id}"
                )
                try:
                    # Delete the CHILD# reference item
                    child_ref = ChildReferenceModel(
                        f"{COLLECTION_PK_PREFIX}{parent_id}",
                        f"{CHILD_SK_PREFIX}{collection_id}",
                    )
                    child_ref.delete()

                    # Decrement parent's childCollectionCount
                    parent = CollectionModel.get(
                        f"{COLLECTION_PK_PREFIX}{parent_id}", METADATA_SK
                    )
                    parent.update(
                        actions=[
                            CollectionModel.childCollectionCount.add(-1),
                            CollectionModel.updatedAt.set(current_timestamp),
                        ]
                    )
                    logger.info(
                        "[DELETE] Successfully removed CHILD# reference and decremented count"
                    )
                except Exception as e:
                    logger.warning(
                        f"[DELETE] Failed to remove CHILD# reference from parent {parent_id}: {e}"
                    )

            logger.info(f"[DELETE] Cascade delete complete: {collection_id}")
            metrics.add_metric(
                name="SuccessfulCollectionDeletions", unit=MetricUnit.Count, value=1
            )
            metrics.add_metric(
                name="CollectionItemsDeleted",
                unit=MetricUnit.Count,
                value=total_deleted,
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "id": collection_id,
                            "status": "DELETED",
                            "itemsDeleted": total_deleted,
                            "deletionType": "CASCADE",
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
