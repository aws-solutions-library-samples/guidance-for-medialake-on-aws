import json
import os
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import (
    OpenSearch,
    RequestsHttpConnection,
    AWSV4SignerAuth,
    exceptions,
)

from lambda_middleware import lambda_middleware
from nodes_utils import seconds_to_smpte

# ── Powertools ───────────────────────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

# ── Environment ──────────────────────────────────────────────────────────────
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
INDEX_NAME          = os.getenv("INDEX_NAME", "media")
CONTENT_TYPE        = os.getenv("CONTENT_TYPE", "video").lower()
AWS_REGION          = os.getenv("AWS_REGION", "us-east-1")

IS_AUDIO_CONTENT    = CONTENT_TYPE == "audio"

# ── OpenSearch client ────────────────────────────────────────────────────────
_session     = boto3.Session()
_credentials = _session.get_credentials()
_auth        = AWSV4SignerAuth(_credentials, AWS_REGION, "es")  # OpenSearch service


def get_opensearch_client():
    if not OPENSEARCH_ENDPOINT:
        logger.warning("OPENSEARCH_ENDPOINT not set – skipping OpenSearch calls.")
        return None

    parsed = urlparse(OPENSEARCH_ENDPOINT)
    host   = parsed.netloc if parsed.scheme else OPENSEARCH_ENDPOINT

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
        http_compress=True,
        retry_on_timeout=True,
        max_retries=3,
    )

# ── Helper extraction functions ──────────────────────────────────────────────
def _item(container: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return payload.data.item when present."""
    if isinstance(container.get("data"), dict):
        itm = container["data"].get("item")
        if isinstance(itm, dict):
            return itm
    return None


def _map_item(container: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return payload.map.item when present (audio segmentation metadata)."""
    m = container.get("map")
    if isinstance(m, dict) and isinstance(m.get("item"), dict):
        return m["item"]
    return None


def extract_asset_id(container: Dict[str, Any]) -> Optional[str]:
    """
    1. payload.data.item.asset_id
    2. payload.map.item.asset_id
    3. payload.assets[*].DigitalSourceAsset.ID
    4. payload.DigitalSourceAsset.ID
    """
    itm = _item(container)
    if itm and itm.get("asset_id"):
        return itm["asset_id"]

    m_itm = _map_item(container)
    if m_itm and m_itm.get("asset_id"):
        return m_itm["asset_id"]

    for asset in container.get("assets", []):
        dsa_id = asset.get("DigitalSourceAsset", {}).get("ID")
        if dsa_id:
            return dsa_id

    return container.get("DigitalSourceAsset", {}).get("ID")


def extract_scope(container: Dict[str, Any]) -> Optional[str]:
    """
    1. payload.data.item.embedding_scope
    2. payload.data.embedding_scope
    3. payload.map.item.embedding_scope
    4. payload.embedding_scope
    5. payload.externalTaskResults[*].embedding_scope
    """
    itm = _item(container)
    if itm and itm.get("embedding_scope"):
        return itm["embedding_scope"]

    data = container.get("data")
    if isinstance(data, dict) and data.get("embedding_scope"):
        return data["embedding_scope"]

    m_itm = _map_item(container)
    if m_itm and m_itm.get("embedding_scope"):
        return m_itm["embedding_scope"]

    if container.get("embedding_scope"):
        return container["embedding_scope"]

    for res in container.get("externalTaskResults", []):
        if res.get("embedding_scope"):
            return res["embedding_scope"]

    return None


def extract_embedding_option(container: Dict[str, Any]) -> Optional[str]:
    """
    1. payload.data.item.embedding_option
    2. payload.data.embedding_option
    3. payload.map.item.embedding_option
    4. payload.embedding_option
    5. payload.externalTaskResults[*].embedding_option
    """
    itm = _item(container)
    if itm and itm.get("embedding_option"):
        return itm["embedding_option"]

    data = container.get("data")
    if isinstance(data, dict) and data.get("embedding_option"):
        return data["embedding_option"]

    m_itm = _map_item(container)
    if m_itm and m_itm.get("embedding_option"):
        return m_itm["embedding_option"]

    if container.get("embedding_option"):
        return container["embedding_option"]

    for res in container.get("externalTaskResults", []):
        if res.get("embedding_option"):
            return res["embedding_option"]

    return None


def extract_embedding_vector(container: Dict[str, Any]) -> Optional[List[float]]:
    """
    1. payload.data.item.float
    2. payload.data.float
    3. payload.float
    4. payload.externalTaskResults[*].float
    """
    itm = _item(container)
    if itm and isinstance(itm.get("float"), list) and itm["float"]:
        return itm["float"]

    if (
        isinstance(container.get("data"), dict)
        and isinstance(container["data"].get("float"), list)
        and container["data"]["float"]
    ):
        return container["data"]["float"]

    if isinstance(container.get("float"), list) and container["float"]:
        return container["float"]

    for res in container.get("externalTaskResults", []):
        if isinstance(res.get("float"), list) and res["float"]:
            return res["float"]

    return None


# ── NEW helper ───────────────────────────────────────────────────────────────
def _get_segment_bounds(payload: Dict[str, Any]) -> tuple[int, int]:
    """
    Return (start_sec, end_sec) or (0, 0) if not found.
    Searches the three shapes we meet in production and accepts both
    *_offset_sec and *_time field names.
    """
    candidates: list[Dict[str, Any]] = []

    itm = _item(payload)
    if itm:
        candidates.append(itm)

    if isinstance(payload.get("data"), dict):
        candidates.append(payload["data"])

    m_itm = _map_item(payload)
    if m_itm:
        candidates.append(m_itm)

    for c in candidates:
        start = c.get("start_offset_sec") or c.get("start_time")
        end   = c.get("end_offset_sec")   or c.get("end_time")
        if start is not None and end is not None:
            return int(start), int(end)

    logger.warning("Segment bounds not found – defaulting to 0-0")
    return 0, 0


# ── Small helpers for early exits ────────────────────────────────────────────
def _bad_request(msg: str):
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _ok_no_op(vector: Optional[List], asset_id: Optional[str]):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Embedding processed (OpenSearch not available)",
                "asset_id": asset_id,
                "vector_length": len(vector or []),
            }
        ),
    }


