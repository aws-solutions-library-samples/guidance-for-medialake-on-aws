"""Migrate ownership of collections from a deleted user to a new owner.

When a user is deleted, any collections they OWN would otherwise be orphaned —
the ``ownerId`` on the collection metadata keeps pointing at a user that no
longer exists, and nobody can manage the collection. To avoid this, ownership
is transferred to a new owner (typically the administrator performing the
deletion) before the user is removed.

Because a user may own an unbounded number of collections, the migration runs
**asynchronously**: the delete handler self-invokes this Lambda
(``InvocationType="Event"``) so the API call returns immediately, and the
background worker has the full Lambda timeout to process everything. The
relationship-row writes are issued through ``batch_writer`` (``BatchWriteItem``,
25 items per request, with automatic retry of unprocessed items) so hundreds or
thousands of collections migrate efficiently.

This module operates directly on the collections single-table design via the
boto3 DynamoDB resource (the same style used by ``users_delete._cleanup_user_data``)
so the users Lambda does not need the PynamoDB models or VPC/OpenSearch access.
OpenSearch stays consistent automatically: the collections table has DynamoDB
Streams enabled and a sync Lambda mirrors ``ownerId`` changes into the search
index.

Single-table layout touched here:
- Collection metadata: ``PK=COLL#{id}``, ``SK=METADATA`` (authoritative ``ownerId``)
- User relationship:    ``PK=USER#{user_id}``, ``SK=COLL#{id}`` (``relationship`` in
  {OWNER, EDITOR, VIEWER}); GSI1 ``UserCollectionsGSI`` is keyed on
  ``GSI1_PK=USER#{user_id}``.
"""

import json
import os
from datetime import datetime, timezone
from typing import List

import boto3
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

USER_PK_PREFIX = "USER#"
COLLECTION_PK_PREFIX = "COLL#"
METADATA_SK = "METADATA"
USER_COLLECTIONS_GSI = "UserCollectionsGSI"
OWNER_RELATIONSHIP = "OWNER"

# Marker key on a self-invoke payload that routes the Lambda to the async
# collection-migration worker instead of the API Gateway router.
ASYNC_MIGRATE_EVENT_KEY = "async_migrate_collections"


def trigger_collection_migration(
    deleted_user_id: str,
    new_owner_id: str,
    logger,
) -> bool:
    """Fire-and-forget a self-invoke to migrate collections in the background.

    Deleting a user can leave them owning an unbounded number of collections.
    Reassigning all of them inline would risk exceeding the API Gateway 29s
    timeout, so the work is offloaded to an asynchronous invocation of this
    same Lambda (``InvocationType="Event"``) which has the full function
    timeout to churn through everything in batches.

    Args:
        deleted_user_id: Cognito sub of the user being deleted.
        new_owner_id: Cognito sub that should inherit the collections.
        logger: Logger instance.

    Returns:
        True if the async worker was successfully invoked, False otherwise.
    """
    if not new_owner_id or new_owner_id == deleted_user_id:
        logger.warning(
            {
                "message": (
                    "Skipping collection migration — no valid new owner "
                    "distinct from the deleted user"
                ),
                "deleted_user_id": deleted_user_id,
                "new_owner_id": new_owner_id,
                "operation": "trigger_collection_migration",
            }
        )
        return False

    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    if not function_name:
        logger.warning(
            {
                "message": "Cannot self-invoke — AWS_LAMBDA_FUNCTION_NAME unset",
                "deleted_user_id": deleted_user_id,
                "operation": "trigger_collection_migration",
            }
        )
        return False

    payload = json.dumps(
        {
            ASYNC_MIGRATE_EVENT_KEY: True,
            "deleted_user_id": deleted_user_id,
            "new_owner_id": new_owner_id,
        }
    )

    try:
        boto3.client("lambda").invoke(
            FunctionName=function_name,
            InvocationType="Event",  # async — returns immediately
            Payload=payload,
        )
        logger.info(
            {
                "message": "Triggered async collection migration",
                "deleted_user_id": deleted_user_id,
                "new_owner_id": new_owner_id,
                "operation": "trigger_collection_migration",
            }
        )
        return True
    except Exception:
        logger.exception(
            "Failed to trigger async collection migration",
            extra={
                "deleted_user_id": deleted_user_id,
                "new_owner_id": new_owner_id,
            },
        )
        return False


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a trailing ``Z``."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _find_owned_collection_ids(table, deleted_user_id: str) -> List[str]:
    """Return the IDs of all collections OWNED by ``deleted_user_id``.

    Queries the ``UserCollectionsGSI`` for every collection the user has a
    relationship with, keeping only the rows where they are the OWNER.
    """
    owned_collection_ids: List[str] = []
    params = {
        "IndexName": USER_COLLECTIONS_GSI,
        "KeyConditionExpression": "GSI1_PK = :user_pk",
        "FilterExpression": "relationship = :owner",
        "ExpressionAttributeValues": {
            ":user_pk": f"{USER_PK_PREFIX}{deleted_user_id}",
            ":owner": OWNER_RELATIONSHIP,
        },
    }

    while True:
        response = table.query(**params)
        for item in response.get("Items", []):
            sk = item.get("SK", "")
            if sk.startswith(COLLECTION_PK_PREFIX):
                collection_id = sk[len(COLLECTION_PK_PREFIX) :]
                owned_collection_ids.append(collection_id)

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        params["ExclusiveStartKey"] = last_key

    return owned_collection_ids


