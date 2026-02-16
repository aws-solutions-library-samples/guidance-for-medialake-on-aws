#!/usr/bin/env python3
"""
Backfill script for collections table: GSI5 attributes and itemCount.

This script scans all collection METADATA records and:
1. Sets GSI5_PK = "COLLECTIONS" and GSI5_SK = updatedAt (for RecentlyModifiedGSI)
2. Recalculates itemCount by counting ASSET# and ITEM# sort keys per collection

Run with:
    python INTERNAL-utils/backfill_collections_gsi5_itemcount.py \
        --table-name <table-name> \
        --region <aws-region> \
        [--dry-run]

Requires boto3 and AWS credentials with read/write access to the table.
"""

import argparse
import sys
import time

import boto3
from boto3.dynamodb.conditions import Attr, Key

COLLECTION_PK_PREFIX = "COLL#"
METADATA_SK = "METADATA"
ASSET_SK_PREFIX = "ASSET#"
ITEM_SK_PREFIX = "ITEM#"
COLLECTIONS_GSI5_PK = "COLLECTIONS"


def count_items_for_collection(table, collection_pk: str) -> int:
    """Count ASSET# and ITEM# sort keys under a collection PK."""
    total = 0
    for prefix in (ASSET_SK_PREFIX, ITEM_SK_PREFIX):
        kwargs = {
            "KeyConditionExpression": (
                Key("PK").eq(collection_pk) & Key("SK").begins_with(prefix)
            ),
            "Select": "COUNT",
        }
        while True:
            response = table.query(**kwargs)
            total += response.get("Count", 0)
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return total


def scan_all_collections(table):
    """Yield all METADATA records with PK starting with COLL#."""
    kwargs = {
        "FilterExpression": (
            Attr("SK").eq(METADATA_SK) & Attr("PK").begins_with(COLLECTION_PK_PREFIX)
        ),
    }
    while True:
        response = table.scan(**kwargs)
        yield from response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key


def backfill(table_name: str, region: str, dry_run: bool = False):
    """Run the backfill process."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    print(f"Table:   {table_name}")
    print(f"Region:  {region}")
    print(f"Dry run: {dry_run}")
    print("-" * 60)

    updated = 0
    skipped = 0
    errors = 0

    for item in scan_all_collections(table):
        pk = item["PK"]
        collection_id = pk.replace(COLLECTION_PK_PREFIX, "")
        updated_at = item.get("updatedAt") or item.get("createdAt")

        if not updated_at:
            print(f"  WARNING: {collection_id} has no updatedAt or createdAt, skipping")
            skipped += 1
            continue

        # Check if GSI5 is already populated correctly
        existing_gsi5_pk = item.get("GSI5_PK")
        existing_gsi5_sk = item.get("GSI5_SK")
        gsi5_needs_update = (
            existing_gsi5_pk != COLLECTIONS_GSI5_PK or existing_gsi5_sk != updated_at
        )

        # Count actual items
        try:
            actual_count = count_items_for_collection(table, pk)
        except Exception as e:
            print(f"  ERROR counting items for {collection_id}: {e}")
            errors += 1
            continue

        stored_count = item.get("itemCount", 0)
        # Treat Decimal as int for comparison
        count_needs_update = int(stored_count) != actual_count

        if not gsi5_needs_update and not count_needs_update:
            skipped += 1
            continue

        changes = []
        if gsi5_needs_update:
            changes.append(f"GSI5 {existing_gsi5_pk}→{COLLECTIONS_GSI5_PK}")
        if count_needs_update:
            changes.append(f"itemCount {stored_count}→{actual_count}")

        print(f"  {collection_id}: {', '.join(changes)}")

        if dry_run:
            updated += 1
            continue

        try:
            update_expr_parts = []
            expr_values = {}

            if gsi5_needs_update:
                update_expr_parts.append("GSI5_PK = :gsi5pk, GSI5_SK = :gsi5sk")
                expr_values[":gsi5pk"] = COLLECTIONS_GSI5_PK
                expr_values[":gsi5sk"] = updated_at

            if count_needs_update:
                update_expr_parts.append("itemCount = :ic")
                expr_values[":ic"] = actual_count

            table.update_item(
                Key={"PK": pk, "SK": METADATA_SK},
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeValues=expr_values,
            )
            updated += 1
        except Exception as e:
            print(f"  ERROR updating {collection_id}: {e}")
            errors += 1

        # Gentle throttle to avoid burning through WCU
        if updated % 25 == 0:
            time.sleep(0.5)

    print("-" * 60)
    print(f"Done. Updated: {updated}, Skipped: {skipped}, Errors: {errors}")
    if dry_run:
        print("(dry run — no writes were made)")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Backfill GSI5 attributes and itemCount on collection METADATA records."
    )
    parser.add_argument(
        "--table-name",
        required=True,
        help="DynamoDB table name (e.g. medialake-collections-dev)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be updated without writing",
    )
    args = parser.parse_args()
    error_count = backfill(args.table_name, args.region, args.dry_run)
    if error_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
