import json
import os
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Union

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
_auth        = AWSV4SignerAuth(_credentials, AWS_REGION, "es")


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


# ── Helper extraction functions ────────────────────────────────────────────────
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


# ── Small helpers ────────────────────────────────────────────────────────────
def _bad_request(msg: str):
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _ok_no_op(vector_len: int, asset_id: Optional[str]):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message":       "Embedding processed (OpenSearch not available)",
                "asset_id":      asset_id,
                "vector_length": vector_len,
            }
        ),
    }


def check_opensearch_response(response: Dict[str, Any], operation: str) -> None:
    status = response.get("status", 200)
    if status not in (200, 201):
        error_msg = response.get("error", {}).get("reason", "Unknown error")
        logger.error(f"OpenSearch {operation} failed", extra={
            "status":   status,
            "error":    error_msg,
            "response": response
        })
        raise RuntimeError(f"OpenSearch {operation} failed: {error_msg} (status: {status})")


# ── Lambda entrypoint ────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    try:
        # Unwrap any Powertools wrapper
        logger.info("Received raw event", extra={"event": event})
        inner = event.get("event", event)
        raw_payload = inner.get("payload")
        if raw_payload is None:
            return _bad_request("Event missing 'payload'")

        # Detect batch list in either form
        batch: Optional[List[Dict[str, Any]]] = None
        if isinstance(raw_payload, list):
            batch = raw_payload
        elif isinstance(raw_payload, dict) and isinstance(raw_payload.get("data"), list):
            batch = raw_payload["data"]

        # ────────────────────────────────────────────────────────────────────
        # 1️⃣ Batch payload handling
        # ────────────────────────────────────────────────────────────────────
        if batch is not None:
            if not batch:
                return _bad_request("Payload list is empty")

            shared_asset_id = batch[0].get("asset_id")
            if not shared_asset_id:
                return _bad_request("Unable to determine asset_id in batch")

            logger.info("Processing batch embeddings", extra={
                "count":    len(batch),
                "asset_id": shared_asset_id,
            })

            # Split into clip/audio vs. other scopes
            to_index = []
            to_update = []
            for rec in batch:
                opt   = rec.get("embedding_option")
                scope = rec.get("embedding_scope")

                # skip audio+video
                if opt == "audio" and scope == "video":
                    logger.info("Skipping record (audio+video)", extra={"record": rec})
                    continue

                if scope in {"clip", "audio"}:
                    to_index.append(rec)
                else:
                    to_update.append(rec)

            client = get_opensearch_client()
            if not client:
                total_len = sum(len(r.get("float", [])) for r in batch)
                return _ok_no_op(total_len, shared_asset_id)

            # Index each clip/audio record
            for rec in to_index:
                vec = rec["float"]
                if rec["embedding_scope"] == "clip":
                    start, end = rec.get("start_offset_sec", 0), rec.get("end_offset_sec", 0)
                else:
                    start, end = rec.get("start_time", 0), rec.get("end_time", 0)

                doc = {
                    "type":               CONTENT_TYPE,
                    "embedding":          vec,
                    "embedding_scope":    rec["embedding_scope"],
                    "embedding_option":   rec.get("embedding_option"),
                    "DigitalSourceAsset": {"ID": shared_asset_id},
                    "start_timecode":     seconds_to_smpte(start),
                    "end_timecode":       seconds_to_smpte(end),
                    "timestamp":          datetime.utcnow().isoformat(),
                }
                logger.info("Indexing clip/audio doc", extra={"asset_id": shared_asset_id})
                res = client.index(index=INDEX_NAME, body=doc)
                check_opensearch_response(res, "index")

            # Update parent for other-scope records
            if to_update:
                search_q = {
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"DigitalSourceAsset.ID": shared_asset_id}},
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
                logger.info("Searching parent doc for batch update", extra={"asset_id": shared_asset_id})
                start = time.time()
                sr = client.search(index=INDEX_NAME, body=search_q, size=1)
                check_opensearch_response(sr, "search")
                while sr["hits"]["total"]["value"] == 0 and time.time() - start < 120:
                    client.indices.refresh(index=INDEX_NAME)
                    time.sleep(5)
                    sr = client.search(index=INDEX_NAME, body=search_q, size=1)
                    check_opensearch_response(sr, "search")

                if sr["hits"]["total"]["value"] == 0:
                    return _bad_request(f"No parent document for asset_id={shared_asset_id}")

                doc_id = sr["hits"]["hits"][0]["_id"]
                meta   = client.get(index=INDEX_NAME, id=doc_id)
                check_opensearch_response(meta, "get")
                seq_no = meta["_seq_no"]
                pt     = meta["_primary_term"]

                for rec in to_update:
                    vec = rec["float"]
                    doc = {
                        "type":               CONTENT_TYPE,
                        "embedding":          vec,
                        "embedding_scope":    rec.get("embedding_scope"),
                        "embedding_option":   rec.get("embedding_option"),
                        "DigitalSourceAsset": {"ID": shared_asset_id},
                        "timestamp":          datetime.utcnow().isoformat(),
                    }
                    logger.info("Updating parent doc from batch", extra={"doc_id": doc_id})
                    for _ in range(50):
                        try:
                            upd = client.update(
                                index=INDEX_NAME,
                                id=doc_id,
                                body={"doc": doc},
                                if_seq_no=seq_no,
                                if_primary_term=pt,
                            )
                            check_opensearch_response(upd, "update")
                            seq_no, pt = upd["_seq_no"], upd["_primary_term"]
                            break
                        except exceptions.ConflictError:
                            meta   = client.get(index=INDEX_NAME, id=doc_id)
                            seq_no = meta["_seq_no"]
                            pt     = meta["_primary_term"]
                            time.sleep(0.5)

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "message":     f"Indexed {len(to_index)} docs, updated {len(to_update)} docs",
                        "asset_id":    shared_asset_id,
                        "document_id": doc_id,
                    }),
                }

            # only clip/audio were present
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message":  f"Indexed {len(to_index)} clip/audio docs",
                    "asset_id": shared_asset_id,
                }),
            }

        # ────────────────────────────────────────────────────────────────────
        # 2️⃣ Single-object payload – original logic follows unchanged
        # ────────────────────────────────────────────────────────────────────
        payload_dict: Dict[str, Any] = raw_payload or {}
        if not payload_dict:
            return _bad_request("Event missing 'payload'")

        logger.info("Processing payload", extra={
            "payload_structure": {
                "has_data": "data" in payload_dict,
                "has_assets": "assets" in payload_dict,
                "data_type": type(payload_dict.get("data")).__name__ if payload_dict.get("data") else None,
                "assets_length": len(payload_dict.get("assets", [])),
            }
        })

        if isinstance(payload_dict.get("data"), dict):
            response_data = payload_dict["data"]
            if response_data.get("statusCode") == 400:
                err_body = json.loads(response_data.get("body", "{}"))
                err_msg  = err_body.get("error", "Unknown 400 error")
                logger.error(f"Received 400 in payload.data: {err_msg}")
                logger.info("Continuing despite error in payload.data")

        asset_id = extract_asset_id(payload_dict) or next(
            (
                a.get("DigitalSourceAsset", {}).get("ID")
                for a in payload_dict.get("assets", [])
                if a.get("DigitalSourceAsset", {}).get("ID")
            ),
            None,
        )
        if not asset_id:
            return _bad_request("Unable to determine asset_id – aborting")

        embedding_vector = extract_embedding_vector(payload_dict)
        if not embedding_vector and payload_dict.get("assets"):
            logger.info("Trying asset metadata for vector")
            for asset in payload_dict["assets"]:
                md = asset.get("Metadata", {}).get("CustomMetadata", {})
                if md.get("embedding"):
                    embedding_vector = md["embedding"]
                    logger.info("Found embedding in asset metadata")
                    break

        if not embedding_vector:
            err = "No embedding vector found in event or assets data"
            logger.error(err, extra={"payload_structure": payload_dict})
            return _bad_request(err)

        scope            = extract_scope(payload_dict)
        embedding_option = extract_embedding_option(payload_dict)
        logger.info(f"Scope: {scope}, Embedding option: {embedding_option}")

        if embedding_option == "audio" and scope == "video":
            logger.info("Skipping: audio scope=video", extra={
                "embedding_option": embedding_option,
                "embedding_scope": scope,
                "asset_id": asset_id
            })
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Skipped processing: audio+video",
                    "asset_id": asset_id,
                })
            }

        client = get_opensearch_client()
        if not client:
            return _ok_no_op(len(embedding_vector), asset_id)

        document: Dict[str, Any] = {
            "type":            CONTENT_TYPE,
            "embedding":       embedding_vector,
            "embedding_scope": scope,
            "timestamp":       datetime.utcnow().isoformat(),
        }

        if scope in {"clip", "audio"}:
            itm = _item(payload_dict) or {} if scope == "clip" else _map_item(payload_dict) or _item(payload_dict) or {}
            start_sec = itm.get("start_offset_sec", 0) if scope == "clip" else itm.get("start_time", 0)
            end_sec   = itm.get("end_offset_sec",   0) if scope == "clip" else itm.get("end_time",   0)

            document |= {
                "DigitalSourceAsset": {"ID": asset_id},
                "start_timecode":     seconds_to_smpte(start_sec),
                "end_timecode":       seconds_to_smpte(end_sec),
            }
            if embedding_option is not None:
                document["embedding_option"] = embedding_option

            logger.info("Indexing new clip/audio doc", extra={"overview": {"vector_len": len(embedding_vector)}})
            idx_res = client.index(index=INDEX_NAME, body=document)
            check_opensearch_response(idx_res, "index")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message":     "Embedding stored successfully",
                    "index":       INDEX_NAME,
                    "document_id": idx_res.get("_id", "unknown"),
                    "asset_id":    asset_id,
                })
            }

        search_query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"DigitalSourceAsset.ID": asset_id}},
                        {"exists": {"field": "InventoryID"}},
                        {
                            "nested": {
                                "path": "DerivedRepresentations",
                                "query": {"exists": {"field": "DerivedRepresentations.ID"}}
                            }
                        }
                    ]
                }
            }
        }
        logger.info("Searching for existing document", extra={"asset_id": asset_id})
        start_time      = time.time()
        search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
        check_opensearch_response(search_response, "search")
        while (
            search_response["hits"]["total"]["value"] == 0
            and time.time() - start_time < 120
        ):
            client.indices.refresh(index=INDEX_NAME)
            time.sleep(5)
            search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
            check_opensearch_response(search_response, "search")

        if search_response["hits"]["total"]["value"] == 0:
            msg = f"No document found with DigitalSourceAsset.ID={asset_id}"
            logger.error(msg)
            raise RuntimeError(msg)

        existing_id = search_response["hits"]["hits"][0]["_id"]
        meta        = client.get(index=INDEX_NAME, id=existing_id)
        check_opensearch_response(meta, "get")
        seq_no, p_term = meta["_seq_no"], meta["_primary_term"]
        document["DigitalSourceAsset"] = {"ID": asset_id}

        logger.info("Updating document", extra={"doc_id": existing_id})
        for attempt in range(50):
            try:
                upd = client.update(
                    index=INDEX_NAME,
                    id=existing_id,
                    body={"doc": document},
                    if_seq_no=seq_no,
                    if_primary_term=p_term,
                )
                check_opensearch_response(upd, "update")
                break
            except exceptions.ConflictError:
                meta   = client.get(index=INDEX_NAME, id=existing_id)
                seq_no = meta["_seq_no"]
                p_term = meta["_primary_term"]
                time.sleep(1)
        else:
            err = "Failed to update document after 50 retries"
            logger.error(err)
            return _bad_request(err)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message":     "Embedding stored successfully",
                "index":       INDEX_NAME,
                "document_id": existing_id,
                "asset_id":    asset_id,
            }),
        }

    except Exception as exc:
        logger.exception("Error storing embedding")
        raise RuntimeError("Error storing embedding") from exc