def check_opensearch_response(response: Dict[str, Any], operation: str) -> None:
    """Raise if OpenSearch response status is not 200/201."""
    status = response.get("status", 200)
    if status not in (200, 201):
        error_msg = response.get("error", {}).get("reason", "Unknown error")
        logger.error(f"OpenSearch {operation} failed", extra={
            "status": status,
            "error": error_msg,
            "response": response
        })
        raise RuntimeError(f"OpenSearch {operation} failed: {error_msg} (status: {status})")


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    try:
        # 1) Get payload
        logger.info("Received event", extra={"event": event})
        payload = event.get("payload") or {}
        if not payload:
            return _bad_request("Event missing 'payload'")

        # 2) Resolve asset_id
        asset_id = extract_asset_id(payload)
        if not asset_id:
            return _bad_request("Unable to determine asset_id – aborting")

        # 3) Resolve embedding_vector
        embedding_vector = extract_embedding_vector(payload)
        if not embedding_vector and payload.get("assets"):
            for asset in payload["assets"]:
                cm = asset.get("Metadata", {}).get("CustomMetadata", {})
                if isinstance(cm.get("embedding"), list):
                    embedding_vector = cm["embedding"]
                    break
        if not embedding_vector:
            return _bad_request("No embedding vector found in event or assets")

        # 4) Resolve scope and embedding_option
        scope = extract_scope(payload)
        if IS_AUDIO_CONTENT and not scope:
            scope = "audio"
        embedding_option = extract_embedding_option(payload)
        logger.info(f"Scope={scope}, embedding_option={embedding_option}")

        # 5) Build base document
        document: Dict[str, Any] = {
            "type":              CONTENT_TYPE,
            "embedding_scope":   scope,
            "timestamp":         datetime.utcnow().isoformat(),
            "DigitalSourceAsset": {"ID": asset_id},
        }

        # 6) Inject vector
        if embedding_option == "audio" and scope == "video":
            document["audio_embedding"] = embedding_vector
            logger.info("Merged audio_embedding into video master", extra={
                "asset_id": asset_id, "vector_length": len(embedding_vector)
            })
        elif scope == "audio":
            document["audio_embedding"] = embedding_vector
        else:
            document["embedding"] = embedding_vector

        # 7) Get client or no-op
        client = get_opensearch_client()
        if not client:
            return _ok_no_op(embedding_vector, asset_id)

        # 8) New doc for clips/audio
        if scope in {"clip", "audio"}:
            start_sec, end_sec = _get_segment_bounds(payload)
            document.update({
                "start_timecode": seconds_to_smpte(start_sec),
                "end_timecode":   seconds_to_smpte(end_sec),
            })
            if IS_AUDIO_CONTENT:
                document["embedding_scope"] = "clip"
            if embedding_option is not None:
                document["embedding_option"] = embedding_option

            logger.info("Indexing new document", extra={
                "index": INDEX_NAME,
                "doc_preview": {
                    **document,
                    ("audio_embedding" if scope == "audio" else "embedding"):
                        f"<vector length {len(embedding_vector)}>"
                }
            })
            res = client.index(index=INDEX_NAME, body=document)
            check_opensearch_response(res, "index")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message":     "Embedding stored successfully",
                    "index":       INDEX_NAME,
                    "document_id": res.get("_id", "unknown"),
                    "asset_id":    asset_id,
                }),
            }

        # 9) Update existing master doc
        search_q = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"DigitalSourceAsset.ID": asset_id}},
                        {"exists": {"field": "InventoryID"}}
                    ]
                }
            }
        }
        logger.info("Searching for existing document", extra={"query": search_q})
        start = time.time()
        resp = client.search(index=INDEX_NAME, body=search_q, size=1)
        check_opensearch_response(resp, "search")

        # retry refresh
        while resp["hits"]["total"]["value"] == 0 and time.time() - start < 120:
            client.indices.refresh(index=INDEX_NAME)
            time.sleep(5)
            resp = client.search(index=INDEX_NAME, body=search_q, size=1)
            check_opensearch_response(resp, "search")

        if resp["hits"]["total"]["value"] == 0:
            raise RuntimeError(f"No document found with ID={asset_id} in {INDEX_NAME}")

        existing_id = resp["hits"]["hits"][0]["_id"]
        meta       = client.get(index=INDEX_NAME, id=existing_id)
        check_opensearch_response(meta, "get")
        seq_no, p_term = meta["_seq_no"], meta["_primary_term"]

        # optimistic update
        for _ in range(50):
            try:
                update_body = {"doc": document}
                ures = client.update(
                    index=INDEX_NAME,
                    id=existing_id,
                    body=update_body,
                    if_seq_no=seq_no,
                    if_primary_term=p_term,
                )
                check_opensearch_response(ures, "update")
                logger.info("Update successful", extra={"result": ures.get("result")})
                break
            except exceptions.ConflictError:
                meta   = client.get(index=INDEX_NAME, id=existing_id)
                check_opensearch_response(meta, "get")
                seq_no, p_term = meta["_seq_no"], meta["_primary_term"]
                time.sleep(1)
        else:
            raise RuntimeError("Failed to update document after 50 retries")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message":     "Embedding stored successfully",
                "index":       INDEX_NAME,
                "document_id": existing_id,
                "asset_id":    asset_id,
            }),
        }

    except Exception:
        logger.exception("Error storing embedding")
        raise

