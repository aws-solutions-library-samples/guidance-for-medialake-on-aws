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
    """
    Return payload.data.item if present (new Twelve Labs shape).
    """
    if isinstance(container.get("data"), dict):
        itm = container["data"].get("item")
        if isinstance(itm, dict):
            return itm
    return None


def _map_item(container: Dict[str, Any]) -> Optional[Dict[str, Any]]:  # 👈 NEW
    """
    Return payload.map.item when present (audio segmentation metadata).
    """
    m = container.get("map")
    if isinstance(m, dict) and isinstance(m.get("item"), dict):
        return m["item"]
    return None


def extract_asset_id(container: Dict[str, Any]) -> Optional[str]:
    """
    Locate the first asset ID, in order of priority:

    1. payload.data.item.asset_id          (new shape – PRIMARY)
    2. payload.map.item.asset_id           (audio map – SECONDARY)  # 👈 NEW
    3. payload.assets[ ].DigitalSourceAsset.ID
    4. payload.DigitalSourceAsset.ID
    """
    itm = _item(container)
    if itm and itm.get("asset_id"):
        return itm["asset_id"]

    m_itm = _map_item(container)                                     # 👈 NEW
    if m_itm and m_itm.get("asset_id"):                              # 👈 NEW
        return m_itm["asset_id"]                                     # 👈 NEW

    for asset in container.get("assets", []):
        dsa_id = asset.get("DigitalSourceAsset", {}).get("ID")
        if dsa_id:
            return dsa_id

    return container.get("DigitalSourceAsset", {}).get("ID")


def extract_scope(container: Dict[str, Any]) -> Optional[str]:
    """
    1. payload.data.item.embedding_scope   (new shape – PRIMARY)
    2. payload.embedding_scope
    3. payload.externalTaskResults[*].embedding_scope
    """
    itm = _item(container)
    if itm and itm.get("embedding_scope"):
        return itm["embedding_scope"]

    if container.get("embedding_scope"):
        return container["embedding_scope"]

    for res in container.get("externalTaskResults", []):
        if "embedding_scope" in res:
            return res["embedding_scope"]

    return None


def extract_embedding_vector(container: Dict[str, Any]) -> Optional[List[float]]:
    """
    1. payload.data.item.float             (new shape – PRIMARY)
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

# ── Lambda entrypoint ────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    try:
        logger.info("Received event", extra={"event": event})

        # 1️⃣ Unpack the envelope ------------------------------------------------
        payload: Dict[str, Any] = event.get("payload") or {}
        if not payload:
            return _bad_request("Event missing 'payload'")

        # 2️⃣ Extract critical fields ------------------------------------------
        asset_id         = extract_asset_id(payload)
        if not asset_id:
            return _bad_request("Unable to determine asset_id – aborting")

        embedding_vector = extract_embedding_vector(payload)
        if not embedding_vector:
            return _bad_request("No embedding vector found in event")

        scope            = extract_scope(payload)

        # 3️⃣ OpenSearch client (skip if unavailable) ---------------------------
        client = get_opensearch_client()
        if not client:
            return _ok_no_op(embedding_vector, asset_id)

        # 4️⃣ Base document definition ------------------------------------------
        document: Dict[str, Any] = {
            "type":            CONTENT_TYPE,
            "embedding":       embedding_vector,
            "embedding_scope": scope,
            "timestamp":       datetime.utcnow().isoformat(),
        }

        # ── Clip / audio scopes – create a new document ────────────────────────
        if scope in {"clip", "audio"}:
            # --------------------------------------------------------------
            # Where to grab segment timing?
            #  • clip  -> payload.data.item
            #  • audio -> payload.map.item  (preferred) OR payload.data.item
            # --------------------------------------------------------------
            itm: Dict[str, Any] = {}

            if scope == "clip":
                itm = _item(payload) or {}
                start_sec        = itm.get("start_offset_sec", 0)
                end_sec          = itm.get("end_offset_sec",   0)
                embedding_option = itm.get("embedding_option")
            else:  # audio
                itm = _map_item(payload) or _item(payload) or {}        # 👈 NEW
                start_sec = itm.get("start_time", 0)                    # 👈 NEW
                end_sec   = itm.get("end_time",   0)                    # 👈 NEW
                embedding_option = None  # audio: not stored

            document |= {
                "DigitalSourceAsset": {"ID": asset_id},
                "start_timecode":     seconds_to_smpte(start_sec),
                "end_timecode":       seconds_to_smpte(end_sec),
            }

            if embedding_option is not None:
                document["embedding_option"] = embedding_option

            res = client.index(index=INDEX_NAME, body=document)
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message":     "Embedding stored successfully",
                        "index":       INDEX_NAME,
                        "document_id": res.get("_id", "unknown"),
                        "asset_id":    asset_id,
                    }
                ),
            }

        # ── Non‑clip / non‑audio scopes – update existing document ────────────
        search_query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"DigitalSourceAsset.ID.keyword": asset_id}},
                        {"exists": {"field": "InventoryID"}},
                        {"exists": {"field": "DerivedRepresentations.ID"}},
                    ]
                }
            }
        }

        start_time      = time.time()
        search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
        while (
            search_response["hits"]["total"]["value"] == 0
            and time.time() - start_time < 120
        ):
            logger.info(f"Doc {asset_id} not found – refreshing index & retrying …")
            client.indices.refresh(index=INDEX_NAME)
            time.sleep(5)
            search_response = client.search(index=INDEX_NAME, body=search_query, size=1)

        if search_response["hits"]["total"]["value"] == 0:
            return _bad_request(
                f"No document found with DigitalSourceAsset.ID={asset_id} in '{INDEX_NAME}'"
            )

        existing_id       = search_response["hits"]["hits"][0]["_id"]
        meta              = client.get(index=INDEX_NAME, id=existing_id)
        seq_no, p_term    = meta["_seq_no"], meta["_primary_term"]
        document["DigitalSourceAsset"] = {"ID": asset_id}

        for attempt in range(50):
            try:
                res = client.update(
                    index=INDEX_NAME,
                    id=existing_id,
                    body={"doc": document},
                    if_seq_no=seq_no,
                    if_primary_term=p_term,
                )
                logger.info("Update succeeded", extra={"response": res})
                break
            except exceptions.ConflictError:
                logger.warning("Version conflict – retrying")
                meta   = client.get(index=INDEX_NAME, id=existing_id)
                seq_no = meta["_seq_no"]
                p_term = meta["_primary_term"]
                time.sleep(1)
        else:
            return _bad_request("Failed to update document after 50 retries")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message":     "Embedding stored successfully",
                    "index":       INDEX_NAME,
                    "document_id": existing_id,
                    "asset_id":    asset_id,
                }
            ),
        }

    # ── Un‑handled errors raise a RuntimeError (as requested) ────────────────
    except Exception as exc:
        logger.exception("Error storing embedding")
        raise RuntimeError("Error storing embedding") from exc
