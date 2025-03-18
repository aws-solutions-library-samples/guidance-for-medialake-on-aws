import json
import os
import boto3
import uuid
from urllib.parse import urlparse
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

from lambda_middleware import lambda_middleware

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# OpenSearch configuration
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
INDEX_NAME = os.environ.get("INDEX_NAME", "twelvelabs_embeddings")
CONTENT_TYPE = os.environ.get("CONTENT_TYPE", "video").lower()
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
VECTOR_DIMENSION = 1024  # Twelve Labs embeddings dimension

# Initialize AWS session and clients
session = boto3.Session()
credentials = session.get_credentials()
auth = AWSV4SignerAuth(credentials, AWS_REGION, 'es')  # 'es' for managed OpenSearch service

def get_opensearch_client():
    """Initialize and return an OpenSearch client"""
    if not OPENSEARCH_ENDPOINT:
        logger.warning("OPENSEARCH_ENDPOINT environment variable not set")
        # Return a dummy client for testing
        return None
    
    # Parse the endpoint to extract hostname if necessary
    parsed = urlparse(OPENSEARCH_ENDPOINT)
    host = parsed.netloc if parsed.scheme else OPENSEARCH_ENDPOINT

    # Initialize OpenSearch client
    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
        http_compress=True,
        retry_on_timeout=True,
        max_retries=3
    )
    return client

def create_index_if_not_exists(client, index_name, dimension=VECTOR_DIMENSION):
    """Create OpenSearch index with vector search capabilities if it doesn't exist"""
    try:
        if not client:
            logger.warning("No OpenSearch client available")
            return False
            
        if not client.indices.exists(index=index_name):
            logger.info(f"Creating index {index_name} with vector dimension {dimension}")
            index_body = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "type": {
                            "type": "keyword"
                        },
                        "document_id": {
                            "type": "keyword"
                        },
                        "asset_id": {
                            "type": "keyword"
                        },
                        "start_offset_sec": {
                            "type": "float"
                        },
                        "end_offset_sec": {
                            "type": "float"
                        },
                        "embedding_scope": {
                            "type": "keyword"
                        },
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 16
                                }
                            }
                        }
                    }
                }
            }
            client.indices.create(index=index_name, body=index_body)
            logger.info(f"Successfully created index {index_name}")
            return True
        else:
            logger.info(f"Index {index_name} already exists")
            return True
    except Exception as e:
        logger.error(f"Error creating index {index_name}: {str(e)}")
        return False

@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
    large_payload_bucket=os.environ.get("LARGE_PAYLOAD_BUCKET")
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        # Log the entire event for debugging
        logger.info("Received event", extra={"event": event})
        
        # Extract embedding data from the event
        item = event.get("item", {})
        if not item:
            logger.warning("No embedding item found in event")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No embedding item found in event"})
            }
        
        # Extract metadata from the event
        metadata = event.get("detail", {}).get("outputs", {}).get("input", {})
        asset_id = metadata.get("assetId", str(uuid.uuid4()))
        
        # Get configuration parameters
        config = metadata.get("configuration", {})
        index_name = config.get("indexName", INDEX_NAME)
        content_type = config.get("contentType", CONTENT_TYPE)
        
        # Validate embedding vector
        embedding_vector = item.get("float", [])
        if not embedding_vector or not isinstance(embedding_vector, list):
            logger.warning("Invalid embedding vector")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid embedding vector"})
            }
        
        # Get OpenSearch client
        client = get_opensearch_client()
        if not client:
            # For testing or when OpenSearch is not available, just log and return success
            logger.info("OpenSearch client not available, skipping index creation and document storage")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Embedding processed (OpenSearch not available)",
                    "asset_id": asset_id,
                    "vector_length": len(embedding_vector)
                })
            }
        
        # Create index if it doesn't exist
        if not create_index_if_not_exists(client, index_name, len(embedding_vector)):
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to create or verify index"})
            }
        
        # Prepare document for indexing
        document = {
            "type": content_type,
            "document_id": asset_id,
            "asset_id": asset_id,
            "embedding": embedding_vector,
            "embedding_scope": item.get("embedding_scope", "clip"),
            "start_offset_sec": item.get("start_offset_sec", 0),
            "end_offset_sec": item.get("end_offset_sec", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Index the document
        response = client.index(
            index=index_name,
            body=document
        )
        
        logger.info(f"Successfully indexed document: {response}")
        
        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Embedding stored successfully",
                "index": index_name,
                "document_id": response.get("_id"),
                "asset_id": asset_id
            })
        }
        
    except Exception as e:
        error_message = f"Error storing embedding: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }