import json
import os
import time
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
INDEX_NAME = os.environ.get("INDEX_NAME", "media")
CONTENT_TYPE = os.environ.get("CONTENT_TYPE", "video").lower()
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize AWS session and clients
session = boto3.Session()
credentials = session.get_credentials()
auth = AWSV4SignerAuth(credentials, AWS_REGION, 'es')  # 'es' for managed OpenSearch service

def get_opensearch_client():
    """Initialize and return an OpenSearch client"""
    if not OPENSEARCH_ENDPOINT:
        logger.warning("OPENSEARCH_ENDPOINT environment variable not set")
        return None

    parsed = urlparse(OPENSEARCH_ENDPOINT)
    host = parsed.netloc if parsed.scheme else OPENSEARCH_ENDPOINT

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

@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
    large_payload_bucket=os.environ.get("LARGE_PAYLOAD_BUCKET")
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event", extra={"event": event})
        item = event.get("item", {})
        if not item:
            logger.warning("No embedding item found in event")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No embedding item found in event"})
            }
        
        asset_id = item.get("assetId", None)
        if asset_id is None:
            logger.warning("Missing asset_id in embedding item")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing asset_id in embedding item"})
            }
        
        embedding_vector = item.get("float", [])
        if not embedding_vector or not isinstance(embedding_vector, list):
            logger.warning("Invalid embedding vector")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid embedding vector"})
            }
        
        client = get_opensearch_client()
        if not client:
            logger.info("OpenSearch client not available, skipping index creation and document storage")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Embedding processed (OpenSearch not available)",
                    "asset_id": asset_id,
                    "vector_length": len(embedding_vector)
                })
            }
        
        document = {
            "type": CONTENT_TYPE,
            "document_id": asset_id,
            "asset_id": asset_id,
            "embedding": embedding_vector,
            "embedding_scope": item.get("embedding_scope", "clip"),
            "start_offset_sec": item.get("start_offset_sec", 0),
            "end_offset_sec": item.get("end_offset_sec", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(INDEX_NAME)
        logger.info(document)
        
        # Wait for the document to exist in the index before updating
        max_wait_time = 60  # maximum wait time in seconds
        poll_interval = 5   # check every 1 second
        start_time = time.time()
        while not client.exists(index=INDEX_NAME, id=asset_id):
            if time.time() - start_time > max_wait_time:
                error_msg = f"Document with id {asset_id} not found in index {INDEX_NAME} after {max_wait_time} seconds"
                logger.error(error_msg)
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": error_msg})
                }
            time.sleep(poll_interval)

        # Retrieve and log the existing document for debugging purposes
        existing_doc = client.get(index=INDEX_NAME, id=asset_id)
        logger.info("Existing document in OpenSearch before update: %s", json.dumps(existing_doc, indent=2))
        logger.info("New document content to update: %s", json.dumps(document, indent=2))

        
        # Once the document exists, update it
        response = client.update(
            index=INDEX_NAME,
            id=asset_id,
            body={
                "doc": document,
                # Uncomment the line below if you want to upsert in case the document doesn't exist
                # "doc_as_upsert": True
            }
        )
        
        logger.info(f"Successfully updated document wow: {response}")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Embedding stored successfully",
                "index": INDEX_NAME,
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
