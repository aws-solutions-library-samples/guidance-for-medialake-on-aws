import json
import boto3
from boto3.dynamodb.types import TypeDeserializer
from decimal import Decimal
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger(service="ddb-to-os-index")
tracer = Tracer()
metrics = Metrics()

# OpenSearch configuration
REGION = os.environ["OS_DOMAIN_REGION"]
HOST = os.environ["OPENSEARCH_ENDPOINT"].split("://")[-1]  # Extract hostname from URL
INDEX = os.environ["OPENSEARCH_INDEX"]
SQS_URL = os.environ["SQS_URL"]

deserializer = TypeDeserializer()


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal objects from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convert to int if it's a whole number, otherwise float
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

# Initialize AWS credentials and clients
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    'es',
    session_token=credentials.token
)
sqs = boto3.client('sqs')
opensearch_client = OpenSearch(
    hosts=[{'host': HOST, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def dynamodb_item_to_dict(item):
    """
    Convert a DynamoDB record (e.g., NewImage from a Streams event)
    into a normal Python dict.
    """
    return {k: deserializer.deserialize(v) for k, v in item.items()}


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    logger.info("Lambda invoked", extra={"aws_request_id": context.aws_request_id})
    logger.debug("Full event payload", extra={"event": event})
    try:
        for record in event.get('Records', []):
            event_name = record.get('eventName')
            logger.info(f"Processing record", extra={"eventName": event_name})

            # ---------------------------- REMOVE ----------------------------
            if event_name == 'REMOVE':
                document_id = record['dynamodb']['OldImage']['InventoryID']['S']
                logger.info(f"Deleting document from OpenSearch", extra={"document_id": document_id})

                try:
                    opensearch_client.delete(index=INDEX, id=document_id)
                    logger.info("Deleted document successfully", extra={"document_id": document_id})
                except Exception as e:
                    logger.error("Failed to delete document; sending to SQS", extra={"document_id": document_id, "error": str(e)})
                    old_doc = dynamodb_item_to_dict(record['dynamodb']['OldImage'])
                    sqs.send_message(
                        QueueUrl=SQS_URL,
                        MessageBody=json.dumps(old_doc, cls=DecimalEncoder),
                        MessageAttributes={
                            'MessageType': {'DataType': 'String', 'StringValue': 'Delete the Index'}
                        }
                    )

            # ---------------------------- INSERT ----------------------------
            elif event_name == 'INSERT':
                new_image = record['dynamodb'].get('NewImage')
                if not new_image:
                    logger.warning("INSERT event without NewImage; skipping")
                    continue

                document = dynamodb_item_to_dict(new_image)
                document_id = document['InventoryID']
                logger.info("Indexing new document", extra={"document_id": document_id})

                try:
                    opensearch_client.index(
                        index=INDEX,
                        id=document_id,
                        body=document,
                        refresh=True
                    )
                    logger.info("Indexed document successfully", extra={"document_id": document_id})
                except Exception as e:
                    logger.error("Failed to index document; sending to SQS", extra={"document_id": document_id, "error": str(e)})
                    sqs.send_message(
                        QueueUrl=SQS_URL,
                        MessageBody=json.dumps(document, cls=DecimalEncoder),
                        MessageAttributes={
                            'MessageType': {'DataType': 'String', 'StringValue': 'Insert the Index'}
                        }
                    )

            # ---------------------------- MODIFY ----------------------------
            elif event_name == 'MODIFY':
                new_image = record['dynamodb'].get('NewImage')
                if not new_image:
                    logger.warning("MODIFY event without NewImage; skipping")
                    continue

                partial_doc = dynamodb_item_to_dict(new_image)
                document_id = partial_doc['InventoryID']
                logger.info("Updating document", extra={
                    "document_id": document_id,
                    "updated_keys": list(partial_doc.keys())
                })

                try:
                    opensearch_client.update(
                        index=INDEX,
                        id=document_id,
                        body={'doc': partial_doc},
                        refresh=True
                    )
                    logger.info("Updated document successfully", extra={"document_id": document_id})
                except Exception as e:
                    logger.error("Failed to update document; sending to SQS", extra={"document_id": document_id, "error": str(e)})
                    sqs.send_message(
                        QueueUrl=SQS_URL,
                        MessageBody=json.dumps(partial_doc, cls=DecimalEncoder),
                        MessageAttributes={
                            'MessageType': {'DataType': 'String', 'StringValue': 'Modify the Index'}
                        }
                    )

        logger.info("All records processed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps('Processing completed successfully')
        }

    except Exception as e:
        logger.exception("Unhandled exception processing stream")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing stream: {e}')
        }
