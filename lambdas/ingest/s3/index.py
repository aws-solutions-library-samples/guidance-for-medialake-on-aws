from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from typing import Dict, Optional, TypedDict, List
import boto3
import json
import uuid
import os
import urllib.parse
from datetime import datetime
import hashlib
from botocore.exceptions import ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics()


class FileHash(TypedDict):
    Algorithm: str
    Value: str


class FileInfo(TypedDict):
    Size: int
    Hash: FileHash
    CreateDate: str


class ObjectKey(TypedDict):
    Name: str
    Path: str
    FullPath: str


class PrimaryLocation(TypedDict):
    StorageType: str
    Bucket: str
    ObjectKey: ObjectKey
    Status: str
    FileInfo: FileInfo


class StorageInfo(TypedDict):
    PrimaryLocation: PrimaryLocation


class S3Metadata(TypedDict):
    Metadata: Dict
    ContentType: str
    LastModified: str


class EmbeddedMetadata(TypedDict):
    ExtractedDate: str
    S3: S3Metadata


class AssetMetadata(TypedDict):
    Embedded: EmbeddedMetadata


class AssetRepresentation(TypedDict):
    ID: str
    Type: str
    Format: str
    Purpose: str
    StorageInfo: StorageInfo


class DigitalSourceAsset(TypedDict):
    ID: str
    Type: str
    CreateDate: str
    MainRepresentation: AssetRepresentation


class AssetRecord(TypedDict):
    InventoryID: str
    DigitalSourceAsset: DigitalSourceAsset
    DerivedRepresentations: Optional[List[AssetRepresentation]]
    Metadata: Optional[AssetMetadata]


