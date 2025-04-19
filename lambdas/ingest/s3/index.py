from typing import Dict, Optional, TypedDict, List, Any, Callable, Tuple
import boto3
import json
import uuid
import os
import urllib.parse
from datetime import datetime
import hashlib
import functools
import concurrent.futures
import threading
from botocore.config import Config
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.parser import parse, event_parser
from decimal import Decimal

# Configure environment-specific logging
def configure_logging():
    """Configure logging based on environment"""
    env = os.environ.get("ENVIRONMENT", "dev")
    if env == "prod":
        # In production, only log warnings and errors to reduce costs
        logger.setLevel("WARNING")
    else:
        # In dev/test, log everything
        logger.setLevel("INFO")

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configure logging based on environment
configure_logging()

# Configure S3 client with retries
s3_config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'
    },
    read_timeout=15,
    connect_timeout=5
)

# Improved JSON serialization
class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects and Decimal types from DynamoDB"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            # Convert Decimal to int or float appropriately
            return float(obj) if obj % 1 != 0 else int(obj)
        return super(DateTimeEncoder, self).default(obj)

# Global instance to reduce instantiation costs
datetime_encoder = DateTimeEncoder()

def json_serialize(obj):
    """Serialize object to JSON string handling datetime objects"""
    return json.dumps(obj, cls=DateTimeEncoder)

# LRU cache for type mappings
@functools.lru_cache(maxsize=100)
def get_type_abbreviation(asset_type: str) -> str:
    """Cache type mappings to reduce dict lookups"""
    type_abbreviations = {
        "Image": "img",
        "Video": "vid", 
        "Audio": "aud"
    }
    return type_abbreviations.get(asset_type, "img")

@functools.lru_cache(maxsize=200)
def determine_asset_type(content_type: str, file_extension: str) -> str:
    """
    Determine the asset type using content type and file extension.
    Uses a more comprehensive classification based on mime types and extensions.
    
    Args:
        content_type: The MIME type from S3 metadata
        file_extension: The file extension (without the dot)
    
    Returns:
        One of: "Image", "Video", "Audio", or "Other"
    """
    # Convert to lowercase for comparison
    content_type = content_type.lower() if content_type else ""
    file_extension = file_extension.lower() if file_extension else ""
    
    # Image classification
    image_mimes = ["image/", "application/photoshop", "application/illustrator"]
    image_extensions = ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "svg", "webp", "heic", "heif", "raw", "psd", "ai", "eps"]
    
    # Video classification
    video_mimes = ["video/"]
    video_extensions = ["mp4", "mov", "avi", "wmv", "webm", "flv", "mkv", "m4v", "mpg", "mpeg", "3gp"]
    
    # Audio classification
    audio_mimes = ["audio/"]
    audio_extensions = ["mp3", "wav", "aac", "flac", "ogg", "wma", "m4a", "aiff", "opus"]
    
    # Check MIME type first as it's more reliable
    for prefix in image_mimes:
        if content_type.startswith(prefix):
            return "Image"
    
    for prefix in video_mimes:
        if content_type.startswith(prefix):
            return "Video"
    
    for prefix in audio_mimes:
        if content_type.startswith(prefix):
            return "Audio"
    
    # If MIME type doesn't give us a clear answer, check file extension
    if file_extension in image_extensions:
        return "Image"
    
    if file_extension in video_extensions:
        return "Video"
    
    if file_extension in audio_extensions:
        return "Audio"
    
    # If we have a content type but no clear match, try to infer from the main type
    if content_type:
        mime_main_type = content_type.split('/')[0].capitalize()
        if mime_main_type in ["Image", "Video", "Audio"]:
            return mime_main_type
    
    # If we have a file extension but no clear match, try to infer from common patterns
    if file_extension:
        # Log the unknown extension for monitoring
        logger.warning(f"Unknown file extension encountered: {file_extension}")
        # Default to "Other" instead of "Image" for unknown types
        return "Other"
    
    # If we have no information at all, log it and return "Other"
    logger.warning("No content type or file extension available for type determination")
    return "Other"

# Event filtering optimization
def is_relevant_event(event_name: str, allowed_prefixes=("ObjectCreated:", "ObjectRemoved:")) -> bool:
    """Quick check if event should be processed"""
    # For improved logging, explicitly check for 'Copy' events
    if event_name == "ObjectCreated:Copy":
        logger.info("Processing ObjectCreated:Copy event as a relevant event")
        return True
    return any(event_name.startswith(prefix) for prefix in allowed_prefixes)


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
    originalIngestDate: Optional[str]
    lastModifiedDate: Optional[str]


class AssetRecord(TypedDict):
    InventoryID: str
    DigitalSourceAsset: DigitalSourceAsset
    DerivedRepresentations: Optional[List[AssetRepresentation]]
    Metadata: Optional[AssetMetadata]
    FileHash: str
    StoragePath: str


