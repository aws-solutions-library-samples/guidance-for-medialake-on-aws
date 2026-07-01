"""Collection Manager pipeline node.

Creates or updates a collection in MediaLake's DynamoDB collections table, or
adds assets to an existing collection. Supports setting name, description,
visibility, collection type, custom metadata key-value pairs, and free-form
tags, plus an add-assets operation that writes collection membership rows.

The node is invoked as a Step Functions task inside a pipeline execution.
Its configuration comes from the pipeline node's parameters, which the pipeline
deployer exposes as ENVIRONMENT VARIABLES (e.g. "Owner ID" -> ``OWNER_ID``),
not on the event. The standardized pipeline ``payload`` (data + assets) is
provided by the shared ``lambda_middleware`` decorator, same as every other
utility node. It writes directly to DynamoDB (the same table the Collections
API uses) — the collections DynamoDB stream then syncs the change to OpenSearch,
so the collection/items show up in the OpenSearch-backed list API. It also
publishes an EventBridge event for any other downstream consumers.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware

logger = Logger(service="collection-manager-node")
tracer = Tracer(service="collection-manager-node")

dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")

COLLECTIONS_TABLE_NAME = os.environ.get("COLLECTIONS_TABLE_NAME", "")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")

COLLECTION_PK_PREFIX = "COLL#"
METADATA_SK = "METADATA"
ASSET_SK_PREFIX = "ASSET#"

# Pipeline node parameters are delivered as environment variables by the
# deployer (param label uppercased, spaces -> underscores). Map each label to
# its env var so the handler can resolve config the way the framework provides
# it (with a fallback to event["parameters"] for direct invocation / tests).
_PARAM_ENV = {
    "Operation": "OPERATION",
    "Collection ID": "COLLECTION_ID",
    "Collection Name": "COLLECTION_NAME",
    "Description": "DESCRIPTION",
    "Collection Type ID": "COLLECTION_TYPE_ID",
    "Is Public": "IS_PUBLIC",
    "Owner ID": "OWNER_ID",
    "Metadata": "METADATA",
    "Tags": "TAGS",
    "Asset IDs": "ASSET_IDS",
}


def _resolve_params(event: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve node parameters from env vars (the framework's contract), falling
    back to ``event['parameters']`` by label for direct invocation / tests."""
    event_params = event.get("parameters") or {}
    resolved: Dict[str, Any] = {}
    for label, env_key in _PARAM_ENV.items():
        val = os.environ.get(env_key)
        if val is None or val == "":
            val = event_params.get(label)
        resolved[label] = val
    return resolved


def _generate_collection_id() -> str:
    """Generate a short prefixed collection ID matching the API's format."""
    return f"col_{uuid.uuid4().hex[:8]}"


def _parse_asset_ids(explicit: Any, payload: Dict[str, Any]) -> List[str]:
    """Resolve the asset IDs to add to a collection.

    Priority:
    1. An explicit "Asset IDs" node parameter (comma-separated string or JSON
       array) — deterministic override / field-mapping friendly.
    2. The pipeline payload's standardized assets (``payload.assets[*].InventoryID``).
    3. Fallback to ``payload.data.inventory_id`` (manual-trigger single asset).

    Returns a de-duplicated, order-preserving list of asset IDs.
    """
    ids: List[str] = []

    if isinstance(explicit, list):
        ids = [str(a).strip() for a in explicit if str(a).strip()]
    elif isinstance(explicit, str) and explicit.strip():
        raw = explicit.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    ids = [str(a).strip() for a in parsed if str(a).strip()]
            except json.JSONDecodeError:
                ids = []
        if not ids:
            ids = [a.strip() for a in raw.split(",") if a.strip()]

    if not ids and isinstance(payload, dict):
        for asset in payload.get("assets") or []:
            if isinstance(asset, dict):
                aid = (
                    asset.get("InventoryID") or asset.get("assetId") or asset.get("id")
                )
                if aid:
                    ids.append(str(aid))
        if not ids:
            data = payload.get("data")
            if isinstance(data, dict) and data.get("inventory_id"):
                ids.append(str(data["inventory_id"]))

    # De-dupe while preserving order.
    seen = set()
    result = []
    for aid in ids:
        if aid not in seen:
            seen.add(aid)
            result.append(aid)
    return result


def _parse_tags(raw: Any) -> List[str]:
    """Parse tags from the node parameter value.

    Accepts:
    - A comma-separated string: "q1, french, 2026"
    - A JSON array string: '["q1","french","2026"]'
    - An actual list (if the form already parsed it)
    """
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(t).strip() for t in parsed if str(t).strip()]
            except json.JSONDecodeError:
                pass
        # Fall back to comma-separated
        return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def _parse_metadata(raw: Any) -> Dict[str, str]:
    """Parse custom metadata from the node parameter value.

    Accepts:
    - A dict (if the KeyValueEditor already serialised it)
    - A JSON string: '{"project": "alpha"}'
    """
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if str(k).strip()}
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items() if str(k).strip()}
            except json.JSONDecodeError:
                pass
    return {}


