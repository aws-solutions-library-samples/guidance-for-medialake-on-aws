from typing import Dict, Optional, TypedDict, List
import boto3
import json
import uuid
import os
import urllib.parse
from datetime import datetime
import hashlib
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit

from botocore.exceptions import ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics()


class FileHash(TypedDict):
    Algorithm: str
    Value: str
    MD5Hash: str


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
    FileHash: str


class AssetProcessor:
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.dynamodb = boto3.resource("dynamodb").Table(os.environ["ASSETS_TABLE"])
        self.eventbridge = boto3.client("events")

    def _decode_s3_event_key(self, encoded_key: str) -> str:
        """Decode S3 event key by handling URL encoding and plus signs"""
        # First decode any URL encoding (handles %20, %2B etc.)
        decoded_key = urllib.parse.unquote(encoded_key)

        # Then handle plus signs that represent spaces
        decoded_key = decoded_key.replace("+", " ")

        return decoded_key

    def _calculate_md5(self, bucket: str, key: str) -> str:
        """Calculate MD5 hash of S3 object for file identification purposes"""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            md5_hash = hashlib.md5(usedforsecurity=False)
            for chunk in response["Body"].iter_chunks(4096):
                md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            logger.exception(
                f"Error calculating MD5 hash for {bucket}/{key}, error: {e}"
            )
            raise

    def _check_existing_file(self, md5_hash: str) -> Optional[Dict]:
        """Check if file with same MD5 hash exists"""
        try:
            response = self.dynamodb.query(
                IndexName="FileHashIndex",
                KeyConditionExpression="FileHash = :hash",
                ExpressionAttributeValues={":hash": md5_hash},
            )

            if response["Items"]:
                return response["Items"][0]
            return None
        except ClientError as e:
            logger.exception(f"Error querying DynamoDB for hash {md5_hash}, error {e}")
            raise

    @tracer.capture_method
    def process_asset(self, bucket: str, key: str) -> Optional[Dict]:
        """Process new asset from S3"""
        key = self._decode_s3_event_key(key)

        try:
            response = self.s3.head_object(Bucket=bucket, Key=key)
            existing_tags = self.s3.get_object_tagging(Bucket=bucket, Key=key)
            tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}

            # Check existing tags first
            if "InventoryID" in tags and "AssetID" in tags:
                logger.info(f"Asset already fully processed: {tags['AssetID']}")
                
                # Add logging to check if the record exists in DynamoDB
                try:
                    existing_record = self.dynamodb.get_item(
                        Key={
                            "InventoryID": tags["InventoryID"]
                        }
                    )
                    if "Item" in existing_record:
                        logger.info(f"Found existing record in DynamoDB: {json.dumps(existing_record['Item'])}")
                    else:
                        logger.warning(f"Asset has tags but no record found in DynamoDB for InventoryID: {tags['InventoryID']}")
                        
                        # Recreate the record if it doesn't exist in DynamoDB
                        logger.info(f"Recreating DynamoDB record for tagged asset: {key}")
                        
                        # Calculate MD5 hash for the file
                        md5_hash = self._calculate_md5(bucket, key)
                        
                        # Create metadata structure
                        metadata = self._create_asset_metadata(response, bucket, key, md5_hash)
                        
                        # Create DynamoDB entry using existing InventoryID and AssetID
                        asset_id = tags["AssetID"]
                        inventory_id = tags["InventoryID"]
                        
                        # Extract asset type from AssetID or content type
                        if ":" in asset_id:
                            parts = asset_id.split(":")
                            if len(parts) >= 2:
                                type_abbrev = parts[1]
                                asset_type_map = {"img": "Image", "vid": "Video", "aud": "Audio"}
                                asset_type = asset_type_map.get(type_abbrev, "Image")
                            else:
                                content_type = response.get("ContentType", "")
                                asset_type = content_type.split("/")[0].capitalize() if content_type else "Image"
                        else:
                            content_type = response.get("ContentType", "")
                            asset_type = content_type.split("/")[0].capitalize() if content_type else "Image"
                        
                        # Create the item structure
                        item = {
                            "InventoryID": inventory_id,
                            "FileHash": md5_hash,
                            "DigitalSourceAsset": {
                                "ID": asset_id,
                                "Type": asset_type,
                                "CreateDate": datetime.utcnow().isoformat(),
                                "IngestedAt": datetime.utcnow().isoformat(),
                                "MainRepresentation": {
                                    "ID": f"{asset_id}:master",
                                    "Type": asset_type,
                                    "Format": key.split(".")[-1].upper() if "." in key else "",
                                    "Purpose": "master",
                                    "StorageInfo": metadata["StorageInfo"],
                                },
                            },
                            "DerivedRepresentations": [],
                            "Metadata": metadata.get("Metadata"),
                        }
                        
                        # Log the item we're about to write
                        logger.info(f"Recreating DynamoDB item: {json.dumps(item)}")
                        
                        # Write to DynamoDB
                        try:
                            self.dynamodb.put_item(Item=item)
                            logger.info(f"Successfully recreated DynamoDB record for {inventory_id}")
                            
                            # Verify the write
                            verification = self.dynamodb.get_item(
                                Key={
                                    "InventoryID": inventory_id
                                }
                            )
                            if "Item" in verification:
                                logger.info(f"Verification successful - recreated item exists in DynamoDB")
                            else:
                                logger.warning(f"Verification failed - recreated item not found in DynamoDB")
                                
                            # Publish event for the recreated record
                            self.publish_event(
                                inventory_id,
                                asset_id,
                                metadata,
                            )
                            
                            return item
                        except Exception as e:
                            logger.exception(f"Error recreating DynamoDB record: {str(e)}")
                except Exception as e:
                    logger.exception(f"Error checking existing record in DynamoDB: {str(e)}")
                
                return None
            
            # Calculate MD5 hash for duplicate checking
            md5_hash = self._calculate_md5(bucket, key)
            
            # Check if file with same hash exists in DynamoDB
            existing_file = self._check_existing_file(md5_hash)
            
            if existing_file:
                logger.info(f"Duplicate file found with hash {md5_hash}")
                
                # If we have InventoryID tag but no AssetID tag, generate new AssetID under existing inventory
                if "InventoryID" in tags and "AssetID" not in tags:
                    logger.info(f"Object has InventoryID but no AssetID. Generating new AssetID under existing inventory.")
                    
                    # Extract asset type from content type
                    content_type = response.get("ContentType", "")
                    asset_type = content_type.split("/")[0].capitalize() if content_type else "Image"
                    type_abbreviations = {"Image": "img", "Video": "vid", "Audio": "aud"}
                    type_abbrev = type_abbreviations.get(asset_type, "img")
                    
                    # Generate new AssetID
                    new_asset_id = f"asset:{type_abbrev}:{str(uuid.uuid4())}"
                    
                    # Tag with existing InventoryID and new AssetID
                    self.s3.put_object_tagging(
                        Bucket=bucket,
                        Key=key,
                        Tagging={
                            "TagSet": [
                                {"Key": "InventoryID", "Value": tags["InventoryID"]},
                                {"Key": "AssetID", "Value": new_asset_id},
                                {"Key": "FileHash", "Value": md5_hash},
                            ]
                        },
                    )
                    
                    # Create new asset entry with existing inventory ID
                    metadata = self._create_asset_metadata(response, bucket, key, md5_hash)
                    dynamo_entry = self.create_dynamo_entry(metadata, inventory_id=tags["InventoryID"])
                    
                    self.publish_event(
                        dynamo_entry["InventoryID"],
                        dynamo_entry["DigitalSourceAsset"]["ID"],
                        metadata,
                    )
                    
                    return dynamo_entry
                
                # If hash exists in DB but object has no tags, tag with existing IDs and stop processing
                if "InventoryID" not in tags and "AssetID" not in tags:
                    logger.info(f"Hash exists in DB but object has no tags. Tagging with existing IDs.")
                    self.s3.put_object_tagging(
                        Bucket=bucket,
                        Key=key,
                        Tagging={
                            "TagSet": [
                                {"Key": "InventoryID", "Value": existing_file["InventoryID"]},
                                {"Key": "AssetID", "Value": existing_file["DigitalSourceAsset"]["ID"]},
                                {"Key": "FileHash", "Value": md5_hash},
                                {"Key": "DuplicateHash", "Value": "true"},
                            ]
                        },
                    )
                    return None
                
                # Handle other cases from existing code
                existing_object_key = (
                    existing_file.get("DigitalSourceAsset", {})
                    .get("MainRepresentation", {})
                    .get("StorageInfo", {})
                    .get("PrimaryLocation", {})
                    .get("ObjectKey", {})
                    .get("FullPath")
                )

                if existing_object_key == key:
                    logger.info(
                        "Duplicate file with same object key. Tagging with existing IDs"
                    )
                    # Tag with the same IDs as the existing file
                    self.s3.put_object_tagging(
                        Bucket=bucket,
                        Key=key,
                        Tagging={
                            "TagSet": [
                                {
                                    "Key": "InventoryID",
                                    "Value": existing_file["InventoryID"],
                                },
                                {
                                    "Key": "AssetID",
                                    "Value": existing_file["DigitalSourceAsset"]["ID"],
                                },
                                {"Key": "FileHash", "Value": md5_hash},
                            ]
                        },
                    )
                    return None
                else:
                    # Same hash but different key - tag with same InventoryID but new AssetID
                    logger.info(
                        "Same hash but different key. Tagging with same InventoryID but new AssetID"
                    )
                    # Extract asset type from content type
                    content_type = response.get("ContentType", "")
                    asset_type = content_type.split("/")[0].capitalize() if content_type else "Image"
                    type_abbreviations = {"Image": "img", "Video": "vid", "Audio": "aud"}
                    type_abbrev = type_abbreviations.get(asset_type, "img")
                    
                    new_asset_id = f"asset:{type_abbrev}:{str(uuid.uuid4())}"
                    self.s3.put_object_tagging(
                        Bucket=bucket,
                        Key=key,
                        Tagging={
                            "TagSet": [
                                {
                                    "Key": "InventoryID",
                                    "Value": existing_file["InventoryID"],
                                },
                                {
                                    "Key": "AssetID",
                                    "Value": new_asset_id,
                                },
                                {"Key": "FileHash", "Value": md5_hash},
                                {
                                    "Key": "DuplicateHash",
                                    "Value": "true",
                                },
                            ]
                        },
                    )
                    return None

            # Process new unique file...
            metadata = self._create_asset_metadata(response, bucket, key, md5_hash)
            
            # If we have InventoryID tag but no AssetID tag, use existing inventory
            if "InventoryID" in tags and "AssetID" not in tags:
                logger.info(f"Using existing InventoryID: {tags['InventoryID']}")
                dynamo_entry = self.create_dynamo_entry(metadata, inventory_id=tags["InventoryID"])
            else:
                # Normal processing for new file
                dynamo_entry = self.create_dynamo_entry(metadata)

            # Add tags to S3 object
            self.s3.put_object_tagging(
                Bucket=bucket,
                Key=key,
                Tagging={
                    "TagSet": [
                        {"Key": "InventoryID", "Value": dynamo_entry["InventoryID"]},
                        {
                            "Key": "AssetID",
                            "Value": dynamo_entry["DigitalSourceAsset"]["ID"],
                        },
                        {"Key": "FileHash", "Value": md5_hash},
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
            logger.exception(f"Error processing asset: {key}, error: {e}")
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
                            "MD5Hash": md5_hash,  # Add MD5 hash to metadata
                        },
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
    def create_dynamo_entry(self, metadata: StorageInfo, inventory_id: str = None) -> AssetRecord:
        """Create DynamoDB entry for the asset"""
        if not inventory_id:
            inventory_id = f"asset:uuid:{str(uuid.uuid4())}"
        else:
            # Use the provided inventory_id if it exists
            if not inventory_id.startswith("asset:uuid:"):
                inventory_id = f"asset:uuid:{inventory_id}"
        
        asset_id = str(uuid.uuid4())

        # Extract and capitalize the first part of the MIME type
        content_type = (
            metadata.get("Metadata", {})
            .get("Embedded", {})
            .get("S3", {})
            .get("ContentType", "")
        )
        asset_type = (
            content_type.split("/")[0].capitalize() if content_type else "Image"
        )

        # Map asset types to their abbreviations
        type_abbreviations = {
            "Image": "img",
            "Video": "vid",
            "Audio": "aud"
        }
        type_abbrev = type_abbreviations.get(asset_type, "img")  # Default to "img" if type not found

        item: AssetRecord = {
            "InventoryID": inventory_id,
            "FileHash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"]["Hash"][
                "MD5Hash"
            ],
            "DigitalSourceAsset": {
                "ID": f"asset:{type_abbrev}:{asset_id}",
                "Type": asset_type,
                "CreateDate": datetime.utcnow().isoformat(),
                "IngestedAt": datetime.utcnow().isoformat(),
                "MainRepresentation": {
                    "ID": f"asset:rep:{asset_id}:master",
                    "Type": asset_type,
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

        # Add detailed logging before DynamoDB operation
        logger.info(f"Attempting to write to DynamoDB table: {os.environ['ASSETS_TABLE']}")
        logger.info(f"Item to be written: {json.dumps(item)}")
        
        try:
            response = self.dynamodb.put_item(Item=item)
            logger.info(f"DynamoDB put_item response: {json.dumps(response)}")
            
            # Verify the item was written by doing a get_item
            verification_response = self.dynamodb.get_item(
                Key={
                    "InventoryID": inventory_id
                }
            )
            
            if "Item" in verification_response:
                logger.info(f"Verification successful - item exists in DynamoDB")
            else:
                logger.warning(f"Verification failed - item not found in DynamoDB after put_item")
            
        except Exception as e:
            logger.exception(f"Error writing to DynamoDB: {str(e)}")
            raise
        
        return item

    @tracer.capture_method
    def publish_event(self, inventory_id: str, asset_id: str, metadata: StorageInfo):
        """Publish event to EventBridge using the same structure"""
        try:
            content_type = (
                metadata.get("Metadata", {})
                .get("Embedded", {})
                .get("S3", {})
                .get("ContentType", "")
            )
            asset_type = (
                content_type.split("/")[0].capitalize() if content_type else "Image"
            )

            event_detail: AssetRecord = {
                "InventoryID": inventory_id,
                "FileHash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"][
                    "Hash"
                ]["MD5Hash"],
                "DigitalSourceAsset": {
                    "ID": asset_id,
                    "Type": asset_type,
                    "CreateDate": datetime.utcnow().isoformat(),
                    "MainRepresentation": {
                        "ID": f"{asset_id}:master",
                        "Type": asset_type,
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

    @tracer.capture_method
    def delete_asset(self, bucket: str, key: str) -> None:
        """Delete asset record from DynamoDB based on S3 object deletion"""
        try:
            # First get the object tags to find the InventoryID
            try:
                existing_tags = self.s3.get_object_tagging(Bucket=bucket, Key=key)
                tags = {
                    tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])
                }
            except self.s3.exceptions.NoSuchKey:
                # Object is already deleted, try to find by key
                logger.info(f"Object already deleted, searching by key: {key}")
                tags = {}

            if "InventoryID" in tags:
                inventory_id = tags["InventoryID"]
                logger.info(f"Deleting asset with InventoryID: {inventory_id}")

                # Delete from DynamoDB
                self.dynamodb.delete_item(
                    Key={
                        "InventoryID": inventory_id,
                        "ID": "asset",  # Using 'asset' as the sort key
                    }
                )

                # Publish deletion event
                self.publish_deletion_event(inventory_id)

                logger.info(f"Successfully deleted asset: {inventory_id}")
            else:
                logger.warning(f"No InventoryID tag found for object: {bucket}/{key}")

        except Exception as e:
            logger.exception(f"Error deleting asset: {bucket}/{key}, error: {e}")
            raise

    @tracer.capture_method
    def publish_deletion_event(self, inventory_id: str):
        """Publish asset deletion event to EventBridge"""
        try:
            event_detail = {
                "InventoryID": inventory_id,
                "DeletedAt": datetime.utcnow().isoformat(),
            }

            logger.info(f"Publishing deletion event: {json.dumps(event_detail)}")

            response = self.eventbridge.put_events(
                Entries=[
                    {
                        "Source": "custom.asset.processor",
                        "DetailType": "AssetDeleted",
                        "Detail": json.dumps(event_detail),
                        "EventBusName": os.environ["EVENT_BUS_NAME"],
                    }
                ]
            )

            logger.info(f"EventBridge response: {json.dumps(response)}")

        except Exception as e:
            logger.exception(f"Error publishing deletion event: {str(e)}")
            raise


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict, context: LambdaContext) -> Dict:
    """Handle S3 events via SQS from either direct S3 notifications or EventBridge Pipes"""
    processor = AssetProcessor()

    # Log environment variables for debugging
    logger.info(f"Environment variables: ASSETS_TABLE={os.environ.get('ASSETS_TABLE')}, EVENT_BUS_NAME={os.environ.get('EVENT_BUS_NAME')}")
    
    # Check DynamoDB table exists and is accessible
    try:
        # Fix: Use the boto3 client directly instead of trying to access through the Table object
        dynamodb_client = boto3.client('dynamodb')
        table_info = dynamodb_client.describe_table(
            TableName=os.environ["ASSETS_TABLE"]
        )
        logger.info(f"DynamoDB table info: {json.dumps(table_info)}")
    except Exception as e:
        logger.exception(f"Error accessing DynamoDB table: {str(e)}")
    
    try:
        # Process each record directly since event is already a list
        for record in event:
            try:
                # Log the raw message for debugging
                logger.debug(f"Processing SQS record: {json.dumps(record)}")

                # Extract and parse the message body
                if "body" not in record:
                    logger.warning("No body found in SQS record")
                    continue

                # Try to parse the body as JSON
                try:
                    body = json.loads(record["body"])
                except json.JSONDecodeError:
                    # If it's not valid JSON, use the raw body
                    logger.warning("Failed to parse body as JSON, using raw body")
                    body = record["body"]

                # Check if this is a test event
                if isinstance(body, dict) and body.get("Event") == "s3:TestEvent":
                    logger.info("Received S3 test event - skipping processing")
                    continue

                # Handle both direct S3 events and EventBridge events
                if isinstance(body, dict) and "Records" in body:
                    # Direct S3 event format
                    for s3_record in body["Records"]:
                        if "s3" not in s3_record:
                            logger.warning("No S3 data in record")
                            continue

                        bucket = s3_record["s3"]["bucket"]["name"]
                        key = s3_record["s3"]["object"]["key"]
                        event_name = s3_record.get("eventName", "")

                        process_s3_event(processor, bucket, key, event_name)

                elif isinstance(body, dict) and "detail-type" in body:
                    # EventBridge event format
                    logger.info(f"Processing EventBridge event: {json.dumps(body)}")
                    
                    if body.get("source") != "aws.s3":
                        logger.warning(f"Unexpected event source: {body.get('source')}")
                        continue

                    detail = body.get("detail", {})
                    
                    # Extract bucket and key information based on EventBridge S3 event structure
                    bucket = detail.get("bucket", {}).get("name")
                    
                    # Handle different object key locations in EventBridge events
                    key = None
                    if "object" in detail and isinstance(detail["object"], dict):
                        key = detail["object"].get("key")
                    elif "object" in detail and isinstance(detail["object"], str):
                        key = detail["object"]
                    
                    # If key is still None, try other possible locations
                    if key is None and "key" in detail:
                        key = detail["key"]
                    
                    # Map EventBridge detail-type to S3 event name
                    detail_type = body.get("detail-type", "")
                    event_type_mapping = {
                        "Object Created": "ObjectCreated:",
                        "Object Deleted": "ObjectRemoved:",
                        "Object Restored": "ObjectRestore:",
                        "Object Tagged": "ObjectTagging:",
                        "PutObject": "ObjectCreated:Put",
                        "CompleteMultipartUpload": "ObjectCreated:CompleteMultipartUpload",
                        "DeleteObject": "ObjectRemoved:Delete"
                    }
                    
                    event_name = event_type_mapping.get(detail_type, "")
                    
                    # If we couldn't map the detail-type, try to infer from the event name
                    if not event_name and "name" in detail:
                        event_detail_name = detail["name"]
                        if "Created" in event_detail_name or "Put" in event_detail_name:
                            event_name = "ObjectCreated:"
                        elif "Deleted" in event_detail_name or "Remove" in event_detail_name:
                            event_name = "ObjectRemoved:"
                    
                    # Log the extracted information
                    logger.info(f"Extracted from EventBridge: bucket={bucket}, key={key}, event_name={event_name}")
                    
                    if not bucket or not key:
                        logger.warning(f"Missing required fields in EventBridge event. Detail: {json.dumps(detail)}")
                        continue

                    process_s3_event(processor, bucket, key, event_name)
                
                # Handle raw EventBridge events (not wrapped in SQS)
                elif isinstance(record, dict) and "detail-type" in record and "source" in record:
                    logger.info(f"Processing direct EventBridge event: {json.dumps(record)}")
                    
                    if record.get("source") != "aws.s3":
                        logger.warning(f"Unexpected event source: {record.get('source')}")
                        continue
                        
                    detail = record.get("detail", {})
                    
                    # Extract bucket and key information
                    bucket = detail.get("bucket", {}).get("name")
                    
                    # Handle different object key locations
                    key = None
                    if "object" in detail and isinstance(detail["object"], dict):
                        key = detail["object"].get("key")
                    elif "object" in detail and isinstance(detail["object"], str):
                        key = detail["object"]
                    
                    # If key is still None, try other possible locations
                    if key is None and "key" in detail:
                        key = detail["key"]
                    
                    # Map EventBridge detail-type to S3 event name
                    detail_type = record.get("detail-type", "")
                    event_type_mapping = {
                        "Object Created": "ObjectCreated:",
                        "Object Deleted": "ObjectRemoved:",
                        "Object Restored": "ObjectRestore:",
                        "Object Tagged": "ObjectTagging:",
                        "PutObject": "ObjectCreated:Put",
                        "CompleteMultipartUpload": "ObjectCreated:CompleteMultipartUpload",
                        "DeleteObject": "ObjectRemoved:Delete"
                    }
                    
                    event_name = event_type_mapping.get(detail_type, "")
                    
                    # Log the extracted information
                    logger.info(f"Extracted from direct EventBridge: bucket={bucket}, key={key}, event_name={event_name}")
                    
                    if not bucket or not key:
                        logger.warning(f"Missing required fields in direct EventBridge event. Detail: {json.dumps(detail)}")
                        continue

                    process_s3_event(processor, bucket, key, event_name)

                else:
                    logger.warning(f"Unrecognized event format: {json.dumps(body) if isinstance(body, dict) else body}")

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

def process_s3_event(processor: AssetProcessor, bucket: str, key: str, event_name: str):
    """Process a single S3 event"""
    logger.info(f"Processing {event_name} event for asset: {key}")

    if event_name.startswith("ObjectRemoved:"):
        # Handle deletion
        processor.delete_asset(bucket, key)
        metrics.add_metric(name="DeletedAssets", unit=MetricUnit.Count, value=1)
        logger.info(f"Asset deletion processed: {key}")
    else:
        # Handle creation/modification
        try:
            result = processor.process_asset(bucket, key)
            if result:
                metrics.add_metric(name="ProcessedAssets", unit=MetricUnit.Count, value=1)
                logger.info(f"Asset processed successfully: {result['DigitalSourceAsset']['ID']}")
                
                # Verify the item exists in DynamoDB
                try:
                    verification = processor.dynamodb.get_item(
                        Key={
                            "InventoryID": result["InventoryID"]
                        }
                    )
                    if "Item" in verification:
                        logger.info(f"Verified item exists in DynamoDB with InventoryID: {result['InventoryID']}")
                    else:
                        logger.warning(f"Item not found in DynamoDB after processing with InventoryID: {result['InventoryID']}")
                except Exception as e:
                    logger.exception(f"Error verifying item in DynamoDB: {str(e)}")
            else:
                logger.info(f"Asset already processed or skipped: {key}")
        except Exception as e:
            logger.exception(f"Error in process_asset for {bucket}/{key}: {str(e)}")