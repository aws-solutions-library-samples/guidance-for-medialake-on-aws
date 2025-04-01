import json
import os
import time
import boto3
from urllib.parse import urlparse
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, exceptions

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
    large_payload_bucket=os.environ.get("EXTERNAL_PAYLOAD_BUCKET")
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        logger.info("Received event", extra={"event": event})
        item = event.get("item", {})
        if not item:
            item = event.get("payload", {})
            if not item:
                logger.warning("No embedding item found in event")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "No embedding item found in event"})
                }
        
        asset_id = item.get("assetId")
        if asset_id is None:
            # Attempt to get asset_id from metadata.pipelineAssets
            metadata = item.get("metadata", {})
            pipeline_assets = metadata.get("pipelineAssets", [])
            if pipeline_assets and isinstance(pipeline_assets, list):
                asset_id = pipeline_assets[0].get("assetId")
            # If still not found, try payload.externalTaskResults
            if asset_id is None:
                external_results = item.get("externalTaskResults", [])
                if external_results and isinstance(external_results, list):
                    asset_id = external_results[0].get("assetId")
        
        scope = item.get("embedding_scope")
        if scope is None:
            # Attempt to get embedding_scope from externalTaskResults if available
            external_results = item.get("externalTaskResults", [])
            if isinstance(external_results, list):
                for result in external_results:
                    scope = result.get("embedding_scope")
                    if scope is not None:
                        break
        
        embedding_vector = item.get("float")
        if not embedding_vector or not isinstance(embedding_vector, list):
            external_results = item.get("externalTaskResults", [])
            if isinstance(external_results, list):
                for result in external_results:
                    embedding_vector = result.get("float")
                    if embedding_vector and isinstance(embedding_vector, list):
                        break
        
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
        
        # Build the document to be stored/updated.
        document = {
            "type": CONTENT_TYPE,
            "embedding": embedding_vector,
            "embedding_scope": scope,
            "timestamp": datetime.utcnow().isoformat()
        }

        if scope == "clip" or scope == "audio":
            scope = "clip"
            # For clips, store the original asset_id and add timecodes.
            document["DigitalSourceAsset"] = {"ID": asset_id}
            document["start_timecode"] = seconds_to_smpte(item.get("start_offset_sec", None))
            document["end_timecode"] = seconds_to_smpte(item.get("end_offset_sec", None))

            # Index the document without a forced refresh.
            response = client.index(index=INDEX_NAME, body=document)
            document_id = response.get("_id", "unknown")
            logger.info(f"Successfully created new document for clip: {response}")

        else:
            # Search for an existing document by DigitalSourceAsset.ID
            search_query = {
                "query": {
                    "bool": {
                    "must": [
                        {
                        "term": {
                            "DigitalSourceAsset.ID.keyword": asset_id
                        }
                        },
                        {"exists": {"field": "InventoryID"}},
                        {
                        "exists": {
                            "field": "DerivedRepresentations.ID"
                        }
                        }
                    ]
                    }
                }
            }

            
            start_time = time.time()
            search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
            # Retry search for up to 2 minutes if the document is not found.
            while search_response["hits"]["total"]["value"] == 0 and (time.time() - start_time) < 120:
                logger.info("Document not found, refreshing index and retrying search...")
                client.indices.refresh(index=INDEX_NAME)
                time.sleep(5)
                search_response = client.search(index=INDEX_NAME, body=search_query, size=1)
            
            if search_response["hits"]["total"]["value"] == 0:
                error_msg = (f"No existing document found with DigitalSourceAsset.ID={asset_id} "
                             f"in index {INDEX_NAME} after retrying for 2 minutes")
                logger.error(error_msg)
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": error_msg})
                }
            
            # Extract the document ID.
            existing_doc_id = search_response["hits"]["hits"][0]["_id"]
            logger.info(f"Found existing document with ID: {existing_doc_id} for asset_id: {asset_id}")
            
            # Retrieve current document for sequence number and primary term.
            existing_doc = client.get(index=INDEX_NAME, id=existing_doc_id)
            current_seq_no = existing_doc.get("_seq_no")
            current_primary_term = existing_doc.get("_primary_term")
            
            # Include DigitalSourceAsset in the document.
            document["DigitalSourceAsset"] = {"ID": asset_id}
            
            # Log the document before update
            logger.info("Document before update: %s", json.dumps(document))
            
            # Retry loop for update with conflict error handling
            max_update_retries = 50
            update_attempt = 0
            while update_attempt < max_update_retries:
                try:
                    response = client.update(
                        index=INDEX_NAME,
                        id=existing_doc_id,
                        body={"doc": document},
                        if_seq_no=current_seq_no,
                        if_primary_term=current_primary_term
                    )
                    logger.info(f"Successfully updated document with optimistic concurrency: {response}")
                    break  # Exit the loop if the update succeeded
                except exceptions.ConflictError as ce:
                    update_attempt += 1
                    logger.error(f"Conflict detected on attempt {update_attempt}: {ce}")
                    # Get the latest sequence number and primary term before retrying
                    updated_doc = client.get(index=INDEX_NAME, id=existing_doc_id)
                    current_seq_no = updated_doc.get("_seq_no")
                    current_primary_term = updated_doc.get("_primary_term")
                    time.sleep(1)  # Short delay before retrying

            if update_attempt == max_update_retries:
                error_msg = "Failed to update document due to conflict errors after 50 attempts"
                logger.error(error_msg)
                return {
                    "statusCode": 409,
                    "body": json.dumps({"error": error_msg})
                }
            
            # Validation loop: ensure the updated document has the "embedding_scope" field.
            max_validation_attempts = 50
            validation_attempt = 0
            while validation_attempt < max_validation_attempts:
                updated_doc = client.get(index=INDEX_NAME, id=existing_doc_id)
                source = updated_doc.get("_source", {})
                if "embedding_scope" in source:
                    logger.info("Validation succeeded: 'embedding_scope' field found in updated document.")
                    break
                else:
                    logger.warning("Validation failed: 'embedding_scope' field not found. Re-updating document.")
                    current_seq_no = updated_doc.get("_seq_no")
                    current_primary_term = updated_doc.get("_primary_term")
                    response = client.update(
                        index=INDEX_NAME,
                        id=existing_doc_id,
                        body={"doc": document},
                        if_seq_no=current_seq_no,
                        if_primary_term=current_primary_term
                    )
                    validation_attempt += 1
                    time.sleep(5)  # Pause briefly before checking again

            if validation_attempt == max_validation_attempts:
                error_msg = "Failed to validate the update after multiple attempts. 'embedding_scope' field missing."
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Log the final updated document after validation
            logger.info("Document after update validation: %s", json.dumps(updated_doc))
            document_id = existing_doc_id
        
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
