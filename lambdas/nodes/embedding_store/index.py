"""
Store embedding vectors in OpenSearch.

* Clip/audio segments are indexed as new documents with SMPTE time-codes.
* Master video documents are updated in-place when a whole-file embedding arrives.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from distributed_map_utils import download_s3_external_payload, is_s3_reference
from lambda_middleware import lambda_middleware
from lambda_utils import _truncate_floats
from nodes_utils import seconds_to_smpte
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, exceptions

# S3 client for downloading external payloads
s3_client = boto3.client("s3")

# ─────────────────────────────────────────────────────────────────────────────
# Powertools
logger = Logger()
tracer = Tracer(disabled=False)

# Environment
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
INDEX_NAME = os.getenv("INDEX_NAME", "media")
ASSET_EMBEDDINGS_INDEX = os.getenv("ASSET_EMBEDDINGS_INDEX", "asset-embeddings")
CONTENT_TYPE = os.getenv("CONTENT_TYPE", "video").lower()  # "video" | "audio" | "image"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default-event-bus")

# Model metadata env vars (set per-pipeline from template parameters)
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
MODEL_VERSION = os.getenv("MODEL_VERSION", "")

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
        timeout=600,
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


def extract_inventory_id(container: Dict[str, Any]) -> Optional[str]:
    # Check if data is an array (batch processing) - get from first item
    if isinstance(container.get("data"), list) and container["data"]:
        first_item = container["data"][0]
        if isinstance(first_item, dict) and first_item.get("inventory_id"):
            return first_item["inventory_id"]

    itm = _item(container)
    if itm and itm.get("inventory_id"):
        return itm["inventory_id"]

    m_itm = _map_item(container)
    if m_itm and m_itm.get("inventory_id"):
        return m_itm["inventory_id"]

    for asset in container.get("assets", []):
        inventory_id = asset.get("InventoryID")
        if inventory_id:
            return inventory_id

    return container.get("InventoryID")


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
    """Extract embedding vector from container, supporting both direct vectors and S3 references.

    This function supports multiple input patterns:
    1. Direct embedding in payload (backward compatible)
    2. S3 reference in nested data structure (new pattern for distributed map)
    3. Already-resolved embedding in nested data.data structure (retry scenario)
    4. External task results
    """
    # Check for S3 reference in nested data structure (distributed map pattern)
    if isinstance(container.get("data"), dict):
        data = container["data"]

        # Check for nested data.data structure (Bedrock Results pattern)
        if isinstance(data.get("data"), dict):
            nested_data = data["data"]

            # First check if it's an S3 reference that needs to be downloaded
            if "s3_bucket" in nested_data and "s3_key" in nested_data:
                try:
                    embedding_data = download_s3_external_payload(
                        s3_client, nested_data, logger
                    )
                    if (
                        isinstance(embedding_data.get("float"), list)
                        and embedding_data["float"]
                    ):
                        logger.info(
                            "Successfully extracted embedding from S3 reference (nested data.data)"
                        )
                        return embedding_data["float"]
                except Exception as e:
                    logger.warning(
                        f"Failed to download embedding from S3 reference: {str(e)}"
                    )
            # Handle already-resolved embedding data in nested data.data (retry scenario)
            # This happens when Step Functions retries after an error - the S3 reference
            # was already resolved to actual embedding data in a previous invocation
            elif isinstance(nested_data.get("float"), list) and nested_data["float"]:
                logger.info(
                    "Successfully extracted embedding from nested data.data.float (already resolved)"
                )
                return nested_data["float"]

        # Check for S3 reference directly in data
        if "s3_bucket" in data and "s3_key" in data:
            try:
                embedding_data = download_s3_external_payload(s3_client, data, logger)
                if (
                    isinstance(embedding_data.get("float"), list)
                    and embedding_data["float"]
                ):
                    logger.info(
                        "Successfully extracted embedding from S3 reference (data)"
                    )
                    return embedding_data["float"]
            except Exception as e:
                logger.warning(
                    f"Failed to download embedding from S3 reference: {str(e)}"
                )

        # Check nested data.data for float array (after S3 download replaces the reference)
        if isinstance(data.get("data"), dict):
            nested_data = data["data"]
            if isinstance(nested_data.get("float"), list) and nested_data["float"]:
                logger.info(
                    "Successfully extracted embedding from nested data.data.float"
                )
                return nested_data["float"]

        # Direct vector in data (backward compatible)
        if isinstance(data.get("float"), list) and data["float"]:
            return data["float"]

    # Check item structure (backward compatible)
    itm = _item(container)
    if itm:
        # Check for S3 reference in item
        if "s3_bucket" in itm and "s3_key" in itm:
            try:
                embedding_data = download_s3_external_payload(s3_client, itm, logger)
                if (
                    isinstance(embedding_data.get("float"), list)
                    and embedding_data["float"]
                ):
                    logger.info(
                        "Successfully extracted embedding from S3 reference (item)"
                    )
                    return embedding_data["float"]
            except Exception as e:
                logger.warning(
                    f"Failed to download embedding from S3 reference: {str(e)}"
                )

        # Direct vector in item (backward compatible)
        if isinstance(itm.get("float"), list) and itm["float"]:
            return itm["float"]

    # Direct vector in container (backward compatible)
    if isinstance(container.get("float"), list) and container["float"]:
        return container["float"]

    # Check external task results (backward compatible)
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

    logger.error("Segment bounds not found – this indicates a data structure mismatch")
    raise RuntimeError(
        "Segment bounds not found – expected 'start_offset_sec'/'start_time' and 'end_offset_sec'/'end_time' fields"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Early-exit helpers
def _bad_request(msg: str):
    logger.error(msg)
    raise RuntimeError(msg)


def _ok_no_op(vector_len: int, inventory_id: Optional[str]):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Embedding processed (OpenSearch not available)",
                "inventory_id": inventory_id,
                "vector_length": vector_len,
            }
        ),
    }


def exponential_backoff_with_jitter(
    attempt: int, base_delay: float = 0.1, max_delay: float = 30.0
) -> float:
    """
    Calculate exponential backoff delay with full jitter.

    This helps prevent thundering herd problems when multiple Lambda functions
    are retrying simultaneously.

    Args:
        attempt: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds (default 0.1s)
        max_delay: Maximum delay in seconds (default 30s)

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential: base_delay * 2^attempt
    exponential_delay = base_delay * (2**attempt)

    # Cap at max_delay
    capped_delay = min(exponential_delay, max_delay)

    # Full jitter: random value between 0 and capped_delay
    jittered_delay = random.uniform(0, capped_delay)

    return jittered_delay