class AssetProcessor:
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.dynamodb = boto3.resource("dynamodb").Table(os.environ["ASSETS_TABLE"])
        self.eventbridge = boto3.client("events")


    def _decode_s3_event_key(self,encoded_key):
        # First decode any URL encoding (handles %20, %2B etc.)
        decoded_key = urllib.parse.unquote(encoded_key)
        
        # Then handle plus signs that represent spaces
        decoded_key = decoded_key.replace("+", " ")
        
        return decoded_key

    def _calculate_md5(self, bucket: str, key: str) -> str:
        """Calculate MD5 hash of S3 object"""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            md5_hash = hashlib.md5()
            for chunk in response['Body'].iter_chunks(4096):
                md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            logger.exception(f"Error calculating MD5 hash for {bucket}/{key}")
            raise

    def _check_existing_file(self, md5_hash: str) -> Optional[Dict]:
        """Check if file with same MD5 hash exists"""
        try:
            response = self.dynamodb.query(
                IndexName='FileHashIndex',
                KeyConditionExpression='FileHash = :hash',
                ExpressionAttributeValues={
                    ':hash': md5_hash
                }
            )
            
            if response['Items']:
                return response['Items'][0]
            return None
        except ClientError as e:
            logger.exception(f"Error querying DynamoDB for hash {md5_hash}")
            raise

    @tracer.capture_method
    def process_asset(self, bucket: str, key: str) -> Optional[Dict]:
        """Process new asset from S3"""
        key = self._decode_s3_event_key(key)
        
        try:
            response = self.s3.head_object(Bucket=bucket, Key=key)
            existing_tags = self.s3.get_object_tagging(Bucket=bucket, Key=key)
            tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}

            if "AssetID" in tags:
                logger.info(f"Asset already processed: {tags['AssetID']}")
                return None

            # Calculate MD5 hash and check for duplicates
            md5_hash = self._calculate_md5(bucket, key)
            existing_file = self._check_existing_file(md5_hash)
            
            if existing_file:
                logger.info(f"Duplicate file found with hash {md5_hash}")
                # Tag the duplicate file with reference to original
                self.s3.put_object_tagging(
                    Bucket=bucket,
                    Key=key,
                    Tagging={
                        "TagSet": [
                            {"Key": "DuplicateOf", "Value": existing_file["InventoryID"]},
                            {"Key": "FileHash", "Value": md5_hash}
                        ]
                    }
                )
                return None

            metadata = self._create_asset_metadata(response, bucket, key, md5_hash)
            dynamo_entry = self.create_dynamo_entry(metadata)

            # Add tags to S3 object
            self.s3.put_object_tagging(
                Bucket=bucket,
                Key=key,
                Tagging={
                    "TagSet": [
                        {"Key": "InventoryID", "Value": dynamo_entry["InventoryID"]},
                        {"Key": "AssetID", "Value": dynamo_entry["DigitalSourceAsset"]["ID"]},
                        {"Key": "FileHash", "Value": md5_hash}
                    ]
                },
            )

            self.publish_event(
                dynamo_entry["InventoryID"],
                dynamo_entry["DigitalSourceAsset"]["ID"],
                metadata,
            )

            return dynamo_entry

        except Exception as e:
            logger.exception(f"Error processing asset: {key}")
            raise

    def _create_asset_metadata(
        self, s3_response: Dict, bucket: str, key: str, md5_hash: str
    ) -> StorageInfo:
        """Create asset metadata structure"""
        return {
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Bucket": bucket,
                    "ObjectKey": {
                        "Name": key.split("/")[-1],
                        "Path": "/".join(key.split("/")[:-1]),
                        "FullPath": key,
                    },
                    "Status": "active",
                    "FileInfo": {
                        "Size": s3_response["ContentLength"],
                        "Hash": {
                            "Algorithm": "SHA256",
                            "Value": s3_response["ETag"].strip('"'),
                        },
                        "MD5Hash": md5_hash,  # Add MD5 hash to metadata
                        "CreateDate": s3_response["LastModified"].isoformat(),
                    },
                }
            },
            "Metadata": {
                "Embedded": {
                    "ExtractedDate": datetime.utcnow().isoformat(),
                    "S3": {
                        "Metadata": s3_response.get("Metadata", {}),
                        "ContentType": s3_response.get("ContentType"),
                        "LastModified": s3_response["LastModified"].isoformat(),
                    },
                }
            },
        }

    @tracer.capture_method
    def create_dynamo_entry(self, metadata: StorageInfo) -> AssetRecord:
        """Create DynamoDB entry for the asset"""
        inventory_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        item: AssetRecord = {
            "InventoryID": f"asset:uuid:{inventory_id}",
            "FileHash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"]["MD5Hash"],  # Add FileHash as top-level attribute
            "DigitalSourceAsset": {
                "ID": f"asset:img:{asset_id}",
                "Type": "Image",
                "CreateDate": datetime.utcnow().isoformat(),
                "MainRepresentation": {
                    "ID": f"asset:rep:{asset_id}:master",
                    "Type": "Image",
                    "Format": metadata["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                        "Name"
                    ]
                    .split(".")[-1]
                    .upper(),
                    "Purpose": "master",
                    "StorageInfo": metadata["StorageInfo"],
                },
            },
            "DerivedRepresentations": [],
            "Metadata": metadata.get("Metadata"),
        }

        self.dynamodb.put_item(Item=item)
        return item

    @tracer.capture_method
    def publish_event(self, inventory_id: str, asset_id: str, metadata: StorageInfo):
        """Publish event to EventBridge using the same structure"""
        try:
            event_detail: AssetRecord = {
                "InventoryID": inventory_id,
                "DigitalSourceAsset": {
                    "ID": asset_id,
                    "Type": "Image",
                    "CreateDate": datetime.utcnow().isoformat(),
                    "MainRepresentation": {
                        "ID": f"{asset_id}:master",
                        "Type": "Image",
                        "Format": metadata["StorageInfo"]["PrimaryLocation"][
                            "ObjectKey"
                        ]["Name"]
                        .split(".")[-1]
                        .upper(),
                        "Purpose": "master",
                        "StorageInfo": metadata["StorageInfo"],
                    },
                },
                "DerivedRepresentations": [],
                "Metadata": metadata.get("Metadata"),
            }

            logger.info(f"Publishing event with detail: {json.dumps(event_detail)}")

            response = self.eventbridge.put_events(
                Entries=[
                    {
                        "Source": "custom.asset.processor",
                        "DetailType": "AssetCreated",
                        "Detail": json.dumps(event_detail),
                        "EventBusName": os.environ["EVENT_BUS_NAME"],
                    }
                ]
            )

            logger.info(f"EventBridge response: {json.dumps(response)}")

        except Exception as e:
            logger.exception(f"Error publishing event: {str(e)}")
            raise


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict, context: LambdaContext) -> Dict:
    """Handle S3 events via SQS"""
    processor = AssetProcessor()

    try:
        # Process each record from SQS
        for record in event.get("Records", []):
            try:
                # Log the raw message for debugging
                logger.debug(f"Processing SQS record: {json.dumps(record)}")

                # Extract and parse the message body
                if "body" not in record:
                    logger.warning("No body found in SQS record")
                    continue

                body = json.loads(record["body"])

                # Check if this is a test event
                if body.get("Event") == "s3:TestEvent":
                    logger.info("Received S3 test event - skipping processing")
                    continue

                # Handle S3 event directly from SQS message
                if "Records" in body:
                    for s3_record in body["Records"]:
                        if "s3" not in s3_record:
                            logger.warning("No S3 data in record")
                            continue

                        bucket = s3_record["s3"]["bucket"]["name"]
                        key = s3_record["s3"]["object"]["key"]

                        logger.info(f"Processing asset: {key}")

                        result = processor.process_asset(bucket, key)

                        if result:
                            metrics.add_metric(
                                name="ProcessedAssets", unit=MetricUnit.Count, value=1
                            )
                            logger.info(
                                f"Asset processed successfully: {result['DigitalSourceAsset']['ID']}"
                            )
                        else:
                            logger.info(f"Asset already processed: {key}")
                else:
                    logger.warning("No Records found in message body")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse SQS message body: {e}")
                continue
            except KeyError as e:
                logger.error(f"Missing required field in event structure: {e}")
                continue
            except Exception as e:
                logger.exception(f"Error processing record: {e}")
                continue

        return {"statusCode": 200, "body": "Processing complete"}

    except Exception as e:
        logger.exception("Error in handler")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        raise
