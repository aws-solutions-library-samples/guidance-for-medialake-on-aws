from typing import Any, Dict, Optional
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import DynamoDBStreamEvent
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import (
    DynamoDBRecord,
)
import json
import boto3
import os
from requests_aws4auth import AWS4Auth
from opensearchpy import RequestsHttpConnection, OpenSearch, AWSV4SignerAuth
import time  # Add this import at the top with other imports

logger = Logger()

HOST = os.environ["OPENSEARCH_ENDPOINT"]
INDEX_NAME = os.environ["OPENSEARCH_INDEX"]

# Add s3 client initialization near the top with other clients
s3 = boto3.client("s3")


class OpenSearchClient:
    def __init__(self):
        self.client = self._initialize_client()

    def _initialize_client(self) -> OpenSearch:
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, "us-east-1", "aoss")
        return OpenSearch(
            hosts=[HOST],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

    def search_by_inventory_id(self, inventory_id: str) -> Dict:
        # Use term query with .keyword field for exact matching
        search_query = {"query": {"term": {"inventoryId.keyword": inventory_id}}}
        logger.info(f"Searching for inventoryId: {inventory_id}")
        logger.info(f"Search query: {json.dumps(search_query, default=str)}")

        try:
            result = self.client.search(
                index=INDEX_NAME,
                body=search_query,
                size=100,
            )
            total_hits = result["hits"]["total"]["value"]
            logger.info(f"Search found {total_hits} documents")
            logger.info(f"Raw search response: {json.dumps(result, default=str)}")
            return result
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def update_document(self, doc_id: str, data: Dict) -> Dict:
        """Update document using the update API"""
        try:
            body = {"doc": data}
            logger.info(
                f"Updating document {doc_id} with body: {json.dumps(body, default=str)}"
            )
            result = self.client.update(
                index=INDEX_NAME,
                id=doc_id,
                body=body,
            )
            logger.info(f"Update result: {json.dumps(result, default=str)}")
            return result
        except Exception as e:
            logger.error(f"Error updating document: {str(e)}")
            raise

    def index_document(self, data: Dict) -> Dict:
        """Index or update document based on inventoryId existence"""
        inventory_id = data.get("inventoryId")
        logger.info(f"Starting index_document for inventoryId: {inventory_id}")

        if not inventory_id:
            logger.error("No inventoryId provided in data")
            raise ValueError("Document must have an inventoryId")

        try:
            # Add sleep before searching
            logger.info("Sleeping for 5 seconds before searching...")
            time.sleep(20)

            # First search for existing document
            search_result = self.search_by_inventory_id(inventory_id)

            if search_result["hits"]["total"]["value"] > 0:
                # Get the _id of the first matching document
                doc_id = search_result["hits"]["hits"][0]["_id"]
                logger.info(f"Found existing document with ID: {doc_id}")

                # Update the existing document using _update endpoint
                return self.update_document(doc_id, data)
            else:
                # Create new document if none exists
                logger.info("No existing document found, creating new one")
                result = self.client.index(
                    index=INDEX_NAME,
                    body=data,
                    # refresh=True,  # Force refresh after indexing
                )
                logger.info(f"Index result: {json.dumps(result, default=str)}")
                return result
        except Exception as e:
            logger.error(f"Error in index_document: {str(e)}")
            raise

    def delete_documents(self, inventory_id: str) -> Dict:
        """Delete all documents with matching inventoryId"""
        try:
            # First search for all documents with this inventory ID
            search_result = self.search_by_inventory_id(inventory_id)
            total_hits = search_result["hits"]["total"]["value"]

            if total_hits > 0:
                logger.info(
                    f"Found {total_hits} documents to delete for inventoryId: {inventory_id}"
                )
                deletion_results = []

                # Delete each document found
                for hit in search_result["hits"]["hits"]:
                    doc_id = hit["_id"]
                    logger.info(f"Deleting document with ID: {doc_id}")

                    # Delete the document using the DELETE /{index}/_doc/{id} endpoint
                    result = self.client.delete(
                        index=INDEX_NAME,
                        id=doc_id,
                        # refresh=True  # Force refresh after deletion
                    )
                    deletion_results.append(result)
                    logger.info(
                        f"Delete result for doc {doc_id}: {json.dumps(result, default=str)}"
                    )

                return {
                    "deleted_count": len(deletion_results),
                    "results": deletion_results,
                }
            else:
                logger.warning(
                    f"No documents found to delete for inventoryId: {inventory_id}"
                )
                return {"result": "not_found", "deleted_count": 0}

        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            raise


def normalize_storage_info(storage_info: Dict) -> Dict:
    primary_location = storage_info.get("PrimaryLocation", {})
    return {
        "storageType": primary_location.get("StorageType"),
        "bucket": primary_location.get("Bucket"),
        "path": primary_location.get("ObjectKey", {}).get("FullPath"),
        "status": primary_location.get("Status"),
        "fileSize": primary_location.get("FileInfo", {}).get("Size"),
        "hashValue": primary_location.get("FileInfo", {}).get("Hash", {}).get("Value"),
    }


def normalize_image_spec(image_spec: Dict) -> Dict:
    return {
        "colorSpace": image_spec.get("ColorSpace"),
        "width": image_spec.get("Resolution", {}).get("Width"),
        "height": image_spec.get("Resolution", {}).get("Height"),
        "dpi": image_spec.get("DPI"),
    }


def normalize_representation(representation: Dict) -> Dict:
    return {
        "id": representation.get("ID"),
        "type": representation.get("Type"),
        "format": representation.get("Format"),
        "purpose": representation.get("Purpose"),
        "storage": normalize_storage_info(representation.get("StorageInfo", {})),
        "imageSpec": normalize_image_spec(representation.get("ImageSpec", {})),
    }


def normalize_asset_data(inventory_data: Dict) -> Dict:
    digital_asset = inventory_data.get("DigitalSourceAsset", {})

    # Process derived representations
    derived_representations = []
    for derived_rep in inventory_data.get("DerivedRepresentations", []):
        if derived_rep:
            normalized_derived = normalize_representation(derived_rep)
            derived_representations.append(normalized_derived)

    normalized_data = {
        "inventoryId": inventory_data.get("InventoryID"),
        "assetId": digital_asset.get("ID"),
        "assetType": digital_asset.get("Type"),
        "createDate": digital_asset.get("CreateDate"),
        "mainRepresentation": normalize_representation(
            digital_asset.get("MainRepresentation", {})
        ),
        "derivedRepresentations": derived_representations,
    }

    return normalized_data


def delete_s3_objects(asset_data: Dict) -> None:
    """Deletes all S3 objects associated with the asset"""
    try:
        # Delete main representation
        main_rep = asset_data.get("DigitalSourceAsset", {}).get(
            "MainRepresentation", {}
        )
        if main_rep:
            main_storage = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            if main_storage:
                main_bucket = main_storage.get("Bucket")
                main_key = main_storage.get("ObjectKey", {}).get("FullPath")
                if main_bucket and main_key:
                    logger.info(
                        "Deleting main representation",
                        extra={
                            "bucket": main_bucket,
                            "key": main_key,
                        },
                    )
                    s3.delete_object(Bucket=main_bucket, Key=main_key)

        # Delete derived representations
        derived_reps = asset_data.get("DerivedRepresentations", [])
        for derived in derived_reps:
            if not derived:
                continue
            storage = derived.get("StorageInfo", {}).get("PrimaryLocation", {})
            if storage:
                derived_bucket = storage.get("Bucket")
                derived_key = storage.get("ObjectKey", {}).get("FullPath")
                if derived_bucket and derived_key:
                    logger.info(
                        "Deleting derived representation",
                        extra={
                            "bucket": derived_bucket,
                            "key": derived_key,
                        },
                    )
                    s3.delete_object(Bucket=derived_bucket, Key=derived_key)

    except Exception as e:
        logger.error(f"Error deleting S3 objects: {str(e)}")
        raise


def process_dynamodb_record(
    record: DynamoDBRecord, opensearch_client: OpenSearchClient
) -> None:
    event_name = record.event_name
    logger.info(f"Processing DynamoDB record with event type: {event_name}")

    # Handle DELETE events
    if event_name == "REMOVE":
        # Get the old image (data before deletion)
        old_data = record.dynamodb.old_image
        inventory_id = old_data.get("InventoryID")
        logger.info(f"Processing DELETE event for inventoryId: {inventory_id}")

        if inventory_id:
            try:
                # First delete all S3 objects
                delete_s3_objects(old_data)
                logger.info("Successfully deleted S3 objects")

                # Then delete from OpenSearch
                delete_result = opensearch_client.delete_documents(inventory_id)
                logger.info(
                    f"Delete result from OpenSearch: {json.dumps(delete_result, default=str)}"
                )

            except Exception as e:
                logger.error(f"Error in deletion process: {str(e)}")
                raise
        return

    # Handle INSERT and MODIFY events
    if "NewImage" not in record.dynamodb:
        logger.info("No new image in record, skipping")
        return

    logger.info("Processing INSERT/MODIFY event")
    new_data = record.dynamodb.new_image
    logger.info(f"Raw DynamoDB data: {json.dumps(new_data, default=str)}")

    normalized_data = normalize_asset_data(new_data)
    logger.info(f"Normalized data: {json.dumps(normalized_data, default=str)}")

    if not normalized_data:
        logger.warning("No valid asset data found in record")
        return

    try:
        response = opensearch_client.index_document(normalized_data)
        logger.info(f"Final processing result: {json.dumps(response, default=str)}")
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise


@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    try:
        stream_event = DynamoDBStreamEvent(event)
        opensearch_client = OpenSearchClient()

        for record in stream_event.records:
            if record.event_source != "aws:dynamodb":
                logger.warning(
                    f"Skipping non-DynamoDB event source: {record.event_source}"
                )
                continue
            process_dynamodb_record(record, opensearch_client)

        return {
            "statusCode": 200,
            "body": json.dumps("Successfully processed DynamoDB Stream event"),
        }
    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error processing DynamoDB Stream event: {str(e)}"),
        }
