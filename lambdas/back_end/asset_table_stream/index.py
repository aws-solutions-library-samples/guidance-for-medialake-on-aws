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

logger = Logger()

HOST = os.environ["OPENSEARCH_ENDPOINT"]
INDEX_NAME = os.environ["OPENSEARCH_INDEX"]


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
        search_query = {"query": {"term": {"inventoryId.keyword": inventory_id}}}
        return self.client.search(index=INDEX_NAME, body=search_query)

    def update_document(self, data: Dict) -> Dict:
        body = {
            "script": {
                "source": "ctx._source = params.data",
                "lang": "painless",
                "params": {"data": data},
            },
            "query": {"term": {"inventoryId.keyword": data["inventoryId"]}},
        }
        return self.client.update_by_query(index=INDEX_NAME, body=body)

    def index_document(self, data: Dict) -> Dict:
        return self.client.index(index=INDEX_NAME, body=data)

    def delete_documents(self, inventory_id: str) -> Dict:
        body = {"query": {"term": {"inventoryId.keyword": inventory_id}}}
        return self.client.delete_by_query(index=INDEX_NAME, body=body)


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
    event_name = record.event_name

    # Handle DELETE events
    if event_name == "REMOVE":
        inventory_id = record.dynamodb.old_image.get("Inventory", {}).get("InventoryID")
        if inventory_id:
            try:
                opensearch_client.delete_documents(inventory_id)
                logger.info(f"Deleted documents for inventory ID {inventory_id}")
            except Exception as e:
                logger.error(f"Error deleting documents: {str(e)}")
                raise
        return

    # Handle INSERT and MODIFY events
    if "NewImage" not in record.dynamodb:
        logger.info("No new image in record, skipping")
        return

    new_data = record.dynamodb.new_image
    normalized_data = normalize_asset_data(new_data)

    if not normalized_data:
        logger.warning("No valid asset data found in record")
        return

    try:
        if event_name == "MODIFY":
            response = opensearch_client.update_document(normalized_data)
            logger.info(f"Updated document with result: {response}")
        else:  # INSERT
            response = opensearch_client.index_document(normalized_data)
            logger.info(f"Indexed new document with result: {response}")
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
