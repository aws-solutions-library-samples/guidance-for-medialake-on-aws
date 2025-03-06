import os
import boto3
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any, List

# Import AWS Lambda Powertools V3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent, event_source

# Import libraries for file type detection and metadata extraction
try:
    import magic
    from io import BytesIO
    from PIL import Image
    import ffmpeg
    import mutagen
except ImportError:
    pass  # Libraries will be available in Lambda layer

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="AssetProcessor")

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
eventbridge = boto3.client('events')

# Define constants
class JobStatus:
    """Job status constants"""
    INITIALIZING = "INITIALIZING"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ErrorType:
    """Error type constants"""
    S3_ACCESS_ERROR = "S3_ACCESS_ERROR"
    TAG_FETCH_ERROR = "TAG_FETCH_ERROR"
    DYNAMO_QUERY_ERROR = "DYNAMO_QUERY_ERROR"
    SQS_SEND_ERROR = "SQS_SEND_ERROR"
    PROCESS_ERROR = "PROCESS_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class AssetProcessor:
    @staticmethod
    def format_error(error_id, object_key, error_type, error_message, batch_number, job_id, bucket_name):
        return {
            "errorId": error_id,
            "objectKey": object_key,
            "errorType": error_type,
            "errorMessage": error_message,
            "batchNumber": batch_number,
            "jobId": job_id,
            "bucketName": bucket_name,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def log_error(error_details):
        logger.error(f"Processing error: {json.dumps(error_details)}")
    
    @staticmethod
    def increment_job_counter(job_id, counter_name, increment_by):
        try:
            job_table = dynamodb.Table(os.environ.get('JOBS_TABLE_NAME', 'AssetSyncJobs'))
            
            # First check if the job exists
            try:
                job_response = job_table.get_item(Key={'jobId': job_id})
                if 'Item' not in job_response:
                    logger.warning(f"Job {job_id} not found in table {job_table.name}, cannot update counter {counter_name}")
                    return
            except Exception as e:
                if 'ResourceNotFoundException' in str(e):
                    logger.error(f"Table {job_table.name} does not exist: {str(e)}")
                else:
                    logger.error(f"Error checking job {job_id} existence: {str(e)}")
                return
            
            # If we get here, the job exists, so update the counter
            job_table.update_item(
                Key={'jobId': job_id},
                UpdateExpression=f"ADD {counter_name} :inc",
                ExpressionAttributeValues={':inc': increment_by}
            )
            logger.info(f"Updated counter {counter_name} for job {job_id} by {increment_by}")
        except Exception as e:
            logger.error(f"Failed to update job counter {counter_name} for job {job_id}: {str(e)}")

    @tracer.capture_method
    def calculate_md5(self, bucket: str, key: str) -> str:
        """Calculate MD5 hash of S3 object for file identification purposes"""
        try:
            # Get the object's ETag which is usually the MD5 hash for non-multipart uploads
            response = s3.head_object(Bucket=bucket, Key=key)
            etag = response.get('ETag', '').strip('"')
            
            # If this is a multipart upload (ETag contains a dash), we need to calculate our own MD5
            if '-' in etag:
                # Only read the first 8KB of the file for header analysis
                response = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-8191')
                md5_hash = hashlib.md5(usedforsecurity=False)
                md5_hash.update(response["Body"].read())
                return md5_hash.hexdigest()
            
            return etag
        except Exception as e:
            logger.exception(f"Error calculating MD5 hash for {bucket}/{key}, error: {e}")
            raise

    @tracer.capture_method
    def detect_file_type(self, bucket: str, key: str) -> Dict[str, Any]:
        """Detect file type and extract technical metadata from file header"""
        try:
            # Only read the first 8KB of the file for header analysis
            response = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-8191')
            header_bytes = response["Body"].read()
            
            # Add metadata to trace
            tracer.put_metadata(key="file_size", value=response.get("ContentLength", 0))
            tracer.put_metadata(key="content_type", value=response.get("ContentType", "unknown"))
            
            # Use python-magic to detect file type from header bytes
            mime_type = magic.from_buffer(header_bytes, mime=True)
            file_type = mime_type.split('/')[0].capitalize()
            
            # Add file type to trace
            tracer.put_annotation(key="file_type", value=file_type)
            
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
                    
                    # Try to extract EXIF/IPTC/XMP metadata from the header
                    if hasattr(img, '_getexif') and callable(img._getexif):
                        exif_data = img._getexif()
                        if exif_data:
                            # Convert EXIF data to a more readable format
                            from PIL.ExifTags import TAGS
                            exif = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
                            technical_metadata["EXIF"] = {k: str(v) for k, v in exif.items() if isinstance(v, (str, int, float, bool))}
                
                except Exception as e:
                    logger.warning(f"Could not extract image metadata from header: {e}")
                    # Fallback: try to get more complete metadata by downloading more of the file
                    try:
                        # Get more of the file (first 1MB) for better image metadata extraction
                        # This larger size should be sufficient for most embedded metadata
                        response = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-1048575')
                        larger_header = response["Body"].read()
                        
                        # Try to extract basic image properties
                        img = Image.open(BytesIO(larger_header))
                        technical_metadata.update({
                            "Width": img.width,
                            "Height": img.height,
                            "Format": img.format,
                            "Mode": img.mode,
                        })
                        
                        # Try to extract EXIF/IPTC/XMP metadata with the larger buffer
                        if hasattr(img, '_getexif') and callable(img._getexif):
                            exif_data = img._getexif()
                            if exif_data:
                                # Convert EXIF data to a more readable format
                                from PIL.ExifTags import TAGS
                                exif = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
                                technical_metadata["EXIF"] = {k: str(v) for k, v in exif.items() if isinstance(v, (str, int, float, bool))}
                        
                        # Try to extract XMP metadata if available
                        try:
                            from PIL import TiffImagePlugin
                            xmp_data = TiffImagePlugin.ImageFileDirectory_v2()
                            xmp_index = 0
                            while True:
                                xmp_index = larger_header.find(b'<x:xmpmeta', xmp_index)
                                if xmp_index == -1:
                                    break
                                xmp_end = larger_header.find(b'</x:xmpmeta', xmp_index)
                                if xmp_end == -1:
                                    break
                                xmp_str = larger_header[xmp_index:xmp_end+12].decode('utf-8', errors='ignore')
                                technical_metadata["XMP"] = {"RawXMP": xmp_str[:1000] + "..." if len(xmp_str) > 1000 else xmp_str}
                                break
                        except Exception as xmp_error:
                            logger.warning(f"Could not extract XMP metadata: {xmp_error}")
                        
                        logger.info(f"Successfully extracted image metadata using larger buffer")
                    except Exception as e2:
                        logger.warning(f"Could not extract image metadata with fallback method: {e2}")
            
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
                        response = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-1048575')
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
                        response = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-1048575')
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

    @tracer.capture_method
    def check_existing_file(self, md5_hash: str) -> Optional[Dict]:
        """Check if file with same MD5 hash exists in DynamoDB"""
        try:
            assets_table = dynamodb.Table(os.environ['ASSETS_TABLE_NAME'])
            response = assets_table.query(
                IndexName="FileHashIndex",
                KeyConditionExpression="FileHash = :hash",
                ExpressionAttributeValues={":hash": md5_hash},
                Limit=1
            )
            
            if response.get("Items") and len(response["Items"]) > 0:
                return response["Items"][0]
            return None
        except Exception as e:
            logger.exception(f"Error checking for existing file with hash {md5_hash}: {e}")
            raise

    @tracer.capture_method
    def process_asset(self, bucket: str, key: str, existing_asset_id: Optional[str] = None, existing_inventory_id: Optional[str] = None) -> Dict:
        """Process asset with existing ID handling and metadata extraction"""
        try:
            # Get basic object metadata
            response = s3.head_object(Bucket=bucket, Key=key)
            
            # Calculate MD5 hash
            md5_hash = self.calculate_md5(bucket, key)
            
            # Check for duplicates if we don't have existing IDs
            if not existing_asset_id and not existing_inventory_id:
                existing_file = self.check_existing_file(md5_hash)
                if existing_file:
                    logger.info(f"Duplicate file found with hash {md5_hash}")
                    existing_inventory_id = existing_file.get("InventoryID")
                    existing_asset_id = existing_file.get("DigitalSourceAsset", {}).get("ID")
            
            # Detect file type and extract technical metadata
            technical_metadata = self.detect_file_type(bucket, key)
            
            # Determine what IDs to use
            inventory_id = existing_inventory_id or f"asset:uuid:{str(uuid.uuid4())}"
            
            # Determine asset type from technical metadata
            file_type = technical_metadata.get("FileType", "Image")
            
            # Map asset types to their abbreviations
            type_abbreviations = {
                "Image": "img",
                "Video": "vid",
                "Audio": "aud",
                "Application": "doc",
                "Text": "txt"
            }
            type_abbrev = type_abbreviations.get(file_type, "img")
            
            # Use existing asset ID or create a new one
            asset_id = existing_asset_id or f"asset:{type_abbrev}:{str(uuid.uuid4())}"
            
            # Create metadata structure
            metadata = {
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
                            "Size": response["ContentLength"],
                            "Hash": {
                                "Algorithm": "SHA256",
                                "Value": response["ETag"].strip('"'),
                                "MD5Hash": md5_hash,
                            },
                            "CreateDate": response["LastModified"].isoformat(),
                        },
                    }
                },
                "Metadata": {
                    "Embedded": {
                        "ExtractedDate": datetime.utcnow().isoformat(),
                        "S3": {
                            "Metadata": response.get("Metadata", {}),
                            "ContentType": response.get("ContentType"),
                            "LastModified": response["LastModified"].isoformat(),
                        },
                        "Technical": technical_metadata,
                    }
                },
            }
            
            # Create DynamoDB entry
            assets_table = dynamodb.Table(os.environ['ASSETS_TABLE_NAME'])
            
            item = {
                "InventoryID": inventory_id,
                "ID": "asset",  # Using 'asset' as the sort key
                "FileHash": md5_hash,
                "DigitalSourceAsset": {
                    "ID": asset_id,
                    "Type": file_type,
                    "CreateDate": datetime.utcnow().isoformat(),
                    "IngestedAt": datetime.utcnow().isoformat(),
                    "MainRepresentation": {
                        "ID": f"{asset_id}:master",
                        "Type": file_type,
                        "Format": key.split(".")[-1].upper() if "." in key else "",
                        "Purpose": "master",
                        "StorageInfo": metadata["StorageInfo"],
                    },
                },
                "DerivedRepresentations": [],
                "Metadata": metadata.get("Metadata"),
            }
            
            # Add technical dimensions if available
            if "Width" in technical_metadata and "Height" in technical_metadata:
                item["DigitalSourceAsset"]["Dimensions"] = {
                    "Width": technical_metadata["Width"],
                    "Height": technical_metadata["Height"]
                }
                
            # Add duration for video/audio if available
            if "Duration" in technical_metadata:
                item["DigitalSourceAsset"]["Duration"] = technical_metadata["Duration"]
            
            assets_table.put_item(Item=item)
            
            # Add tags to S3 object
            s3.put_object_tagging(
                Bucket=bucket,
                Key=key,
                Tagging={
                    "TagSet": [
                        {"Key": "InventoryID", "Value": inventory_id},
                        {"Key": "AssetID", "Value": asset_id},
                        {"Key": "FileHash", "Value": md5_hash},
                    ]
                },
            )
            
            # Publish event to EventBridge
            event_detail = {
                "InventoryID": inventory_id,
                "AssetID": asset_id,
                "StorageInfo": {
                    "Bucket": bucket,
                    "Key": key,
                },
                "FileInfo": {
                    "Size": response["ContentLength"],
                    "Hash": md5_hash,
                },
                "CreatedAt": datetime.utcnow().isoformat(),
            }
            
            # Add technical metadata to event
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
            
            event_bus_name = os.environ.get("INGEST_EVENT_BUS_NAME", "default")
            event_entry = {
                "Source": "custom.asset.processor",
                "DetailType": "AssetCreated",
                "Detail": json.dumps(event_detail),
                "EventBusName": event_bus_name,
            }
            
            logger.info(f"Publishing event to EventBridge bus '{event_bus_name}': {json.dumps(event_entry)}")
            
            response = eventbridge.put_events(
                Entries=[event_entry]
            )
            
            logger.info(f"EventBridge put_events response: {json.dumps(response)}")
            
            return item
            
        except Exception as e:
            logger.exception(f"Error processing asset: {key}, error: {e}")
            raise

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=SQSEvent)
def lambda_handler(event: SQSEvent, context: LambdaContext) -> Dict:
    """Handle SQS messages for asset sync"""
    processor = AssetProcessor()
    
    # Process SQS messages
    failed_message_ids = []
    processed_count = 0
    error_count = 0
    
    try:
        # Process each SQS message
        for record in event.records:
            try:
                # Parse the message
                message_id = record.message_id
                message_body = json.loads(record.body)
                
                job_id = message_body['jobId']
                bucket_name = message_body['bucketName']
                objects = message_body['objects']
                batch_number = message_body.get('batchNumber', 0)
                total_batches = message_body.get('totalBatches', 0)
                
                logger.info(f"Processing batch {batch_number}/{total_batches} with {len(objects)} objects for job {job_id}")
                metrics.add_metric(name="BatchSize", unit=MetricUnit.Count, value=len(objects))
                
                # Process each object in the batch
                for obj in objects:
                    try:
                        object_key = obj['key']
                        
                        # Get existing tags if any
                        existing_tags_response = s3.get_object_tagging(
                            Bucket=bucket_name,
                            Key=object_key
                        )
                        existing_tags = {tag['Key']: tag['Value'] for tag in existing_tags_response.get('TagSet', [])}
                        
                        # Check for existing AssetID and InventoryID
                        existing_asset_id = existing_tags.get('AssetID')
                        existing_inventory_id = existing_tags.get('InventoryID')
                        
                        # Override with values from the message if provided
                        if 'assetId' in obj and obj['assetId']:
                            existing_asset_id = obj['assetId']
                        if 'inventoryId' in obj and obj['inventoryId']:
                            existing_inventory_id = obj['inventoryId']
                        
                        # Process the asset with existing ID handling and metadata extraction
                        result = processor.process_asset(
                            bucket_name, 
                            object_key,
                            existing_asset_id,
                            existing_inventory_id
                        )
                        
                        logger.info(f"Processed object {object_key} for job {job_id}")
                        processed_count += 1
                        metrics.add_metric(name="ProcessedAssets", unit=MetricUnit.Count, value=1)
                        
                    except Exception as e:
                        error_count += 1
                        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
                        error_id = str(uuid.uuid4())
                        error_details = AssetProcessor.format_error(
                            error_id,
                            obj.get('key', 'unknown'),
                            ErrorType.PROCESS_ERROR,
                            str(e),
                            batch_number,
                            job_id,
                            bucket_name
                        )
                        AssetProcessor.log_error(error_details)
                
                # Update job counters
                AssetProcessor.increment_job_counter(job_id, 'objectsProcessed', processed_count)
                if error_count > 0:
                    AssetProcessor.increment_job_counter(job_id, 'errors', error_count)
                
            except Exception as e:
                # Track the failed message for batch failure handling
                failed_message_ids.append(record.message_id)
                logger.error(f"Failed to process message {record.message_id}: {str(e)}")
                metrics.add_metric(name="FailedMessages", unit=MetricUnit.Count, value=1)
        
        # Return failed message IDs for partial batch failures
        if failed_message_ids:
            return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failed_message_ids]}
        
        return {"batchItemFailures": []}
        
    except Exception as e:
        logger.exception("Error in handler")
        metrics.add_metric(name="HandlerErrors", unit=MetricUnit.Count, value=1)
        raise