def _new_owner_relationship_item(
    collection_pk: str,
    new_owner_id: str,
    timestamp: str,
) -> dict:
    """Build the OWNER relationship row for the new owner."""
    return {
        "PK": f"{USER_PK_PREFIX}{new_owner_id}",
        "SK": collection_pk,
        "relationship": OWNER_RELATIONSHIP,
        "addedAt": timestamp,
        "lastAccessed": timestamp,
        "isFavorite": False,
        "GSI1_PK": f"{USER_PK_PREFIX}{new_owner_id}",
        "GSI1_SK": timestamp,
        "GSI2_PK": collection_pk,
        "GSI2_SK": f"{USER_PK_PREFIX}{new_owner_id}",
    }


def migrate_user_collections(
    dynamodb,
    collections_table_name: str,
    deleted_user_id: str,
    new_owner_id: str,
    logger,
    metrics=None,
) -> int:
    """Migrate collections owned by ``deleted_user_id`` to ``new_owner_id``.

    Ownership transfer for each collection involves three writes:
    1. Repoint the authoritative ``ownerId`` on the collection metadata
       (a partial ``update_item`` so other attributes are preserved).
    2. Create/upgrade the new owner's OWNER relationship row.
    3. Remove the deleted user's stale OWNER relationship row.

    Steps 2 and 3 are pure put/delete operations and are issued through
    ``batch_writer`` so they scale to large collection counts. Step 1 is
    applied per collection first; only collections whose metadata update
    succeeds have their relationship rows rewritten, keeping the two in sync.

    Args:
        dynamodb: boto3 DynamoDB resource.
        collections_table_name: The collections single-table name.
        deleted_user_id: The Cognito sub of the user being deleted.
        new_owner_id: The Cognito sub that should inherit the collections
            (typically the administrator performing the deletion).
        logger: Logger instance.
        metrics: Optional PowerTools Metrics instance.

    Returns:
        Number of collections whose ownership was transferred.
    """
    if not new_owner_id or new_owner_id == deleted_user_id:
        logger.warning(
            {
                "message": (
                    "Skipping collection migration — no valid new owner "
                    "distinct from the deleted user"
                ),
                "deleted_user_id": deleted_user_id,
                "new_owner_id": new_owner_id,
                "operation": "migrate_user_collections",
            }
        )
        return 0

    table = dynamodb.Table(collections_table_name)

    try:
        owned_collection_ids = _find_owned_collection_ids(table, deleted_user_id)
        if not owned_collection_ids:
            return 0

        # Step 1: repoint metadata ownerId for each collection. Track which
        # succeed so only those have their relationship rows rewritten.
        migrated_ids: List[str] = []
        for collection_id in owned_collection_ids:
            timestamp = _utc_now()
            try:
                table.update_item(
                    Key={
                        "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                        "SK": METADATA_SK,
                    },
                    UpdateExpression="SET ownerId = :new_owner, updatedAt = :ts",
                    ExpressionAttributeValues={
                        ":new_owner": new_owner_id,
                        ":ts": timestamp,
                    },
                )
                migrated_ids.append(collection_id)
            except ClientError as e:
                # Don't abort the whole migration if a single collection fails.
                logger.error(
                    {
                        "message": "Failed to repoint collection ownerId",
                        "deleted_user_id": deleted_user_id,
                        "new_owner_id": new_owner_id,
                        "collection_id": collection_id,
                        "error_code": e.response["Error"]["Code"],
                        "error_message": e.response["Error"]["Message"],
                        "operation": "migrate_user_collections",
                    }
                )

        # Steps 2 & 3: rewrite relationship rows in batches. batch_writer
        # buffers writes and flushes them via BatchWriteItem (25 per request),
        # automatically retrying any unprocessed items.
        timestamp = _utc_now()
        with table.batch_writer() as batch:
            for collection_id in migrated_ids:
                collection_pk = f"{COLLECTION_PK_PREFIX}{collection_id}"
                batch.put_item(
                    Item=_new_owner_relationship_item(
                        collection_pk, new_owner_id, timestamp
                    )
                )
                batch.delete_item(
                    Key={
                        "PK": f"{USER_PK_PREFIX}{deleted_user_id}",
                        "SK": collection_pk,
                    }
                )

        migrated_count = len(migrated_ids)
        if migrated_count > 0:
            logger.info(
                {
                    "message": "Migrated owned collections to new owner",
                    "deleted_user_id": deleted_user_id,
                    "new_owner_id": new_owner_id,
                    "collections_migrated": migrated_count,
                    "operation": "migrate_user_collections",
                }
            )
            if metrics is not None:
                metrics.add_metric(
                    name="CollectionsMigrated",
                    unit=MetricUnit.Count,
                    value=migrated_count,
                )

        return migrated_count

    except ClientError as e:
        # Log but don't fail — the Cognito user is already gone. The async
        # invocation will be retried automatically by Lambda on error.
        logger.error(
            {
                "message": "Failed to migrate user collections",
                "deleted_user_id": deleted_user_id,
                "new_owner_id": new_owner_id,
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "operation": "migrate_user_collections",
            }
        )
        return 0
