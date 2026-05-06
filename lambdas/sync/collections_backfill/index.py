"""Collections Backfill Lambda handler.

Performs a one-time scan of existing collection and collection group metadata
from the Collections_Table and indexes all records into the OpenSearch
collections index. Designed for ~2,000 records, completing within a single
Lambda invocation (15-minute timeout).

Reuses document_transformer.py and opensearch_client.py (copied from the Sync Lambda).
Dependencies (opensearch-py, requests_aws4auth) come from SearchLayer.
"""

import json
import os
from pathlib import Path

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Attr, Key
from document_transformer import (
    extract_entity_id,
    transform_collection,
    transform_collection_group,
)
from opensearch_client import (
    bulk_index_with_retry,
    create_index_if_not_exists,
    get_opensearch_client,
)

logger = Logger(service="collections-backfill")

BATCH_SIZE = 500

COLLECTIONS_TABLE_NAME = os.environ.get("COLLECTIONS_TABLE_NAME", "")
INDEX_NAME = os.environ.get("COLLECTIONS_INDEX_NAME", "")


def _validate_config():
    """Validate required environment variables are set.

    Raises:
        RuntimeError: If COLLECTIONS_TABLE_NAME or COLLECTIONS_INDEX_NAME is empty/unset.
    """
    if not COLLECTIONS_TABLE_NAME:
        raise RuntimeError(
            "COLLECTIONS_TABLE_NAME environment variable is required but empty/unset"
        )
    if not INDEX_NAME:
        raise RuntimeError(
            "COLLECTIONS_INDEX_NAME environment variable is required but empty/unset"
        )


# Load index mapping from the shared JSON file (single source of truth).
# At runtime the JSON is bundled alongside this file; during tests it may
# be in the parent directory.
def _load_index_mapping() -> dict:
    candidates = [
        Path(__file__).parent / "collections_index_mapping.json",
        Path(__file__).parent.parent / "collections_index_mapping.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    raise FileNotFoundError(
        "collections_index_mapping.json not found in any expected location"
    )


INDEX_MAPPING = _load_index_mapping()


def _scan_metadata_records(table_name: str) -> list[dict]:
    """Scan all METADATA records for collections and groups from DynamoDB.

    Uses a FilterExpression to select only records where:
    - SK = "METADATA"
    - PK begins_with "COLL#" OR PK begins_with "GROUP#"

    Args:
        table_name: DynamoDB table name to scan

    Returns:
        List of all matching DynamoDB items (deserialized)
    """
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    filter_expr = Attr("SK").eq("METADATA") & (
        Attr("PK").begins_with("COLL#") | Attr("PK").begins_with("GROUP#")
    )

    all_items = []
    scan_kwargs = {"FilterExpression": filter_expr}

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        all_items.extend(items)

        logger.info(
            "Scan page completed",
            extra={
                "page_items": len(items),
                "total_so_far": len(all_items),
            },
        )

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    logger.info("DynamoDB scan complete", extra={"total_scanned": len(all_items)})
    return all_items


def _query_shared_user_ids(table_name: str, collection_id: str) -> list[str]:
    """Query PERM# records for a collection and return the list of shared user IDs.

    Deprecated: prefer _batch_query_shared_user_ids for bulk operations.

    Args:
        table_name: DynamoDB table name
        collection_id: The collection ID (without COLL# prefix)

    Returns:
        List of user IDs that have been shared access to this collection
    """
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    user_ids = []
    query_kwargs = {
        "KeyConditionExpression": Key("PK").eq(f"COLL#{collection_id}")
        & Key("SK").begins_with("PERM#")
    }

    while True:
        response = table.query(**query_kwargs)

        for item in response.get("Items", []):
            sk = item.get("SK", "")
            if sk.startswith("PERM#"):
                user_id = sk[len("PERM#") :]
                if user_id:
                    user_ids.append(user_id)

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    return user_ids


def _batch_query_shared_user_ids(
    table_name: str, collection_ids: list[str]
) -> dict[str, list[str]]:
    """Batch-query PERM# records for multiple collections.

    Performs one DynamoDB Query per collection but collects all collection IDs
    upfront so the caller avoids the N+1 pattern inside a transform loop.

    Args:
        table_name: DynamoDB table name
        collection_ids: List of collection IDs (without COLL# prefix)

    Returns:
        Mapping of collection_id -> list of shared user IDs
    """
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    result: dict[str, list[str]] = {}
    for cid in collection_ids:
        user_ids: list[str] = []
        query_kwargs = {
            "KeyConditionExpression": Key("PK").eq(f"COLL#{cid}")
            & Key("SK").begins_with("PERM#")
        }
        while True:
            response = table.query(**query_kwargs)
            for item in response.get("Items", []):
                sk = item.get("SK", "")
                if sk.startswith("PERM#"):
                    uid = sk[len("PERM#") :]
                    if uid:
                        user_ids.append(uid)
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        result[cid] = user_ids

    return result


def _transform_item(
    item: dict, shared_user_ids_map: dict[str, list[str]] | None = None
) -> tuple[str, dict] | None:
    """Transform a single DynamoDB item to an OpenSearch document.

    Routes by PK prefix to the appropriate transformer.
    For COLL# items, uses the pre-fetched shared_user_ids_map to populate
    sharedWithUserIds (avoiding per-item DynamoDB queries).

    Args:
        item: Deserialized DynamoDB item
        shared_user_ids_map: Pre-fetched mapping of collection_id -> shared user IDs

    Returns:
        Tuple of (entity_id, opensearch_doc) or None if PK prefix is unknown
        or the document is invalid
    """
    pk = item.get("PK", "")
    entity_id = extract_entity_id(pk)

    if pk.startswith("COLL#"):
        shared_user_ids = (
            shared_user_ids_map.get(entity_id, []) if shared_user_ids_map else []
        )
        item_with_shares = dict(item)
        item_with_shares["sharedWithUserIds"] = shared_user_ids
        doc = transform_collection(item_with_shares)
        if doc is None:
            return None
        return entity_id, doc
    elif pk.startswith("GROUP#"):
        doc = transform_collection_group(item)
        return entity_id, doc
    else:
        logger.warning("Unknown PK prefix, skipping", extra={"pk": pk})
        return None