def check_opensearch_response(resp: Dict[str, Any], op: str) -> None:
    """Check OpenSearch response and raise error if not successful."""
    status = resp.get("status", 200)
    if status not in (200, 201):
        err = resp.get("error", {}).get("reason", "Unknown error")
        logger.error(f"OpenSearch {op} failed", extra={"status": status, "error": err})
        raise RuntimeError(f"OpenSearch {op} failed: {err} (status {status})")


# ─────────────────────────────────────────────────────────────────────────────
# One-shot master-document cache + FPS extraction
_master_doc_cache: Dict[str, Dict[str, Any]] = {}  # inventory_id → _source


def _get_master_doc(
    client: OpenSearch,
    inventory_id: str,
    is_video: bool,
    max_retries: int = 50,
    delay_seconds: float = 1.0,
) -> Dict[str, Any]:
    """
    Fetches the master document for a given inventory_id, retrying up to max_retries
    times if no document is found.
    """
    # return cached if available
    if inventory_id in _master_doc_cache:
        return _master_doc_cache[inventory_id]

    for attempt in range(1, max_retries + 1):
        resp = client.search(
            index=INDEX_NAME,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            {"match_phrase": {"InventoryID": inventory_id}},
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
            },
            size=1,
        )
        total_hits = resp.get("hits", {}).get("total", {}).get("value", 0)

        if total_hits > 0:
            doc = resp["hits"]["hits"][0]["_source"]
            _master_doc_cache[inventory_id] = doc
            return doc

        # not found, wait and retry
        time.sleep(delay_seconds)

    # after all retries
    raise RuntimeError(
        f"No master document found for asset {inventory_id} after {max_retries} attempts"
    )


def _extract_fps(master_src: Dict[str, Any], inventory_id: str) -> int:
    try:
        fr = master_src["Metadata"]["EmbeddedMetadata"]["general"]["FrameRate"]
        fps_int = int(round(float(fr)))
        if fps_int <= 0:
            raise ValueError
        return fps_int
    except Exception as exc:
        raise RuntimeError(
            f"Master document for asset {inventory_id} is missing a valid FrameRate"
        ) from exc


def _determine_embedding_dimension(embedding_vector: List[float]) -> int:
    """Determine the dimension of an embedding vector."""
    return len(embedding_vector)


