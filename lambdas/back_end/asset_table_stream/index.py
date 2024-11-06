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
from opensearchpy import RequestsHttpConnection, RequestsAWSV4SignerAuth, OpenSearch

# Initialize AWS Lambda Powertools
logger = Logger()

# OpenSearch configuration
HOST = os.environ["OPENSEARCH_ENDPOINT"]
INDEX_NAME = os.environ["OPENSEARCH_INDEX"]


class OpenSearchClient:
    def __init__(self):
        self.client = self._initialize_client()

    def _initialize_client(self) -> OpenSearch:
        auth = RequestsAWSV4SignerAuth(
            boto3.Session().get_credentials(), "us-east-1", "aoss"
        )
        return OpenSearch(
            hosts=[{"host": HOST, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

    def search_by_inventory_id(self, inventory_id: str) -> Dict:
        search_query = {"query": {"term": {"InventoryID.keyword": inventory_id}}}
        return self.client.search(index=INDEX_NAME, body=search_query)

    def update_document(self, doc_id: str, data: Dict) -> Dict:
        return self.client.update(
            index=INDEX_NAME, id=doc_id, body={"doc": data}, refresh=True
        )

    def index_document(self, doc_id: str, data: Dict) -> Dict:
        return self.client.index(index=INDEX_NAME, body=data, id=doc_id, refresh=True)

    def delete_document(self, doc_id: str) -> Dict:
        return self.client.delete(index=INDEX_NAME, id=doc_id, refresh=True)


def normalize_storage_info(storage_info: Dict) -> Dict:
    """Normalize storage information for OpenSearch indexing"""
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
    """Normalize image specifications for OpenSearch indexing"""
    return {
        "colorSpace": image_spec.get("ColorSpace"),
        "width": image_spec.get("Resolution", {}).get("Width"),
        "height": image_spec.get("Resolution", {}).get("Height"),
        "dpi": image_spec.get("DPI"),
    }


def normalize_representation(representation: Dict) -> Dict:
    """Normalize representation data for OpenSearch indexing"""
    return {
        "id": representation.get("ID"),
        "type": representation.get("Type"),
        "format": representation.get("Format"),
        "purpose": representation.get("Purpose"),
        "storage": normalize_storage_info(representation.get("StorageInfo", {})),
        "imageSpec": normalize_image_spec(representation.get("ImageSpec", {})),
    }


def normalize_asset_data(inventory_data: Dict) -> Dict:
    """Normalize the asset data for OpenSearch indexing"""
    digital_asset = inventory_data.get("DigitalSourceAsset", {})

    normalized_data = {
        "inventoryId": inventory_data.get("InventoryID"),
        "assetId": digital_asset.get("ID"),
        "assetType": digital_asset.get("Type"),
        "createDate": digital_asset.get("CreateDate"),
        "mainRepresentation": normalize_representation(
            digital_asset.get("MainRepresentation", {})
        ),
        "derivedRepresentations": [],
    }

    return normalized_data


def process_dynamodb_record(
    record: DynamoDBRecord, opensearch_client: OpenSearchClient
) -> None:
    """Process a single DynamoDB Stream record"""
    event_name = record.event_name

    # Handle DELETE events
    if event_name == "REMOVE":
        inventory_id = record.dynamodb.old_image.get("Inventory", {}).get("InventoryID")
        if inventory_id:
            try:
                search_result = opensearch_client.search_by_inventory_id(inventory_id)
                if search_result["hits"]["total"]["value"] > 0:
                    doc_id = search_result["hits"]["hits"][0]["_id"]
                    opensearch_client.delete_document(doc_id)
                    logger.info(f"Deleted document {doc_id} from OpenSearch")
            except Exception as e:
                logger.error(f"Error deleting document: {str(e)}")
                raise
        return

    # Handle INSERT and MODIFY events
    if "NewImage" not in record.dynamodb:
        logger.info("No new image in record, skipping")
        return

    # Get the new data
    new_data = record.dynamodb.new_image

    # Normalize the data for OpenSearch
    normalized_data = normalize_asset_data(new_data)
    print(normalized_data)
    if not normalized_data:
        logger.warning("No valid asset data found in record")
        return

    inventory_id = normalized_data["inventoryId"]

    try:
        # Search for existing document
        search_result = opensearch_client.search_by_inventory_id(inventory_id)

        if search_result["hits"]["total"]["value"] > 0:
            # Update existing document
            existing_doc_id = search_result["hits"]["hits"][0]["_id"]
            response = opensearch_client.update_document(
                existing_doc_id, normalized_data
            )
            logger.info(
                f"Updated document {existing_doc_id} with result: {response.get('result', 'unknown')}"
            )
        else:
            # Index new document
            response = opensearch_client.index_document(inventory_id, normalized_data)
            logger.info(
                f"Indexed new document {inventory_id} with result: {response.get('result', 'unknown')}"
            )
    except Exception as e:
        logger.error(f"Error processing document {inventory_id}: {str(e)}")
        raise


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for processing DynamoDB Stream events and syncing to OpenSearch
    """
    try:
        stream_event = DynamoDBStreamEvent(event)
        opensearch_client = OpenSearchClient()

        for record in stream_event.records:
            if record.event_source != "aws:dynamodb":
                logger.warning(
                    f"Skipping non-DynamoDB event source: {record.event_source}"
                )
                continue
            print(record)
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
