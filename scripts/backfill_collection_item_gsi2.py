#!/usr/bin/env python3
"""Backfill the asset -> collections reverse lookup on legacy collection items.

Legacy collections store items as ``ITEM#{uuid}`` rows whose GSI2_PK is not derived
from the asset id, so ``POST /collections/membership`` (the "in a collection" badge on
the Assets tab) cannot find them. This sets, on each full-file ``ITEM#`` row::

    GSI2_PK = ASSET#{assetId}#FULL
    GSI2_SK = COLL#{collection_id}

Rows for clips (non-empty ``clipBoundary``), rows with no ``assetId``, and rows that
already carry the right GSI2 keys are left alone. Dry-run by default; pass --apply to
write. Safe to re-run.

Usage:
    python scripts/backfill_collection_item_gsi2.py --table <collections-table-name>
    python scripts/backfill_collection_item_gsi2.py --table <name> --apply
"""

import argparse
import sys

import boto3
from botocore.exceptions import ClientError

COLLECTION_PK_PREFIX = "COLL#"
ITEM_SK_PREFIX = "ITEM#"
ASSET_SK_PREFIX = "ASSET#"
FULL_SUFFIX = "#FULL"


def iter_legacy_rows(table):
    """Yield every ITEM# row in the table (a scan; run once, off-peak)."""
    kwargs = {
        "FilterExpression": "begins_with(PK, :coll) AND begins_with(SK, :item)",
        "ExpressionAttributeValues": {
            ":coll": COLLECTION_PK_PREFIX,
            ":item": ITEM_SK_PREFIX,
        },
        "ProjectionExpression": "PK, SK, assetId, clipBoundary, GSI2_PK, GSI2_SK",
    }
    while True:
        response = table.scan(**kwargs)
        yield from response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return
        kwargs["ExclusiveStartKey"] = last_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--table", required=True, help="Collections DynamoDB table name")
    parser.add_argument("--region", help="AWS region (default: from environment)")
    parser.add_argument(
        "--apply", action="store_true", help="Write changes (default is a dry run)"
    )
    args = parser.parse_args()

    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    counts = {"scanned": 0, "updated": 0, "already_ok": 0, "skipped": 0, "failed": 0}

    for row in iter_legacy_rows(table):
        counts["scanned"] += 1
        asset_id = row.get("assetId")
        boundary = row.get("clipBoundary") or {}
        has_clip = any(boundary.get(k) for k in ("startTime", "endTime"))
        if not asset_id or has_clip:
            counts["skipped"] += 1
            continue

        gsi2_pk = f"{ASSET_SK_PREFIX}{asset_id}{FULL_SUFFIX}"
        gsi2_sk = row["PK"]  # already COLL#{collection_id}
        if row.get("GSI2_PK") == gsi2_pk and row.get("GSI2_SK") == gsi2_sk:
            counts["already_ok"] += 1
            continue

        action = "UPDATE" if args.apply else "WOULD UPDATE"
        print(f"{action} {row['PK']} {row['SK']} -> {gsi2_pk}")
        if not args.apply:
            counts["updated"] += 1
            continue
        try:
            table.update_item(
                Key={"PK": row["PK"], "SK": row["SK"]},
                UpdateExpression="SET GSI2_PK = :pk, GSI2_SK = :sk",
                # Only touch rows that still exist, so a concurrent delete isn't resurrected.
                ConditionExpression="attribute_exists(PK)",
                ExpressionAttributeValues={":pk": gsi2_pk, ":sk": gsi2_sk},
            )
            counts["updated"] += 1
        except ClientError as e:
            counts["failed"] += 1
            print(f"FAILED {row['PK']} {row['SK']}: {e}", file=sys.stderr)

    verb = "updated" if args.apply else "would update"
    print(
        f"\nscanned={counts['scanned']} {verb}={counts['updated']} "
        f"already_ok={counts['already_ok']} skipped={counts['skipped']} "
        f"failed={counts['failed']}" + ("" if args.apply else "  (dry run)")
    )
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
