"""
Store embedding vectors in S3 Vector Store using custom boto3 SDK.

This Lambda function provides operations to store, retrieve, and search vector embeddings
using the new S3 Vector Store service with the custom unreleased boto3 SDK.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware
from lambda_utils import _truncate_floats
from nodes_utils import seconds_to_smpte

# ─────────────────────────────────────────────────────────────────────────────
# Powertools
logger = Logger()
tracer = Tracer(disabled=False)

# Environment
VECTOR_BUCKET_NAME = os.getenv("VECTOR_BUCKET_NAME", "media-vectors")
INDEX_NAME = os.getenv("INDEX_NAME", "media-vectors")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default-event-bus")

# Content type will be determined dynamically from payload data


def detect_content_type(
    payload: Dict[str, Any], embedding_data: Dict[str, Any] = None
) -> str:
    """Dynamically detect content type from payload data."""
    # Check for explicit content type in embedding data
    if embedding_data and embedding_data.get("content_type"):
        return embedding_data.get("content_type").lower()

    # Check for explicit content type in payload
    if payload.get("content_type"):
        return payload.get("content_type").lower()

    # Check for image-specific indicators (embedding scope = "image")
    data = payload.get("data", {})
    if isinstance(data, dict):
        if data.get("embedding_scope") == "image":
            return "image"
        if data.get("content_type"):
            return data.get("content_type").lower()

    # Check for image scope in other locations
    if payload.get("embedding_scope") == "image":
        return "image"

    # Check for audio-specific indicators (timing data from audio splitter)
    if (
        payload.get("map", {}).get("item", {}).get("start_time") is not None
        and payload.get("map", {}).get("item", {}).get("end_time") is not None
    ):
        return "audio"

    # Check for audio indicators in data structure
    if isinstance(data, dict):
        if data.get("start_time") is not None and data.get("end_time") is not None:
            return "audio"

    # Default to video if no specific indicators found
    return "video"


# ─────────────────────────────────────────────────────────────────────────────
# Extraction helpers
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


def extract_scope(container: Dict[str, Any]) -> Optional[str]:
    """Extract embedding scope with validation."""
    if not isinstance(container, dict):
        raise ValueError("Container must be a dictionary")

    def validate_scope(scope, source: str) -> str:
        if not isinstance(scope, str):
            raise ValueError(
                f"Embedding scope from {source} must be a string, got {type(scope)}"
            )
        scope = scope.strip()
        if not scope:
            raise ValueError(f"Embedding scope from {source} cannot be empty")
        valid_scopes = {"clip", "video", "audio", "image"}
        if scope not in valid_scopes:
            raise ValueError(
                f"Invalid embedding scope '{scope}' from {source}. Must be one of: {valid_scopes}"
            )
        return scope

    itm = _item(container)
    if itm and itm.get("embedding_scope"):
        return validate_scope(itm["embedding_scope"], "item.embedding_scope")

    data = container.get("data")
    if isinstance(data, dict) and data.get("embedding_scope"):
        return validate_scope(data["embedding_scope"], "data.embedding_scope")

    m_itm = _map_item(container)
    if m_itm and m_itm.get("embedding_scope"):
        return validate_scope(m_itm["embedding_scope"], "map.item.embedding_scope")

    if container.get("embedding_scope"):
        return validate_scope(container["embedding_scope"], "container.embedding_scope")

    for i, res in enumerate(container.get("externalTaskResults", [])):
        if not isinstance(res, dict):
            continue
        if res.get("embedding_scope"):
            return validate_scope(
                res["embedding_scope"], f"externalTaskResults[{i}].embedding_scope"
            )

    return None


def extract_embedding_option(container: Dict[str, Any]) -> Optional[str]:
    """Extract embedding option with validation."""
    if not isinstance(container, dict):
        raise ValueError("Container must be a dictionary")

    def validate_option(option, source: str) -> str:
        if not isinstance(option, str):
            raise ValueError(
                f"Embedding option from {source} must be a string, got {type(option)}"
            )
        option = option.strip()
        if not option:
            raise ValueError(f"Embedding option from {source} cannot be empty")
        return option

    itm = _item(container)
    if itm and itm.get("embedding_option"):
        return validate_option(itm["embedding_option"], "item.embedding_option")

    data = container.get("data")
    if isinstance(data, dict) and data.get("embedding_option"):
        return validate_option(data["embedding_option"], "data.embedding_option")

    m_itm = _map_item(container)
    if m_itm and m_itm.get("embedding_option"):
        return validate_option(m_itm["embedding_option"], "map.item.embedding_option")

    if container.get("embedding_option"):
        return validate_option(
            container["embedding_option"], "container.embedding_option"
        )

    for i, res in enumerate(container.get("externalTaskResults", [])):
        if not isinstance(res, dict):
            continue
        if res.get("embedding_option"):
            return validate_option(
                res["embedding_option"], f"externalTaskResults[{i}].embedding_option"
            )

    return None


def extract_inventory_id(container: Dict[str, Any]) -> Optional[str]:
    """Extract inventory ID with validation."""
    if not isinstance(container, dict):
        raise ValueError("Container must be a dictionary")

    if isinstance(container.get("data"), list) and container["data"]:
        first_item = container["data"][0]
        if isinstance(first_item, dict) and first_item.get("inventory_id"):
            inventory_id = first_item["inventory_id"]
            if not isinstance(inventory_id, str) or not inventory_id.strip():
                raise ValueError("Inventory ID must be a non-empty string")
            return inventory_id.strip()

    itm = _item(container)
    if itm and itm.get("inventory_id"):
        inventory_id = itm["inventory_id"]
        if not isinstance(inventory_id, str) or not inventory_id.strip():
            raise ValueError("Inventory ID must be a non-empty string")
        return inventory_id.strip()

    m_itm = _map_item(container)
    if m_itm and m_itm.get("inventory_id"):
        inventory_id = m_itm["inventory_id"]
        if not isinstance(inventory_id, str) or not inventory_id.strip():
            raise ValueError("Inventory ID must be a non-empty string")
        return inventory_id.strip()

    for asset in container.get("assets", []):
        if not isinstance(asset, dict):
            continue
        inv = asset.get("InventoryID")
        if inv:
            if not isinstance(inv, str) or not inv.strip():
                raise ValueError("Inventory ID must be a non-empty string")
            return inv.strip()

    inventory_id = container.get("InventoryID")
    if inventory_id:
        if not isinstance(inventory_id, str) or not inventory_id.strip():
            raise ValueError("Inventory ID must be a non-empty string")
        return inventory_id.strip()

    return None


def extract_asset_id(container: Dict[str, Any]) -> Optional[str]:
    # alias for compatibility
    return extract_inventory_id(container)


def extract_embedding_vector(container: Dict[str, Any]) -> Optional[List[float]]:
    """Extract embedding vector with validation."""
    if not isinstance(container, dict):
        raise ValueError("Container must be a dictionary")

    def validate_vector(vector, source: str) -> List[float]:
        if not isinstance(vector, list):
            raise ValueError(f"Embedding vector from {source} must be a list")
        if not vector:
            raise ValueError(f"Embedding vector from {source} cannot be empty")
        for i, val in enumerate(vector):
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"Embedding vector element {i} from {source} must be a number, got {type(val)}"
                )
        return [float(v) for v in vector]

    itm = _item(container)
    if itm and isinstance(itm.get("float"), list) and itm["float"]:
        return validate_vector(itm["float"], "item.float")

    if (
        isinstance(container.get("data"), dict)
        and isinstance(container["data"].get("float"), list)
        and container["data"]["float"]
    ):
        return validate_vector(container["data"]["float"], "data.float")

    if isinstance(container.get("float"), list) and container["float"]:
        return validate_vector(container["float"], "container.float")

    for i, res in enumerate(container.get("externalTaskResults", [])):
        if not isinstance(res, dict):
            continue
        if isinstance(res.get("float"), list) and res["float"]:
            return validate_vector(res["float"], f"externalTaskResults[{i}].float")

    return None


def extract_framerate(container: Dict[str, Any]) -> Optional[float]:
    """Extract framerate with validation."""
    if not isinstance(container, dict):
        raise ValueError("Container must be a dictionary")

    def validate_framerate(framerate, source: str) -> float:
        if not isinstance(framerate, (int, float)):
            raise ValueError(
                f"Framerate from {source} must be a number, got {type(framerate)}"
            )
        framerate = float(framerate)
        if framerate <= 0:
            raise ValueError(
                f"Framerate from {source} must be positive, got {framerate}"
            )
        if framerate > 1000:  # Reasonable upper bound
            raise ValueError(
                f"Framerate from {source} seems unreasonably high: {framerate}"
            )
        return framerate

    # Check if data is an array (batch processing) - get from first item
    if isinstance(container.get("data"), list) and container["data"]:
        first_item = container["data"][0]
        if isinstance(first_item, dict) and first_item.get("framerate"):
            return validate_framerate(first_item["framerate"], "data[0].framerate")

    itm = _item(container)
    if itm and itm.get("framerate"):
        return validate_framerate(itm["framerate"], "item.framerate")

    data = container.get("data")
    if isinstance(data, dict) and data.get("framerate"):
        return validate_framerate(data["framerate"], "data.framerate")

    m_itm = _map_item(container)
    if m_itm and m_itm.get("framerate"):
        return validate_framerate(m_itm["framerate"], "map.item.framerate")

    if container.get("framerate"):
        return validate_framerate(container["framerate"], "container.framerate")

    return None


def _get_segment_bounds(payload: Dict[str, Any]) -> Tuple[int, int]:
    """Extract segment bounds with validation."""
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")

    candidates: List[Dict[str, Any]] = []
    if isinstance(payload.get("data"), dict):
        candidates.append(payload["data"])
    if isinstance(payload.get("item"), dict):
        candidates.append(payload["item"])
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
    candidates.append(payload)

    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            logger.info(f"Candidate {i} is not a dict: {type(c)}")
            continue
        start = c.get("start_offset_sec")
        if start is None:
            start = c.get("start_time")
        end = c.get("end_offset_sec")
        if end is None:
            end = c.get("end_time")
        logger.info(
            f"Candidate {i}: start={start}, end={end}, keys={list(c.keys()) if c else 'None'}"
        )
        if start is not None and end is not None:
            try:
                start_int = int(float(start))
                end_int = int(float(end))
                if start_int < 0:
                    raise ValueError(f"Start offset cannot be negative: {start_int}")
                if end_int < 0:
                    raise ValueError(f"End offset cannot be negative: {end_int}")
                if start_int > end_int:
                    raise ValueError(
                        f"Start offset ({start_int}) cannot be greater than end offset ({end_int})"
                    )
                logger.info(f"Found segment bounds: {start_int}-{end_int}")
                return start_int, end_int
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid segment bounds - start: {start}, end: {end}. Error: {e}"
                )

    logger.warning(
        f"Segment bounds not found in {len(candidates)} candidates – defaulting to 0-0"
    )
    return 0, 0


# ─────────────────────────────────────────────────────────────────────────────
# S3 Vector Store client
def get_s3_vector_client():
    try:
        session = boto3.Session()
        return session.client("s3vectors", region_name=AWS_REGION)
    except Exception as e:
        logger.error(f"Failed to initialize S3 Vector client: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Early-exit helpers
def _bad_request(msg: str):
    logger.warning(msg)
    return {"statusCode": 400, "body": json.dumps({"error": msg})}


def _ok_no_op(vector_len: int, inventory_id: Optional[str]):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Embedding processed (S3 Vector Store not available)",
                "inventory_id": inventory_id,
                "vector_length": vector_len,
            }
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
def ensure_vector_bucket_exists(client, bucket_name: str) -> None:
    """Ensure vector bucket exists or raise exception."""
    if not bucket_name:
        raise RuntimeError(
            "Vector bucket name cannot be empty - check VECTOR_BUCKET_NAME environment variable"
        )

    try:
        client.get_vector_bucket(vectorBucketName=bucket_name)
        logger.info(f"Vector bucket {bucket_name} already exists")
    except client.exceptions.NotFoundException:
        try:
            client.create_vector_bucket(
                vectorBucketName=bucket_name,
                encryptionConfiguration={"sseType": "AES256"},
            )
            logger.info(f"Created vector bucket {bucket_name}")
        except Exception as e:
            logger.error(f"Failed to create vector bucket {bucket_name}: {e}")
            raise RuntimeError(f"Cannot create vector bucket {bucket_name}: {e}") from e
    except Exception as e:
        logger.error(f"Error checking vector bucket {bucket_name}: {e}")
        raise RuntimeError(f"Cannot access vector bucket {bucket_name}: {e}") from e


def ensure_index_exists(
    client, bucket_name: str, index_name: str, vector_dimension: int
) -> None:
    """Ensure vector index exists or raise exception."""
    if not bucket_name:
        raise RuntimeError(
            "Vector bucket name cannot be empty - check VECTOR_BUCKET_NAME environment variable"
        )
    if not index_name:
        raise RuntimeError(
            "Vector index name cannot be empty - check INDEX_NAME environment variable"
        )
    if vector_dimension <= 0:
        raise ValueError(f"Invalid vector dimension: {vector_dimension}")

    try:
        client.get_index(vectorBucketName=bucket_name, indexName=index_name)
        logger.info(f"Index {index_name} already exists in bucket {bucket_name}")
    except client.exceptions.NotFoundException:
        try:
            client.create_index(
                vectorBucketName=bucket_name,
                indexName=index_name,
                dimension=vector_dimension,
                dataType="float32",
                distanceMetric="cosine",
            )
            logger.info(f"Created index {index_name} (dim={vector_dimension})")
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            raise RuntimeError(f"Cannot create index {index_name}: {e}") from e
    except Exception as e:
        logger.error(f"Error checking index {index_name}: {e}")
        raise RuntimeError(f"Cannot access index {index_name}: {e}") from e


def store_vectors(
    client, bucket_name: str, index_name: str, vectors_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Store vectors in S3 Vector Store with strict validation."""
    if not bucket_name:
        raise RuntimeError(
            "Vector bucket name cannot be empty - check VECTOR_BUCKET_NAME environment variable"
        )
    if not index_name:
        raise RuntimeError(
            "Vector index name cannot be empty - check INDEX_NAME environment variable"
        )
    if not vectors_data:
        raise ValueError("No vectors provided for storage")

    try:
        vectors = []
        for i, vd in enumerate(vectors_data):
            if not isinstance(vd, dict):
                raise ValueError(f"Vector data at index {i} must be a dictionary")
            if "vector" not in vd:
                raise ValueError(f"Vector data at index {i} missing 'vector' field")
            if "metadata" not in vd:
                raise ValueError(f"Vector data at index {i} missing 'metadata' field")

            vector = vd["vector"]
            meta = vd["metadata"]

            if not isinstance(vector, list) or not vector:
                raise ValueError(f"Vector at index {i} must be a non-empty list")
            if not isinstance(meta, dict):
                raise ValueError(f"Metadata at index {i} must be a dictionary")
            if not meta.get("inventory_id"):
                raise ValueError(
                    f"Metadata at index {i} missing required 'inventory_id'"
                )

            embedding_option = meta.get("embedding_option", "default")

            # Start with inventory_id, only add embedding_option if it's not "default"
            if embedding_option == "default":
                key = meta["inventory_id"]
            else:
                key = f"{meta['inventory_id']}_{embedding_option}"

            scope = meta.get("embedding_scope")
            content_type = meta.get("content_type", "video")

            # Handle different content types and scopes
            if content_type == "audio":
                # Audio content: always include time segments with audio_clip prefix
                start_sec = meta.get("start_offset_sec")
                end_sec = meta.get("end_offset_sec")
                if start_sec is None or end_sec is None:
                    raise ValueError(
                        f"Audio embedding at index {i} missing start/end offset seconds"
                    )
                key = f"{key}_audio_clip_{start_sec}_{end_sec}"
            elif content_type == "video" and scope == "clip":
                # Video clip content: include time segments with video_clip prefix
                start_sec = meta.get("start_offset_sec")
                end_sec = meta.get("end_offset_sec")
                if start_sec is None or end_sec is None:
                    raise ValueError(
                        f"Video clip embedding at index {i} missing start/end offset seconds"
                    )
                key = f"{key}_video_clip_{start_sec}_{end_sec}"
            elif content_type == "image":
                # Image content: just add image suffix, no time segments
                key = f"{key}_image"
            # For video master/other scopes, keep the key as is (inventory_id or inventory_id_embedding_option)

            vectors.append(
                {
                    "key": key,
                    "data": {"float32": vector},
                    "metadata": meta,
                }
            )

        batch_size = 500
        stored_keys = []
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            try:
                client.put_vectors(
                    vectorBucketName=bucket_name,
                    indexName=index_name,
                    vectors=batch,
                )
                stored_keys.extend(v["key"] for v in batch)
                logger.info(f"Stored batch of {len(batch)} vectors")

            except Exception as e:
                logger.error(f"Failed to store batch {i//batch_size + 1}: {e}")
                raise RuntimeError(
                    f"Failed to store vector batch {i//batch_size + 1}: {e}"
                ) from e

        return {"stored_keys": stored_keys}
    except Exception as e:
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        logger.error(f"Unexpected error storing vectors: {e}")
        raise RuntimeError(f"Unexpected error storing vectors: {e}") from e


