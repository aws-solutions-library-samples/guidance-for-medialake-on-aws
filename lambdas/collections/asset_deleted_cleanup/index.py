"""
Collections Asset Deletion Cleanup
==================================
Event-driven consumer that removes a deleted asset from every collection that
referenced it.

Triggered by ``AssetDeleted`` events (source ``medialake.assets``) delivered via
the internal application-service-events EventBridge bus. The asset deletion
service itself does not touch collections, so without this consumer the asset's
collection-item rows would be orphaned (still counted, still listed, pointing at
an asset that no longer exists).

Backwards compatibility
------------------------
This consumer works against the EXISTING collections table as-is. It does not
require any change to the table's keys, GSIs, or index configuration, and it
does not assume a particular ``GSI2_PK`` format.

Collection items are stored with these shapes (all already present in the live
table)::

    new asset format : SK = ASSET#{asset_id}#FULL or ASSET#{asset_id}#CLIP#...
                       assetId = {asset_id}
    legacy item format: SK = ITEM#{item_id}
                       itemId  = {item_id}

An asset may appear several times in one collection (full file plus clips). The
canonical link to the asset is the ``assetId`` attribute (``itemId`` for legacy
rows), which is identical for full file and every clip. We therefore locate all
matching rows with a filtered table scan on those attributes (with an ``SK``
prefix as a defensive fallback) and delete each row by its real PK/SK.

A scan is used deliberately: there is no index keyed on the bare asset id, and
adding one is explicitly out of scope. Asset deletion is an infrequent,
asynchronous operation, so scanning the (comparatively small) collections table
is an acceptable tradeoff.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Attr

logger = Logger(service="collections-asset-cleanup")
tracer = Tracer(service="collections-asset-cleanup")
metrics = Metrics(namespace="medialake", service="collections-asset-cleanup")

TABLE_NAME = os.environ["COLLECTIONS_TABLE_NAME"]

# SK prefixes used by collection-item rows.
ASSET_SK_PREFIX = "ASSET#"
ITEM_SK_PREFIX = "ITEM#"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


@tracer.capture_method
def _find_collection_rows(inventory_id: str) -> List[Tuple[str, str]]:
    """Find all collection-item rows referencing the asset.

    Matches across both storage formats without depending on the GSI:
      * ``assetId`` equals the inventory id (new ASSET# rows, full + clips)
      * ``itemId`` equals the inventory id (legacy ITEM# rows)
      * ``SK`` begins with ``ASSET#{id}#`` (defensive fallback for rows missing
        the ``assetId`` attribute)

    Returns a list of ``(PK, SK)`` tuples.
    """
    asset_sk_prefix = f"{ASSET_SK_PREFIX}{inventory_id}#"

    filter_expression = (
        Attr("assetId").eq(inventory_id)
        | Attr("itemId").eq(inventory_id)
        | Attr("SK").begins_with(asset_sk_prefix)
    )

    rows: List[Tuple[str, str]] = []
    scan_kwargs: Dict[str, Any] = {
        "FilterExpression": filter_expression,
        "ProjectionExpression": "PK, SK",
    }
    last_evaluated_key = None

    while True:
        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        for item in response.get("Items", []):
            pk = item.get("PK")
            sk = item.get("SK")
            # Guard against matching the collection metadata row or any
            # non-item rows that could theoretically carry the attribute.
            if (
                pk
                and sk
                and (sk.startswith(ASSET_SK_PREFIX) or sk.startswith(ITEM_SK_PREFIX))
            ):
                rows.append((pk, sk))

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return rows


@tracer.capture_method
def _delete_rows(rows: List[Tuple[str, str]]) -> int:
    """Batch-delete collection-item rows. Returns the number deleted."""
    deleted = 0
    with table.batch_writer() as batch:
        for pk, sk in rows:
            batch.delete_item(Key={"PK": pk, "SK": sk})
            deleted += 1
    return deleted


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], _context: LambdaContext) -> Dict[str, Any]:
    """Remove a deleted asset from every collection that referenced it."""
    detail = event.get("detail", {}) or {}
    inventory_id = detail.get("inventoryId") or detail.get("inventory_id")

    if not inventory_id:
        logger.warning(
            "AssetDeleted event missing inventoryId; skipping", extra={"event": event}
        )
        return {"removed": 0, "inventoryId": None}

    logger.info(f"Cleaning up collections for deleted asset: {inventory_id}")

    rows = _find_collection_rows(inventory_id)

    if not rows:
        logger.info(f"No collection items found for asset {inventory_id}")
        metrics.add_metric(
            name="OrphanedCollectionItemsRemoved", unit=MetricUnit.Count, value=0
        )
        return {"removed": 0, "inventoryId": inventory_id}

    affected_collections = {pk for pk, _ in rows}
    removed = _delete_rows(rows)

    logger.info(
        f"Removed asset {inventory_id} from {len(affected_collections)} collection(s)",
        extra={"rows_removed": removed, "collections": len(affected_collections)},
    )
    metrics.add_metric(
        name="OrphanedCollectionItemsRemoved", unit=MetricUnit.Count, value=removed
    )

    return {
        "removed": removed,
        "inventoryId": inventory_id,
        "collectionsAffected": len(affected_collections),
    }