class AssetProcessor:
    def __init__(self):
        # Use optimized S3 client with retries
        self.s3 = boto3.client("s3", config=s3_config)
        
        # Setup DynamoDB with batch writer for efficiency
        dynamodb = boto3.resource("dynamodb")
        self.table = dynamodb.Table(os.environ["ASSETS_TABLE"])
        self.dynamodb = self.table  # Keep original reference for compatibility
        
        # EventBridge client
        self.eventbridge = boto3.client("events")
        
        # Cache for extension to content type mapping
        self.extension_content_type_cache = {}
        
        # Initialize a lock for thread-safe access to processed_inventory_ids
        self.lock = threading.Lock()
        
        # Set to track processed inventory IDs to prevent duplicates
        self.processed_inventory_ids = set()

    def _decode_s3_event_key(self, encoded_key: str) -> str:
        """Decode S3 event key by handling URL encoding"""
        # Just decode URL encoding without replacing literal '+' characters
        # urllib.parse.unquote properly handles %20, %2B etc.
        return urllib.parse.unquote(encoded_key)

    def _extract_file_extension(self, key: str) -> str:
        """Extract file extension from key"""
        # The key should already be URL-decoded by the time it reaches this method
        # Just extract the extension directly
        return key.split(".")[-1].lower() if "." in key else ""

    @tracer.capture_method
    def _calculate_md5(self, bucket: str, key: str, chunk_size: int = 8192) -> str:
        """Calculate MD5 hash with optimal chunk size for memory efficiency"""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            md5_hash = hashlib.md5(usedforsecurity=False)
                
            # Use larger chunk size for better performance
            bytes_processed = 0
            for chunk in response["Body"].iter_chunks(chunk_size):
                md5_hash.update(chunk)
                bytes_processed += len(chunk)
            
            return md5_hash.hexdigest()
        except Exception as e:
            logger.exception(f"Error calculating MD5 hash for {bucket}/{key}, error: {e}")
            raise

    @tracer.capture_method
    def _check_existing_file(self, md5_hash: str) -> Optional[Dict]:
        """Check if file with same MD5 hash exists with optimized query"""
        try:
            # Use ProjectionExpression to only fetch needed attributes
            response = self.dynamodb.query(
                IndexName="FileHashIndex",
                KeyConditionExpression="FileHash = :hash",
                ExpressionAttributeValues={":hash": md5_hash},
            )

            if response["Items"]:
                return response["Items"][0]
                
            return None
        except Exception as e:
            logger.exception(f"Error querying DynamoDB for hash {md5_hash}, error {e}")
            raise

    @tracer.capture_method
    def process_asset(self, bucket: str, key: str) -> Optional[Dict]:
        """Process new asset from S3 with optimized performance"""
        key = self._decode_s3_event_key(key)

        try:
            # Get S3 object metadata and tags in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                head_future = executor.submit(self.s3.head_object, Bucket=bucket, Key=key)
                tag_future = executor.submit(self.s3.get_object_tagging, Bucket=bucket, Key=key)
                
                # Wait for both to complete
                concurrent.futures.wait([head_future, tag_future])
                
                # Get results or handle exceptions
                try:
                    response = head_future.result()
                except Exception as e:
                    logger.exception(f"Error getting S3 object metadata: {str(e)}")
                    raise
                    
                try:
                    existing_tags = tag_future.result()
                except Exception as e:
                    logger.exception(f"Error getting S3 object tags: {str(e)}")
                    raise
            
            # Early check for asset type
            content_type = response.get("ContentType", "")
            file_ext = self._extract_file_extension(key)
            asset_type = determine_asset_type(content_type, file_ext)
            
            # Get S3 object's last modified date
            s3_last_modified = response.get("LastModified", datetime.utcnow())
            if isinstance(s3_last_modified, datetime):
                s3_last_modified_str = s3_last_modified.isoformat()
            else:
                s3_last_modified_str = s3_last_modified
            
            # Log the type determination for debugging
            logger.info(f"Asset type determination for {key}: content_type={content_type}, file_ext={file_ext}, determined_type={asset_type}")
            
            # Stop processing if asset type is not one of: "Image", "Video", "Audio"
            if asset_type not in ["Image", "Video", "Audio"]:
                logger.info(f"Skipping processing for unsupported asset type: {asset_type} for {bucket}/{key}")
                metrics.add_metric(name="UnsupportedAssetTypeSkipped", unit=MetricUnit.Count, value=1)
                return None

            tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}

            # Check existing tags first - this is a fast path if object already processed
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
                        logger.info(f"Found existing record in DynamoDB: {json_serialize(existing_record['Item'])}")
                        
                        # Update the lastModifiedDate field but preserve originalIngestDate
                        # Create updateExpression and attributeValues for update operation
                        update_expression = "SET DigitalSourceAsset.lastModifiedDate = :lastModDate"
                        expression_attribute_values = {":lastModDate": s3_last_modified_str}
                        
                        # Update only the lastModifiedDate
                        self.dynamodb.update_item(
                            Key={"InventoryID": tags["InventoryID"]},
                            UpdateExpression=update_expression,
                            ExpressionAttributeValues=expression_attribute_values
                        )
                        logger.info(f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {tags['AssetID']}")
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
                                file_ext = key.split(".")[-1] if "." in key else ""
                                asset_type = determine_asset_type(content_type, file_ext)
                        else:
                            content_type = response.get("ContentType", "")
                            file_ext = key.split(".")[-1] if "." in key else ""
                            asset_type = determine_asset_type(content_type, file_ext)
                        
                        # Current time for ingest date
                        current_time = datetime.utcnow().isoformat()
                        
                        # Create the item structure
                        item = {
                            "InventoryID": inventory_id,
                            "FileHash": md5_hash,
                            "StoragePath": f"{bucket}:{key}",
                            "DigitalSourceAsset": {
                                "ID": asset_id,
                                "Type": asset_type,
                                "CreateDate": datetime.utcnow().isoformat(),
                                "IngestedAt": datetime.utcnow().isoformat(),
                                "originalIngestDate": current_time,
                                "lastModifiedDate": s3_last_modified_str,
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
                        
                        # Use batch writer for better DynamoDB performance
                        try:
                            self.dynamodb.put_item(Item=item)
                            logger.info(f"Successfully recreated DynamoDB record for {inventory_id}")
                            
                            # Verify the write with a get_item
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
                    file_ext = key.split(".")[-1] if "." in key else ""
                    asset_type = determine_asset_type(content_type, file_ext)
                    type_abbrev = get_type_abbreviation(asset_type)  # Use cached function
                    
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
                    dynamo_entry = self.create_dynamo_entry(metadata, inventory_id=tags["InventoryID"], s3_last_modified=s3_last_modified_str)
                    
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
                    
                    # Update lastModifiedDate for the existing file in DynamoDB
                    self.dynamodb.update_item(
                        Key={"InventoryID": existing_file["InventoryID"]},
                        UpdateExpression="SET DigitalSourceAsset.lastModifiedDate = :lastModDate",
                        ExpressionAttributeValues={":lastModDate": s3_last_modified_str}
                    )
                    logger.info(f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {existing_file['DigitalSourceAsset']['ID']}")
                    
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
                    
                    # Update lastModifiedDate for the existing file in DynamoDB
                    self.dynamodb.update_item(
                        Key={"InventoryID": existing_file["InventoryID"]},
                        UpdateExpression="SET DigitalSourceAsset.lastModifiedDate = :lastModDate",
                        ExpressionAttributeValues={":lastModDate": s3_last_modified_str}
                    )
                    logger.info(f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {existing_file['DigitalSourceAsset']['ID']}")
                    
                    return None
                else:
                    # Same hash but different key - tag with same InventoryID but new AssetID
                    logger.info(
                        "Same hash but different key. Tagging with same InventoryID but new AssetID"
                    )
                    # Extract asset type from content type
                    content_type = response.get("ContentType", "")
                    file_ext = key.split(".")[-1] if "." in key else ""
                    asset_type = determine_asset_type(content_type, file_ext)
                    type_abbrev = get_type_abbreviation(asset_type)  # Use cached function
                    
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
                dynamo_entry = self.create_dynamo_entry(metadata, inventory_id=tags["InventoryID"], s3_last_modified=s3_last_modified_str)
            else:
                # Normal processing for new file
                dynamo_entry = self.create_dynamo_entry(metadata, s3_last_modified=s3_last_modified_str)

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
            metrics.add_metric(name="AssetProcessingErrors", unit=MetricUnit.Count, value=1)
            raise

    def _create_asset_metadata(
        self, s3_response: Dict, bucket: str, key: str, md5_hash: str
    ) -> StorageInfo:
        """Create asset metadata structure with optimized field extraction"""
        # Get file extension from key
        filename = key.split("/")[-1]
        file_ext = self._extract_file_extension(filename)
        
        # Optimize path splitting
        path_parts = key.split("/")
        name = path_parts[-1]
        path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
        
        # Use extraction for performance
        content_length = s3_response.get("ContentLength", 0)
        etag = s3_response.get("ETag", "").strip('"')
        last_modified = s3_response.get("LastModified", datetime.utcnow()).isoformat()
        content_type = s3_response.get("ContentType", "")
        
        return {
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Bucket": bucket,
                    "ObjectKey": {
                        "Name": name,
                        "Path": path,
                        "FullPath": key,
                    },
                    "Status": "active",
                    "FileInfo": {
                        "Size": content_length,
                        "Hash": {
                            "Algorithm": "SHA256",
                            "Value": etag,
                            "MD5Hash": md5_hash,
                        },
                        "CreateDate": last_modified,
                    },
                }
            },
            "Metadata": {
                "Embedded": {
                    "ExtractedDate": datetime.utcnow().isoformat(),
                    "S3": {
                        "Metadata": s3_response.get("Metadata", {}),
                        "ContentType": content_type,
                        "LastModified": last_modified,
                    },
                }
            },
        }

    @tracer.capture_method
    def create_dynamo_entry(self, metadata: StorageInfo, inventory_id: str = None, s3_last_modified: str = None) -> AssetRecord:
        """Create DynamoDB entry for the asset with optimized data handling"""
        try:
            if not inventory_id:
                inventory_id = f"asset:uuid:{str(uuid.uuid4())}"
            else:
                # Use the provided inventory_id if it exists
                if not inventory_id.startswith("asset:uuid:"):
                    inventory_id = f"asset:uuid:{inventory_id}"
            
            # Thread-safe check for duplicate inventory IDs
            if hasattr(self, 'lock') and hasattr(self, 'processed_inventory_ids'):
                with self.lock:
                    if inventory_id in self.processed_inventory_ids:
                        logger.warning(f"Duplicate inventory ID detected: {inventory_id} - generating a new one")
                        # Generate a new unique inventory ID instead
                        inventory_id = f"asset:uuid:{str(uuid.uuid4())}"
                    # Add this inventory ID to the set of processed IDs
                    self.processed_inventory_ids.add(inventory_id)
            
            asset_id = str(uuid.uuid4())

            # Extract bucket and key from metadata for StoragePath
            bucket = metadata["StorageInfo"]["PrimaryLocation"]["Bucket"]
            key = metadata["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
            
            # Extract content type and file extension for type determination
            content_type = (
                metadata.get("Metadata", {})
                .get("Embedded", {})
                .get("S3", {})
                .get("ContentType", "")
            )
            file_ext = self._extract_file_extension(key)
            
            # Use more accurate asset type detection
            asset_type = determine_asset_type(content_type, file_ext)

            # Use cached type abbreviation lookup
            type_abbrev = get_type_abbreviation(asset_type)

            # Get current timestamp once for reuse
            timestamp = datetime.utcnow().isoformat()
            
            # Use provided S3 last modified date or current timestamp
            if not s3_last_modified:
                s3_last_modified = timestamp

            item: AssetRecord = {
                "InventoryID": inventory_id,
                "FileHash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"]["Hash"][
                    "MD5Hash"
                ],
                "StoragePath": f"{bucket}:{key}",
                "DigitalSourceAsset": {
                    "ID": f"asset:{type_abbrev}:{asset_id}",
                    "Type": asset_type,
                    "CreateDate": timestamp,
                    "IngestedAt": timestamp,
                    "originalIngestDate": timestamp,  # Set original ingest date to current time for new assets
                    "lastModifiedDate": s3_last_modified,  # Use the S3 object's last modified date
                    "MainRepresentation": {
                        "ID": f"asset:rep:{asset_id}:master",
                        "Type": asset_type,
                        "Format": file_ext.upper(),
                        "Purpose": "master",
                        "StorageInfo": metadata["StorageInfo"],
                    },
                },
                "DerivedRepresentations": [],
                "Metadata": metadata.get("Metadata"),
            }

            # Add detailed logging before DynamoDB operation
            logger.info(f"Attempting to write to DynamoDB table: {os.environ['ASSETS_TABLE']}")
            logger.info(f"Using inventory_id: {inventory_id} for DynamoDB key")
            
            # Use direct put_item instead of batch_writer for immediate feedback
            try:
                # First, check if the item with this ID already exists
                existing_item = self.dynamodb.get_item(
                    Key={"InventoryID": inventory_id}
                ).get("Item")
                
                if existing_item:
                    logger.warning(f"Item with InventoryID {inventory_id} already exists. Generating new ID.")
                    # Generate a new ID and try again
                    item["InventoryID"] = f"asset:uuid:{str(uuid.uuid4())}"
                    logger.info(f"Using new InventoryID: {item['InventoryID']}")
                
                # Now do the put_item operation
                self.dynamodb.put_item(Item=item)
                logger.info(f"put_item operation completed for InventoryID: {item['InventoryID']}")
            except Exception as e:
                logger.exception(f"Error in put_item operation: {str(e)}")
                raise
            
            # Verify the item was written by doing a get_item
            logger.info(f"Verifying item with InventoryID: {item['InventoryID']}")
            verification_response = self.dynamodb.get_item(
                Key={
                    "InventoryID": item["InventoryID"]
                }
            )
            
            # Log the full verification response
            logger.info(f"Verification response: {json_serialize(verification_response)}")
            
            if "Item" in verification_response:
                logger.info(f"Verification successful - item exists in DynamoDB")
            else:
                logger.warning(f"Verification failed - item not found in DynamoDB after put_item")
                
                # Log additional information to help diagnose the issue
                try:
                    # Check if the table is reachable
                    table_info = boto3.client('dynamodb').describe_table(
                        TableName=os.environ["ASSETS_TABLE"]
                    )
                    logger.info(f"Table status: {table_info['Table']['TableStatus']}")
                    
                    # Try a direct query on the table to see if the item exists
                    query_response = self.dynamodb.query(
                        KeyConditionExpression="InventoryID = :id",
                        ExpressionAttributeValues={":id": item["InventoryID"]}
                    )
                    logger.info(f"Direct query response: {json_serialize(query_response)}")
                    
                    # Try to scan the table for recent items
                    scan_response = self.dynamodb.scan(
                        Limit=5
                    )
                    logger.info(f"Recent items scan (count={scan_response.get('Count', 0)})")
                    
                except Exception as e:
                    logger.exception(f"Error during additional diagnostics: {str(e)}")
            
            return item
        except Exception as e:
            logger.exception(f"Error writing to DynamoDB: {str(e)}")
            raise

    @tracer.capture_method
    def publish_event(self, inventory_id: str, asset_id: str, metadata: StorageInfo):
        """Publish event to EventBridge with optimized serialization"""
        try:
            # Extract content type information
            content_type = (
                metadata.get("Metadata", {})
                .get("Embedded", {})
                .get("S3", {})
                .get("ContentType", "")
            )
            # Get file extension from the object key
            object_key = metadata["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
            file_ext = self._extract_file_extension(object_key)
            
            # Use more accurate asset type detection
            asset_type = determine_asset_type(content_type, file_ext)

            # Get timestamp once for reuse
            timestamp = datetime.utcnow().isoformat()
            
            # Get last modified date from S3 metadata if available
            s3_last_modified = (
                metadata.get("Metadata", {})
                .get("Embedded", {})
                .get("S3", {})
                .get("LastModified", timestamp)
            )

            # Construct event detail
            event_detail = {
                "InventoryID": inventory_id,
                "FileHash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"][
                    "Hash"
                ]["MD5Hash"],
                "DigitalSourceAsset": {
                    "ID": asset_id,
                    "Type": asset_type,
                    "CreateDate": timestamp,
                    "originalIngestDate": timestamp,
                    "lastModifiedDate": s3_last_modified,
                    "MainRepresentation": {
                        "ID": f"{asset_id}:master",
                        "Type": asset_type,
                        "Format": file_ext.upper(),
                        "Purpose": "master",
                        "StorageInfo": metadata["StorageInfo"],
                    },
                },
                "DerivedRepresentations": [],
                "Metadata": metadata.get("Metadata"),
            }

            # Use optimized JSON serialization
            event_json = json_serialize(event_detail)
            logger.info(f"Publishing event with detail size: {len(event_json)} bytes")

            # Publish to EventBridge
            response = self.eventbridge.put_events(
                Entries=[
                    {
                        "Source": "custom.asset.processor",
                        "DetailType": "AssetCreated",
                        "Detail": event_json,
                        "EventBusName": os.environ["EVENT_BUS_NAME"],
                    }
                ]
            )

            # Log only relevant parts of the response
            if "FailedEntryCount" in response and response["FailedEntryCount"] > 0:
                logger.error(f"EventBridge publish failed: {json_serialize(response)}")
            else:
                logger.info(f"EventBridge publish successful")

            # Add metrics
            metrics.add_metric(name="EventsPublished", unit=MetricUnit.Count, value=1)

        except Exception as e:
            logger.exception(f"Error publishing event: {str(e)}")
            metrics.add_metric(name="EventPublishErrors", unit=MetricUnit.Count, value=1)
            raise

    @tracer.capture_method
    def delete_asset(self, bucket: str, key: str, is_delete_event: bool = True) -> None:
        """Delete asset record from DynamoDB based on S3 object deletion"""
        try:
            # First, try to find the asset by S3 path
            storage_path = f"{bucket}:{key}"
            logger.info(f"Looking up asset by storage path: {storage_path}")
            
            # Define task for database lookup
            def find_by_s3path():
                try:
                    return self.dynamodb.query(
                        IndexName="S3PathIndex",
                        KeyConditionExpression="StoragePath = :path",
                        ExpressionAttributeValues={":path": storage_path}
                    )
                except Exception as e:
                    logger.exception(f"Error querying DynamoDB for storage path: {str(e)}")
                    return {"Items": []}
            
            # Find the record by S3 path first (this uses DynamoDB, not S3)
            response = find_by_s3path()
            inventory_id = None
            
            if response["Items"]:
                # Found the item in DynamoDB
                item = response["Items"][0]
                inventory_id = item["InventoryID"]
                logger.info(f"Found item in DynamoDB by S3 path: {inventory_id}")
                
                # Delete from DynamoDB
                self.dynamodb.delete_item(
                    Key={
                        "InventoryID": inventory_id
                    }
                )
                
                # Publish deletion event
                self.publish_deletion_event(inventory_id)
                
                logger.info(f"Successfully deleted asset from DynamoDB: {inventory_id}")
            else:
                # For deletion events, skip trying to find by tags as the object is gone
                if not is_delete_event:
                    # Only try to get tags if it's NOT a deletion event
                    try:
                        # Only try tags if the object still exists
                        existing_tags = self.s3.get_object_tagging(Bucket=bucket, Key=key)
                        tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}
                        
                        if "InventoryID" in tags:
                            inventory_id = tags["InventoryID"]
                            logger.info(f"Found InventoryID in S3 tags: {inventory_id}")
                            
                            # Delete from DynamoDB
                            self.dynamodb.delete_item(
                                Key={
                                    "InventoryID": inventory_id
                                }
                            )
                            
                            # Publish deletion event
                            self.publish_deletion_event(inventory_id)
                            
                            logger.info(f"Successfully deleted asset from DynamoDB: {inventory_id}")
                        else:
                            logger.warning(f"No InventoryID found for object: {bucket}/{key}")
                    except Exception as e:
                        logger.warning(f"Error finding by tags: {str(e)}")
                else:
                    logger.info(f"No DynamoDB record found by S3 path and skipping tag lookup for deletion event: {bucket}/{key}")
            
            # Add metrics
            metrics.add_metric(name="AssetDeletionProcessed", unit=MetricUnit.Count, value=1)

        except Exception as e:
            logger.exception(f"Error in delete_asset: {bucket}/{key}, error: {e}")
            metrics.add_metric(name="AssetDeletionErrors", unit=MetricUnit.Count, value=1)
            raise

    @tracer.capture_method
    def publish_deletion_event(self, inventory_id: str):
        """Publish asset deletion event to EventBridge with optimized serialization"""
        try:
            event_detail = {
                "InventoryID": inventory_id,
                "DeletedAt": datetime.utcnow().isoformat(),
            }

            # Use optimized JSON serialization
            event_json = json_serialize(event_detail)
            logger.info(f"Publishing deletion event for: {inventory_id}")

            response = self.eventbridge.put_events(
                Entries=[
                    {
                        "Source": "custom.asset.processor",
                        "DetailType": "AssetDeleted",
                        "Detail": event_json,
                        "EventBusName": os.environ["EVENT_BUS_NAME"],
                    }
                ]
            )

            # Log only if there's an error
            if "FailedEntryCount" in response and response["FailedEntryCount"] > 0:
                logger.error(f"Deletion event publish failed: {json_serialize(response)}")
            else:
                logger.info(f"Deletion event published successfully")
            
            # Add metrics
            metrics.add_metric(name="DeletionEventsPublished", unit=MetricUnit.Count, value=1)

        except Exception as e:
            logger.exception(f"Error publishing deletion event: {str(e)}")
            metrics.add_metric(name="DeletionEventPublishErrors", unit=MetricUnit.Count, value=1)
            raise


# Process records in parallel with improved logging
def process_records_in_parallel(processor: AssetProcessor, records: List[Dict], max_workers: int = 5):
    """Process records in parallel using a ThreadPoolExecutor"""
    # Add logging for initial record count
    logger.info(f"Starting parallel processing with {len(records)} records")
    
    # Debug log the first record structure
    if records and len(records) > 0:
        logger.info(f"First record structure: {json_serialize(records[0])}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        skipped_records = 0
        
        for i, record in enumerate(records):
            try:
                # Extract S3 details using the helper function
                bucket, key, event_name = extract_s3_details_from_event(record)
                
                if bucket and key:
                    # Debug log for keys containing special characters
                    if '+' in key or '%' in key:
                        logger.info(f"Key with special characters: {key}")
                    
                    logger.info(f"Submitting task for bucket: {bucket}, key: {key}, event: {event_name}")
                    futures.append(
                        executor.submit(process_s3_event, processor, bucket, key, event_name)
                    )
                else:
                    logger.warning(f"Could not extract bucket/key from record {i}")
                    skipped_records += 1
            except Exception as e:
                logger.exception(f"Error preparing record {i} for parallel processing: {e}")
                skipped_records += 1
        
        # Log summary of submitted tasks
        logger.info(f"Submitted {len(futures)} tasks for parallel processing, skipped {skipped_records} records")
        
        if not futures:
            logger.warning("No tasks were submitted for processing! Check record format.")
            # Safe serialization for the sample record
            if len(records) > 0:
                sample_record = records[0]
                if isinstance(sample_record, dict):
                    # Fix: Avoid using __name__ attribute for str type
                    sample_str = json_serialize({k: type(v).__name__ if hasattr(type(v), '__name__') else str(type(v)) for k, v in sample_record.items()})
                else:
                    # Fix: Avoid using __name__ attribute for str type
                    sample_str = type(sample_record).__name__ if hasattr(type(sample_record), '__name__') else str(type(sample_record))
            else:
                sample_str = "empty"
                
            logger.info(f"Full event format: {json_serialize({
                'type': type(records).__name__ if hasattr(type(records), '__name__') else str(type(records)),
                'length': len(records) if hasattr(records, '__len__') else 'unknown',
                'sample_structure': sample_str
            })}")
            return
        
        # Wait for all to complete
        completed_futures = concurrent.futures.wait(futures)
        
        # Process results and count successes/failures
        success_count = 0
        error_count = 0
        for future in completed_futures.done:
            try:
                future.result()
                success_count += 1
            except Exception as e:
                error_count += 1
                # Log the actual exception
                logger.exception(f"Task execution failed: {str(e)}")
        
        logger.info(f"Parallel processing complete: {success_count} succeeded, {error_count} failed, {skipped_records} skipped")
        
        # Add metrics
        metrics.add_metric(name="RecordsProcessedSuccessfully", unit=MetricUnit.Count, value=success_count)
        metrics.add_metric(name="RecordsSkipped", unit=MetricUnit.Count, value=skipped_records)
        if error_count > 0:
            metrics.add_metric(name="RecordsProcessedWithErrors", unit=MetricUnit.Count, value=error_count)

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict, context: LambdaContext) -> Dict:
    """Handle S3 events via SQS from either direct S3 notifications or EventBridge Pipes"""
    # Add overall Lambda metrics
    metrics.add_metric(name="Invocations", unit=MetricUnit.Count, value=1)
    
    # Initialize memory usage metrics
    initial_memory = get_memory_usage()
    
    # Thorough event investigation logging
    logger.info(f"Received event type: {type(event).__name__}")
    if isinstance(event, dict):
        logger.info(f"Event keys: {list(event.keys())}")
        if "Records" in event:
            logger.info(f"Records count: {len(event['Records'])}")
            if event['Records']:
                logger.info(f"First record type: {type(event['Records'][0]).__name__}")
                if isinstance(event['Records'][0], dict):
                    logger.info(f"First record keys: {list(event['Records'][0].keys())}")
                    # Check if it's an SQS event
                    if "eventSource" in event['Records'][0] and event['Records'][0]["eventSource"] == "aws:sqs":
                        logger.info("Detected SQS event source")
    
    # Create processor without using batch_writer
    processor = AssetProcessor()

    # Log environment variables at debug level
    logger.debug(f"Environment variables: ASSETS_TABLE={os.environ.get('ASSETS_TABLE')}, EVENT_BUS_NAME={os.environ.get('EVENT_BUS_NAME')}")
    
    # Check DynamoDB table exists
    try:
        dynamodb_client = boto3.client('dynamodb')
        table_info = dynamodb_client.describe_table(
            TableName=os.environ["ASSETS_TABLE"]
        )
        logger.debug(f"DynamoDB table info available - Table Status: {table_info.get('Table', {}).get('TableStatus')}")
    except Exception as e:
        logger.error(f"Error accessing DynamoDB table: {str(e)}")
        metrics.add_metric(name="DynamoDBAccessErrors", unit=MetricUnit.Count, value=1)
    
    try:
        # Quick filter for empty event
        if not event:
            logger.warning("Empty event received")
            # Add comprehensive event structure logging to diagnose issues
            logger.info(f"Event type: {type(event).__name__}")
            if isinstance(event, dict):
                logger.info(f"Event keys: {list(event.keys())}")
                if "Records" in event:
                    logger.info(f"Records count: {len(event['Records'])}")
                    if event['Records']:
                        logger.info(f"First record keys: {list(event['Records'][0].keys())}")
                        if 's3' in event['Records'][0]:
                            logger.info(f"S3 structure: {json_serialize(event['Records'][0]['s3'])}")
            elif isinstance(event, list):
                logger.info(f"List event length: {len(event)}")
                if event:
                    logger.info(f"First item type: {type(event[0]).__name__}")
                    if isinstance(event[0], dict):
                        logger.info(f"First item keys: {list(event[0].keys())}")
            return {"statusCode": 200, "body": "No records to process"}
            
        # Check if it's a test event
        if isinstance(event, dict) and event.get("Event") == "s3:TestEvent":
            logger.info("Received S3 test event - skipping processing")
            return {"statusCode": 200, "body": "Test event received"}
        
        # Count records for metrics
        total_records = 0
        
        # Enhanced event detection - determine event type with less nesting
        if isinstance(event, list):
            # Direct list of records - process in parallel 
            logger.info(f"Processing {len(event)} records directly")
            total_records = len(event)
            process_records_in_parallel(processor, event)
            
        elif isinstance(event, dict) and "Records" in event:
            # Standard S3 event format
            logger.info(f"Processing standard S3 event with {len(event['Records'])} records")
            total_records = len(event["Records"])
            
            # Process records in parallel
            s3_records = []
            for record in event["Records"]:
                if "body" in record:
                    # Parse SQS message body
                    try:
                        body = json.loads(record["body"])
                        if "Records" in body:
                            # Add these records to the batch
                            s3_records.extend(body["Records"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse SQS message body")
                        continue
                elif "s3" in record:
                    # Direct S3 record
                    s3_records.append(record)
            
            # Process the collected records in parallel
            if s3_records:
                logger.info(f"Processing {len(s3_records)} S3 records in parallel")
                process_records_in_parallel(processor, s3_records)
            
        elif isinstance(event, dict) and "detail-type" in event:
            # EventBridge event format - single event
            logger.info("Processing EventBridge event")
            total_records = 1
            
            if event.get("source") != "aws.s3":
                logger.warning(f"Unexpected event source: {event.get('source')}")
                return {"statusCode": 200, "body": "Event ignored - not from S3"}
            
            detail = event.get("detail", {})
            
            # Extract bucket and key with enhanced robustness
            bucket = None
            key = None
            
            # Check all possible locations for bucket
            if isinstance(detail.get("bucket"), dict):
                bucket = detail["bucket"].get("name")
            elif isinstance(detail.get("bucket"), str):
                bucket = detail["bucket"]
            
            # Check all possible locations for key
            if isinstance(detail.get("object"), dict):
                key = detail["object"].get("key")
            elif isinstance(detail.get("object"), str):
                key = detail["object"]
            elif "key" in detail:
                key = detail["key"]
            
            # Map EventBridge detail-type to S3 event name
            detail_type = event.get("detail-type", "")
            event_type_mapping = {
                "Object Created": "ObjectCreated:",
                "Object Deleted": "ObjectRemoved:",
                "Object Restored": "ObjectRestore:",
                "Object Tagged": "ObjectTagging:",
                "PutObject": "ObjectCreated:Put",
                "CompleteMultipartUpload": "ObjectCreated:CompleteMultipartUpload",
                "DeleteObject": "ObjectRemoved:Delete",
                "CopyObject": "ObjectCreated:Copy"  # Add mapping for CopyObject events
            }
            
            event_name = event_type_mapping.get(detail_type, "")
            
            # If we have valid bucket and key, process the event
            if bucket and key:
                logger.info(f"Processing EventBridge event for {bucket}/{key} with event type: {event_name}")
                process_s3_event(processor, bucket, key, event_name)
            else:
                logger.warning(f"Missing bucket or key in EventBridge event: {json_serialize(detail)}")
        
        # Calculate memory usage metrics
        final_memory = get_memory_usage()
        memory_used = final_memory - initial_memory
        
        metrics.add_metric(name="MemoryUsedMB", unit=MetricUnit.Megabytes, value=memory_used)
        metrics.add_metric(name="RecordsProcessed", unit=MetricUnit.Count, value=total_records)
        logger.info(f"Finished processing {total_records} records, memory used: {memory_used}MB")
        
        return {"statusCode": 200, "body": f"Processed {total_records} records successfully"}

    except Exception as e:
        logger.exception("Error in handler")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        raise


def process_s3_event(processor: AssetProcessor, bucket: str, key: str, event_name: str):
    """Process a single S3 event with improved performance"""
    # Skip processing if event type not relevant (quick filtering)
    if not is_relevant_event(event_name):
        logger.info(f"Skipping irrelevant event type: {event_name} for {bucket}/{key}")
        return
    
    logger.info(f"Processing {event_name} event for asset: {bucket}/{key}")

    # Record start time for duration tracking
    start_time = datetime.now()
    
    try:
        if event_name.startswith("ObjectRemoved:"):
            # Handle deletion - only delete from DynamoDB, don't try to delete the S3 object again
            logger.info(f"Processing deletion event for {bucket}/{key}")
            processor.delete_asset(bucket, key, is_delete_event=True)
            metrics.add_metric(name="DeletedAssets", unit=MetricUnit.Count, value=1)
            logger.info(f"Asset deletion processed: {key}")
        else:
            # Handle creation/modification/copy events - process all ObjectCreated events the same way
            logger.info(f"Processing ObjectCreated event for {bucket}/{key}")
            
            # Verify object exists in S3 before processing
            try:
                processor.s3.head_object(Bucket=bucket, Key=key)
            except Exception as s3_error:
                logger.error(f"S3 object verification failed for {bucket}/{key}: {str(s3_error)}")
                # Log exact key for debugging to see if there are encoding issues
                logger.error(f"Failed key details - length: {len(key)}, contains '+': {'+' in key}, raw key: {repr(key)}")
                raise
            
            # Process all ObjectCreated events (including Copy) the same way
            result = processor.process_asset(bucket, key)
            if result:
                metrics.add_metric(name="ProcessedAssets", unit=MetricUnit.Count, value=1)
                metrics.add_metric(name="CreationEvents", unit=MetricUnit.Count, value=1)
                logger.info(f"Asset processed successfully: {result['DigitalSourceAsset']['ID']}")
            else:
                logger.info(f"Asset already processed or skipped: {key}")
        
        # Track processing duration
        duration = (datetime.now() - start_time).total_seconds()
        metrics.add_metric(name="EventProcessingTime", unit=MetricUnit.Seconds, value=duration)
        
    except Exception as e:
        logger.exception(f"Error in process_s3_event for {bucket}/{key}: {str(e)}")
        # Log key details for troubleshooting
        logger.error(f"Key details - length: {len(key)}, contains '+': {'+' in key}, raw key: {repr(key)}")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        # Track error duration too
        duration = (datetime.now() - start_time).total_seconds()
        metrics.add_metric(name="FailedEventProcessingTime", unit=MetricUnit.Seconds, value=duration)
        raise


# Helper function to get memory usage
def get_memory_usage() -> float:
    """Get current memory usage in MB"""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except ImportError:
        # If resource module not available (e.g., on Windows), return 0
        return 0

def extract_s3_details_from_event(event_record: Dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract S3 bucket, key and event type from various event structures
    Returns: (bucket, key, event_name)
    """
    # Direct S3 event structure
    if "s3" in event_record:
        if "bucket" in event_record["s3"] and "object" in event_record["s3"]:
            bucket = event_record["s3"]["bucket"]["name"]
            key = urllib.parse.unquote(event_record["s3"]["object"]["key"])
            event_name = event_record.get("eventName", "ObjectCreated:")
            return bucket, key, event_name
    
    # SQS message with EventBridge payload
    if "body" in event_record and "eventSource" in event_record and event_record["eventSource"] == "aws:sqs":
        try:
            body = json.loads(event_record["body"])
            
            # Check if this is an S3 event (might be in Records array)
            if "Records" in body and isinstance(body["Records"], list) and len(body["Records"]) > 0:
                for record in body["Records"]:
                    if record.get("eventSource") == "aws:s3" and "s3" in record:
                        bucket = record["s3"]["bucket"]["name"]
                        key = urllib.parse.unquote(record["s3"]["object"]["key"])
                        event_name = record.get("eventName", "ObjectCreated:")
                        # Log the extracted details for debugging
                        logger.info(f"Extracted from SQS S3 record: bucket={bucket}, key={key}, event={event_name}")
                        return bucket, key, event_name
            
            # Check if this is an S3 event from EventBridge
            if body.get("source") == "aws.s3" and "detail" in body:
                detail = body["detail"]
                
                # Extract bucket
                bucket = None
                if "bucket" in detail:
                    if isinstance(detail["bucket"], dict):
                        bucket = detail["bucket"].get("name")
                    elif isinstance(detail["bucket"], str):
                        bucket = detail["bucket"]
                
                # Extract key
                key = None
                if "object" in detail:
                    if isinstance(detail["object"], dict):
                        key = detail["object"].get("key")
                    elif isinstance(detail["object"], str):
                        key = detail["object"]
                
                # Apply URL decoding to the key if it exists
                if key:
                    key = urllib.parse.unquote(key)
                
                # Determine event type
                event_name = "ObjectCreated:"
                if body.get("detail-type") == "Object Deleted":
                    event_name = "ObjectRemoved:"
                
                return bucket, key, event_name
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SQS message body: {str(e)}")

    # Log unrecognized event structure to help diagnose issues
    logger.warning(f"Unrecognized event structure: {json_serialize(event_record)}")
    
    return None, None, None