# ─────────────────────────────────────────────────────────────────────────────
def process_single_embedding(
    payload: Dict[str, Any],
    embedding_data: Dict[str, Any],
    client,
    inventory_id: str,
) -> Dict[str, Any]:
    """Process single embedding with strict validation."""
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")
    if not isinstance(embedding_data, dict):
        raise ValueError("Embedding data must be a dictionary")
    if not inventory_id:
        raise ValueError("Inventory ID cannot be empty")

    embedding_vector = embedding_data.get("float")
    if not embedding_vector:
        raise ValueError("No embedding vector found in embedding data")
    if not isinstance(embedding_vector, list) or not embedding_vector:
        raise ValueError("Embedding vector must be a non-empty list")

    temp = {"data": embedding_data, **{k: v for k, v in payload.items() if k != "data"}}
    scope = embedding_data.get("embedding_scope") or extract_scope(temp)
    opt = embedding_data.get("embedding_option") or extract_embedding_option(temp)

    if not scope:
        raise ValueError("Cannot determine embedding scope from payload")

    start_sec, end_sec = _get_segment_bounds(temp)

    # Dynamically detect content type
    content_type = detect_content_type(payload, embedding_data)
    is_audio_content = content_type == "audio"

    # Extract framerate from input data (only for video content)
    if content_type == "video":
        framerate = embedding_data.get("framerate") or extract_framerate(temp)
        fps = int(round(framerate)) if framerate else 30
    else:
        fps = 30

    start_tc = seconds_to_smpte(start_sec, fps)
    end_tc = seconds_to_smpte(end_sec, fps)

    metadata = {
        "inventory_id": inventory_id,
        "content_type": content_type,
        "embedding_scope": "clip" if is_audio_content else scope,
        "timestamp": datetime.utcnow().isoformat(),
        "start_offset_sec": start_sec,
        "end_offset_sec": end_sec,
        "start_timecode": start_tc,
        "end_timecode": end_tc,
    }
    if opt is not None:
        metadata["embedding_option"] = opt

    vectors_data = [{"vector": embedding_vector, "metadata": metadata}]

    # These now raise exceptions instead of returning booleans
    ensure_vector_bucket_exists(client, VECTOR_BUCKET_NAME)
    dim = len(embedding_vector)
    ensure_index_exists(client, VECTOR_BUCKET_NAME, INDEX_NAME, dim)
    store_result = store_vectors(client, VECTOR_BUCKET_NAME, INDEX_NAME, vectors_data)

    return {
        "document_id": f"{inventory_id}_{int(datetime.utcnow().timestamp())}",
        "start_sec": start_sec,
        "end_sec": end_sec,
        **store_result,
    }


