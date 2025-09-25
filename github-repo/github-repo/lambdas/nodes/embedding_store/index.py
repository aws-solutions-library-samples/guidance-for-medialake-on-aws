"""
Store embedding vectors in OpenSearch.

* Clip/audio segments are indexed as new documents with SMPTE time-codes.
* Master video documents are updated in-place when a whole-file embedding arrives.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware
from lambda_utils import _truncate_floats
from nodes_utils import seconds_to_smpte
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, exceptions

# ─────────────────────────────────────────────────────────────────────────────
# Powertools
logger = Logger()
tracer = Tracer(disabled=False)

# Environment
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
INDEX_NAME = os.getenv("INDEX_NAME", "media")
CONTENT_TYPE = os.getenv("CONTENT_TYPE", "video").lower()  # "video" | "audio"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default-event-bus")

IS_AUDIO_CONTENT = CONTENT_TYPE == "audio"

# OpenSearch client
_session = boto3.Session()
_credentials = _session.get_credentials()
_auth = AWSV4SignerAuth(_credentials, AWS_REGION, "es")


def get_opensearch_client() -> Optional[OpenSearch]:
    if not OPENSEARCH_ENDPOINT:
        logger.warning("OPENSEARCH_ENDPOINT not set – skipping OpenSearch calls.")
        return None

    host = OPENSEARCH_ENDPOINT.split("://")[-1]
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


# ─────────────────────────────────────────────────────────────────────────────
# Extraction helpers (unchanged except for type annotations)
def _item(container: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(container.get("data"), dict):
        itm = container["data"].get("item")
        if isinstance(itm, dict):
            return itm
    return None


def _map_item(container: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    m = container.get("map")
    if isinstance(m, dict) and isinstance(m.get("item"), dict):
        return m["item"]
    return None


def extract_asset_id(container: Dict[str, Any]) -> Optional[str]:
    # Check if data is an array (batch processing) - get from first item
    if isinstance(container.get("data"), list) and container["data"]:
        first_item = container["data"][0]
        if isinstance(first_item, dict) and first_item.get("asset_id"):
            return first_item["asset_id"]

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


def extract_framerate(container: Dict[str, Any]) -> Optional[float]:
    """Extract framerate from various payload structures."""
    # Check if data is an array (batch processing) - get from first item
    if isinstance(container.get("data"), list) and container["data"]:
        first_item = container["data"][0]
        if isinstance(first_item, dict) and first_item.get("framerate"):
            return first_item["framerate"]

    itm = _item(container)
    if itm and itm.get("framerate"):
        return itm["framerate"]

    data = container.get("data")
    if isinstance(data, dict) and data.get("framerate"):
        return data["framerate"]

    m_itm = _map_item(container)
    if m_itm and m_itm.get("framerate"):
        return m_itm["framerate"]

    if container.get("framerate"):
        return container["framerate"]

    return None


def _get_segment_bounds(payload: Dict[str, Any]) -> Tuple[int, int]:
    candidates: List[Dict[str, Any]] = []

    # Check payload.data directly (this is the main location based on logs)
    if isinstance(payload.get("data"), dict):
        candidates.append(payload["data"])

    # Check if item is directly in payload
    if isinstance(payload.get("item"), dict):
        candidates.append(payload["item"])

    # Check map.item (also contains the data based on logs)
    if isinstance(payload.get("map"), dict) and isinstance(
        payload["map"].get("item"), dict
    ):
        candidates.append(payload["map"]["item"])

    itm = _item(payload)
    if itm:
        candidates.append(itm)

    m_itm = _map_item(payload)
    if m_itm:
        candidates.append(m_itm)

    # Also check the payload itself as a candidate
    candidates.append(payload)

    for c in candidates:
        if not isinstance(c, dict):
            continue
        start = c.get("start_offset_sec")
        if start is None:
            start = c.get("start_time")
        end = c.get("end_offset_sec")
        if end is None:
            end = c.get("end_time")
        if start is not None and end is not None:
            return int(start), int(end)

    logger.warning("Segment bounds not found – defaulting to 0-0")
    return 0, 0


# ─────────────────────────────────────────────────────────────────────────────
# Early-exit helpers
def _bad_request(msg: str):
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _ok_no_op(vector_len: int, asset_id: Optional[str]):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Embedding processed (OpenSearch not available)",
                "asset_id": asset_id,
                "vector_length": vector_len,
            }
        ),
    }


def check_opensearch_response(resp: Dict[str, Any], op: str) -> None:
    """Check OpenSearch response and raise error if not successful."""
    status = resp.get("status", 200)
    if status not in (200, 201):
        err = resp.get("error", {}).get("reason", "Unknown error")
        logger.error(f"OpenSearch {op} failed", extra={"status": status, "error": err})
        raise RuntimeError(f"OpenSearch {op} failed: {err} (status {status})")


# ─────────────────────────────────────────────────────────────────────────────
# One-shot master-document cache + FPS extraction
_master_doc_cache: Dict[str, Dict[str, Any]] = {}  # asset_id → _source


def _get_master_doc(
    client: OpenSearch,
    asset_id: str,
    is_video: bool,
    max_retries: int = 50,
    delay_seconds: float = 1.0,
) -> Dict[str, Any]:
    """
    Fetches the master document for a given asset_id, retrying up to max_retries
    times if no document is found.
    """
    # return cached if available
    if asset_id in _master_doc_cache:
        return _master_doc_cache[asset_id]

    filters = [
        {"term": {"DigitalSourceAsset.ID": asset_id}},
        {"exists": {"field": "InventoryID"}},
        {
            "nested": {
                "path": "DerivedRepresentations",
                "query": {"exists": {"field": "DerivedRepresentations.ID"}},
            }
        },
    ]

    for attempt in range(1, max_retries + 1):
        resp = client.search(
            index=INDEX_NAME,
            body={"query": {"bool": {"filter": filters}}},
            size=1,
        )
        total_hits = resp.get("hits", {}).get("total", {}).get("value", 0)

        if total_hits > 0:
            doc = resp["hits"]["hits"][0]["_source"]
            _master_doc_cache[asset_id] = doc
            return doc

        # not found, wait and retry
        time.sleep(delay_seconds)

    # after all retries
    raise RuntimeError(
        f"No master document found for asset {asset_id} after {max_retries} attempts"
    )


def _extract_fps(master_src: Dict[str, Any], asset_id: str) -> int:
    try:
        fr = master_src["Metadata"]["EmbeddedMetadata"]["general"]["FrameRate"]
        fps_int = int(round(float(fr)))
        if fps_int <= 0:
            raise ValueError
        return fps_int
    except Exception as exc:
        raise RuntimeError(
            f"Master document for asset {asset_id} is missing a valid FrameRate"
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
def process_single_embedding(
    payload: Dict[str, Any], embedding_data: Dict[str, Any], client, asset_id: str
) -> Dict[str, Any]:
    """Process a single embedding object."""
    embedding_vector = embedding_data.get("float")
    if not embedding_vector:
        return _bad_request("No embedding vector found in embedding data")

    # Create a temporary payload for this embedding
    temp_payload = {
        "data": embedding_data,
        **{k: v for k, v in payload.items() if k != "data"},
    }

    scope = embedding_data.get("embedding_scope") or extract_scope(temp_payload)
    embedding_option = embedding_data.get(
        "embedding_option"
    ) or extract_embedding_option(temp_payload)

    start_sec, end_sec = _get_segment_bounds(temp_payload)

    # Extract framerate from input data (only for video content)
    if CONTENT_TYPE == "video":
        framerate = embedding_data.get("framerate") or extract_framerate(temp_payload)
        fps = int(round(framerate)) if framerate else 30
    else:
        fps = 30

    start_tc = seconds_to_smpte(start_sec, fps)
    end_tc = seconds_to_smpte(end_sec, fps)

    document: Dict[str, Any] = {
        "type": CONTENT_TYPE,
        "embedding": embedding_vector,
        "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
        "timestamp": datetime.utcnow().isoformat(),
        "DigitalSourceAsset": {"ID": asset_id},
        "start_timecode": start_tc,
        "end_timecode": end_tc,
    }
    if embedding_option is not None:
        document["embedding_option"] = embedding_option

    try:
        res = client.index(index=INDEX_NAME, body=document)
        check_opensearch_response(res, "index")

        return {
            "document_id": res.get("_id", "unknown"),
            "start_sec": start_sec,
            "end_sec": end_sec,
        }
    except Exception as e:
        logger.error(
            "Failed to index document in OpenSearch",
            extra={"asset_id": asset_id, "error": str(e), "index": INDEX_NAME},
        )
        raise RuntimeError(
            f"Failed to index document for asset {asset_id}: {str(e)}"
        ) from e


@lambda_middleware(event_bus_name=EVENT_BUS_NAME)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    try:
        truncated = _truncate_floats(event, max_items=10)
        logger.info("Received event", extra={"event": truncated})
        logger.info(f"Content Type {CONTENT_TYPE}")

        payload: Dict[str, Any] = event.get("payload") or {}
        if not payload:
            return _bad_request("Event missing 'payload'")

        asset_id = extract_asset_id(payload)
        if not asset_id:
            return _bad_request("Unable to determine asset_id – aborting")

        # OpenSearch client (may be None in local dev)
        try:
            client = get_opensearch_client()
            if not client:
                return _ok_no_op(None, asset_id)
        except Exception as e:
            logger.error(
                "Failed to initialize OpenSearch client", extra={"error": str(e)}
            )
            raise RuntimeError(
                f"Failed to initialize OpenSearch client: {str(e)}"
            ) from e

        # Check if this is batch processing (array of embeddings)
        if isinstance(payload.get("data"), list):
            logger.info(f"Processing batch of {len(payload['data'])} embeddings")
            results = []
            video_scope_embeddings = []

            # Separate video scope embeddings from clip embeddings
            for i, embedding_data in enumerate(payload["data"]):
                if not isinstance(embedding_data, dict):
                    continue

                # Create temp payload to extract scope
                temp_payload = {
                    "data": embedding_data,
                    **{k: v for k, v in payload.items() if k != "data"},
                }
                scope = embedding_data.get("embedding_scope") or extract_scope(
                    temp_payload
                )

                if scope == "video" and not IS_AUDIO_CONTENT:
                    video_scope_embeddings.append((i, embedding_data, scope))
                else:
                    # Process clip/audio embeddings
                    try:
                        result = process_single_embedding(
                            payload, embedding_data, client, asset_id
                        )
                        results.append(result)
                        logger.info(
                            f"Processed clip embedding {i+1}/{len(payload['data'])}",
                            extra={
                                "document_id": result["document_id"],
                                "start_sec": result["start_sec"],
                                "end_sec": result["end_sec"],
                            },
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process clip embedding {i+1}",
                            extra={"error": str(e)},
                        )
                        raise RuntimeError(
                            f"Failed to process clip embedding {i+1}: {str(e)}"
                        ) from e

            # Process video scope embeddings (update master documents)
            for i, embedding_data, scope in video_scope_embeddings:
                try:
                    embedding_vector = embedding_data.get("float")
                    if not embedding_vector:
                        logger.error(
                            f"No embedding vector found in video embedding {i+1}"
                        )
                        raise RuntimeError(
                            f"No embedding vector found in video embedding {i+1}"
                        )

                    temp_payload = {
                        "data": embedding_data,
                        **{k: v for k, v in payload.items() if k != "data"},
                    }
                    embedding_option = embedding_data.get(
                        "embedding_option"
                    ) or extract_embedding_option(temp_payload)

                    # Update master document (similar to non-batch logic)
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
                                            },
                                        }
                                    },
                                ]
                            }
                        }
                    }

                    logger.info(
                        f"Searching for master document for video embedding {i+1}",
                        extra={"index": INDEX_NAME, "asset_id": asset_id},
                    )
                    start_time = time.time()
                    try:
                        search_resp = client.search(
                            index=INDEX_NAME, body=search_query, size=1
                        )
                        check_opensearch_response(search_resp, "search")
                    except Exception as e:
                        logger.error(
                            f"Failed to search for master document in batch video embedding {i+1}",
                            extra={
                                "asset_id": asset_id,
                                "error": str(e),
                                "index": INDEX_NAME,
                            },
                        )
                        raise RuntimeError(
                            f"Failed to search for master document in batch video embedding {i+1} for asset {asset_id}: {str(e)}"
                        ) from e

                    while (
                        search_resp["hits"]["total"]["value"] == 0
                        and time.time() - start_time < 120
                    ):
                        logger.info(
                            "Master doc not found – refreshing index & retrying …"
                        )
                        try:
                            client.indices.refresh(index=INDEX_NAME)
                            time.sleep(5)
                            search_resp = client.search(
                                index=INDEX_NAME, body=search_query, size=1
                            )
                            check_opensearch_response(search_resp, "search")
                        except Exception as e:
                            logger.error(
                                f"Failed to refresh index and retry search in batch video embedding {i+1}",
                                extra={
                                    "asset_id": asset_id,
                                    "error": str(e),
                                    "index": INDEX_NAME,
                                },
                            )
                            raise RuntimeError(
                                f"Failed to refresh index and retry search in batch video embedding {i+1} for asset {asset_id}: {str(e)}"
                            ) from e

                    if search_resp["hits"]["total"]["value"] == 0:
                        raise RuntimeError(
                            f"No master doc with DigitalSourceAsset.ID={asset_id} in '{INDEX_NAME}'"
                        )

                    existing_id = search_resp["hits"]["hits"][0]["_id"]
                    try:
                        meta = client.get(index=INDEX_NAME, id=existing_id)
                        check_opensearch_response(meta, "get")
                        seq_no = meta["_seq_no"]
                        p_term = meta["_primary_term"]
                    except Exception as e:
                        logger.error(
                            f"Failed to get document metadata in batch video embedding {i+1}",
                            extra={
                                "asset_id": asset_id,
                                "document_id": existing_id,
                                "error": str(e),
                                "index": INDEX_NAME,
                            },
                        )
                        raise RuntimeError(
                            f"Failed to get metadata for document {existing_id} in batch video embedding {i+1} (asset {asset_id}): {str(e)}"
                        ) from e

                    update_body = {
                        "doc": {
                            "type": CONTENT_TYPE,
                            "embedding": embedding_vector,
                            "embedding_scope": scope,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    }
                    if embedding_option == "audio":
                        update_body["doc"]["audio_embedding"] = embedding_vector
                    else:
                        update_body["doc"]["embedding"] = embedding_vector
                    if embedding_option is not None:
                        update_body["doc"]["embedding_option"] = embedding_option

                    for attempt in range(50):
                        try:
                            res = client.update(
                                index=INDEX_NAME,
                                id=existing_id,
                                body=update_body,
                                if_seq_no=seq_no,
                                if_primary_term=p_term,
                            )
                            check_opensearch_response(res, "update")
                            break
                        except exceptions.ConflictError:
                            try:
                                meta = client.get(index=INDEX_NAME, id=existing_id)
                                seq_no = meta["_seq_no"]
                                p_term = meta["_primary_term"]
                                time.sleep(1)
                            except Exception as e:
                                logger.error(
                                    "Failed to resolve conflict during batch video embedding update",
                                    extra={
                                        "asset_id": asset_id,
                                        "document_id": existing_id,
                                        "error": str(e),
                                        "attempt": attempt + 1,
                                        "embedding_index": i + 1,
                                    },
                                )
                                raise RuntimeError(
                                    f"Failed to resolve conflict for batch video embedding {i+1} document {existing_id} (asset {asset_id}): {str(e)}"
                                ) from e
                    else:
                        raise RuntimeError(
                            "Failed to update master document after 50 retries"
                        )

                    results.append(
                        {
                            "document_id": existing_id,
                            "type": "master_update",
                            "scope": scope,
                        }
                    )
                    logger.info(
                        f"Updated master document for video embedding {i+1}/{len(payload['data'])}",
                        extra={"document_id": existing_id, "scope": scope},
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to process video embedding {i+1}",
                        extra={"error": str(e)},
                    )
                    raise RuntimeError(
                        f"Failed to process video embedding {i+1}: {str(e)}"
                    ) from e

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": f"Batch processed: {len(results)} embeddings stored successfully",
                        "index": INDEX_NAME,
                        "asset_id": asset_id,
                        "processed_count": len(results),
                        "total_count": len(payload["data"]),
                    }
                ),
            }

        # Single embedding processing (original logic)
        embedding_vector = extract_embedding_vector(payload)
        if not embedding_vector and payload.get("assets"):
            for asset in payload["assets"]:
                meta = asset.get("Metadata", {}).get("CustomMetadata", {})
                if isinstance(meta.get("embedding"), list):
                    embedding_vector = meta["embedding"]
                    break

        if not embedding_vector:
            return _bad_request("No embedding vector found in event or assets")

        scope = extract_scope(payload)
        embedding_option = extract_embedding_option(payload)

        # ── CLIP / AUDIO SCOPE  → NEW DOC ────────────────────────────────────
        if scope in {"clip", "audio"}:
            start_sec, end_sec = _get_segment_bounds(payload)

            # Extract framerate from input data (only for video content)
            if CONTENT_TYPE == "video":
                framerate = extract_framerate(payload)
                fps = int(round(framerate)) if framerate else 30
            else:  # audio clip
                fps = 30  # arbitrary; frame-rate irrelevant for audio

            logger.info(
                "Segment SMPTE conversion",
                extra={
                    "asset_id": asset_id,
                    "fps": fps,
                    "start_seconds": start_sec,
                    "end_seconds": end_sec,
                },
            )

            start_tc = seconds_to_smpte(start_sec, fps)
            end_tc = seconds_to_smpte(end_sec, fps)

            # ── log the SMPTE strings *after* conversion ────────────────────────
            logger.info(
                "Segment SMPTE values",
                extra={
                    "asset_id": asset_id,
                    "start_timecode": start_tc,
                    "end_timecode": end_tc,
                },
            )

            document: Dict[str, Any] = {
                "type": CONTENT_TYPE,
                "embedding": embedding_vector,
                "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
                "timestamp": datetime.utcnow().isoformat(),
                "DigitalSourceAsset": {"ID": asset_id},
                "start_timecode": start_tc,
                "end_timecode": end_tc,
            }
            if embedding_option is not None:
                document["embedding_option"] = embedding_option

            logger.info(
                "Indexing new clip/audio document",
                extra={
                    "index": INDEX_NAME,
                    "doc_preview": {
                        **document,
                        "embedding": f"<len {len(embedding_vector)}>",
                    },
                },
            )
            try:
                res = client.index(index=INDEX_NAME, body=document)
                check_opensearch_response(res, "index")
            except Exception as e:
                logger.error(
                    "Failed to index clip/audio document",
                    extra={
                        "asset_id": asset_id,
                        "error": str(e),
                        "index": INDEX_NAME,
                        "scope": scope,
                    },
                )
                raise RuntimeError(
                    f"Failed to index {scope} document for asset {asset_id}: {str(e)}"
                ) from e

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Embedding stored successfully",
                        "index": INDEX_NAME,
                        "document_id": res.get("_id", "unknown"),
                        "asset_id": asset_id,
                    }
                ),
            }

        # ── AUDIO MASTER DOCS ARE *NOT* UPDATED ───────────────────────────────
        if IS_AUDIO_CONTENT:
            logger.info(
                "Skipping master-doc update for audio content",
                extra={"asset_id": asset_id},
            )
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Embedding stored (audio clip only – master unchanged)",
                        "asset_id": asset_id,
                    }
                ),
            }

        # ── MASTER-DOC UPDATE for VIDEO (existing query) ──────────────────────
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
                                    "exists": {"field": "DerivedRepresentations.ID"}
                                },
                            }
                        },
                    ]
                }
            }
        }

        logger.info(
            "Searching for existing master document",
            extra={"index": INDEX_NAME, "asset_id": asset_id, "query": search_query},
        )
        start_time = time.time()
        try:
            search_resp = client.search(index=INDEX_NAME, body=search_query, size=1)
            check_opensearch_response(search_resp, "search")
        except Exception as e:
            logger.error(
                "Failed to search for master document",
                extra={"asset_id": asset_id, "error": str(e), "index": INDEX_NAME},
            )
            raise RuntimeError(
                f"Failed to search for master document for asset {asset_id}: {str(e)}"
            ) from e

        while (
            search_resp["hits"]["total"]["value"] == 0
            and time.time() - start_time < 120
        ):
            logger.info("Master doc not found – refreshing index & retrying …")
            try:
                client.indices.refresh(index=INDEX_NAME)
                time.sleep(5)
                search_resp = client.search(index=INDEX_NAME, body=search_query, size=1)
                check_opensearch_response(search_resp, "search")
            except Exception as e:
                logger.error(
                    "Failed to refresh index and retry search",
                    extra={"asset_id": asset_id, "error": str(e), "index": INDEX_NAME},
                )
                raise RuntimeError(
                    f"Failed to refresh index and retry search for asset {asset_id}: {str(e)}"
                ) from e

        if search_resp["hits"]["total"]["value"] == 0:
            raise RuntimeError(
                f"No master doc with DigitalSourceAsset.ID={asset_id} in '{INDEX_NAME}'"
            )

        existing_id = search_resp["hits"]["hits"][0]["_id"]
        try:
            meta = client.get(index=INDEX_NAME, id=existing_id)
            check_opensearch_response(meta, "get")
            seq_no = meta["_seq_no"]
            p_term = meta["_primary_term"]
        except Exception as e:
            logger.error(
                "Failed to get document metadata",
                extra={
                    "asset_id": asset_id,
                    "document_id": existing_id,
                    "error": str(e),
                    "index": INDEX_NAME,
                },
            )
            raise RuntimeError(
                f"Failed to get metadata for document {existing_id} (asset {asset_id}): {str(e)}"
            ) from e

        update_body = {
            "doc": {
                "type": CONTENT_TYPE,
                "embedding": embedding_vector,
                "embedding_scope": scope,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
        if embedding_option == "audio":
            update_body["doc"]["audio_embedding"] = embedding_vector
        else:
            update_body["doc"]["embedding"] = embedding_vector

        if embedding_option is not None:
            update_body["doc"]["embedding_option"] = embedding_option

        for attempt in range(50):
            try:
                res = client.update(
                    index=INDEX_NAME,
                    id=existing_id,
                    body=update_body,
                    if_seq_no=seq_no,
                    if_primary_term=p_term,
                )
                check_opensearch_response(res, "update")
                break
            except exceptions.ConflictError:
                try:
                    meta = client.get(index=INDEX_NAME, id=existing_id)
                    seq_no = meta["_seq_no"]
                    p_term = meta["_primary_term"]
                    time.sleep(1)
                except Exception as e:
                    logger.error(
                        "Failed to resolve conflict during document update",
                        extra={
                            "asset_id": asset_id,
                            "document_id": existing_id,
                            "error": str(e),
                            "attempt": attempt + 1,
                        },
                    )
                    raise RuntimeError(
                        f"Failed to resolve conflict for document {existing_id} (asset {asset_id}): {str(e)}"
                    ) from e
        else:
            raise RuntimeError("Failed to update master document after 50 retries")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Embedding stored successfully",
                    "index": INDEX_NAME,
                    "document_id": existing_id,
                    "asset_id": asset_id,
                }
            ),
        }

    except Exception:
        logger.exception("Error storing embedding")
        raise