def _get_embedding_field_name(dimension: int, space_type: str = "cosine") -> str:
    """
    Get the field name for storing an embedding based on its dimension and space type.

    Args:
        dimension: The embedding dimension (256, 384, 512, 1024, 1536, 3072)
        space_type: The similarity space type (default: "cosine")

    Returns:
        Field name like "embedding_1024_cosine"
    """
    supported_dimensions = [256, 384, 512, 1024, 1536, 3072]
    if dimension not in supported_dimensions:
        logger.warning(
            f"Unsupported embedding dimension: {dimension}. Using closest supported dimension."
        )
        # Find closest supported dimension
        dimension = min(supported_dimensions, key=lambda x: abs(x - dimension))

    return f"embedding_{dimension}_{space_type}"


def _extract_embedding_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract embedding metadata for storage alongside the embedding document.

    Priority order:
    1. Environment variables (MODEL_PROVIDER, MODEL_NAME, MODEL_VERSION)
       — set per-pipeline from template parameters, most reliable source
    2. Payload fields (data, data.data, map.item, top-level)
    3. Defaults to "unknown"

    Returns metadata including:
    - model_provider: e.g., "twelvelabs", "openai", "coactive"
    - model_name: e.g., "Marengo-retrieval-3.0", "text-embedding-3-large"
    - model_version: e.g., "3.0", "2.7"
    - embedding_granularity: e.g., "clip", "video", "frame"
    - segmentation_method: e.g., "shot", "scene", "fixed"
    """
    metadata: Dict[str, Any] = {}

    # 1. Environment variables (set per-pipeline at deployment time)
    if MODEL_PROVIDER:
        metadata["model_provider"] = MODEL_PROVIDER
    if MODEL_NAME:
        metadata["model_name"] = MODEL_NAME
    if MODEL_VERSION:
        metadata["model_version"] = MODEL_VERSION

    # 2. Payload fields (fill in anything not already set by env vars)
    data = payload.get("data", {})
    if isinstance(data, dict):
        if data.get("model_provider") and "model_provider" not in metadata:
            metadata["model_provider"] = data["model_provider"]
        if data.get("model_name") and "model_name" not in metadata:
            metadata["model_name"] = data["model_name"]
        if data.get("model_version") and "model_version" not in metadata:
            metadata["model_version"] = data["model_version"]

        if isinstance(data.get("data"), dict):
            nested = data["data"]
            if nested.get("model_provider") and "model_provider" not in metadata:
                metadata["model_provider"] = nested["model_provider"]
            if nested.get("model_name") and "model_name" not in metadata:
                metadata["model_name"] = nested["model_name"]
            if nested.get("model_version") and "model_version" not in metadata:
                metadata["model_version"] = nested["model_version"]

    map_item = payload.get("map", {}).get("item", {})
    if isinstance(map_item, dict):
        if map_item.get("model_provider") and "model_provider" not in metadata:
            metadata["model_provider"] = map_item["model_provider"]
        if map_item.get("model_name") and "model_name" not in metadata:
            metadata["model_name"] = map_item["model_name"]
        if map_item.get("model_version") and "model_version" not in metadata:
            metadata["model_version"] = map_item["model_version"]

    if payload.get("model_provider") and "model_provider" not in metadata:
        metadata["model_provider"] = payload["model_provider"]
    if payload.get("model_name") and "model_name" not in metadata:
        metadata["model_name"] = payload["model_name"]
    if payload.get("model_version") and "model_version" not in metadata:
        metadata["model_version"] = payload["model_version"]

    # 3. Final defaults
    metadata.setdefault("model_provider", "unknown")
    metadata.setdefault("model_name", "unknown")
    metadata.setdefault("model_version", "unknown")

    logger.info(
        "Extracted embedding metadata",
        extra={
            "model_provider": metadata.get("model_provider"),
            "model_name": metadata.get("model_name"),
            "model_version": metadata.get("model_version"),
            "source_env": bool(MODEL_PROVIDER or MODEL_NAME or MODEL_VERSION),
        },
    )

    # Extract additional metadata from payload (granularity, segmentation)
    data = payload.get("data", {})
    if isinstance(data, dict):
        if (
            data.get("embedding_granularity")
            and "embedding_granularity" not in metadata
        ):
            metadata["embedding_granularity"] = data["embedding_granularity"]
        if data.get("segmentation_method") and "segmentation_method" not in metadata:
            metadata["segmentation_method"] = data["segmentation_method"]

    return metadata


def _should_use_asset_embeddings_mode(payload: Dict[str, Any]) -> bool:
    """
    Determine if we should use the new asset_embeddings separate-document mode
    based on the ASSET_EMBEDDINGS_INDEX environment variable.

    When ASSET_EMBEDDINGS_INDEX is "asset-embeddings", this is a Marengo 3.0
    pipeline and embeddings are stored as separate documents.
    When ASSET_EMBEDDINGS_INDEX is "media", this is a Marengo 2.7 pipeline
    and embeddings update the master document in-place.

    Args:
        payload: The Lambda event payload (not used, kept for compatibility)

    Returns:
        True to use asset_embeddings mode, False for legacy mode
    """
    use_asset_mode = ASSET_EMBEDDINGS_INDEX == "asset-embeddings"

    logger.info(
        "Determined storage mode from ASSET_EMBEDDINGS_INDEX",
        extra={
            "ASSET_EMBEDDINGS_INDEX": ASSET_EMBEDDINGS_INDEX,
            "use_asset_embeddings_mode": use_asset_mode,
        },
    )
    return use_asset_mode


def _get_target_index(is_marengo_30: bool) -> str:
    """
    Determine which OpenSearch index to use for embedding storage.

    The ASSET_EMBEDDINGS_INDEX env var is set per-pipeline at deployment time:
    - Marengo 3.0 pipelines: "asset-embeddings"
    - Marengo 2.7 pipelines: "media"

    For the 3.0 separate-document path, embeddings go to ASSET_EMBEDDINGS_INDEX.
    For the legacy path, embeddings update the master doc in INDEX_NAME (media).

    Args:
        is_marengo_30: True if this is a Marengo 3.0 embedding

    Returns:
        The index name to use for storing the embedding
    """
    if is_marengo_30:
        target_index = ASSET_EMBEDDINGS_INDEX
    else:
        target_index = INDEX_NAME

    logger.info(
        "Index routing",
        extra={
            "target_index": target_index,
            "is_marengo_30": is_marengo_30,
            "INDEX_NAME": INDEX_NAME,
            "ASSET_EMBEDDINGS_INDEX": ASSET_EMBEDDINGS_INDEX,
        },
    )
    return target_index


def _create_separate_embedding_document(
    embedding_vector: List[float],
    inventory_id: str,
    scope: str,
    embedding_option: Optional[str],
    content_type: str,
    start_sec: Optional[int] = None,
    end_sec: Optional[int] = None,
    start_tc: Optional[str] = None,
    end_tc: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a separate embedding document for Marengo 3.0 architecture.

    Args:
        embedding_vector: The embedding vector
        inventory_id: Asset inventory ID
        scope: Embedding scope (clip, video, asset, etc.)
        embedding_option: Embedding option (visual, audio, transcription, image)
        content_type: Content type (video, audio, image)
        start_sec: Start time in seconds (for clips)
        end_sec: End time in seconds (for clips)
        start_tc: Start SMPTE timecode (for clips)
        end_tc: End SMPTE timecode (for clips)
        metadata: Additional metadata (model info, etc.)

    Returns:
        Dictionary ready to be indexed as a separate document
    """
    if metadata is None:
        metadata = {}

    dimension = _determine_embedding_dimension(embedding_vector)
    field_name = _get_embedding_field_name(dimension)

    # Determine embedding_type based on content_type and embedding_option
    # For images: embedding_type = "image"
    # For video/audio clips: embedding_type = content_type (video/audio)
    if content_type == "image":
        embedding_type = "image"
    else:
        embedding_type = content_type  # "video" or "audio"

    # Determine embedding_granularity
    # Map embeddingScope from Bedrock to embedding_granularity:
    # - "asset" (full video/image/audio) -> "asset"
    # - "clip" (segment) -> "segment"
    # - "video"/"image"/"audio" (legacy) -> "asset"
    if scope in ["asset", "video", "image", "audio"]:
        embedding_granularity = "asset"
    else:
        # scope is "clip" - default to "segment"
        embedding_granularity = "segment"

    # Log for debugging
    logger.info(
        "Determined embedding_granularity",
        extra={
            "scope": scope,
            "embedding_granularity": embedding_granularity,
            "content_type": content_type,
            "start_sec": start_sec,
            "end_sec": end_sec,
        },
    )

    # Determine segmentation_method
    # For whole assets: "none"
    # For clips: use metadata or default to "fixed_interval"
    if embedding_granularity == "asset":
        segmentation_method = "none"
    else:
        segmentation_method = metadata.get("segmentation_method", "fixed_interval")

    # Map embedding_option to embedding_representation
    # Schema allows: visual, audio, text, video
    # Marengo 2.7 uses: visual-text, audio, visual-image
    if embedding_option:
        # Normalize to schema format
        if embedding_option == "visual-text":
            embedding_representation = "visual"
        elif embedding_option == "visual-image":
            embedding_representation = "visual"  # Images use "visual" representation
        else:
            embedding_representation = embedding_option  # visual, audio, text, video
    else:
        # Default based on content type
        if content_type == "image":
            embedding_representation = "visual"  # Images use "visual" representation
        elif content_type == "audio":
            embedding_representation = "audio"
        else:
            embedding_representation = "visual"

    # Get model version as string (per schema)
    model_version = str(metadata.get("model_version", "3.0"))

    # Build the separate document per schema
    # Schema uses: inventory_id (not parent_asset_id), created_at (not timestamp)
    # Schema uses: start_smpte_timecode/end_smpte_timecode (not start_timecode/end_timecode)
    document = {
        "inventory_id": inventory_id,
        "embedding_type": embedding_type,
        "model_provider": metadata.get("model_provider", "twelvelabs"),
        "inference_provider": "aws_bedrock",
        "model_name": "marengo",
        "model_version": model_version,
        "created_at": datetime.utcnow().isoformat(),
        "embedding_granularity": embedding_granularity,
        "segmentation_method": segmentation_method,
        "embedding_representation": embedding_representation,
        "embedding_dimension": dimension,
        "space_type": "cosinesimil",
        field_name: embedding_vector,
    }

    # Add temporal information
    if start_sec is not None and end_sec is not None:
        document["start_seconds"] = start_sec
        document["end_seconds"] = end_sec
    else:
        # Default to 0 for images or whole assets (per schema: start_seconds must be 0 for asset granularity)
        document["start_seconds"] = 0
        # Per schema: end_seconds can be null for full-asset
        document["end_seconds"] = None if embedding_granularity == "asset" else 0

    # Use SMPTE timecode fields (per schema)
    if start_tc:
        document["start_smpte_timecode"] = start_tc
    else:
        document["start_smpte_timecode"] = "00:00:00:00"

    if end_tc:
        document["end_smpte_timecode"] = end_tc
    else:
        # Per schema: can be null for full-asset
        document["end_smpte_timecode"] = (
            None if embedding_granularity == "asset" else "00:00:00:00"
        )

    return document


