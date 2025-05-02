import json
import os
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, exceptions

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
def extract_asset_id(container: dict) -> str | None:
    """
    Return the first DigitalSourceAsset.ID we can find.
    • Primary: payload.assets[ ].DigitalSourceAsset.ID
    • Fallback: payload.DigitalSourceAsset.ID
    If none found → return None (handler will raise 400).
    """
    # Look inside each asset in the array
    for asset in container.get("assets", []):
        dsa_id = asset.get("DigitalSourceAsset", {}).get("ID")
        if dsa_id:
            return dsa_id

    # Single-object fallback
    return container.get("DigitalSourceAsset", {}).get("ID")


def extract_scope(container: Dict[str, Any]) -> Optional[str]:
    scope = container.get("embedding_scope")
    if scope:
        return scope
    for res in container.get("externalTaskResults", []):
        if "embedding_scope" in res:
            return res["embedding_scope"]
    return None


def extract_embedding_vector(container: Dict[str, Any]) -> Optional[List[float]]:
    """
    Primary: payload.data.float   (new Twelve Labs shape)
    Fallback: top-level float or externalTaskResults[*].float (legacy)
    """
    if isinstance(container.get("data"), dict):
        vec = container["data"].get("float")
        if isinstance(vec, list) and vec:
            return vec

    vec = container.get("float")
    if isinstance(vec, list) and vec:
        return vec

    for res in container.get("externalTaskResults", []):
        vec = res.get("float")
        if isinstance(vec, list) and vec:
            return vec
    return None


# ── Small helpers for early exits ────────────────────────────────────────────
def _bad_request(msg: str):
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _ok_no_op(vector: List | None, asset_id: str | None):
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
            if scope == "clip":
                start_sec = payload.get("start_offset_sec", 0)
                end_sec   = payload.get("end_offset_sec",   0)
            else:
                start_sec = payload.get("start_time", 0)
                end_sec   = payload.get("end_time",   0)

            document |= {
                "DigitalSourceAsset": {"ID": asset_id},
                "start_timecode":     seconds_to_smpte(start_sec),
                "end_timecode":       seconds_to_smpte(end_sec),
            }

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

        # ── Non-clip / non-audio scopes – update existing document ────────────
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

    # ── Un-handled errors raise a RuntimeError (as requested) ────────────────
    except Exception as exc:
        logger.exception("Error storing embedding")
        raise RuntimeError("Error storing embedding") from exc
