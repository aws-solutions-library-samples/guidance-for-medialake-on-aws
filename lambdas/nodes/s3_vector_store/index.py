"""
Store embedding vectors in S3 Vector Store using custom boto3 SDK.

This Lambda function provides operations to store, retrieve, and search vector embeddings
using the new S3 Vector Store service with the custom unreleased boto3 SDK.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from lambda_middleware import lambda_middleware
from lambda_utils import _truncate_floats
from nodes_utils import seconds_to_smpte

# Powertools
logger = Logger()
tracer = Tracer(disabled=False)

# Environment
VECTOR_BUCKET_NAME = os.getenv("VECTOR_BUCKET_NAME", "media-vectors")
INDEX_NAME = os.getenv("INDEX_NAME", "media-vectors")
CONTENT_TYPE = os.getenv("CONTENT_TYPE", "video").lower()
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default-event-bus")

IS_AUDIO_CONTENT = CONTENT_TYPE == "audio"

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
# S3 Vector Store client using custom boto3
def get_s3_vector_client():
    """Initialize S3 Vector Store client with custom boto3 SDK."""
    try:
        # Use the custom boto3 from the layer
        session = boto3.Session()
        client = session.client('s3vectors', region_name=AWS_REGION)
        return client
    except Exception as e:
        logger.error(f"Failed to initialize S3 Vector client: {str(e)}")
        raise


def extract_inventory_id(container: Dict[str, Any]) -> Optional[str]:
    """Extract inventory ID from various payload structures."""
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

    # Check assets array for InventoryID
    for asset in container.get("assets", []):
        inventory_id = asset.get("InventoryID")
        if inventory_id:
            return inventory_id

    # Check direct InventoryID field
    return container.get("InventoryID")


def extract_asset_id(container: Dict[str, Any]) -> Optional[str]:
    """Extract asset ID from various payload structures."""
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


def extract_embedding_vector(container: Dict[str, Any]) -> Optional[List[float]]:
    """Extract embedding vector from payload."""
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


def extract_metadata(container: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metadata for the vector."""
    metadata = {}
    
    # Extract inventory_id
    inventory_id = extract_inventory_id(container)
    if inventory_id:
        metadata["inventory_id"] = inventory_id
    
    # Extract content type
    metadata["content_type"] = CONTENT_TYPE
    
    # Extract timestamp
    metadata["timestamp"] = datetime.utcnow().isoformat()
    
    # Extract scope and embedding option
    scope = extract_scope(container)
    if scope:
        metadata["embedding_scope"] = scope
        
    embedding_option = extract_embedding_option(container)
    if embedding_option:
        metadata["embedding_option"] = embedding_option
    
    # Extract segment bounds
    start_sec, end_sec = _get_segment_bounds(container)
    if start_sec is not None:
        metadata["start_offset_sec"] = start_sec
    if end_sec is not None:
        metadata["end_offset_sec"] = end_sec
    
    return metadata


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
# Single embedding processing function
def process_single_embedding(
    payload: Dict[str, Any], embedding_data: Dict[str, Any], client, inventory_id: str
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

    # For S3 Vector Store, we don't need FPS calculation like OpenSearch
    # We'll store the raw seconds in metadata
    metadata = {
        "inventory_id": inventory_id,
        "content_type": CONTENT_TYPE,
        "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
        "timestamp": datetime.utcnow().isoformat(),
        "start_offset_sec": start_sec,
        "end_offset_sec": end_sec,
    }
    
    if embedding_option is not None:
        metadata["embedding_option"] = embedding_option

    # Store in S3 Vector Store
    vectors_data = [{
        "vector": embedding_vector,
        "metadata": metadata
    }]
    
    try:
        # Get bucket and index names from environment
        bucket_name = VECTOR_BUCKET_NAME
        index_name = INDEX_NAME
        
        # Ensure bucket and index exist
        if not ensure_vector_bucket_exists(client, bucket_name):
            raise RuntimeError(f"Failed to ensure vector bucket {bucket_name} exists")
        
        vector_dimension = len(embedding_vector)
        if not ensure_index_exists(client, bucket_name, index_name, vector_dimension):
            raise RuntimeError(f"Failed to ensure index {index_name} exists")
        
        # Store the vector
        result = store_vectors(client, bucket_name, index_name, vectors_data)
        
        return {
            "document_id": f"{inventory_id}_{int(datetime.utcnow().timestamp())}",
            "start_sec": start_sec,
            "end_sec": end_sec,
        }
        
    except Exception as e:
        logger.error(
            "Failed to store vector in S3 Vector Store",
            extra={"inventory_id": inventory_id, "error": str(e), "bucket": VECTOR_BUCKET_NAME},
        )
        raise RuntimeError(
            f"Failed to store vector for inventory {inventory_id}: {str(e)}"
        ) from e


# ─────────────────────────────────────────────────────────────────────────────
def ensure_vector_bucket_exists(client, bucket_name: str) -> bool:
    """Ensure the vector bucket exists, create if it doesn't."""
    try:
        # Try to get the bucket
        client.get_vector_bucket(vectorBucketName=bucket_name)
        logger.info(f"Vector bucket {bucket_name} already exists")
        return True
    except client.exceptions.NotFoundException:
        # Bucket doesn't exist, create it
        try:
            client.create_vector_bucket(
                vectorBucketName=bucket_name,
                encryptionConfiguration={
                    'sseType': 'AES256'
                }
            )
            logger.info(f"Created vector bucket {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create vector bucket {bucket_name}: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error checking vector bucket {bucket_name}: {str(e)}")
        return False


def ensure_index_exists(client, bucket_name: str, index_name: str, vector_dimension: int) -> bool:
    """Ensure the vector index exists, create if it doesn't."""
    try:
        # Try to get the index
        client.get_index(vectorBucketName=bucket_name, indexName=index_name)
        logger.info(f"Index {index_name} already exists in bucket {bucket_name}")
        return True
    except client.exceptions.NotFoundException:
        # Index doesn't exist, create it
        try:
            client.create_index(
                vectorBucketName=bucket_name,
                indexName=index_name,
                dimension=vector_dimension,
                dataType='float32',
                distanceMetric='cosine'
            )
            logger.info(f"Created index {index_name} in bucket {bucket_name} with dimension {vector_dimension}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error checking index {index_name}: {str(e)}")
        return False


def store_vectors(client, bucket_name: str, index_name: str, vectors_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Store vectors in S3 Vector Store."""
    try:
        # Prepare vectors for PutVectors API
        vectors = []
        for i, vector_data in enumerate(vectors_data):
            vector_key = f"{vector_data['metadata']['inventory_id']}"
            
            vector_entry = {
                'key': vector_key,
                'data': {'float32': vector_data['vector']},
                'metadata': vector_data['metadata']
            }
            vectors.append(vector_entry)
        
        # Store vectors (max 500 per request)
        batch_size = 500
        stored_keys = []
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            
            response = client.put_vectors(
                vectorBucketName=bucket_name,
                indexName=index_name,
                vectors=batch
            )
            
            # Collect stored keys
            for vector in batch:
                stored_keys.append(vector['key'])
            
            logger.info(f"Stored batch of {len(batch)} vectors in {bucket_name}/{index_name}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully stored {len(vectors)} vectors",
                "bucket_name": bucket_name,
                "index_name": index_name,
                "stored_keys": stored_keys
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to store vectors: {str(e)}")
        raise RuntimeError(f"Failed to store vectors: {str(e)}")


def process_store_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process the store action for embedding vectors."""
    client = get_s3_vector_client()
    
    # Extract parameters
    bucket_name = payload.get("vector_bucket_name", VECTOR_BUCKET_NAME)
    index_name = payload.get("index_name", INDEX_NAME)
    
    # Extract inventory_id
    inventory_id = extract_inventory_id(payload)
    if not inventory_id:
        return _bad_request("Unable to determine inventory_id – aborting")
    
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

        # Process video scope embeddings (store as separate vectors with video scope)
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

                # For video scope, we store as a separate vector with video scope metadata
                metadata = {
                    "inventory_id": inventory_id,
                    "content_type": CONTENT_TYPE,
                    "embedding_scope": scope,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                if embedding_option is not None:
                    metadata["embedding_option"] = embedding_option

                vectors_data = [{
                    "vector": embedding_vector,
                    "metadata": metadata
                }]
                
                # Ensure bucket and index exist
                if not ensure_vector_bucket_exists(client, bucket_name):
                    raise RuntimeError(f"Failed to ensure vector bucket {bucket_name} exists")
                
                vector_dimension = len(embedding_vector)
                if not ensure_index_exists(client, bucket_name, index_name, vector_dimension):
                    raise RuntimeError(f"Failed to ensure index {index_name} exists")
                
                # Store the vector
                store_result = store_vectors(client, bucket_name, index_name, vectors_data)
                
                results.append(
                    {
                        "document_id": f"{inventory_id}_video_{i}_{int(datetime.utcnow().timestamp())}",
                        "type": "video_scope",
                        "scope": scope,
                    }
                )
                logger.info(
                    f"Stored video embedding {i+1}/{len(payload['data'])}",
                    extra={"scope": scope},
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
                    "bucket_name": bucket_name,
                    "index_name": index_name,
                    "inventory_id": inventory_id,
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

    # For clip/audio scope or single embeddings, store directly
    if scope in {"clip", "audio"} or IS_AUDIO_CONTENT:
        start_sec, end_sec = _get_segment_bounds(payload)

        metadata = {
            "inventory_id": inventory_id,
            "content_type": CONTENT_TYPE,
            "embedding_scope": "clip" if IS_AUDIO_CONTENT else scope,
            "timestamp": datetime.utcnow().isoformat(),
            "start_offset_sec": start_sec,
            "end_offset_sec": end_sec,
        }
        
        if embedding_option is not None:
            metadata["embedding_option"] = embedding_option

        vectors_data = [{
            "vector": embedding_vector,
            "metadata": metadata
        }]
        
        # Ensure bucket and index exist
        if not ensure_vector_bucket_exists(client, bucket_name):
            raise RuntimeError(f"Failed to ensure vector bucket {bucket_name} exists")
        
        vector_dimension = len(embedding_vector)
        if not ensure_index_exists(client, bucket_name, index_name, vector_dimension):
            raise RuntimeError(f"Failed to ensure index {index_name} exists")
        
        # Store the vectors
        result = store_vectors(client, bucket_name, index_name, vectors_data)
        
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Embedding stored successfully",
                    "bucket_name": bucket_name,
                    "index_name": index_name,
                    "inventory_id": inventory_id,
                }
            ),
        }

    # For video scope (master document equivalent), store as video scope vector
    metadata = {
        "inventory_id": inventory_id,
        "content_type": CONTENT_TYPE,
        "embedding_scope": scope,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if embedding_option is not None:
        metadata["embedding_option"] = embedding_option

    vectors_data = [{
        "vector": embedding_vector,
        "metadata": metadata
    }]
    
    # Ensure bucket and index exist
    if not ensure_vector_bucket_exists(client, bucket_name):
        raise RuntimeError(f"Failed to ensure vector bucket {bucket_name} exists")
    
    vector_dimension = len(embedding_vector)
    if not ensure_index_exists(client, bucket_name, index_name, vector_dimension):
        raise RuntimeError(f"Failed to ensure index {index_name} exists")
    
    # Store the vectors
    result = store_vectors(client, bucket_name, index_name, vectors_data)
    
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Embedding stored successfully",
                "bucket_name": bucket_name,
                "index_name": index_name,
                "inventory_id": inventory_id,
            }
        ),
    }


@lambda_middleware(event_bus_name=EVENT_BUS_NAME)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], _context: LambdaContext):
    """Main Lambda handler for S3 Vector Store operations."""
    try:
        truncated = _truncate_floats(event, max_items=10)
        logger.info("Received event", extra={"event": truncated})
        logger.info(f"Content Type: {CONTENT_TYPE}")
        
        payload: Dict[str, Any] = event.get("payload") or {}
        if not payload:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Event missing 'payload'"})
            }
        
        # Process store action (write-only like embedding store)
        return process_store_action(payload)
            
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal server error: {str(e)}"})
        }