def _build_bulk_actions(
    items: list[dict], shared_user_ids_map: dict[str, list[str]] | None = None
) -> list[dict]:
    """Build OpenSearch bulk index actions from a list of DynamoDB items.

    Uses entity ID as the document _id for idempotency.

    Args:
        items: List of deserialized DynamoDB items
        shared_user_ids_map: Pre-fetched mapping of collection_id -> shared user IDs

    Returns:
        List of bulk action dicts ready for opensearch_client.bulk_index()
    """
    actions = []
    for item in items:
        result = _transform_item(item, shared_user_ids_map)
        if result is None:
            continue
        entity_id, doc = result
        actions.append(
            {
                "_op_type": "index",
                "_id": entity_id,
                "_source": doc,
            }
        )
    return actions


def lambda_handler(event: dict, context) -> dict:
    """Backfill all existing collection/group metadata to OpenSearch.

    1. Creates the collections index with mapping if it doesn't exist
    2. Scans all METADATA records from Collections_Table
    3. Transforms and bulk-indexes in batches of 500
    4. Logs progress and error counts

    Args:
        event: Lambda event (unused for manual invocation)
        context: Lambda context

    Returns:
        dict with scanned_count, indexed_count, error_count
    """

    # Validate required configuration first
    _validate_config()

    logger.info(
        "Backfill Lambda invoked",
        extra={"table": COLLECTIONS_TABLE_NAME, "index": INDEX_NAME},
    )

    # When invoked as a CloudFormation custom resource, skip backfill on Delete
    # NOTE: This lambda is invoked via AwsCustomResource with InvocationType "Event"
    # (async / fire-and-forget). CloudFormation never sees the return value — the
    # AwsCustomResource reports SUCCESS immediately. If the backfill fails, it fails
    # silently from CloudFormation's perspective. Monitor the backfill Lambda's error
    # metric and CloudWatch logs to detect failures.
    request_type = event.get("RequestType", "")
    if request_type == "Delete":
        logger.info("CloudFormation Delete event — skipping backfill")
        return {
            "PhysicalResourceId": "collections-backfill",
            "Data": {"scanned_count": "0", "indexed_count": "0", "error_count": "0"},
        }

    # Step 1: Create index if it doesn't exist
    client = get_opensearch_client()
    try:
        created = create_index_if_not_exists(client, INDEX_NAME, INDEX_MAPPING)
        if created:
            logger.info("Collections index created", extra={"index": INDEX_NAME})
        else:
            logger.info("Collections index already exists", extra={"index": INDEX_NAME})
    except Exception as e:
        logger.error(
            "Failed to create index, aborting backfill",
            extra={"index": INDEX_NAME, "error": str(e)},
        )
        raise

    # Step 2: Scan all METADATA records
    items = _scan_metadata_records(COLLECTIONS_TABLE_NAME)
    scanned_count = len(items)

    # Step 3: Transform and bulk-index in batches
    indexed_count = 0
    error_count = 0

    for batch_start in range(0, len(items), BATCH_SIZE):
        batch = items[batch_start : batch_start + BATCH_SIZE]
        batch_num = (batch_start // BATCH_SIZE) + 1

        # Batch-fetch shared user IDs for all COLL# items in this batch
        coll_ids = [
            extract_entity_id(item.get("PK", ""))
            for item in batch
            if item.get("PK", "").startswith("COLL#")
        ]
        shared_user_ids_map = (
            _batch_query_shared_user_ids(COLLECTIONS_TABLE_NAME, coll_ids)
            if coll_ids
            else {}
        )

        actions = _build_bulk_actions(batch, shared_user_ids_map)

        if not actions:
            continue

        try:
            response = bulk_index_with_retry(client, INDEX_NAME, actions)

            if response.get("errors"):
                for item_resp in response.get("items", []):
                    for op_type, result in item_resp.items():
                        doc_id = result.get("_id", "")
                        status = result.get("status", 0)
                        if status >= 400:
                            logger.error(
                                "Bulk index item failed",
                                extra={
                                    "batch": batch_num,
                                    "doc_id": doc_id,
                                    "status": status,
                                    "error": result.get("error", {}),
                                },
                            )
                            error_count += 1
                        else:
                            indexed_count += 1
            else:
                indexed_count += len(actions)

            logger.info(
                "Batch indexed",
                extra={
                    "batch": batch_num,
                    "batch_size": len(actions),
                    "indexed_so_far": indexed_count,
                    "errors_so_far": error_count,
                },
            )

        except Exception as e:
            failed_ids = [a["_id"] for a in actions]
            logger.error(
                "Batch indexing failed",
                extra={
                    "batch": batch_num,
                    "error": str(e),
                    "affected_record_ids": failed_ids,
                },
            )
            error_count += len(actions)

    # Step 4: Log completion summary
    logger.info(
        "Backfill complete",
        extra={
            "scanned_count": scanned_count,
            "indexed_count": indexed_count,
            "error_count": error_count,
        },
    )

    return {
        "PhysicalResourceId": "collections-backfill",
        "Data": {
            "scanned_count": str(scanned_count),
            "indexed_count": str(indexed_count),
            "error_count": str(error_count),
        },
    }