# ─────────────────────────────────────────────────────────────────────────────
def process_store_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process store action with strict validation."""
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")

    client = get_s3_vector_client()
    bucket = payload.get("vector_bucket_name", VECTOR_BUCKET_NAME)
    index = payload.get("index_name", INDEX_NAME)

    if not bucket:
        raise ValueError("Vector bucket name cannot be empty")
    if not index:
        raise ValueError("Index name cannot be empty")

    inventory_id = extract_inventory_id(payload)
    if not inventory_id:
        raise ValueError("Unable to determine inventory_id from payload")

    # batch processing
    if isinstance(payload.get("data"), list):
        data_list = payload["data"]
        if not data_list:
            raise ValueError("Data list cannot be empty")

        results = []
        video_scope = []
        for i, emb in enumerate(data_list):
            if not isinstance(emb, dict):
                raise ValueError(f"Embedding data at index {i} must be a dictionary")

            tmp = {"data": emb, **{k: v for k, v in payload.items() if k != "data"}}
            sc = emb.get("embedding_scope") or extract_scope(tmp)

            if not sc:
                raise ValueError(f"Cannot determine embedding scope for item {i}")

            # Dynamically detect content type for this embedding
            content_type = detect_content_type(payload, emb)
            is_audio_content = content_type == "audio"

            if sc == "video" and not is_audio_content:
                video_scope.append((i, emb))
            else:
                try:
                    res = process_single_embedding(payload, emb, client, inventory_id)
                    results.append(res)
                except Exception as e:
                    logger.error(f"Failed to process embedding {i}: {e}")
                    raise RuntimeError(f"Failed to process embedding {i}: {e}") from e

        # Check if this is primarily audio content processing
        first_embedding = data_list[0] if data_list else {}
        primary_content_type = detect_content_type(payload, first_embedding)
        if primary_content_type == "audio":
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Batch processed (audio only)",
                        "inventory_id": inventory_id,
                        "processed_count": len(results),
                        "total_count": len(payload["data"]),
                    }
                ),
            }

        # video-level embeddings → simple put with video scope
        for i, emb in video_scope:
            vector = emb.get("float")
            if not vector:
                raise ValueError(f"No vector in video embedding {i}")
            if not isinstance(vector, list) or not vector:
                raise ValueError(
                    f"Vector in video embedding {i} must be a non-empty list"
                )

            tmp = {"data": emb, **{k: v for k, v in payload.items() if k != "data"}}
            opt = emb.get("embedding_option") or extract_embedding_option(tmp)

            # Dynamically detect content type for this video embedding
            video_content_type = detect_content_type(payload, emb)

            # Extract framerate from input data (only for video content)
            if video_content_type == "video":
                framerate = emb.get("framerate") or extract_framerate(tmp)
                int(round(framerate)) if framerate else 30
            else:
                pass

            # video-level has no start/end
            metadata = {
                "inventory_id": inventory_id,
                "content_type": video_content_type,
                "embedding_scope": "video",
                "timestamp": datetime.utcnow().isoformat(),
            }
            if opt is not None:
                metadata["embedding_option"] = opt

            vectors_data = [{"vector": vector, "metadata": metadata}]

            # These now raise exceptions instead of returning booleans
            ensure_vector_bucket_exists(client, bucket)
            dim = len(vector)
            ensure_index_exists(client, bucket, index, dim)
            store_vectors(client, bucket, index, vectors_data)

            results.append(
                {
                    "document_id": f"{inventory_id}_video_{i}_{int(datetime.utcnow().timestamp())}",
                    "type": "video_scope",
                }
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Batch processed {len(results)} embeddings",
                    "inventory_id": inventory_id,
                    "processed_count": len(results),
                    "total_count": len(payload["data"]),
                }
            ),
        }

    # single embedding processing
    embedding_vector = extract_embedding_vector(payload)
    if not embedding_vector:
        raise ValueError("No embedding vector found in payload")
    if not isinstance(embedding_vector, list) or not embedding_vector:
        raise ValueError("Embedding vector must be a non-empty list")

    scope = extract_scope(payload)
    if not scope:
        raise ValueError("Cannot determine embedding scope from payload")

    opt = extract_embedding_option(payload)

    # Dynamically detect content type for single embedding
    single_content_type = detect_content_type(payload)
    is_audio_content = single_content_type == "audio"

    # clip, audio, or image
    if scope in {"clip", "audio", "image"} or is_audio_content:
        # Check for embedding data in either 'data' or 'item' field
        embedding_data = payload.get("data") or payload.get("item")
        if not embedding_data:
            raise ValueError(
                "Missing 'data' or 'item' field in payload for single embedding processing"
            )

        result = process_single_embedding(payload, embedding_data, client, inventory_id)
        return {"statusCode": 200, "body": json.dumps(result)}

    # master/video - extract framerate from input data (only for video content)
    master_content_type = detect_content_type(payload)
    if master_content_type == "video":
        framerate = extract_framerate(payload)
        int(round(framerate)) if framerate else 30
    else:
        pass

    metadata = {
        "inventory_id": inventory_id,
        "content_type": master_content_type,
        "embedding_scope": scope,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if opt is not None:
        metadata["embedding_option"] = opt

    vectors_data = [{"vector": embedding_vector, "metadata": metadata}]

    # These now raise exceptions instead of returning booleans
    ensure_vector_bucket_exists(client, VECTOR_BUCKET_NAME)
    dim = len(embedding_vector)
    ensure_index_exists(client, VECTOR_BUCKET_NAME, INDEX_NAME, dim)
    store_vectors(client, VECTOR_BUCKET_NAME, INDEX_NAME, vectors_data)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Embedding stored successfully",
                "inventory_id": inventory_id,
            }
        ),
    }


@lambda_middleware(event_bus_name=EVENT_BUS_NAME)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    """Main Lambda handler with strict error handling."""
    try:
        if not isinstance(event, dict):
            raise ValueError("Event must be a dictionary")

        truncated = _truncate_floats(event, max_items=10)
        logger.info("Received event", extra={"event": truncated})
        # Content type will be determined dynamically per request
        logger.info("S3 Vector Store Lambda - Content type determined dynamically")

        payload = event.get("payload")
        if not payload:
            raise ValueError("Event missing required 'payload' field")
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary")

        return process_store_action(payload)

    except ValueError as e:
        # Client errors - return 400
        logger.error(f"Validation error: {e}")
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        # All other errors - return 500 and re-raise to fail the Lambda
        logger.error(f"Lambda handler error: {e}")
        error_response = {"statusCode": 500, "body": json.dumps({"error": str(e)})}
        # Re-raise the exception to ensure Lambda fails hard
        raise RuntimeError(f"Lambda execution failed: {e}") from e
