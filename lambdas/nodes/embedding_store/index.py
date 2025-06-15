"""
Store embedding vectors in OpenSearch.

* Clip/audio segments are indexed as new documents with SMPTE time-codes.
* Master video documents are updated in-place when a whole-file embedding
  arrives.
* Audio vectors are written to `audio_embedding` so they can live
  alongside visual embeddings on the same master document.
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
from opensearchpy import (
    AWSV4SignerAuth,
    OpenSearch,
    RequestsHttpConnection,
    exceptions,
)

from lambda_middleware import lambda_middleware
from nodes_utils import seconds_to_smpte
from lambda_utils import _truncate_floats

# ─────────────────────────────────────────────────────────────────────────────
# Powertools
logger = Logger()
tracer = Tracer(disabled=False)

# Environment
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
INDEX_NAME          = os.getenv("INDEX_NAME", "media")
CONTENT_TYPE        = os.getenv("CONTENT_TYPE", "video").lower()  # video | audio
AWS_REGION          = os.getenv("AWS_REGION", "us-east-1")
EVENT_BUS_NAME      = os.getenv("EVENT_BUS_NAME", "default-event-bus")

IS_AUDIO_CONTENT    = CONTENT_TYPE == "audio"

# OpenSearch client
_session     = boto3.Session()
_credentials = _session.get_credentials()
_auth        = AWSV4SignerAuth(_credentials, AWS_REGION, "es")


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
    # Batch case first
    if isinstance(container.get("data"), list) and container["data"]:
        itm0 = container["data"][0]
        if isinstance(itm0, dict) and itm0.get("asset_id"):
            return itm0["asset_id"]

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


def _get_segment_bounds(payload: Dict[str, Any]) -> Tuple[int, int]:
    candidates: List[Dict[str, Any]] = []

    # most common first
    if isinstance(payload.get("data"), dict):
        candidates.append(payload["data"])
    if isinstance(payload.get("item"), dict):
        candidates.append(payload["item"])
    if isinstance(payload.get("map"), dict) and isinstance(payload["map"].get("item"), dict):
        candidates.append(payload["map"]["item"])

    itm = _item(payload)
    if itm:
        candidates.append(itm)
    m_itm = _map_item(payload)
    if m_itm:
        candidates.append(m_itm)
    candidates.append(payload)  # fallback

    for c in candidates:
        if not isinstance(c, dict):
            continue
        start = c.get("start_offset_sec") or c.get("start_time")
        end   = c.get("end_offset_sec")   or c.get("end_time")
        if start is not None and end is not None:
            return int(start), int(end)

    logger.warning("Segment bounds not found – defaulting to 0-0")
    return 0, 0

# ─────────────────────────────────────────────────────────────────────────────
# Early-exit helpers
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


def check_opensearch_response(resp: Dict[str, Any], op: str) -> None:
    status = resp.get("status", 200)
    if status not in (200, 201):
        err = resp.get("error", {}).get("reason", "Unknown error")
        logger.error(f"OpenSearch {op} failed", extra={"status": status, "error": err})
        raise RuntimeError(f"OpenSearch {op} failed: {err} (status {status})")

# ─────────────────────────────────────────────────────────────────────────────
# Master-doc cache + FPS helpers
_master_doc_cache: Dict[str, Dict[str, Any]] = {}   # asset_id → _source


def _get_master_doc(client: OpenSearch, asset_id: str) -> Dict[str, Any]:
    if asset_id in _master_doc_cache:
        return _master_doc_cache[asset_id]

    filters = [
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

    resp = client.search(index=INDEX_NAME, body={"query": {"bool": {"filter": filters}}}, size=1)
    if resp["hits"]["total"]["value"] == 0:
        raise RuntimeError(f"No master document found for asset {asset_id}")

    _master_doc_cache[asset_id] = resp["hits"]["hits"][0]["_source"]
    return _master_doc_cache[asset_id]


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
def _vector_field(scope: str, embedding_option: Optional[str]) -> str:
    """
    Decide whether to write into `embedding` or `audio_embedding`.
      – clip/audio docs:   always audio_embedding when scope == "audio"
      – master-video docs: audio_embedding when embedding_option == "audio"
                           otherwise embedding
    """
    if scope == "audio":
        return "audio_embedding"
    if scope == "video" and embedding_option == "audio":
        return "audio_embedding"
    return "embedding"


def process_single_embedding(
    payload: Dict[str, Any],
    embedding_data: Dict[str, Any],
    client: OpenSearch,
    asset_id: str,
) -> Dict[str, Any]:
    """Process a single clip/audio embedding object."""
    embedding_vector = embedding_data.get("float")
    if not embedding_vector:
        return _bad_request("No embedding vector found in embedding data")

    # Build a temp payload for helpers
    temp_payload = {"data": embedding_data, **{k: v for k, v in payload.items() if k != "data"}}

    scope            = embedding_data.get("embedding_scope") or extract_scope(temp_payload)
    embedding_option = embedding_data.get("embedding_option") or extract_embedding_option(
        temp_payload
    )

    start_sec, end_sec = _get_segment_bounds(temp_payload)

    fps = 30  # default for audio
    if CONTENT_TYPE == "video":
        master_src = _get_master_doc(client, asset_id)
        fps = _extract_fps(master_src, asset_id)

    start_tc = seconds_to_smpte(start_sec, fps)
    end_tc   = seconds_to_smpte(end_sec, fps)

    vec_field = _vector_field(scope, embedding_option)

    document: Dict[str, Any] = {
        "type": CONTENT_TYPE,
        "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
        "timestamp": datetime.utcnow().isoformat(),
        "DigitalSourceAsset": {"ID": asset_id},
        "start_timecode": start_tc,
        "end_timecode": end_tc,
        vec_field: embedding_vector,
    }
    if embedding_option is not None:
        document["embedding_option"] = embedding_option

    res = client.index(index=INDEX_NAME, body=document)
    check_opensearch_response(res, "index")

    return {
        "document_id": res.get("_id", "unknown"),
        "start_sec": start_sec,
        "end_sec": end_sec,
    }


@lambda_middleware(event_bus_name=EVENT_BUS_NAME)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    try:
        logger.info("Received event", extra={"event": _truncate_floats(event, 10)})

        payload: Dict[str, Any] = event.get("payload") or {}
        if not payload:
            return _bad_request("Event missing 'payload'")

        asset_id = extract_asset_id(payload)
        if not asset_id:
            return _bad_request("Unable to determine asset_id – aborting")

        client = get_opensearch_client()
        if not client:
            return _ok_no_op(None, asset_id)

        # ──────────────────────────────────────────────────────────────────
        # BATCH
        if isinstance(payload.get("data"), list):
            logger.info(f"Processing batch of {len(payload['data'])} embeddings")
            results: List[Dict[str, Any]] = []

            # Separate clip/audio embeddings from potential master-video updates
            video_master_embeds: List[Tuple[int, Dict[str, Any]]] = []

            for i, emb in enumerate(payload["data"]):
                if not isinstance(emb, dict):
                    continue

                tmp = {"data": emb, **{k: v for k, v in payload.items() if k != "data"}}
                scope            = emb.get("embedding_scope") or extract_scope(tmp)
                embedding_option = emb.get("embedding_option") or extract_embedding_option(tmp)

                if scope == "video" and not IS_AUDIO_CONTENT:
                    # master-doc update
                    video_master_embeds.append((i, emb))
                else:
                    # clip/audio doc
                    try:
                        res = process_single_embedding(payload, emb, client, asset_id)
                        results.append(res)
                    except Exception as exc:
                        logger.error(f"Clip embedding {i+1} failed", extra={"error": str(exc)})

            # Master-doc updates (video scope)
            for i, emb in video_master_embeds:
                try:
                    embedding_vector = emb.get("float")
                    if not embedding_vector:
                        logger.error(f"No vector in video embedding {i+1}")
                        continue

                    tmp_payload = {"data": emb, **{k: v for k, v in payload.items() if k != "data"}}
                    embedding_option = emb.get("embedding_option") or extract_embedding_option(
                        tmp_payload
                    )
                    vec_field = _vector_field("video", embedding_option)

                    # Find master doc
                    search_q = {
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
                    start = time.time()
                    resp  = client.search(index=INDEX_NAME, body=search_q, size=1)
                    check_opensearch_response(resp, "search")
                    while resp["hits"]["total"]["value"] == 0 and time.time() - start < 120:
                        client.indices.refresh(index=INDEX_NAME)
                        time.sleep(5)
                        resp = client.search(index=INDEX_NAME, body=search_q, size=1)
                        check_opensearch_response(resp, "search")

                    if resp["hits"]["total"]["value"] == 0:
                        raise RuntimeError(f"No master doc for asset {asset_id}")

                    doc_id = resp["hits"]["hits"][0]["_id"]
                    meta   = client.get(index=INDEX_NAME, id=doc_id)
                    check_opensearch_response(meta, "get")
                    seq_no = meta["_seq_no"]
                    p_term = meta["_primary_term"]

                    update = {
                        "doc": {
                            "type":            CONTENT_TYPE,
                            "embedding_scope": "video",
                            "timestamp":       datetime.utcnow().isoformat(),
                            vec_field:         embedding_vector,
                        }
                    }
                    if embedding_option is not None:
                        update["doc"]["embedding_option"] = embedding_option

                    for _ in range(50):
                        try:
                            ures = client.update(
                                index=INDEX_NAME,
                                id=doc_id,
                                body=update,
                                if_seq_no=seq_no,
                                if_primary_term=p_term,
                            )
                            check_opensearch_response(ures, "update")
                            break
                        except exceptions.ConflictError:
                            meta   = client.get(index=INDEX_NAME, id=doc_id)
                            seq_no = meta["_seq_no"]
                            p_term = meta["_primary_term"]
                            time.sleep(1)
                    else:
                        raise RuntimeError("Failed to update master after 50 retries")

                    results.append({"document_id": doc_id, "type": "master_update", "field": vec_field})
                except Exception as exc:
                    logger.error(f"Video embedding {i+1} failed", extra={"error": str(exc)})

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message":        f"Batch processed: {len(results)} embeddings stored",
                        "index":          INDEX_NAME,
                        "asset_id":       asset_id,
                        "processed":      len(results),
                        "total_received": len(payload["data"]),
                    }
                ),
            }

        # ──────────────────────────────────────────────────────────────────
        # SINGLE
        embedding_vector = extract_embedding_vector(payload)
        if not embedding_vector and payload.get("assets"):
            for asset in payload["assets"]:
                meta = asset.get("Metadata", {}).get("CustomMetadata", {})
                if isinstance(meta.get("embedding"), list):
                    embedding_vector = meta["embedding"]
                    break
        if not embedding_vector:
            return _bad_request("No embedding vector found in event or assets")

        scope            = extract_scope(payload)
        embedding_option = extract_embedding_option(payload)
        vec_field        = _vector_field(scope or "", embedding_option)

        # CLIP/AUDIO → NEW DOC
        if scope in {"clip", "audio"}:
            start_sec, end_sec = _get_segment_bounds(payload)
            fps = 30
            if CONTENT_TYPE == "video":
                master_src = _get_master_doc(client, asset_id)
                fps = _extract_fps(master_src, asset_id)

            doc = {
                "type":            CONTENT_TYPE,
                "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
                "timestamp":       datetime.utcnow().isoformat(),
                "DigitalSourceAsset": {"ID": asset_id},
                "start_timecode":  seconds_to_smpte(start_sec, fps),
                "end_timecode":    seconds_to_smpte(end_sec,   fps),
                vec_field:         embedding_vector,
            }
            if embedding_option is not None:
                doc["embedding_option"] = embedding_option

            res = client.index(index=INDEX_NAME, body=doc)
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

        # AUDIO masters are never updated
        if IS_AUDIO_CONTENT:
            logger.info("Skipping master-doc update for audio content", extra={"asset_id": asset_id})
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Embedding stored (audio clip only – master unchanged)", "asset_id": asset_id}),
            }

        # VIDEO master-doc update
        search_q = {
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
        start = time.time()
        resp  = client.search(index=INDEX_NAME, body=search_q, size=1)
        check_opensearch_response(resp, "search")
        while resp["hits"]["total"]["value"] == 0 and time.time() - start < 120:
            client.indices.refresh(index=INDEX_NAME)
            time.sleep(5)
            resp = client.search(index=INDEX_NAME, body=search_q, size=1)
            check_opensearch_response(resp, "search")
        if resp["hits"]["total"]["value"] == 0:
            raise RuntimeError(f"No master doc with DigitalSourceAsset.ID={asset_id}")

        doc_id = resp["hits"]["hits"][0]["_id"]
        meta   = client.get(index=INDEX_NAME, id=doc_id)
        check_opensearch_response(meta, "get")
        seq_no = meta["_seq_no"]
        p_term = meta["_primary_term"]

        update = {
            "doc": {
                "type":            CONTENT_TYPE,
                "embedding_scope": scope,
                "timestamp":       datetime.utcnow().isoformat(),
                vec_field:         embedding_vector,
            }
        }
        if embedding_option is not None:
            update["doc"]["embedding_option"] = embedding_option

        for _ in range(50):
            try:
                ures = client.update(
                    index=INDEX_NAME,
                    id=doc_id,
                    body=update,
                    if_seq_no=seq_no,
                    if_primary_term=p_term,
                )
                check_opensearch_response(ures, "update")
                break
            except exceptions.ConflictError:
                meta   = client.get(index=INDEX_NAME, id=doc_id)
                seq_no = meta["_seq_no"]
                p_term = meta["_primary_term"]
                time.sleep(1)
        else:
            raise RuntimeError("Failed to update master doc after 50 retries")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message":     "Embedding stored successfully",
                    "index":       INDEX_NAME,
                    "document_id": doc_id,
                    "asset_id":    asset_id,
                }
            ),
        }

    except Exception:
        logger.exception("Error storing embedding")
        raise
