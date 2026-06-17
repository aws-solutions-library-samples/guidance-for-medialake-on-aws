"""Collections Sync Lambda handler.

Processes DynamoDB Stream events from the Collections table and syncs
collection/group metadata to OpenSearch. Filters to SK="METADATA" only,
routes by PK prefix (COLL# or GROUP#), transforms, and bulk indexes/deletes.

Returns batchItemFailures for partial batch response reporting.
"""

import json
import os
import random
import time
from pathlib import Path

from aws_lambda_powertools import Logger, Metrics
from boto3.dynamodb.types import TypeDeserializer
from document_transformer import (
    extract_entity_id,
    transform_collection,
    transform_collection_group,
)
from opensearch_client import (
    bulk_index_with_retry,
    create_index_if_not_exists,
    delete_document,
    get_opensearch_client,
    update_document,
)

logger = Logger(service="collections-sync")
metrics = Metrics(namespace="MediaLake/CollectionsSync", service="collections-sync")

# Environment variables
INDEX_NAME = os.environ.get("COLLECTIONS_INDEX_NAME", "")


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

deserializer = TypeDeserializer()


def deserialize_dynamodb_item(item: dict) -> dict:
    """Convert a DynamoDB stream image to a plain Python dict."""
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def _is_metadata_record(record: dict) -> bool:
    """Check if a DynamoDB stream record is a METADATA record."""
    event_name = record.get("eventName", "")
    dynamodb_data = record.get("dynamodb", {})

    if event_name == "REMOVE":
        image = dynamodb_data.get("OldImage", {})
    else:
        image = dynamodb_data.get("NewImage", {})

    if not image:
        return False

    sk_value = image.get("SK", {}).get("S", "")
    return sk_value == "METADATA"


def _is_perm_record(record: dict) -> bool:
    """Check if a DynamoDB stream record is a PERM# record (SK starts with 'PERM#')."""
    event_name = record.get("eventName", "")
    dynamodb_data = record.get("dynamodb", {})

    if event_name == "REMOVE":
        image = dynamodb_data.get("OldImage", {})
    else:
        image = dynamodb_data.get("NewImage", {})

    if not image:
        return False

    sk_value = image.get("SK", {}).get("S", "")
    return sk_value.startswith("PERM#")


def _process_perm_record(record: dict, event_name: str) -> dict | None:
    """Process a PERM# record and return an OpenSearch update action.

    Extracts collection_id from PK (strip 'COLL#' prefix) and user_id from
    SK (strip 'PERM#' prefix). Returns a script-based update action.

    Args:
        record: DynamoDB stream record
        event_name: 'INSERT', 'MODIFY', or 'REMOVE'

    Returns:
        Dict with collection_id and script for update_document, or None to skip.
    """
    dynamodb_data = record.get("dynamodb", {})

    if event_name == "REMOVE":
        image = dynamodb_data.get("OldImage", {})
    else:
        image = dynamodb_data.get("NewImage", {})

    if not image:
        return None

    pk = image.get("PK", {}).get("S", "")
    sk = image.get("SK", {}).get("S", "")

    if not pk.startswith("COLL#"):
        logger.warning(
            "PERM# record has unexpected PK prefix, skipping",
            extra={"pk": pk, "sk": sk},
        )
        return None

    collection_id = pk[len("COLL#") :]
    user_id = sk[len("PERM#") :]

    if not collection_id or not user_id:
        logger.warning(
            "PERM# record has empty collection_id or user_id, skipping",
            extra={"pk": pk, "sk": sk},
        )
        return None

    if event_name in ("INSERT", "MODIFY"):
        script = {
            "source": (
                "if (ctx._source.sharedWithUserIds == null) { "
                "ctx._source.sharedWithUserIds = [params.userId] "
                "} else if (!ctx._source.sharedWithUserIds.contains(params.userId)) { "
                "ctx._source.sharedWithUserIds.add(params.userId) "
                "}"
            ),
            "params": {"userId": user_id},
        }
    else:  # REMOVE
        script = {
            "source": (
                "if (ctx._source.sharedWithUserIds != null) { "
                "ctx._source.sharedWithUserIds.removeIf(id -> id == params.userId) "
                "}"
            ),
            "params": {"userId": user_id},
        }

    return {
        "collection_id": collection_id,
        "script": script,
    }


def _get_pk_from_record(record: dict) -> str:
    """Extract the PK value from a DynamoDB stream record."""
    event_name = record.get("eventName", "")
    dynamodb_data = record.get("dynamodb", {})

    if event_name == "REMOVE":
        image = dynamodb_data.get("OldImage", {})
    else:
        image = dynamodb_data.get("NewImage", {})

    return image.get("PK", {}).get("S", "")


