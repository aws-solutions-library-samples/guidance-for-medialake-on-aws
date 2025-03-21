import json
import os
import boto3
from urllib.parse import urlparse
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

from lambda_middleware import lambda_middleware
from nodes_utils import seconds_to_smpte

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
        
        scope = item.get("embedding_scope", None)
        if scope is None:
            logger.warning("Missing scope in embedding item")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing scope in embedding item"})
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
            "embedding": embedding_vector,
            "embedding_scope": scope,
            "timestamp": datetime.utcnow().isoformat()
        }

        if scope == "clip":
            # Store the original asset_id inside an object called DigitalSourceAsset with a key called ID
            document["DigitalSourceAsset"] = {"ID": asset_id}
            document["start_timecode"] = seconds_to_smpte(item.get("start_offset_sec", None))
            document["end_timecode"] = seconds_to_smpte(item.get("end_offset_sec", None))

            # Index the document and let OpenSearch generate the ID
            response = client.index(index=INDEX_NAME, body=document, refresh=True)
            document_id = response.get("_id", "unknown")
            logger.info(f"Successfully created new document for clip: {response}")

        else:
            # Search for an existing document by DigitalSourceAsset.ID
            search_query = {
                "query": {
                    "term": {
                        "DigitalSourceAsset.ID.keyword": asset_id
                    }
                }
            }
            search_response = client.search(index=INDEX_NAME, body=search_query, size=1)

            if search_response["hits"]["total"]["value"] == 0:
                error_msg = f"No existing document found with DigitalSourceAsset.ID={asset_id} in index {INDEX_NAME}"
                logger.error(error_msg)
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": error_msg})
                }

            # Extract document ID from search response
            existing_doc_id = search_response["hits"]["hits"][0]["_id"]
            logger.info(f"Found existing document with ID: {existing_doc_id} for asset_id: {asset_id}")

            # Update the existing document
            document["asset_id"] = asset_id
            response = client.update(
                index=INDEX_NAME,
                id=existing_doc_id,
                body={"doc": document},
                refresh=True
            )
            document_id = existing_doc_id
            logger.info(f"Successfully updated document: {response}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Embedding stored successfully",
                "index": INDEX_NAME,
                "document_id": document_id,
                "asset_id": asset_id if scope != "clip" else "Generated by OpenSearch"
            })
        }
        
    except Exception as e:
        error_message = f"Error storing embedding: {str(e)}"
        logger.exception(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }
