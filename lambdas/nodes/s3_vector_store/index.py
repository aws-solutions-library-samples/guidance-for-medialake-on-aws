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
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from lambda_middleware import lambda_middleware
from lambda_utils import _truncate_floats

# Powertools
logger = Logger()
tracer = Tracer(disabled=False)

# Environment
VECTOR_BUCKET_NAME = os.getenv("VECTOR_BUCKET_NAME", "media-vectors")
INDEX_NAME = os.getenv("INDEX_NAME", "media")
CONTENT_TYPE = os.getenv("CONTENT_TYPE", "video").lower()
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default-event-bus")

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


def extract_asset_id(container: Dict[str, Any]) -> Optional[str]:
    """Extract asset ID from various payload structures."""
    # Check if data is an array (batch processing) - get from first item
    if isinstance(container.get("data"), list) and container["data"]:
        first_item = container["data"][0]
        if isinstance(first_item, dict) and first_item.get("asset_id"):
            return first_item["asset_id"]

    # Check data.item structure
    if isinstance(container.get("data"), dict):
        item = container["data"].get("item")
        if isinstance(item, dict) and item.get("asset_id"):
            return item["asset_id"]

    # Check map.item structure
    if isinstance(container.get("map"), dict) and isinstance(container["map"].get("item"), dict):
        if container["map"]["item"].get("asset_id"):
            return container["map"]["item"]["asset_id"]

    # Check assets array
    for asset in container.get("assets", []):
        dsa_id = asset.get("DigitalSourceAsset", {}).get("ID")
        if dsa_id:
            return dsa_id

    # Check direct DigitalSourceAsset
    return container.get("DigitalSourceAsset", {}).get("ID")


def extract_embedding_vector(container: Dict[str, Any]) -> Optional[List[float]]:
    """Extract embedding vector from payload."""
    # Check data.item.float
    if isinstance(container.get("data"), dict):
        item = container["data"].get("item")
        if isinstance(item, dict) and isinstance(item.get("float"), list):
            return item["float"]

    # Check data.float directly
    if isinstance(container.get("data"), dict) and isinstance(container["data"].get("float"), list):
        return container["data"]["float"]

    # Check direct float
    if isinstance(container.get("float"), list):
        return container["float"]

    # Check externalTaskResults
    for res in container.get("externalTaskResults", []):
        if isinstance(res.get("float"), list) and res["float"]:
            return res["float"]

    return None


def extract_metadata(container: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metadata for the vector."""
    metadata = {}
    
    # Extract asset_id
    asset_id = extract_asset_id(container)
    if asset_id:
        metadata["asset_id"] = asset_id
    
    # Extract content type
    metadata["content_type"] = CONTENT_TYPE
    
    # Extract timestamp
    metadata["timestamp"] = datetime.utcnow().isoformat()
    
    # Extract any additional metadata from the payload
    if isinstance(container.get("data"), dict):
        item = container["data"].get("item", {})
        if isinstance(item, dict):
            # Add relevant metadata fields
            for key in ["embedding_scope", "embedding_option", "start_offset_sec", "end_offset_sec"]:
                if key in item:
                    metadata[key] = item[key]
    
    return metadata


def ensure_vector_bucket_exists(client, bucket_name: str) -> bool:
    """Ensure the vector bucket exists, create if it doesn't."""
    try:
        # Try to get the bucket
        client.get_vector_bucket(bucketName=bucket_name)
        logger.info(f"Vector bucket {bucket_name} already exists")
        return True
    except client.exceptions.NotFoundException:
        # Bucket doesn't exist, create it
        try:
            client.create_vector_bucket(
                bucketName=bucket_name,
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
        client.get_index(bucketName=bucket_name, indexName=index_name)
        logger.info(f"Index {index_name} already exists in bucket {bucket_name}")
        return True
    except client.exceptions.NotFoundException:
        # Index doesn't exist, create it
        try:
            client.create_index(
                bucketName=bucket_name,
                indexName=index_name,
                vectorDimension=vector_dimension,
                dataType='float32'
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
            vector_key = f"{vector_data['metadata']['asset_id']}_{i}_{int(datetime.utcnow().timestamp())}"
            
            vector_entry = {
                'key': vector_key,
                'vector': vector_data['vector'],
                'metadata': vector_data['metadata']
            }
            vectors.append(vector_entry)
        
        # Store vectors (max 500 per request)
        batch_size = 500
        stored_keys = []
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            
            response = client.put_vectors(
                bucketName=bucket_name,
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
    
    # Ensure bucket and index exist
    if not ensure_vector_bucket_exists(client, bucket_name):
        raise RuntimeError(f"Failed to ensure vector bucket {bucket_name} exists")
    
    # Prepare vectors data
    vectors_data = []
    
    # Check if this is batch processing
    if isinstance(payload.get("data"), list):
        logger.info(f"Processing batch of {len(payload['data'])} embeddings")
        
        for embedding_data in payload["data"]:
            if not isinstance(embedding_data, dict):
                continue
                
            vector = embedding_data.get("float")
            if not vector:
                continue
                
            # Create temporary payload for metadata extraction
            temp_payload = {
                "data": {"item": embedding_data},
                **{k: v for k, v in payload.items() if k != "data"}
            }
            
            metadata = extract_metadata(temp_payload)
            vectors_data.append({
                "vector": vector,
                "metadata": metadata
            })
    else:
        # Single embedding
        vector = extract_embedding_vector(payload)
        if not vector:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No embedding vector found in payload"})
            }
        
        metadata = extract_metadata(payload)
        vectors_data.append({
            "vector": vector,
            "metadata": metadata
        })
    
    if not vectors_data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No valid vectors found in payload"})
        }
    
    # Ensure index exists with correct dimension
    vector_dimension = len(vectors_data[0]["vector"])
    if not ensure_index_exists(client, bucket_name, index_name, vector_dimension):
        raise RuntimeError(f"Failed to ensure index {index_name} exists")
    
    # Store the vectors
    return store_vectors(client, bucket_name, index_name, vectors_data)


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
        
        # Extract action from the event (default to store)
        action = event.get("action", "store")
        
        if action == "store":
            return process_store_action(payload)
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unsupported action: {action}"})
            }
            
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal server error: {str(e)}"})
        }