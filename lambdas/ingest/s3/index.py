from typing import Dict, Optional, TypedDict, List, Any
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
from aws_lambda_powertools.utilities.validation import validate, validator
from aws_lambda_powertools.utilities.validation.exceptions import SchemaValidationError
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source

from botocore.exceptions import ClientError

# Import libraries for file type detection and metadata extraction
try:
    import magic
    from io import BytesIO
    from PIL import Image
    import ffmpeg
    import mutagen
except ImportError:
    pass  # Libraries will be available in Lambda layer

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Define S3 event schema for validation
S3_EVENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "Records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "eventName": {"type": "string"},
                    "s3": {
                        "type": "object",
                        "properties": {
                            "bucket": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"}
                                },
                                "required": ["name"]
                            },
                            "object": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"}
                                },
                                "required": ["key"]
                            }
                        },
                        "required": ["bucket", "object"]
                    }
                },
                "required": ["eventName", "s3"]
            }
        }
    },
    "required": ["Records"]
}

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
            # Get the object's ETag which is usually the MD5 hash for non-multipart uploads
            response = self.s3.head_object(Bucket=bucket, Key=key)
            etag = response.get('ETag', '').strip('"')
            
            # If this is a multipart upload (ETag contains a dash), we need to calculate our own MD5
            if '-' in etag:
                # Only read the first 8KB of the file for header analysis
                response = self.s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-8191')
                md5_hash = hashlib.md5(usedforsecurity=False)
                md5_hash.update(response["Body"].read())
                return md5_hash.hexdigest()
            
            return etag
        except Exception as e:
            logger.exception(
                f"Error calculating MD5 hash for {bucket}/{key}, error: {e}"
            )
            raise

    @tracer.capture_method
    def _detect_file_type(self, bucket: str, key: str) -> Dict[str, Any]:
        """Detect file type and extract technical metadata from file header"""
        try:
            # Only read the first 8KB of the file for header analysis
            response = self.s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-8191')
            header_bytes = response["Body"].read()
            
            # Add metadata to trace
            tracer.add_metadata(key="file_size", value=response.get("ContentLength", 0))
            tracer.add_metadata(key="content_type", value=response.get("ContentType", "unknown"))
            
            # Use python-magic to detect file type from header bytes
            mime_type = magic.from_buffer(header_bytes, mime=True)
            file_type = mime_type.split('/')[0].capitalize()
            
            # Add file type to trace
            tracer.add_annotation(key="file_type", value=file_type)
            
            # Extract basic technical metadata
            technical_metadata = {
                "MimeType": mime_type,
                "FileType": file_type,
                "FileExtension": key.split('.')[-1] if '.' in key else '',
            }
            
            # Add more specific metadata based on file type
            if file_type == "Image":
                try:
                    img = Image.open(BytesIO(header_bytes))
                    technical_metadata.update({
                        "Width": img.width,
                        "Height": img.height,
                        "Format": img.format,
                        "Mode": img.mode,
                    })
                except Exception as e:
                    logger.warning(f"Could not extract image metadata: {e}")
            
            elif file_type == "Video":
                try:
                    # For video files, we need to download to a temp file for ffmpeg
                    import tempfile
                    
                    # Create a temporary file to store the video header
                    with tempfile.NamedTemporaryFile(suffix=f".{technical_metadata['FileExtension']}") as temp_file:
                        # Write the header bytes to the temp file
                        temp_file.write(header_bytes)
                        temp_file.flush()
                        
                        # Use ffmpeg to extract video metadata
                        probe = ffmpeg.probe(temp_file.name)
                        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                        
                        if video_stream:
                            technical_metadata.update({
                                "Width": int(video_stream.get('width', 0)),
                                "Height": int(video_stream.get('height', 0)),
                                "Codec": video_stream.get('codec_name', ''),
                                "Duration": float(probe.get('format', {}).get('duration', 0)),
                                "Bitrate": int(probe.get('format', {}).get('bit_rate', 0)),
                                "FrameRate": eval(video_stream.get('r_frame_rate', '0/1')),
                            })
                            
                            # Extract audio stream info if available
                            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
                            if audio_stream:
                                technical_metadata["AudioCodec"] = audio_stream.get('codec_name', '')
                                technical_metadata["AudioChannels"] = int(audio_stream.get('channels', 0))
                                technical_metadata["AudioSampleRate"] = int(audio_stream.get('sample_rate', 0))
                except Exception as e:
                    logger.warning(f"Could not extract video metadata: {e}")
                    
                    # Fallback: try to get more complete metadata by downloading more of the file
                    try:
                        # Get more of the file (first 1MB) for better metadata extraction
                        response = self.s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-1048575')
                        larger_header = response["Body"].read()
                        
                        with tempfile.NamedTemporaryFile(suffix=f".{technical_metadata['FileExtension']}") as temp_file:
                            temp_file.write(larger_header)
                            temp_file.flush()
                            
                            probe = ffmpeg.probe(temp_file.name)
                            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                            
                            if video_stream:
                                technical_metadata.update({
                                    "Width": int(video_stream.get('width', 0)),
                                    "Height": int(video_stream.get('height', 0)),
                                    "Codec": video_stream.get('codec_name', ''),
                                    "Duration": float(probe.get('format', {}).get('duration', 0)),
                                    "Bitrate": int(probe.get('format', {}).get('bit_rate', 0)),
                                    "FrameRate": eval(video_stream.get('r_frame_rate', '0/1')),
                                })
                    except Exception as e2:
                        logger.warning(f"Could not extract video metadata with fallback method: {e2}")
            
            elif file_type == "Audio":
                try:
                    # For audio files, we need to download to a temp file for mutagen
                    import tempfile
                    
                    # Create a temporary file to store the audio header
                    with tempfile.NamedTemporaryFile(suffix=f".{technical_metadata['FileExtension']}") as temp_file:
                        # Write the header bytes to the temp file
                        temp_file.write(header_bytes)
                        temp_file.flush()
                        
                        # Use mutagen to extract audio metadata
                        audio = mutagen.File(temp_file.name)
                        
                        if audio:
                            technical_metadata.update({
                                "Duration": audio.info.length,
                                "Bitrate": audio.info.bitrate,
                                "Channels": getattr(audio.info, 'channels', None),
                                "SampleRate": getattr(audio.info, 'sample_rate', None),
                            })
                            
                            # Extract tags if available
                            if hasattr(audio, 'tags') and audio.tags:
                                tags = {}
                                for key in audio.tags.keys():
                                    tags[key] = str(audio.tags[key])
                                technical_metadata["Tags"] = tags
                except Exception as e:
                    logger.warning(f"Could not extract audio metadata: {e}")
                    
                    # Fallback: try to get more complete metadata by downloading more of the file
                    try:
                        # Get more of the file (first 1MB) for better metadata extraction
                        response = self.s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-1048575')
                        larger_header = response["Body"].read()
                        
                        with tempfile.NamedTemporaryFile(suffix=f".{technical_metadata['FileExtension']}") as temp_file:
                            temp_file.write(larger_header)
                            temp_file.flush()
                            
                            audio = mutagen.File(temp_file.name)
                            
                            if audio:
                                technical_metadata.update({
                                    "Duration": audio.info.length,
                                    "Bitrate": audio.info.bitrate,
                                    "Channels": getattr(audio.info, 'channels', None),
                                    "SampleRate": getattr(audio.info, 'sample_rate', None),
                                })
                    except Exception as e2:
                        logger.warning(f"Could not extract audio metadata with fallback method: {e2}")
                
            return technical_metadata
            
        except Exception as e:
            logger.exception(
                f"Error detecting file type for {bucket}/{key}, error: {e}"
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
            # Get basic object metadata using head_object (no content download)
            response = self.s3.head_object(Bucket=bucket, Key=key)
            existing_tags = self.s3.get_object_tagging(Bucket=bucket, Key=key)
            tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}

            if "AssetID" in tags:
                logger.info(f"Asset already processed: {tags['AssetID']}")
                return None

            # Calculate MD5 hash using optimized method (uses ETag when possible)
            md5_hash = self._calculate_md5(bucket, key)
            existing_file = self._check_existing_file(md5_hash)

            if existing_file:
                logger.info(f"Duplicate file found with hash {md5_hash}")

                # Check if the object key matches
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
                    new_asset_id = f"asset:img:{str(uuid.uuid4())}"
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

            # Detect file type and extract technical metadata from header
            technical_metadata = self._detect_file_type(bucket, key)
            
            # Process new unique file with technical metadata
            metadata = self._create_asset_metadata(response, bucket, key, md5_hash, technical_metadata)
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
        self, s3_response: Dict, bucket: str, key: str, md5_hash: str, technical_metadata: Dict[str, Any]
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
                    "Technical": technical_metadata,
                }
            },
        }

    @tracer.capture_method
    def create_dynamo_entry(self, metadata: StorageInfo) -> AssetRecord:
        """Create DynamoDB entry for the asset"""
        inventory_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        # Get technical metadata if available
        technical_metadata = (
            metadata.get("Metadata", {})
            .get("Embedded", {})
            .get("Technical", {})
        )
        
        # Extract and capitalize the first part of the MIME type from technical metadata if available
        mime_type = technical_metadata.get("MimeType", "")
        if mime_type:
            asset_type = technical_metadata.get("FileType", "Image")
        else:
            # Fallback to content type from S3 metadata
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
            "Audio": "aud",
            "Application": "doc",
            "Text": "txt"
        }
        type_abbrev = type_abbreviations.get(asset_type, "img")  # Default to "img" if type not found

        item: AssetRecord = {
            "InventoryID": f"asset:uuid:{inventory_id}",
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

        # Add technical dimensions if available
        if technical_metadata and "Width" in technical_metadata and "Height" in technical_metadata:
            item["DigitalSourceAsset"]["Dimensions"] = {
                "Width": technical_metadata["Width"],
                "Height": technical_metadata["Height"]
            }
            
        # Add duration for video/audio if available
        if technical_metadata and "Duration" in technical_metadata:
            item["DigitalSourceAsset"]["Duration"] = technical_metadata["Duration"]

        self.dynamodb.put_item(Item=item)
        return item

    @tracer.capture_method
    def publish_event(self, inventory_id: str, asset_id: str, metadata: StorageInfo):
        """Publish asset creation event to EventBridge"""
        try:
            # Extract technical metadata if available
            technical_metadata = (
                metadata.get("Metadata", {})
                .get("Embedded", {})
                .get("Technical", {})
            )
            
            # Create event detail with basic information
            event_detail = {
                "InventoryID": inventory_id,
                "AssetID": asset_id,
                "StorageInfo": {
                    "Bucket": metadata["StorageInfo"]["PrimaryLocation"]["Bucket"],
                    "Key": metadata["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"],
                },
                "FileInfo": {
                    "Size": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"]["Size"],
                    "Hash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"]["Hash"]["MD5Hash"],
                },
                "CreatedAt": datetime.utcnow().isoformat(),
            }
            
            # Add technical metadata if available
            if technical_metadata:
                event_detail["TechnicalMetadata"] = {
                    "FileType": technical_metadata.get("FileType", ""),
                    "MimeType": technical_metadata.get("MimeType", ""),
                }
                
                # Add dimensions if available
                if "Width" in technical_metadata and "Height" in technical_metadata:
                    event_detail["TechnicalMetadata"]["Dimensions"] = {
                        "Width": technical_metadata["Width"],
                        "Height": technical_metadata["Height"]
                    }
                
                # Add duration for video/audio if available
                if "Duration" in technical_metadata:
                    event_detail["TechnicalMetadata"]["Duration"] = technical_metadata["Duration"]

            logger.info(f"Publishing event: {json.dumps(event_detail)}")

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

            logger.info(f"Event published: {response}")
        except Exception as e:
            logger.exception(f"Error publishing event: {e}")
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
@event_source(data_class=S3Event)
def handler(event: S3Event, context: LambdaContext) -> Dict:
    """Handle S3 events using Powertools V3 data classes"""
    processor = AssetProcessor()

    try:
        # Validate the event against our schema
        try:
            # Convert S3Event back to dict for validation
            event_dict = event.raw_event
            validate(event=event_dict, schema=S3_EVENT_SCHEMA)
            logger.info("Event validation successful")
        except SchemaValidationError as e:
            logger.warning(f"Event validation failed: {e}")
            # Continue processing as the event_source decorator already parsed the event
        
        # Process each S3 record
        for record in event.records:
            try:
                bucket = record.s3.bucket.name
                key = record.s3.object.key
                event_name = record.event_name

                # Add custom metrics for monitoring
                metrics.add_metric(name="IncomingEvents", unit=MetricUnit.Count, value=1)
                
                # Process the S3 event
                process_s3_event(processor, bucket, key, event_name)

            except Exception as e:
                logger.exception(f"Error processing record: {e}")
                metrics.add_metric(name="FailedRecords", unit=MetricUnit.Count, value=1)
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
        result = processor.process_asset(bucket, key)
        if result:
            metrics.add_metric(name="ProcessedAssets", unit=MetricUnit.Count, value=1)
            logger.info(f"Asset processed successfully: {result['DigitalSourceAsset']['ID']}")
        else:
            logger.info(f"Asset already processed: {key}")
