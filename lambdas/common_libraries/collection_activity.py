"""
Collection activity tracking for MediaLake Lambda functions.

This module provides the shared helper for recording per-user collection
modification activity. Each (user, collection) pair maintains a single
recency record on the user table with a conditional keep-max upsert that
guarantees the stored timestamp is the maximum seen for the pair, even
under out-of-order events.

The record populates GSI5 (RecentCollectionsByUser) via a reverse-timestamp
sort key so the most recently modified collections appear first.
"""

import os
import time
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="collection-activity")

USER_TABLE_NAME = os.getenv("USER_TABLE_NAME", "")
_RECENT_PREFIX = "RECENTCOLL#"
_REVERSE_TS_CEILING = 9_999_999_999_999

# Module-level cached table reference (initialised lazily)
_user_table = None


def _get_user_table(table=None):
    """Return the DynamoDB Table resource, using a cached instance when possible."""
    global _user_table
    if table is not None:
        return table
    if _user_table is None and USER_TABLE_NAME:
        _user_table = boto3.resource("dynamodb").Table(USER_TABLE_NAME)
    return _user_table


def _iso_from_ms(epoch_ms: int) -> str:
    """Convert epoch milliseconds to an ISO-8601 UTC timestamp string."""
    dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def record_collection_activity(user_id: str, collection_id: str, table=None) -> None:
    """Upsert the (user, collection) recency record, keeping the latest timestamp.

    Writes a single item per (user, collection) pair to the user table with a
    stable sort key ``RECENTCOLL#{collectionId}``. The ``ConditionExpression``
    ensures the stored timestamp is the maximum seen for the pair even when
    events arrive out of order.

    Silent-fail: activity tracking must never break the calling operation.

    Args:
        user_id: The identifier of the user performing the activity.
        collection_id: The identifier of the collection being acted upon.
        table: Optional DynamoDB Table resource (for testing injection).
    """
    if not USER_TABLE_NAME or not user_id or not collection_id:
        return

    try:
        now_ms = int(time.time() * 1000)
        reverse_ts = str(_REVERSE_TS_CEILING - now_ms).zfill(16)
        iso = _iso_from_ms(now_ms)
        tbl = _get_user_table(table)
        if tbl is None:
            return

        tbl.update_item(
            Key={
                "userId": f"USER#{user_id}",
                "itemKey": f"{_RECENT_PREFIX}{collection_id}",
            },
            UpdateExpression=(
                "SET collectionId = :cid, itemType = :t, "
                "lastActivityAt = :iso, lastActivityMs = :ms, gsi5Sk = :rts"
            ),
            ConditionExpression=(
                "attribute_not_exists(lastActivityMs) OR lastActivityMs < :ms"
            ),
            ExpressionAttributeValues={
                ":cid": collection_id,
                ":t": "RECENT_COLLECTION",
                ":iso": iso,
                ":ms": now_ms,
                ":rts": reverse_ts,
            },
        )
    except Exception as e:
        # ConditionalCheckFailedException means a newer activity is already
        # recorded — this is expected and not an error.
        if (
            hasattr(e, "response")
            and e.response.get("Error", {}).get("Code")
            == "ConditionalCheckFailedException"
        ):
            pass  # a newer activity already recorded — fine
        else:
            logger.warning(
                "record_collection_activity failed",
                extra={
                    "user_id": user_id,
                    "collection_id": collection_id,
                    "error": str(e),
                },
            )