def _process_record(record: dict) -> dict | None:
    """Process a single DynamoDB stream record into a bulk action.

    Returns:
        A bulk action dict for OpenSearch, or None if the record should be skipped.
    """
    event_name = record.get("eventName", "")
    pk = _get_pk_from_record(record)
    entity_id = extract_entity_id(pk)
    sequence_number = record.get("dynamodb", {}).get("SequenceNumber", "")

    logger.info(
        "Processing stream event",
        extra={
            "collection_id": entity_id,
            "event_type": event_name,
            "sequence_number": sequence_number,
        },
    )

    if event_name == "REMOVE":
        return {
            "_op_type": "delete",
            "_id": entity_id,
        }

    # INSERT or MODIFY
    dynamodb_data = record.get("dynamodb", {})
    new_image = dynamodb_data.get("NewImage")
    if not new_image:
        logger.warning(
            "Event without NewImage, skipping",
            extra={"event_type": event_name, "collection_id": entity_id},
        )
        return None

    item = deserialize_dynamodb_item(new_image)

    if pk.startswith("COLL#"):
        doc = transform_collection(item)
        if doc is None:
            logger.warning(
                "transform_collection returned None, skipping",
                extra={"pk": pk, "collection_id": entity_id},
            )
            return None
    elif pk.startswith("GROUP#"):
        doc = transform_collection_group(item)
    else:
        logger.warning(
            "Unknown PK prefix, skipping",
            extra={"pk": pk, "collection_id": entity_id},
        )
        return None

    return {
        "_op_type": "index",
        "_id": entity_id,
        "_source": doc,
    }


def _handle_recreate_index():
    """Delete and recreate the OpenSearch index with correct mapping.

    Gated behind the ALLOW_INDEX_RECREATION environment variable to prevent
    accidental data loss from unauthorized Lambda invocations. Only callers
    who explicitly set {"action": "recreate_index"} AND have the env var
    set to "true" can trigger this destructive operation.
    """
    if os.environ.get("ALLOW_INDEX_RECREATION", "").lower() != "true":
        logger.error(
            "Index recreation blocked — ALLOW_INDEX_RECREATION env var is not 'true'",
            extra={"index": INDEX_NAME},
        )
        return {
            "action": "recreate_index",
            "status": "blocked",
            "reason": "ALLOW_INDEX_RECREATION environment variable must be set to 'true'",
        }

    logger.warning("Recreating OpenSearch index", extra={"index": INDEX_NAME})
    client = get_opensearch_client()

    # Check current mapping
    try:
        mapping = client.indices.get_mapping(index=INDEX_NAME)
        props = mapping[INDEX_NAME]["mappings"]["properties"]
        current_owner_type = props.get("ownerId", {}).get("type", "MISSING")
        logger.info(
            "Current mapping",
            extra={"ownerId_type": current_owner_type},
        )
    except Exception as e:
        logger.warning(f"Could not get current mapping: {e}")
        current_owner_type = "unknown"

    # Delete existing index
    try:
        client.indices.delete(index=INDEX_NAME)
        logger.info("Deleted index", extra={"index": INDEX_NAME})
    except Exception as e:
        logger.warning(f"Could not delete index (may not exist): {e}")

    # Create with correct mapping
    client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
    logger.info("Created index with correct mapping", extra={"index": INDEX_NAME})

    # Verify
    mapping = client.indices.get_mapping(index=INDEX_NAME)
    props = mapping[INDEX_NAME]["mappings"]["properties"]
    new_owner_type = props.get("ownerId", {}).get("type", "MISSING")

    return {
        "action": "recreate_index",
        "previous_ownerId_type": current_owner_type,
        "new_ownerId_type": new_owner_type,
        "index": INDEX_NAME,
        "status": "success",
    }


def _ensure_index_exists():
    """Ensure the OpenSearch index exists with the correct mapping.

    Called once per Lambda cold start. If the index doesn't exist, creates it
    with the explicit INDEX_MAPPING to prevent OpenSearch from auto-creating
    it with dynamic mapping (which would map keyword fields like ownerId as text).

    Raises:
        RuntimeError: If the index existence cannot be verified and creation fails.
            This prevents processing records against a potentially auto-created
            index with incorrect dynamic mapping.
    """
    global _index_verified
    if _index_verified:
        return

    try:
        client = get_opensearch_client()
        create_index_if_not_exists(client, INDEX_NAME, INDEX_MAPPING)
        _index_verified = True
    except Exception as e:
        logger.error(
            "Failed to verify/create index — failing batch to prevent dynamic mapping",
            extra={"error": str(e), "index": INDEX_NAME},
        )
        raise RuntimeError(
            f"Cannot verify OpenSearch index '{INDEX_NAME}' exists with correct mapping. "
            f"Failing batch to prevent auto-creation with dynamic mapping: {e}"
        ) from e


