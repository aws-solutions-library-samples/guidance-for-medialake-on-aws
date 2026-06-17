"""Collection Manager pipeline node.

Creates or updates a collection in MediaLake's DynamoDB collections table.
Supports setting name, description, visibility, collection type, custom
metadata key-value pairs, and free-form tags.

The node is invoked as a Step Functions task inside a pipeline execution.
It receives its configuration from the pipeline definition's node parameters
and writes directly to DynamoDB (same table the Collections API uses).
After the write it publishes an EventBridge event so downstream consumers
(e.g. the DynamoDB → OpenSearch stream sync) can react.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(service="collection-manager-node")
tracer = Tracer(service="collection-manager-node")

dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")

COLLECTIONS_TABLE_NAME = os.environ.get("COLLECTIONS_TABLE_NAME", "")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")

COLLECTION_PK_PREFIX = "COLL#"
METADATA_SK = "METADATA"


def _generate_collection_id() -> str:
    """Generate a short prefixed collection ID matching the API's format."""
    return f"col_{uuid.uuid4().hex[:8]}"


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


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the Collection Manager pipeline node.

    Expected event shape (from Step Functions task):
    {
        "payload": { ... },          # upstream pipeline payload (passed through)
        "parameters": {
            "Operation": "create" | "update",
            "Collection ID": "<id>",  # required for update
            "Collection Name": "...",
            "Description": "...",
            "Collection Type ID": "...",
            "Is Public": "true" | "false",
            "Owner ID": "...",
            "Metadata": { "key": "value", ... } | '{"key":"value"}',
            "Tags": "q1, french, 2026" | '["q1","french"]'
        }
    }
    """
    parameters = event.get("parameters", {})
    payload = event.get("payload", {})

    operation = (parameters.get("Operation") or "create").lower()
    collection_name = parameters.get("Collection Name", "").strip()
    description = parameters.get("Description", "").strip()
    collection_type_id = parameters.get("Collection Type ID", "").strip()
    is_public = str(parameters.get("Is Public", "false")).lower() == "true"
    owner_id = parameters.get("Owner ID", "").strip() or "system"
    raw_metadata = parameters.get("Metadata")
    raw_tags = parameters.get("Tags")

    metadata = _parse_metadata(raw_metadata) if raw_metadata else {}
    tags = _parse_tags(raw_tags) if raw_tags else []

    if not COLLECTIONS_TABLE_NAME:
        raise RuntimeError("COLLECTIONS_TABLE_NAME environment variable not set")

    table = dynamodb.Table(COLLECTIONS_TABLE_NAME)
    current_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if operation == "create":
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
            item["tags"] = set(tags)  # DynamoDB StringSet

        table.put_item(Item=item)

        logger.info(
            "Collection created",
            extra={
                "collection_id": collection_id,
                "name": collection_name,
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
            **payload,
            "collectionResult": {
                "operation": "create",
                "collectionId": collection_id,
                "name": collection_name,
                "status": "ACTIVE",
            },
        }

    elif operation == "update":
        collection_id = parameters.get("Collection ID", "").strip()
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
            attr_values[":tg"] = set(tags)

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
            **payload,
            "collectionResult": {
                "operation": "update",
                "collectionId": collection_id,
                "status": "updated",
            },
        }

    else:
        raise ValueError(
            f"Unknown operation: {operation}. Must be 'create' or 'update'."
        )