def _write_owner_relationship(
    table, owner_id: str, collection_id: str, now: str
) -> None:
    """Write the USER->COLLECTION OWNER relationship row.

    Mirrors the admin create handler's ``UserRelationshipModel`` write so a
    pipeline-created collection behaves like an API-created one: it shows in the
    owner's "my collections" (GSI1 USER#{id}) and is found/reassigned by the
    user-deletion migration (which queries OWNER relationship rows) — so the
    collection is never orphaned if the owner is later deleted.
    """
    table.put_item(
        Item={
            "PK": f"USER#{owner_id}",
            "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "relationship": "OWNER",
            "addedAt": now,
            "lastAccessed": now,
            "isFavorite": False,
            "GSI1_PK": f"USER#{owner_id}",
            "GSI1_SK": now,
            "GSI2_PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "GSI2_SK": f"USER#{owner_id}",
        }
    )


def _put_event(detail_type: str, detail: Dict[str, Any]) -> None:
    """Publish an event to EventBridge so downstream consumers can react."""
    try:
        events_client.put_events(
            Entries=[
                {
                    "Source": "medialake.pipeline.collection-manager",
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail, default=str),
                    "EventBusName": EVENT_BUS_NAME,
                }
            ]
        )
    except Exception as e:
        logger.warning("Failed to publish EventBridge event", extra={"error": str(e)})


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the Collection Manager pipeline node.

    Parameters arrive as environment variables (see ``_PARAM_ENV``); the
    standardized pipeline payload (``payload.data`` / ``payload.assets``) is
    provided by ``lambda_middleware``. The returned dict becomes the next
    node's ``payload.data``.
    """
    parameters = _resolve_params(event)
    payload = event.get("payload", {})

    operation = (parameters.get("Operation") or "create").lower()
    collection_name = (parameters.get("Collection Name") or "").strip()
    description = (parameters.get("Description") or "").strip()
    collection_type_id = (parameters.get("Collection Type ID") or "").strip()
    is_public = str(parameters.get("Is Public") or "false").lower() == "true"
    # Owner of the collection. We deliberately do NOT fall back to a "system"
    # principal: a system-owned collection is invisible to every user and
    # undeletable through the API (access is ownerId/isPublic/shared only). For
    # create we require a real owner (validated at deploy time too); the owner
    # also gets a USER->COLLECTION OWNER relationship row so it appears in their
    # collections and is reassigned (not orphaned) if that user is later deleted.
    owner_id = (parameters.get("Owner ID") or "").strip()
    raw_metadata = parameters.get("Metadata")
    raw_tags = parameters.get("Tags")

    metadata = _parse_metadata(raw_metadata) if raw_metadata else {}
    tags = _parse_tags(raw_tags) if raw_tags else []

    if not COLLECTIONS_TABLE_NAME:
        raise RuntimeError("COLLECTIONS_TABLE_NAME environment variable not set")

    table = dynamodb.Table(COLLECTIONS_TABLE_NAME)
    current_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if operation == "create":
        if not owner_id:
            raise ValueError(
                "Owner ID is required to create a collection. Set the node's "
                "'Owner ID' to the user that should own it — collections without "
                "a real owner are invisible and cannot be managed."
            )
        collection_id = _generate_collection_id()
        if not collection_name:
            collection_name = f"Pipeline Collection {collection_id}"

        item: Dict[str, Any] = {
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": METADATA_SK,
            "name": collection_name,
            "description": description,
            "ownerId": owner_id,
            "isPublic": is_public,
            "status": "ACTIVE",
            "itemCount": 0,
            "childCollectionCount": 0,
            "createdAt": current_timestamp,
            "updatedAt": current_timestamp,
        }
        if collection_type_id:
            item["collectionTypeId"] = collection_type_id
        if metadata:
            item["customMetadata"] = metadata
        if tags:
            item["tags"] = tags  # list (matches CollectionModel.tags + OpenSearch)

        table.put_item(Item=item)
        # Owner relationship row so it shows in the owner's collections and is
        # reassigned (not orphaned) if the owner is deleted.
        _write_owner_relationship(table, owner_id, collection_id, current_timestamp)

        logger.info(
            "Collection created",
            extra={
                "collection_id": collection_id,
                "collection_name": collection_name,
                "owner_id": owner_id,
                "tags_count": len(tags),
                "metadata_keys": list(metadata.keys()),
            },
        )

        _put_event(
            "CollectionCreated",
            {
                "collectionId": collection_id,
                "name": collection_name,
                "source": "pipeline-node",
            },
        )

        return {
            "collectionResult": {
                "operation": "create",
                "collectionId": collection_id,
                "name": collection_name,
                "status": "ACTIVE",
            },
        }

    elif operation == "update":
        collection_id = (parameters.get("Collection ID") or "").strip()
        if not collection_id:
            raise ValueError("Collection ID is required for update operation")

        # Build update expression dynamically — only set fields that were provided
        update_parts: List[str] = []
        attr_names: Dict[str, str] = {}
        attr_values: Dict[str, Any] = {}

        update_parts.append("#ua = :ua")
        attr_names["#ua"] = "updatedAt"
        attr_values[":ua"] = current_timestamp

        if collection_name:
            update_parts.append("#nm = :nm")
            attr_names["#nm"] = "name"
            attr_values[":nm"] = collection_name

        if description:
            update_parts.append("#desc = :desc")
            attr_names["#desc"] = "description"
            attr_values[":desc"] = description

        if collection_type_id:
            update_parts.append("#ctid = :ctid")
            attr_names["#ctid"] = "collectionTypeId"
            attr_values[":ctid"] = collection_type_id

        # Always set isPublic (it has a default of false)
        update_parts.append("#pub = :pub")
        attr_names["#pub"] = "isPublic"
        attr_values[":pub"] = is_public

        if metadata:
            update_parts.append("#cm = :cm")
            attr_names["#cm"] = "customMetadata"
            attr_values[":cm"] = metadata

        if tags:
            update_parts.append("#tg = :tg")
            attr_names["#tg"] = "tags"
            attr_values[":tg"] = tags  # list, not StringSet

        update_expression = "SET " + ", ".join(update_parts)

        try:
            table.update_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": METADATA_SK,
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=attr_values,
                ConditionExpression="attribute_exists(PK)",
            )
        except boto3.client("dynamodb").exceptions.ConditionalCheckFailedException:
            raise ValueError(f"Collection '{collection_id}' does not exist")
        except Exception as e:
            if (
                hasattr(e, "response")
                and e.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                raise ValueError(f"Collection '{collection_id}' does not exist")
            raise

        logger.info(
            "Collection updated",
            extra={
                "collection_id": collection_id,
                "updated_fields": list(attr_names.values()),
                "tags_count": len(tags),
                "metadata_keys": list(metadata.keys()),
            },
        )

        _put_event(
            "CollectionUpdated",
            {
                "collectionId": collection_id,
                "source": "pipeline-node",
            },
        )

        return {
            "collectionResult": {
                "operation": "update",
                "collectionId": collection_id,
                "status": "updated",
            },
        }

    elif operation == "add_assets":
        collection_id = (parameters.get("Collection ID") or "").strip()
        if not collection_id:
            raise ValueError("Collection ID is required for add_assets operation")

        # Verify the collection exists before writing membership rows, so we
        # never leave orphaned ASSET# items pointing at a missing collection.
        meta = table.get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK}
        ).get("Item")
        if not meta:
            raise ValueError(f"Collection '{collection_id}' does not exist")

        asset_ids = _parse_asset_ids(parameters.get("Asset IDs"), payload)
        if not asset_ids:
            raise ValueError(
                "No asset IDs to add. Provide an 'Asset IDs' parameter or run "
                "this node after a step that yields assets."
            )

        added: List[str] = []
        for asset_id in asset_ids:
            sk = f"{ASSET_SK_PREFIX}{asset_id}"
            table.put_item(
                Item={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": sk,
                    "itemType": "asset",
                    "assetId": asset_id,
                    "sortOrder": 0,
                    "addedAt": current_timestamp,
                    "addedBy": owner_id or "pipeline",  # provenance, not ownership
                    # GSI2 reverse lookup (asset -> collections), mirrors the API.
                    "GSI2_PK": sk,
                    "GSI2_SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                }
            )
            added.append(asset_id)

        # Bump the collection's updatedAt so the change is reflected/synced.
        table.update_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": METADATA_SK},
            UpdateExpression="SET #ua = :ua",
            ExpressionAttributeNames={"#ua": "updatedAt"},
            ExpressionAttributeValues={":ua": current_timestamp},
        )

        logger.info(
            "Assets added to collection",
            extra={"collection_id": collection_id, "asset_count": len(added)},
        )

        _put_event(
            "CollectionItemsAdded",
            {
                "collectionId": collection_id,
                "assetIds": added,
                "source": "pipeline-node",
            },
        )

        return {
            "collectionResult": {
                "operation": "add_assets",
                "collectionId": collection_id,
                "addedAssetIds": added,
                "addedCount": len(added),
                "status": "items_added",
            },
        }

    else:
        raise ValueError(
            f"Unknown operation: {operation}. "
            "Must be 'create', 'update', or 'add_assets'."
        )