# Track whether we've verified the index exists (once per cold start)
_index_verified = False


@metrics.log_metrics
def lambda_handler(event: dict, context) -> dict:
    """Process DynamoDB Stream events and sync to OpenSearch.

    Filters to SK="METADATA" only, routes by PK prefix (COLL# or GROUP#),
    transforms items, and bulk indexes/deletes via OpenSearch bulk API.

    Args:
        event: DynamoDB Streams event with 'Records' list, or
               {"action": "recreate_index"} to delete and recreate the index
        context: Lambda context

    Returns:
        dict with batchItemFailures for partial batch response reporting
    """
    # Handle index recreation request
    if event.get("action") == "recreate_index":
        return _handle_recreate_index()

    records = event.get("Records", [])
    total_records = len(records)

    logger.info(
        "Lambda invoked",
        extra={"total_records": total_records},
    )

    batch_item_failures = []
    success_count = 0
    failure_count = 0

    # Filter to METADATA records only
    metadata_records = []
    perm_records = []
    for record in records:
        if _is_metadata_record(record):
            metadata_records.append(record)
        elif _is_perm_record(record):
            perm_records.append(record)
        else:
            logger.debug(
                "Skipping non-metadata record",
                extra={
                    "event_type": record.get("eventName", ""),
                    "sequence_number": record.get("dynamodb", {}).get(
                        "SequenceNumber", ""
                    ),
                },
            )

    if not metadata_records and not perm_records:
        logger.info("No metadata or PERM# records to process")
        metrics.add_metric(name="SuccessCount", unit="Count", value=0)
        metrics.add_metric(name="FailureCount", unit="Count", value=0)
        return {"batchItemFailures": []}

    # Ensure the index exists with correct mapping before processing any records.
    # This prevents OpenSearch from auto-creating the index with dynamic mapping
    # when the first document is indexed (which would map ownerId as text, not keyword).
    # Placed after the empty-batch early return to avoid unnecessary OpenSearch calls.
    _ensure_index_exists()

    # Separate REMOVE events (delete) from INSERT/MODIFY events (index)
    index_actions = []
    delete_records = []
    record_to_action_map = {}

    for record in metadata_records:
        event_name = record.get("eventName", "")
        sequence_number = record.get("dynamodb", {}).get("SequenceNumber", "")
        pk = _get_pk_from_record(record)

        # Only process COLL# and GROUP# prefixes
        if not (pk.startswith("COLL#") or pk.startswith("GROUP#")):
            logger.warning(
                "Skipping record with unknown PK prefix",
                extra={"pk": pk, "sequence_number": sequence_number},
            )
            continue

        try:
            action = _process_record(record)
            if action is None:
                continue

            if action["_op_type"] == "delete":
                delete_records.append((record, action))
            else:
                index_actions.append(action)
                record_to_action_map[action["_id"]] = record
        except Exception as e:
            logger.error(
                "Failed to process record",
                extra={
                    "error": str(e),
                    "event_type": event_name,
                    "sequence_number": sequence_number,
                    "collection_id": extract_entity_id(pk),
                    "processing_result": "failure",
                },
            )
            failure_count += 1
            batch_item_failures.append(
                {"itemIdentifier": record["dynamodb"]["SequenceNumber"]}
            )

    # Process bulk index actions (INSERT/MODIFY) with retry
    if index_actions:
        try:
            client = get_opensearch_client()
            response = bulk_index_with_retry(client, INDEX_NAME, index_actions)

            # Check for partial failures in bulk response
            if response.get("errors"):
                for item in response.get("items", []):
                    for op_type, result in item.items():
                        doc_id = result.get("_id", "")
                        status = result.get("status", 0)
                        if status >= 400:
                            logger.error(
                                "Bulk index item failed",
                                extra={
                                    "collection_id": doc_id,
                                    "status": status,
                                    "error": result.get("error", {}),
                                    "processing_result": "failure",
                                },
                            )
                            failure_count += 1
                            if doc_id in record_to_action_map:
                                record = record_to_action_map[doc_id]
                                batch_item_failures.append(
                                    {
                                        "itemIdentifier": record["dynamodb"][
                                            "SequenceNumber"
                                        ]
                                    }
                                )
                        else:
                            success_count += 1
                            logger.info(
                                "Document indexed successfully",
                                extra={
                                    "collection_id": doc_id,
                                    "event_type": "INDEX",
                                    "processing_result": "success",
                                },
                            )
            else:
                success_count += len(index_actions)
                for action in index_actions:
                    logger.info(
                        "Document indexed successfully",
                        extra={
                            "collection_id": action["_id"],
                            "event_type": "INDEX",
                            "processing_result": "success",
                        },
                    )

        except Exception as e:
            logger.error(
                "Bulk index operation failed after retries",
                extra={
                    "error": str(e),
                    "action_count": len(index_actions),
                    "processing_result": "failure",
                },
            )
            failure_count += len(index_actions)
            for action in index_actions:
                if action["_id"] in record_to_action_map:
                    record = record_to_action_map[action["_id"]]
                    batch_item_failures.append(
                        {"itemIdentifier": record["dynamodb"]["SequenceNumber"]}
                    )

    # Process delete actions individually with retry
    for record, action in delete_records:
        entity_id = action["_id"]
        sequence_number = record.get("dynamodb", {}).get("SequenceNumber", "")
        last_exception = None

        for attempt in range(4):  # 1 initial + 3 retries
            try:
                client = get_opensearch_client()
                delete_document(client, INDEX_NAME, entity_id)
                success_count += 1
                logger.info(
                    "Document deleted successfully",
                    extra={
                        "collection_id": entity_id,
                        "event_type": "REMOVE",
                        "sequence_number": sequence_number,
                        "processing_result": "success",
                    },
                )
                last_exception = None
                break
            except Exception as e:
                last_exception = e
                if attempt < 3:
                    delay = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Delete attempt {attempt + 1} failed, retrying in {delay:.1f}s",
                        extra={
                            "collection_id": entity_id,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)

        if last_exception is not None:
            logger.error(
                "Delete operation failed after retries",
                extra={
                    "collection_id": entity_id,
                    "event_type": "REMOVE",
                    "sequence_number": sequence_number,
                    "error": str(last_exception),
                    "processing_result": "failure",
                },
            )
            failure_count += 1
            batch_item_failures.append({"itemIdentifier": sequence_number})

    # Process PERM# records (sharedWithUserIds updates) with retry
    for record in perm_records:
        event_name = record.get("eventName", "")
        sequence_number = record.get("dynamodb", {}).get("SequenceNumber", "")

        try:
            perm_action = _process_perm_record(record, event_name)
            if perm_action is None:
                continue

            collection_id = perm_action["collection_id"]
            script = perm_action["script"]

            last_perm_exception = None
            for attempt in range(4):  # 1 initial + 3 retries
                try:
                    client = get_opensearch_client()
                    update_document(client, INDEX_NAME, collection_id, script)
                    success_count += 1
                    logger.info(
                        "PERM# record processed successfully",
                        extra={
                            "collection_id": collection_id,
                            "event_type": event_name,
                            "sequence_number": sequence_number,
                            "processing_result": "success",
                        },
                    )
                    last_perm_exception = None
                    break
                except Exception as e:
                    last_perm_exception = e
                    if attempt < 3:
                        delay = (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"PERM# update attempt {attempt + 1} failed, retrying in {delay:.1f}s",
                            extra={
                                "collection_id": collection_id,
                                "attempt": attempt + 1,
                                "delay": delay,
                                "error": str(e),
                            },
                        )
                        time.sleep(delay)

            if last_perm_exception is not None:
                logger.error(
                    "PERM# update failed after retries",
                    extra={
                        "collection_id": collection_id,
                        "event_type": event_name,
                        "sequence_number": sequence_number,
                        "error": str(last_perm_exception),
                        "processing_result": "failure",
                    },
                )
                failure_count += 1
                batch_item_failures.append({"itemIdentifier": sequence_number})

        except Exception as e:
            logger.error(
                "Failed to process PERM# record",
                extra={
                    "error": str(e),
                    "event_type": event_name,
                    "sequence_number": sequence_number,
                    "processing_result": "failure",
                },
            )
            failure_count += 1
            batch_item_failures.append({"itemIdentifier": sequence_number})

    # Emit CloudWatch metrics
    metrics.add_metric(name="SuccessCount", unit="Count", value=success_count)
    metrics.add_metric(name="FailureCount", unit="Count", value=failure_count)

    logger.info(
        "Processing complete",
        extra={
            "total_records": total_records,
            "metadata_records": len(metadata_records),
            "perm_records": len(perm_records),
            "success_count": success_count,
            "failure_count": failure_count,
            "batch_item_failures": len(batch_item_failures),
        },
    )

    return {"batchItemFailures": batch_item_failures}
