import json
import os
import time
import sys
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

# Add common_libraries to path for importing shared modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'common_libraries'))
from lambda_middleware import lambda_middleware
from lambda_error_handler import (
    check_response_status,
    ResponseError,
    with_error_handling
)
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

    1. payload.data.item.asset_id    
    2. payload.map.item.asset_id     
    3. payload.assets[ ].DigitalSourceAsset.ID
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

# Using the new error handler module instead of the local function
def check_opensearch_response(response: Dict[str, Any], operation: str) -> None:
    """
    Check OpenSearch response for errors and raise if status is not 200/201
    
    This is a wrapper around check_response_status for backward compatibility
    """
    check_response_status(response, "OpenSearch", operation, [200, 201])

# ── Lambda entrypoint ────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
@with_error_handling
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    try:
        logger.info("Received event", extra={"event": event})

        # Extract and validate payload
        payload: Dict[str, Any] = event.get("payload") or {}
        if not payload:
            return _bad_request("Event missing 'payload'")

        # Log the full payload structure for debugging
        logger.info("Processing payload", extra={
            "payload_structure": {
                "has_data": "data" in payload,
                "has_assets": "assets" in payload,
                "data_type": type(payload.get("data")).__name__ if payload.get("data") else None,
                "assets_length": len(payload.get("assets", [])),
            }
        })

        # Check if we're receiving an error response
        if isinstance(payload.get("data"), dict):
            response_data = payload["data"]
            if isinstance(response_data, dict) and response_data.get("statusCode") == 400:
                error_body = json.loads(response_data.get("body", "{}"))
                error_message = error_body.get("error", "Unknown 400 error")
                logger.error(f"Received 400 status code in payload.data: {error_message}")
                # Don't immediately fail - continue processing as the embedding might be elsewhere
                logger.info("Attempting to process assets data despite error in payload.data")

        # Extract asset_id first since we need it for both paths
        asset_id = extract_asset_id(payload)
        if not asset_id:
            # Try to extract from assets array if present
            if payload.get("assets"):
                for asset in payload["assets"]:
                    if asset.get("DigitalSourceAsset", {}).get("ID"):
                        asset_id = asset["DigitalSourceAsset"]["ID"]
                        logger.info(f"Found asset_id in assets array: {asset_id}")
                        break

        if not asset_id:
            return _bad_request("Unable to determine asset_id – aborting")

        # Try to extract embedding vector from multiple locations
        embedding_vector = extract_embedding_vector(payload)
        if not embedding_vector and payload.get("assets"):
            # If embedding_vector not found in primary location, try to extract from assets
            logger.info("Attempting to extract embedding vector from assets data")
            for asset in payload["assets"]:
                if isinstance(asset, dict):
                    # Try to extract from asset's metadata or other relevant fields
                    # This might need adjustment based on where the embedding actually is
                    if "Metadata" in asset and "CustomMetadata" in asset["Metadata"]:
                        metadata = asset["Metadata"]["CustomMetadata"]
                        if "embedding" in metadata:
                            embedding_vector = metadata["embedding"]
                            logger.info("Found embedding vector in asset metadata")
                            break

        if not embedding_vector:
            error_msg = "No embedding vector found in event or assets data"
            logger.error(error_msg, extra={"payload_structure": payload})
            return _bad_request(error_msg)

        scope = extract_scope(payload)

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
                itm = _map_item(payload) or _item(payload) or {}
                start_sec = itm.get("start_time", 0)
                end_sec   = itm.get("end_time",   0)
                embedding_option = None  # audio: not stored

            document |= {
                "DigitalSourceAsset": {"ID": asset_id},
                "start_timecode":     seconds_to_smpte(start_sec),
                "end_timecode":       seconds_to_smpte(end_sec),
            }

            if embedding_option is not None:
                document["embedding_option"] = embedding_option

            logger.info("Inserting new document into OpenSearch", extra={
                "operation": "index",
                "index": INDEX_NAME,
                "document_structure": {
                    **document,
                    "embedding": f"<vector with length {len(embedding_vector)}>"  # Don't log full vector
                }
            })
            res = client.index(index=INDEX_NAME, body=document)
            check_opensearch_response(res, "index")
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
                        {"term": {"DigitalSourceAsset.ID": asset_id}},
                        {"exists": {"field": "InventoryID"}},
                        {
                            "nested": {
                                "path": "DerivedRepresentations",
                                "query": {
                                    "exists": {
                                        "field": "DerivedRepresentations.ID"
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }

        logger.info("Searching for existing document", extra={
            "operation": "search",
            "index": INDEX_NAME,
            "asset_id": asset_id,
            "query": search_query
        })

        start_time      = time.time()
        search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
        check_opensearch_response(search_response, "search")
        
        logger.info("Search response received", extra={
            "total_hits": search_response["hits"]["total"]["value"],
            "took_ms": search_response.get("took", 0),
            "asset_id": asset_id
        })

        while (
            search_response["hits"]["total"]["value"] == 0
            and time.time() - start_time < 120
        ):
            logger.info(f"Doc {asset_id} not found – refreshing index & retrying …")
            refresh_response = client.indices.refresh(index=INDEX_NAME)
            check_opensearch_response(refresh_response, "refresh")
            time.sleep(5)
            search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
            check_opensearch_response(search_response, "search")

        if search_response["hits"]["total"]["value"] == 0:
            error_msg = f"No document found with DigitalSourceAsset.ID={asset_id} in '{INDEX_NAME}'"
            logger.error(error_msg, extra={
                "asset_id": asset_id,
                "index": INDEX_NAME,
                "search_query": search_query
            })
            raise RuntimeError(error_msg)

        existing_id       = search_response["hits"]["hits"][0]["_id"]
        meta             = client.get(index=INDEX_NAME, id=existing_id)
        check_opensearch_response(meta, "get")
        seq_no, p_term    = meta["_seq_no"], meta["_primary_term"]
        document["DigitalSourceAsset"] = {"ID": asset_id}

        logger.info("Starting document update process", extra={
            "document_id": existing_id,
            "asset_id": asset_id,
            "index": INDEX_NAME,
            "sequence_no": seq_no,
            "primary_term": p_term
        })

        for attempt in range(50):
            try:
                update_body = {"doc": document}
                logger.info("Attempting document update", extra={
                    "attempt": attempt + 1,
                    "operation": "update",
                    "index": INDEX_NAME,
                    "document_id": existing_id,
                    "asset_id": asset_id,
                    "update_structure": {
                        **update_body,
                        "doc": {
                            **document,
                            "embedding": f"<vector with length {len(embedding_vector)}>"
                        }
                    },
                    "seq_no": seq_no,
                    "primary_term": p_term
                })

                res = client.update(
                    index=INDEX_NAME,
                    id=existing_id,
                    body=update_body,
                    if_seq_no=seq_no,
                    if_primary_term=p_term,
                )
                check_opensearch_response(res, "update")
                
                logger.info("Update operation successful", extra={
                    "operation": "update",
                    "document_id": existing_id,
                    "asset_id": asset_id,
                    "attempt": attempt + 1,
                    "response": {
                        "result": res.get("result"),
                        "version": res.get("_version"),
                        "seq_no": res.get("_seq_no"),
                        "primary_term": res.get("_primary_term")
                    }
                })
                break

            except exceptions.ConflictError:
                logger.warning("Version conflict during update", extra={
                    "attempt": attempt + 1,
                    "document_id": existing_id,
                    "asset_id": asset_id,
                    "old_seq_no": seq_no,
                    "old_primary_term": p_term
                })
                meta   = client.get(index=INDEX_NAME, id=existing_id)
                check_opensearch_response(meta, "get")
                seq_no = meta["_seq_no"]
                p_term = meta["_primary_term"]
                logger.info("Retrieved new sequence numbers after conflict", extra={
                    "new_seq_no": seq_no,
                    "new_primary_term": p_term,
                    "document_id": existing_id,
                    "asset_id": asset_id
                })
                time.sleep(1)
        else:
            error_msg = "Failed to update document after 50 retries"
            logger.error(error_msg, extra={
                "document_id": existing_id,
                "asset_id": asset_id,
                "final_seq_no": seq_no,
                "final_primary_term": p_term
            })
            return _bad_request(error_msg)

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

    except ResponseError:
        # ResponseError is already logged and formatted by the with_error_handling decorator
        raise
    except Exception as exc:
        logger.exception("Error storing embedding")
        raise RuntimeError("Error storing embedding") from exc