# ─────────────────────────────────────────────────────────────────────────────
def process_single_embedding(
    payload: Dict[str, Any], embedding_data: Dict[str, Any], client, inventory_id: str
) -> Dict[str, Any]:
    """Process a single embedding object."""
    # Check if this is a lightweight reference that needs to be downloaded
    if is_s3_reference(embedding_data):
        logger.info("Detected lightweight reference, downloading from S3")
        embedding_data = download_s3_external_payload(s3_client, embedding_data, logger)

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
        "InventoryID": inventory_id,
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
            extra={"inventory_id": inventory_id, "error": str(e), "index": INDEX_NAME},
        )
        raise RuntimeError(
            f"Failed to index document for asset {inventory_id}: {str(e)}"
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

        inventory_id = extract_inventory_id(payload)
        if not inventory_id:
            return _bad_request("Unable to determine inventory_id – aborting")

        # OpenSearch client (may be None in local dev)
        try:
            client = get_opensearch_client()
            if not client:
                return _ok_no_op(None, inventory_id)
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
                            payload, embedding_data, client, inventory_id
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
                                    {"match_phrase": {"InventoryID": inventory_id}},
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
                        extra={"index": INDEX_NAME, "inventory_id": inventory_id},
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
                                "inventory_id": inventory_id,
                                "error": str(e),
                                "index": INDEX_NAME,
                            },
                        )
                        raise RuntimeError(
                            f"Failed to search for master document in batch video embedding {i+1} for asset {inventory_id}: {str(e)}"
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
                                    "inventory_id": inventory_id,
                                    "error": str(e),
                                    "index": INDEX_NAME,
                                },
                            )
                            raise RuntimeError(
                                f"Failed to refresh index and retry search in batch video embedding {i+1} for asset {inventory_id}: {str(e)}"
                            ) from e

                    if search_resp["hits"]["total"]["value"] == 0:
                        raise RuntimeError(
                            f"No master doc with InventoryID={inventory_id} in '{INDEX_NAME}'"
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
                                "inventory_id": inventory_id,
                                "document_id": existing_id,
                                "error": str(e),
                                "index": INDEX_NAME,
                            },
                        )
                        raise RuntimeError(
                            f"Failed to get metadata for document {existing_id} in batch video embedding {i+1} (asset {inventory_id}): {str(e)}"
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
                                        "inventory_id": inventory_id,
                                        "document_id": existing_id,
                                        "error": str(e),
                                        "attempt": attempt + 1,
                                        "embedding_index": i + 1,
                                    },
                                )
                                raise RuntimeError(
                                    f"Failed to resolve conflict for batch video embedding {i+1} document {existing_id} (asset {inventory_id}): {str(e)}"
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
                        "inventory_id": inventory_id,
                        "processed_count": len(results),
                        "total_count": len(payload["data"]),
                    }
                ),
            }

        # Single embedding processing (original logic)
        # Check if payload.data contains a nested S3 reference
        data = payload.get("data")
        if isinstance(data, dict):
            # Check for nested data.data structure (Bedrock Results pattern)
            if isinstance(data.get("data"), dict) and is_s3_reference(data["data"]):
                logger.info(
                    "Detected S3 reference in nested data.data structure, downloading from S3"
                )
                nested_ref = data["data"]
                embedding_data = download_s3_external_payload(
                    s3_client, nested_ref, logger
                )
                # Replace the nested reference with the downloaded data
                data["data"] = embedding_data
                payload["data"] = data
            # Check if data itself is an S3 reference (other patterns)
            elif is_s3_reference(data):
                logger.info("Detected S3 reference in data, downloading from S3")
                data = download_s3_external_payload(s3_client, data, logger)
                # Update payload with the downloaded embedding
                payload["data"] = data

        embedding_vector = extract_embedding_vector(payload)
        logger.info(
            "Embedding vector extraction result",
            extra={
                "embedding_vector_found": embedding_vector is not None,
                "embedding_length": len(embedding_vector) if embedding_vector else 0,
                "payload_data_keys": (
                    list(payload.get("data", {}).keys())
                    if isinstance(payload.get("data"), dict)
                    else "not_dict"
                ),
                "payload_data_has_float": (
                    "float" in payload.get("data", {})
                    if isinstance(payload.get("data"), dict)
                    else False
                ),
            },
        )
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

        # ── CLIP / AUDIO SCOPE  → NEW DOC OR NESTED ARRAY ────────────────────
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
                    "inventory_id": inventory_id,
                    "fps": fps,
                    "start_seconds": start_sec,
                    "end_seconds": end_sec,
                },
            )

            start_tc = seconds_to_smpte(start_sec, fps)
            end_tc = seconds_to_smpte(end_sec, fps)

            logger.info(
                "Segment SMPTE values",
                extra={
                    "inventory_id": inventory_id,
                    "start_timecode": start_tc,
                    "end_timecode": end_tc,
                },
            )

            if _should_use_asset_embeddings_mode(payload):
                # MARENGO 3.0 MODE: Create separate document for each clip embedding
                # This avoids document size limits and version conflicts from concurrent writes
                logger.info(
                    "Using Marengo 3.0 mode - creating separate clip document with parent reference",
                    extra={"inventory_id": inventory_id, "scope": scope},
                )

                # Extract embedding metadata
                metadata = _extract_embedding_metadata(payload)

                # Log scope and temporal info for debugging granularity detection
                logger.info(
                    "Creating separate embedding document",
                    extra={
                        "inventory_id": inventory_id,
                        "scope": scope,
                        "embedding_option": embedding_option,
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                        "content_type": CONTENT_TYPE,
                    },
                )

                # Create separate clip document using new schema
                document = _create_separate_embedding_document(
                    embedding_vector=embedding_vector,
                    inventory_id=inventory_id,
                    scope=scope,
                    embedding_option=embedding_option,
                    content_type=CONTENT_TYPE,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    start_tc=start_tc,
                    end_tc=end_tc,
                    metadata=metadata,
                )

                # Route Marengo 3.0 embeddings to dedicated asset-embeddings index
                target_index = _get_target_index(is_marengo_30=True)

                # Log the full asset-embeddings document (excluding the vector for readability)
                doc_for_logging = {
                    k: v
                    for k, v in document.items()
                    if not k.startswith("embedding_")
                    or k
                    in (
                        "embedding_type",
                        "embedding_granularity",
                        "embedding_representation",
                        "embedding_dimension",
                    )
                }
                logger.info(
                    "asset-embeddings document (clip)",
                    extra={"document": doc_for_logging},
                )

                logger.info(
                    "Indexing separate clip document (Marengo 3.0)",
                    extra={
                        "index": target_index,
                        "inventory_id": inventory_id,
                        "parent_asset_id": inventory_id,
                        "embedding_type": document.get("embedding_type"),
                        "embedding_representation": document.get(
                            "embedding_representation"
                        ),
                        "embedding_granularity": document.get("embedding_granularity"),
                        "dimension": document.get("embedding_dimension"),
                        "start_tc": start_tc,
                        "end_tc": end_tc,
                    },
                )

                try:
                    res = client.index(index=target_index, body=document)
                    check_opensearch_response(res, "index")

                    return {
                        "statusCode": 200,
                        "body": json.dumps(
                            {
                                "message": "Clip embedding stored as separate document (Marengo 3.0)",
                                "index": target_index,
                                "document_id": res.get("_id", "unknown"),
                                "parent_asset_id": inventory_id,
                                "inventory_id": inventory_id,
                                "start_timecode": start_tc,
                                "end_timecode": end_tc,
                                "mode": "marengo_3.0_separate_documents",
                            }
                        ),
                    }
                except Exception as e:
                    logger.error(
                        "Failed to index clip document (Marengo 3.0)",
                        extra={
                            "inventory_id": inventory_id,
                            "error": str(e),
                            "index": target_index,
                        },
                    )
                    raise RuntimeError(
                        f"Failed to index clip document for asset {inventory_id}: {str(e)}"
                    ) from e

            else:
                # LEGACY MODE: Create separate clip document (backward compatible)
                logger.info(
                    "Using legacy mode - creating separate clip document",
                    extra={"inventory_id": inventory_id, "scope": scope},
                )

                # Determine the correct embedding field based on dimension
                dimension = _determine_embedding_dimension(embedding_vector)

                # For 1024-d use legacy "embedding" field, otherwise use dimension-specific field
                if dimension == 1024:
                    embedding_field = "embedding"
                else:
                    embedding_field = _get_embedding_field_name(dimension)

                document: Dict[str, Any] = {
                    "type": CONTENT_TYPE,
                    embedding_field: embedding_vector,
                    "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
                    "timestamp": datetime.utcnow().isoformat(),
                    "InventoryID": inventory_id,
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
                            "inventory_id": inventory_id,
                            "error": str(e),
                            "index": INDEX_NAME,
                            "scope": scope,
                        },
                    )
                    raise RuntimeError(
                        f"Failed to index {scope} document for asset {inventory_id}: {str(e)}"
                    ) from e

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "Embedding stored successfully",
                            "index": INDEX_NAME,
                            "document_id": res.get("_id", "unknown"),
                            "inventory_id": inventory_id,
                            "mode": "legacy",
                        }
                    ),
                }

        # ── AUDIO MASTER DOCS ARE *NOT* UPDATED ───────────────────────────────
        if IS_AUDIO_CONTENT:
            logger.info(
                "Skipping master-doc update for audio content",
                extra={"inventory_id": inventory_id},
            )
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Embedding stored (audio clip only – master unchanged)",
                        "inventory_id": inventory_id,
                    }
                ),
            }

        # ── MASTER-DOC UPDATE for VIDEO ───────────────────────────────────────

        if _should_use_asset_embeddings_mode(payload):
            # MARENGO 3.0 MODE: Create separate document for video/image-level embedding
            # Do NOT search for or update master document - keep embeddings separate
            logger.info(
                "Using Marengo 3.0 mode - creating separate document for video/image-level embedding",
                extra={
                    "inventory_id": inventory_id,
                    "scope": scope,
                    "content_type": CONTENT_TYPE,
                },
            )

            # Extract embedding metadata
            metadata = _extract_embedding_metadata(payload)

            # For asset-level embeddings, try to get actual duration from payload
            # Otherwise default to 0 (for images or when duration not available)
            try:
                start_sec, end_sec = _get_segment_bounds(payload)
                # Get framerate for SMPTE timecode calculation
                framerate = extract_framerate(payload)
                if framerate:
                    start_tc = seconds_to_smpte(start_sec, framerate)
                    end_tc = seconds_to_smpte(end_sec, framerate)
                else:
                    start_tc = "00:00:00:00"
                    end_tc = "00:00:00:00"
            except Exception as e:
                logger.warning(
                    f"Could not extract segment bounds for asset-level embedding: {e}, using defaults"
                )
                start_sec = 0
                end_sec = 0
                start_tc = "00:00:00:00"
                end_tc = "00:00:00:00"

            # Create separate document for video/image-level embedding
            document = _create_separate_embedding_document(
                embedding_vector=embedding_vector,
                inventory_id=inventory_id,
                scope=scope or CONTENT_TYPE or "video",
                embedding_option=embedding_option,
                content_type=CONTENT_TYPE,
                start_sec=start_sec,
                end_sec=end_sec,
                start_tc=start_tc,
                end_tc=end_tc,
                metadata=metadata,
            )

            # Route Marengo 3.0 embeddings to dedicated asset-embeddings index
            target_index = _get_target_index(is_marengo_30=True)

            # Log the full asset-embeddings document (excluding the vector for readability)
            doc_for_logging = {
                k: v
                for k, v in document.items()
                if not k.startswith("embedding_")
                or k
                in (
                    "embedding_type",
                    "embedding_granularity",
                    "embedding_representation",
                    "embedding_dimension",
                )
            }
            logger.info(
                "asset-embeddings document (asset-level)",
                extra={"document": doc_for_logging},
            )

            logger.info(
                "Indexing separate document for video/image-level embedding (Marengo 3.0)",
                extra={
                    "index": target_index,
                    "inventory_id": inventory_id,
                    "parent_asset_id": inventory_id,
                    "embedding_type": document.get("embedding_type"),
                    "embedding_representation": document.get(
                        "embedding_representation"
                    ),
                    "embedding_granularity": document.get("embedding_granularity"),
                    "dimension": document.get("embedding_dimension"),
                },
            )

            try:
                res = client.index(index=target_index, body=document)
                check_opensearch_response(res, "index")

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "Video/image-level embedding stored as separate document (Marengo 3.0)",
                            "index": target_index,
                            "document_id": res.get("_id", "unknown"),
                            "parent_asset_id": inventory_id,
                            "inventory_id": inventory_id,
                            "mode": "marengo_3.0_separate_documents",
                        }
                    ),
                }
            except Exception as e:
                logger.error(
                    "Failed to index video/image-level embedding document (Marengo 3.0)",
                    extra={
                        "inventory_id": inventory_id,
                        "error": str(e),
                        "index": target_index,
                    },
                )
                raise RuntimeError(
                    f"Failed to index video/image-level embedding document for asset {inventory_id}: {str(e)}"
                ) from e

        # ── LEGACY MODE: Search for master doc and update in-place ────────────
        search_query = {
            "query": {
                "bool": {
                    "filter": [
                        {"match_phrase": {"InventoryID": inventory_id}},
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
            extra={
                "index": INDEX_NAME,
                "inventory_id": inventory_id,
                "query": search_query,
            },
        )
        start_time = time.time()
        try:
            search_resp = client.search(index=INDEX_NAME, body=search_query, size=1)
            check_opensearch_response(search_resp, "search")
        except Exception as e:
            logger.error(
                "Failed to search for master document",
                extra={
                    "inventory_id": inventory_id,
                    "error": str(e),
                    "index": INDEX_NAME,
                },
            )
            raise RuntimeError(
                f"Failed to search for master document for asset {inventory_id}: {str(e)}"
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
                    extra={
                        "inventory_id": inventory_id,
                        "error": str(e),
                        "index": INDEX_NAME,
                    },
                )
                raise RuntimeError(
                    f"Failed to refresh index and retry search for asset {inventory_id}: {str(e)}"
                ) from e

        if search_resp["hits"]["total"]["value"] == 0:
            raise RuntimeError(
                f"No master doc with InventoryID={inventory_id} in '{INDEX_NAME}'"
            )

        existing_id = search_resp["hits"]["hits"][0]["_id"]

        # LEGACY MODE: Update root-level embedding field (backward compatible)
        logger.info(
            "Using legacy mode - updating root-level embedding field",
            extra={
                "inventory_id": inventory_id,
                "scope": scope,
                "document_id": existing_id,
            },
        )

        try:
            meta = client.get(index=INDEX_NAME, id=existing_id)
            check_opensearch_response(meta, "get")
            seq_no = meta["_seq_no"]
            p_term = meta["_primary_term"]
        except Exception as e:
            logger.error(
                "Failed to get document metadata",
                extra={
                    "inventory_id": inventory_id,
                    "document_id": existing_id,
                    "error": str(e),
                    "index": INDEX_NAME,
                },
            )
            raise RuntimeError(
                f"Failed to get metadata for document {existing_id} (asset {inventory_id}): {str(e)}"
            ) from e

        # Determine the correct embedding field based on dimension
        dimension = _determine_embedding_dimension(embedding_vector)

        # For 1024-d use legacy "embedding" field, otherwise use dimension-specific field
        if dimension == 1024:
            embedding_field = "embedding"
        else:
            embedding_field = _get_embedding_field_name(dimension)

        update_body = {
            "doc": {
                "type": CONTENT_TYPE,
                embedding_field: embedding_vector,
                "embedding_scope": scope,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
        if embedding_option == "audio":
            update_body["doc"]["audio_embedding"] = embedding_vector
        else:
            update_body["doc"][embedding_field] = embedding_vector

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
                            "inventory_id": inventory_id,
                            "document_id": existing_id,
                            "error": str(e),
                            "attempt": attempt + 1,
                        },
                    )
                    raise RuntimeError(
                        f"Failed to resolve conflict for document {existing_id} (asset {inventory_id}): {str(e)}"
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
                    "inventory_id": inventory_id,
                    "mode": "legacy",
                }
            ),
        }

    except Exception:
        logger.exception("Error storing embedding")
        raise
