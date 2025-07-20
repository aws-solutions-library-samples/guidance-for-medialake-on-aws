import concurrent.futures
import functools
import hashlib
import http.client
import json
import os
import resource
import threading
import urllib.parse
import uuid
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, TypedDict
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config

# OpenSearch configuration
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("INDEX_NAME", "media")
OPENSEARCH_SERVICE = os.environ.get("OPENSEARCH_SERVICE", "es")
AWS_REGION = os.environ.get("REGION", "")

# S3 Vector Store configuration
VECTOR_BUCKET_NAME = os.environ.get("VECTOR_BUCKET_NAME", "")
VECTOR_INDEX_NAME = os.environ.get("VECTOR_INDEX_NAME", "media-vectors")

# Re-use boto3’s session credentials
_session = boto3.Session()
_credentials = _session.get_credentials()

# Global clients - initialized once for Lambda container reuse
s3_client = None
dynamodb_resource = None
dynamodb_client = None
eventbridge_client = None
s3_vector_client = None

# Environment configuration
DO_NOT_INGEST_DUPLICATES = (
    os.environ.get("DO_NOT_INGEST_DUPLICATES", "True").lower() == "true"
)


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

# Log configuration at startup
logger.info(
    f"Lambda configuration - DO_NOT_INGEST_DUPLICATES: {DO_NOT_INGEST_DUPLICATES}"
)
logger.info(
    "Note: Files with same hash AND same object key will always be skipped regardless of DO_NOT_INGEST_DUPLICATES setting"
)

# Configure S3 client with retries
s3_config = Config(
    retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=15, connect_timeout=5
)


def initialize_global_clients():
    """Initialize global AWS clients for container reuse"""
    global s3_client, dynamodb_resource, dynamodb_client, eventbridge_client, s3_vector_client

    if s3_client is None:
        s3_client = boto3.client("s3", config=s3_config)
        logger.info("Initialized global S3 client")

    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb")
        logger.info("Initialized global DynamoDB resource")

    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")
        logger.info("Initialized global DynamoDB client")

    if eventbridge_client is None:
        eventbridge_client = boto3.client("events")
        logger.info("Initialized global EventBridge client")

    if s3_vector_client is None and VECTOR_BUCKET_NAME:
        try:
            s3_vector_client = boto3.client("s3vectors", region_name=AWS_REGION)
            logger.info("Initialized global S3 Vector Store client")
        except Exception as e:
            logger.warning(f"Failed to initialize S3 Vector Store client: {e}")
            s3_vector_client = None


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


boto3  # Global instance to reduce instantiation costs
datetime_encoder = DateTimeEncoder()


def json_serialize(obj):
    """Serialize object to JSON string handling datetime objects"""
    return json.dumps(obj, cls=DateTimeEncoder)


# LRU cache for type mappings
@functools.lru_cache(maxsize=100)
def get_type_abbreviation(asset_type: str) -> str:
    """Cache type mappings to reduce dict lookups"""
    type_abbreviations = {"Image": "img", "Video": "vid", "Audio": "aud"}
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

    # Image classification - matching Default Image Pipeline: PSD, TIF, JPG, JPEG, PNG, WEBP, GIF, SVG
    image_mimes = ["image/", "application/photoshop", "application/illustrator"]
    image_extensions = [
        "psd",
        "tif",
        "tiff",
        "jpg",
        "jpeg",
        "png",
        "webp",
        "gif",
        "svg",
    ]

    # Video classification - matching Default Video Pipeline: FLV, MP4, MOV, AVI, MKV, WEBM, MXF
    video_mimes = ["video/"]
    video_extensions = ["flv", "mp4", "mov", "avi", "mkv", "webm", "mxf"]

    # Audio classification - matching Default Audio Pipeline: WAV, AIFF, AIF, MP3, PCM, M4A
    audio_mimes = ["audio/"]
    audio_extensions = ["wav", "aiff", "aif", "mp3", "pcm", "m4a"]

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
        mime_main_type = content_type.split("/")[0].capitalize()
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
def is_relevant_event(
    event_name: str, allowed_prefixes=("ObjectCreated:", "ObjectRemoved:")
) -> bool:
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
        # Ensure global clients are initialized
        initialize_global_clients()

        # Use global clients for better performance
        self.s3 = s3_client

        # Setup DynamoDB with global resources
        self.table = dynamodb_resource.Table(os.environ["ASSETS_TABLE"])
        self.dynamodb = self.table

        # EventBridge client
        self.eventbridge = eventbridge_client

        # Cache for extension to content type mapping
        self.extension_content_type_cache = {}

        # Initialize a lock for thread-safe access to processed_inventory_ids
        self.lock = threading.Lock()

        # Set to track processed inventory IDs to prevent duplicates
        self.processed_inventory_ids = set()

        # Add current asset tracking
        self.current_asset_id = None
        self.current_inventory_id = None

        _session = boto3.Session()
        self._credentials = _session.get_credentials()

    def _signed_request(
        self, method: str, url: str, payload: dict | None = None, timeout: int = 60
    ) -> tuple[int, str]:
        """Build, sign and send an HTTPS request with SigV4 auth."""
        headers = {"Content-Type": "application/json"}
        if payload:
            body = json.dumps(payload)
        else:
            body = None

        req = AWSRequest(method=method, url=url, data=body, headers=headers)

        SigV4Auth(self._credentials, OPENSEARCH_SERVICE, AWS_REGION).add_auth(req)

        prepared = req.prepare()

        parsed = urlparse(prepared.url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        conn = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=timeout
        )
        conn.request(
            prepared.method, path, body=prepared.body, headers=dict(prepared.headers)
        )
        resp = conn.getresponse()
        resp_body = resp.read().decode("utf-8")
        conn.close()
        return resp.status, resp_body

    def _parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        """Parse S3 URI into bucket and key components"""
        if not s3_uri or not s3_uri.startswith("s3://"):
            return None, None

        # Remove s3:// prefix and split
        path = s3_uri[5:]  # Remove "s3://"
        parts = path.split("/", 1)

        if len(parts) != 2:
            return None, None

        return parts[0], parts[1]  # bucket, key

    def _delete_associated_s3_files(
        self, asset_record: Dict, main_bucket: str, main_key: str
    ) -> None:
        """Delete all S3 files associated with this asset (excluding already deleted main file)"""
        files_to_delete = []

        # Extract derived representations
        for rep in asset_record.get("DerivedRepresentations", []):
            storage_info = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            if storage_info:
                bucket = storage_info.get("Bucket")
                key = storage_info.get("ObjectKey", {}).get("FullPath")
                if bucket and key and not (bucket == main_bucket and key == main_key):
                    files_to_delete.append((bucket, key))

        # Extract transcript files
        if transcript_uri := asset_record.get("TranscriptionS3Uri"):
            transcript_bucket, transcript_key = self._parse_s3_uri(transcript_uri)
            if transcript_bucket and transcript_key:
                files_to_delete.append((transcript_bucket, transcript_key))

        # Delete files in parallel
        if files_to_delete:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(self._safe_delete_s3_file, bucket, key): (
                        bucket,
                        key,
                    )
                    for bucket, key in files_to_delete
                }

                for future in concurrent.futures.as_completed(futures):
                    bucket, key = futures[future]
                    try:
                        future.result()
                        logger.info(f"Deleted associated file: {bucket}/{key}")
                    except Exception as e:
                        logger.error(
                            f"Failed to delete associated file {bucket}/{key}: {str(e)}"
                        )

    def _safe_delete_s3_file(self, bucket: str, key: str) -> None:
        """Safely delete S3 file with error handling"""
        try:
            self.s3.delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            logger.error(f"Error deleting S3 file {bucket}/{key}: {str(e)}")
            raise

    def delete_opensearch_docs(self, asset_id: str) -> None:
        """Delete all OpenSearch docs for a given DigitalSourceAsset.ID."""
        if not OPENSEARCH_ENDPOINT:
            logger.info("OPENSEARCH_ENDPOINT not set – skipping OpenSearch deletion.")
            return

        host = OPENSEARCH_ENDPOINT.lstrip("https://").lstrip("http://")
        url = f"https://{host}/{OPENSEARCH_INDEX}/_delete_by_query?refresh=true&conflicts=proceed"
        query = {"query": {"term": {"DigitalSourceAsset.ID": asset_id}}}

        status, body = self._signed_request("POST", url, payload=query)
        if status not in (200, 202):
            logger.error(f"OpenSearch deletion failed (status={status}): {body}")
        else:
            deleted = 0
            try:
                deleted = json.loads(body).get("deleted", 0)
            except Exception:
                pass
            logger.info(
                f"OpenSearch deletion complete – deleted {deleted} docs for {asset_id}"
            )
            metrics.add_metric(
                name="OpenSearchDocsDeleted", unit=MetricUnit.Count, value=deleted
            )

    def delete_s3_vectors(self, inventory_id: str) -> int:
        """
        Delete S3 vectors associated with inventory_id.
        Uses metadata filtering to find all vectors for the asset.
        """
        if not VECTOR_BUCKET_NAME or not s3_vector_client:
            logger.info("S3 Vector Store not configured – skipping vector deletion")
            return 0

        try:
            # List all vectors with metadata to filter by inventory_id
            vectors_to_delete = []
            next_token = None

            while True:
                list_params = {
                    "vectorBucketName": VECTOR_BUCKET_NAME,
                    "indexName": VECTOR_INDEX_NAME,
                    "returnMetadata": True,
                    "maxResults": 500,  # Process in batches
                }

                if next_token:
                    list_params["nextToken"] = next_token

                response = s3_vector_client.list_vectors(**list_params)
                vectors = response.get("vectors", [])

                # Filter vectors by inventory_id in metadata
                for vector in vectors:
                    metadata = vector.get("metadata", {})
                    if (
                        isinstance(metadata, dict)
                        and metadata.get("inventory_id") == inventory_id
                    ):
                        vectors_to_delete.append(vector["key"])

                next_token = response.get("nextToken")
                if not next_token:
                    break

            if not vectors_to_delete:
                logger.info(f"No vectors found for inventory_id: {inventory_id}")
                return 0

            logger.info(
                f"Found {len(vectors_to_delete)} vectors to delete for {inventory_id}",
                extra={
                    "keys": vectors_to_delete[:10]
                },  # Log first 10 keys for debugging
            )

            # Batch delete vectors
            s3_vector_client.delete_vectors(
                vectorBucketName=VECTOR_BUCKET_NAME,
                indexName=VECTOR_INDEX_NAME,
                keys=vectors_to_delete,
            )

            logger.info(
                f"Successfully deleted {len(vectors_to_delete)} vectors for {inventory_id}"
            )
            metrics.add_metric(
                "VectorsDeleted", MetricUnit.Count, len(vectors_to_delete)
            )
            return len(vectors_to_delete)

        except Exception as e:
            logger.error(f"S3 vector deletion failed for {inventory_id}: {e}")
            metrics.add_metric("VectorDeletionErrors", MetricUnit.Count, 1)
            # Don't raise - vector deletion failure shouldn't block asset deletion
            return 0

    @contextmanager
    def asset_context(self, asset_id=None, inventory_id=None):
        """Context manager to set asset ID in logs for the duration of an operation"""
        # Store previous values
        previous_asset_id = self.current_asset_id
        previous_inventory_id = self.current_inventory_id

        try:
            # Set new values if provided
            if asset_id:
                self.current_asset_id = asset_id
                logger.append_keys(assetID=asset_id)
            if inventory_id:
                self.current_inventory_id = inventory_id
                logger.append_keys(inventoryID=inventory_id)
            yield
        finally:
            # Restore previous values
            self.current_asset_id = previous_asset_id
            self.current_inventory_id = previous_inventory_id
            # Update logger context
            logger.append_keys(
                assetID=previous_asset_id, inventoryID=previous_inventory_id
            )

    def _log_with_asset_context(
        self, message, level="INFO", asset_id=None, inventory_id=None
    ):
        """Helper to log with asset context"""
        asset_id = asset_id or self.current_asset_id
        inventory_id = inventory_id or self.current_inventory_id

        context = {}
        if asset_id:
            context["assetID"] = asset_id
        if inventory_id:
            context["inventoryID"] = inventory_id

        if level.upper() == "INFO":
            logger.info(message, **context)
        elif level.upper() == "WARNING":
            logger.warning(message, **context)
        elif level.upper() == "ERROR":
            logger.error(message, **context)
        elif level.upper() == "CRITICAL":
            logger.critical(message, **context)
        else:
            logger.info(message, **context)

    def _decode_s3_event_key(self, encoded_key: str) -> str:
        """Decode S3 event key by handling URL encoding properly"""
        # First, decode all URL-encoded sequences (%20, %E2%80%AF, etc.)
        decoded_key = urllib.parse.unquote(encoded_key)

        # In S3 event notifications, '+' characters typically represent spaces
        # This is different from general URL encoding where '+' in paths should be literal
        # But S3 notifications often use '+' to represent spaces in object keys
        decoded_key = decoded_key.replace("+", " ")

        return decoded_key

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
            logger.exception(
                f"Error calculating MD5 hash for {bucket}/{key}, error: {e}"
            )
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
        original_key = key
        key = self._decode_s3_event_key(key)

        # Log key transformation for debugging
        if original_key != key:
            logger.info(f"Key decoded from '{original_key}' to '{key}'")

        try:
            # Get S3 object metadata and tags in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                head_future = executor.submit(
                    self.s3.head_object, Bucket=bucket, Key=key
                )
                tag_future = executor.submit(
                    self.s3.get_object_tagging, Bucket=bucket, Key=key
                )

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
            logger.info(
                f"Asset type determination for {key}: content_type={content_type}, file_ext={file_ext}, determined_type={asset_type}"
            )

            # Stop processing if asset type is not one of: "Image", "Video", "Audio"
            if asset_type not in ["Image", "Video", "Audio"]:
                logger.info(
                    f"Skipping processing for unsupported asset type: {asset_type} for {bucket}/{key}"
                )
                metrics.add_metric(
                    name="UnsupportedAssetTypeSkipped", unit=MetricUnit.Count, value=1
                )
                return None

            tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}

            # Check existing tags first - this is a fast path if object already processed
            if "InventoryID" in tags and "AssetID" in tags:
                # Use the asset context for consistent logging
                with self.asset_context(
                    asset_id=tags["AssetID"], inventory_id=tags["InventoryID"]
                ):
                    self._log_with_asset_context(
                        f"Asset already fully processed: {tags['AssetID']}"
                    )

                    # Add logging to check if the record exists in DynamoDB
                    try:
                        existing_record = self.dynamodb.get_item(
                            Key={"InventoryID": tags["InventoryID"]}
                        )
                        if "Item" in existing_record:
                            self._log_with_asset_context(
                                f"Found existing record in DynamoDB: {json_serialize(existing_record['Item'])}"
                            )

                            # Update the lastModifiedDate field but preserve originalIngestDate
                            # Create updateExpression and attributeValues for update operation
                            update_expression = (
                                "SET DigitalSourceAsset.lastModifiedDate = :lastModDate"
                            )
                            expression_attribute_values = {
                                ":lastModDate": s3_last_modified_str
                            }

                            # Update only the lastModifiedDate
                            self.dynamodb.update_item(
                                Key={"InventoryID": tags["InventoryID"]},
                                UpdateExpression=update_expression,
                                ExpressionAttributeValues=expression_attribute_values,
                            )
                            self._log_with_asset_context(
                                f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {tags['AssetID']}"
                            )
                        else:
                            self._log_with_asset_context(
                                f"Asset has tags but no record found in DynamoDB for InventoryID: {tags['InventoryID']}",
                                level="WARNING",
                            )

                            # Recreate the record if it doesn't exist in DynamoDB
                            self._log_with_asset_context(
                                f"Recreating DynamoDB record for tagged asset: {key}"
                            )

                            # Calculate MD5 hash for the file
                            md5_hash = self._calculate_md5(bucket, key)

                            # Create metadata structure
                            metadata = self._create_asset_metadata(
                                response, bucket, key, md5_hash
                            )

                            # Create DynamoDB entry using existing InventoryID and AssetID
                            asset_id = tags["AssetID"]
                            inventory_id = tags["InventoryID"]

                            # Extract asset type from AssetID or content type
                            if ":" in asset_id:
                                parts = asset_id.split(":")
                                if len(parts) >= 2:
                                    type_abbrev = parts[1]
                                    asset_type_map = {
                                        "img": "Image",
                                        "vid": "Video",
                                        "aud": "Audio",
                                    }
                                    asset_type = asset_type_map.get(
                                        type_abbrev, "Image"
                                    )
                                else:
                                    content_type = response.get("ContentType", "")
                                    file_ext = key.split(".")[-1] if "." in key else ""
                                    asset_type = determine_asset_type(
                                        content_type, file_ext
                                    )
                            else:
                                content_type = response.get("ContentType", "")
                                file_ext = key.split(".")[-1] if "." in key else ""
                                asset_type = determine_asset_type(
                                    content_type, file_ext
                                )

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
                                        "Format": (
                                            key.split(".")[-1].upper()
                                            if "." in key
                                            else ""
                                        ),
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
                                self._log_with_asset_context(
                                    f"Successfully recreated DynamoDB record for {inventory_id}"
                                )

                                # Verify the write with a get_item
                                verification = self.dynamodb.get_item(
                                    Key={"InventoryID": inventory_id}
                                )
                                if "Item" in verification:
                                    self._log_with_asset_context(
                                        f"Verification successful - recreated item exists in DynamoDB"
                                    )
                                else:
                                    self._log_with_asset_context(
                                        f"Verification failed - recreated item not found in DynamoDB",
                                        level="WARNING",
                                    )

                                # Publish event for the recreated record
                                self.publish_event(
                                    inventory_id,
                                    asset_id,
                                    metadata,
                                )

                                return item
                            except Exception as e:
                                self._log_with_asset_context(
                                    f"Error recreating DynamoDB record: {str(e)}",
                                    level="ERROR",
                                )
                                logger.exception(
                                    f"Error recreating DynamoDB record: {str(e)}"
                                )
                    except Exception as e:
                        self._log_with_asset_context(
                            f"Error checking existing record in DynamoDB: {str(e)}",
                            level="ERROR",
                        )
                        logger.exception(
                            f"Error checking existing record in DynamoDB: {str(e)}"
                        )

                    return None

            # Calculate MD5 hash for duplicate checking
            md5_hash = self._calculate_md5(bucket, key)

            # Always check if file with same hash exists in DynamoDB
            # We need this check even when DO_NOT_INGEST_DUPLICATES is False to handle same hash + same key scenario
            existing_file = self._check_existing_file(md5_hash)
            if existing_file:
                logger.info(f"Found existing file with hash {md5_hash}")
                metrics.add_metric(
                    name="DuplicateCheckPerformed", unit=MetricUnit.Count, value=1
                )
            else:
                logger.info(f"No existing file found with hash {md5_hash}")
                metrics.add_metric(
                    name="DuplicateCheckPerformed", unit=MetricUnit.Count, value=1
                )

            # Handle duplicate logic based on DO_NOT_INGEST_DUPLICATES setting
            if existing_file:
                logger.info(f"Duplicate file found with hash {md5_hash}")

                # Get the existing object key to check if it's the same file
                existing_object_key = (
                    existing_file.get("DigitalSourceAsset", {})
                    .get("MainRepresentation", {})
                    .get("StorageInfo", {})
                    .get("PrimaryLocation", {})
                    .get("ObjectKey", {})
                    .get("FullPath")
                )

                # Check if it's the same object key (same hash + same key = exact same file)
                if existing_object_key == key:
                    logger.info(
                        "Duplicate file with same hash AND same object key - skipping processing regardless of DO_NOT_INGEST_DUPLICATES setting"
                    )
                    # Always skip processing if it's the exact same file (same hash + same key)
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
                        ExpressionAttributeValues={
                            ":lastModDate": s3_last_modified_str
                        },
                    )
                    logger.info(
                        f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {existing_file['DigitalSourceAsset']['ID']}"
                    )

                    return None

                # Different object key but same hash - behavior depends on DO_NOT_INGEST_DUPLICATES
                if DO_NOT_INGEST_DUPLICATES:
                    logger.info(
                        "Same hash but different key with DO_NOT_INGEST_DUPLICATES=True - applying duplicate prevention logic"
                    )

                    # If we have InventoryID tag but no AssetID tag, generate new AssetID under existing inventory
                    if "InventoryID" in tags and "AssetID" not in tags:
                        logger.info(
                            f"Object has InventoryID but no AssetID. Generating new AssetID under existing inventory."
                        )

                        # Extract asset type from content type
                        content_type = response.get("ContentType", "")
                        file_ext = key.split(".")[-1] if "." in key else ""
                        asset_type = determine_asset_type(content_type, file_ext)
                        type_abbrev = get_type_abbreviation(
                            asset_type
                        )  # Use cached function

                        # Generate new AssetID
                        new_asset_id = f"asset:{type_abbrev}:{str(uuid.uuid4())}"

                        # Tag with existing InventoryID and new AssetID
                        self.s3.put_object_tagging(
                            Bucket=bucket,
                            Key=key,
                            Tagging={
                                "TagSet": [
                                    {
                                        "Key": "InventoryID",
                                        "Value": tags["InventoryID"],
                                    },
                                    {"Key": "AssetID", "Value": new_asset_id},
                                    {"Key": "FileHash", "Value": md5_hash},
                                ]
                            },
                        )

                        # Create new asset entry with existing inventory ID
                        metadata = self._create_asset_metadata(
                            response, bucket, key, md5_hash
                        )
                        dynamo_entry = self.create_dynamo_entry(
                            metadata,
                            inventory_id=tags["InventoryID"],
                            s3_last_modified=s3_last_modified_str,
                        )

                        self.publish_event(
                            dynamo_entry["InventoryID"],
                            dynamo_entry["DigitalSourceAsset"]["ID"],
                            metadata,
                        )

                        return dynamo_entry

                    # If hash exists in DB but object has no tags, tag with existing IDs and stop processing
                    if "InventoryID" not in tags and "AssetID" not in tags:
                        logger.info(
                            f"Hash exists in DB but object has no tags. Tagging with existing IDs."
                        )
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
                                        "Value": existing_file["DigitalSourceAsset"][
                                            "ID"
                                        ],
                                    },
                                    {"Key": "FileHash", "Value": md5_hash},
                                    {"Key": "DuplicateHash", "Value": "true"},
                                ]
                            },
                        )

                        # Update lastModifiedDate for the existing file in DynamoDB
                        self.dynamodb.update_item(
                            Key={"InventoryID": existing_file["InventoryID"]},
                            UpdateExpression="SET DigitalSourceAsset.lastModifiedDate = :lastModDate",
                            ExpressionAttributeValues={
                                ":lastModDate": s3_last_modified_str
                            },
                        )
                        logger.info(
                            f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {existing_file['DigitalSourceAsset']['ID']}"
                        )

                        return None

                    # Same hash but different key - tag with same InventoryID but new AssetID
                    logger.info(
                        "Same hash but different key. Tagging with same InventoryID but new AssetID"
                    )
                    # Extract asset type from content type
                    content_type = response.get("ContentType", "")
                    file_ext = key.split(".")[-1] if "." in key else ""
                    asset_type = determine_asset_type(content_type, file_ext)
                    type_abbrev = get_type_abbreviation(
                        asset_type
                    )  # Use cached function

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
                                {"Key": "AssetID", "Value": new_asset_id},
                                {"Key": "FileHash", "Value": md5_hash},
                                {"Key": "DuplicateHash", "Value": "true"},
                            ]
                        },
                    )
                    return None
                else:
                    logger.info(
                        "Same hash but different key with DO_NOT_INGEST_DUPLICATES=False - proceeding to create new asset"
                    )
                    # Fall through to process as new asset since DO_NOT_INGEST_DUPLICATES is False

            # Process new unique file...
            metadata = self._create_asset_metadata(response, bucket, key, md5_hash)

            # If we have InventoryID tag but no AssetID tag, use existing inventory
            if "InventoryID" in tags and "AssetID" not in tags:
                logger.info(f"Using existing InventoryID: {tags['InventoryID']}")
                dynamo_entry = self.create_dynamo_entry(
                    metadata,
                    inventory_id=tags["InventoryID"],
                    s3_last_modified=s3_last_modified_str,
                )
            else:
                # Normal processing for new file
                dynamo_entry = self.create_dynamo_entry(
                    metadata, s3_last_modified=s3_last_modified_str
                )

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
            metrics.add_metric(
                name="AssetProcessingErrors", unit=MetricUnit.Count, value=1
            )
            raise

    def _create_asset_metadata(
        self, s3_response: Dict, bucket: str, key: str, md5_hash: str
    ) -> StorageInfo:
        """Create asset metadata structure with optimized field extraction"""
        # Get file extension from key
        filename = key.split("/")[-1]
        self._extract_file_extension(filename)

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
                "ObjectMetadata": {
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
    def create_dynamo_entry(
        self,
        metadata: StorageInfo,
        inventory_id: str = None,
        s3_last_modified: str = None,
    ) -> AssetRecord:
        """Create DynamoDB entry for the asset with optimized data handling"""
        try:
            if not inventory_id:
                inventory_id = f"asset:uuid:{str(uuid.uuid4())}"
            else:
                # Use the provided inventory_id if it exists
                if not inventory_id.startswith("asset:uuid:"):
                    inventory_id = f"asset:uuid:{inventory_id}"

            # Thread-safe check for duplicate inventory IDs
            if hasattr(self, "lock") and hasattr(self, "processed_inventory_ids"):
                with self.lock:
                    if inventory_id in self.processed_inventory_ids:
                        logger.warning(
                            f"Duplicate inventory ID detected: {inventory_id} - generating a new one"
                        )
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
                "FileHash": metadata["StorageInfo"]["PrimaryLocation"]["FileInfo"][
                    "Hash"
                ]["MD5Hash"],
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
            logger.info(
                f"Attempting to write to DynamoDB table: {os.environ['ASSETS_TABLE']}"
            )
            logger.info(f"Using inventory_id: {inventory_id} for DynamoDB key")

            # Use direct put_item instead of batch_writer for immediate feedback
            try:
                # First, check if the item with this ID already exists
                existing_item = self.dynamodb.get_item(
                    Key={"InventoryID": inventory_id}
                ).get("Item")

                if existing_item:
                    logger.warning(
                        f"Item with InventoryID {inventory_id} already exists. Generating new ID."
                    )
                    # Generate a new ID and try again
                    item["InventoryID"] = f"asset:uuid:{str(uuid.uuid4())}"
                    logger.info(f"Using new InventoryID: {item['InventoryID']}")

                # Now do the put_item operation
                self.dynamodb.put_item(Item=item)
                logger.info(
                    f"put_item operation completed for InventoryID: {item['InventoryID']}"
                )
            except Exception as e:
                logger.exception(f"Error in put_item operation: {str(e)}")
                raise

            # Verify the item was written by doing a get_item
            logger.info(f"Verifying item with InventoryID: {item['InventoryID']}")
            verification_response = self.dynamodb.get_item(
                Key={"InventoryID": item["InventoryID"]}
            )

            # Log the full verification response
            logger.info(
                f"Verification response: {json_serialize(verification_response)}"
            )

            if "Item" in verification_response:
                logger.info(f"Verification successful - item exists in DynamoDB")
            else:
                logger.warning(
                    f"Verification failed - item not found in DynamoDB after put_item"
                )

                # Log additional information to help diagnose the issue
                try:
                    # Check if the table is reachable
                    table_info = dynamodb_client.describe_table(
                        TableName=os.environ["ASSETS_TABLE"]
                    )
                    logger.info(f"Table status: {table_info['Table']['TableStatus']}")

                    # Try a direct query on the table to see if the item exists
                    query_response = self.dynamodb.query(
                        KeyConditionExpression="InventoryID = :id",
                        ExpressionAttributeValues={":id": item["InventoryID"]},
                    )
                    logger.info(
                        f"Direct query response: {json_serialize(query_response)}"
                    )

                    # Try to scan the table for recent items
                    scan_response = self.dynamodb.scan(Limit=5)
                    logger.info(
                        f"Recent items scan (count={scan_response.get('Count', 0)})"
                    )

                except Exception as e:
                    logger.exception(f"Error during additional diagnostics: {str(e)}")

            return item
        except Exception as e:
            logger.exception(f"Error writing to DynamoDB: {str(e)}")
            raise

    @tracer.capture_method
    def publish_event(self, inventory_id: str, asset_id: str, metadata: StorageInfo):
        """Publish event to EventBridge with optimized serialization"""
        with self.asset_context(asset_id=asset_id, inventory_id=inventory_id):
            try:
                # Extract content type information
                content_type = (
                    metadata.get("Metadata", {})
                    .get("Embedded", {})
                    .get("S3", {})
                    .get("ContentType", "")
                )
                # Get file extension from the object key
                object_key = metadata["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                    "FullPath"
                ]
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
                self._log_with_asset_context(
                    f"Publishing event with detail size: {len(event_json)} bytes"
                )

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
                    self._log_with_asset_context(
                        f"EventBridge publish failed: {json_serialize(response)}",
                        level="ERROR",
                    )
                else:
                    self._log_with_asset_context(f"EventBridge publish successful")

                # Add metrics
                metrics.add_metric(
                    name="EventsPublished", unit=MetricUnit.Count, value=1
                )

            except Exception as e:
                self._log_with_asset_context(
                    f"Error publishing event: {str(e)}", level="ERROR"
                )
                metrics.add_metric(
                    name="EventPublishErrors", unit=MetricUnit.Count, value=1
                )
                raise

    @tracer.capture_method
    def delete_asset(
        self,
        bucket: str,
        key: str,
        is_delete_event: bool = True,
        version_id: str = None,
    ) -> None:
        """Delete asset record from DynamoDB based on S3 object deletion"""
        try:
            # Check if this deletion should be processed based on versioning
            if not self._should_process_deletion(
                bucket, key, version_id, is_delete_event
            ):
                logger.info(
                    f"Skipping deletion processing for {bucket}/{key} - not latest version or versioning check failed"
                )
                return

            # First, try to find the asset by S3 path
            storage_path = f"{bucket}:{key}"
            logger.info(f"Looking up asset by storage path: {storage_path}")

            # Define task for database lookup
            def find_by_s3path():
                try:
                    return self.dynamodb.query(
                        IndexName="S3PathIndex",
                        KeyConditionExpression="StoragePath = :path",
                        ExpressionAttributeValues={":path": storage_path},
                    )
                except Exception as e:
                    logger.exception(
                        f"Error querying DynamoDB for storage path: {str(e)}"
                    )
                    return {"Items": []}

            # Find the record by S3 path first (this uses DynamoDB, not S3)
            response = find_by_s3path()
            inventory_id = None

            if response["Items"]:
                # Found the item in DynamoDB
                asset_record = response["Items"][0]
                inventory_id = asset_record["InventoryID"]
                logger.info(f"Found item in DynamoDB by S3 path: {inventory_id}")

                # Delete all associated S3 files BEFORE deleting DynamoDB record
                self._delete_associated_s3_files(asset_record, bucket, key)

                # Delete from DynamoDB
                self.dynamodb.delete_item(Key={"InventoryID": inventory_id})
                metrics.add_metric(
                    name="AssetDeletionProcessed", unit=MetricUnit.Count, value=1
                )

                # Delete associated OpenSearch docs
                self.delete_opensearch_docs(inventory_id)

                # Delete S3 vectors
                vector_count = self.delete_s3_vectors(inventory_id)
                logger.info(f"Deleted {vector_count} vectors for asset {inventory_id}")

                # Publish deletion event
                self.publish_deletion_event(inventory_id)

                logger.info(
                    f"Successfully deleted asset {inventory_id} and all associated files"
                )

            else:
                # For deletion events, skip trying to find by tags as the object is gone
                if not is_delete_event:
                    # Only try to get tags if it's NOT a deletion event
                    try:
                        # Only try tags if the object still exists
                        existing_tags = self.s3.get_object_tagging(
                            Bucket=bucket, Key=key
                        )
                        tags = {
                            tag["Key"]: tag["Value"]
                            for tag in existing_tags.get("TagSet", [])
                        }

                        if "InventoryID" in tags:
                            inventory_id = tags["InventoryID"]
                            logger.info(f"Found InventoryID in S3 tags: {inventory_id}")

                            # Delete from DynamoDB
                            self.dynamodb.delete_item(Key={"InventoryID": inventory_id})

                            # Delete S3 vectors
                            vector_count = self.delete_s3_vectors(inventory_id)
                            logger.info(
                                f"Deleted {vector_count} vectors for asset {inventory_id}"
                            )

                            # Publish deletion event
                            self.publish_deletion_event(inventory_id)

                            logger.info(
                                f"Successfully deleted asset from DynamoDB: {inventory_id}"
                            )
                        else:
                            logger.warning(
                                f"No InventoryID found for object: {bucket}/{key}"
                            )
                    except Exception as e:
                        logger.warning(f"Error finding by tags: {str(e)}")
                else:
                    logger.info(
                        f"No DynamoDB record found by S3 path and skipping tag lookup for deletion event: {bucket}/{key}"
                    )

            # Add metrics
            metrics.add_metric(
                name="AssetDeletionProcessed", unit=MetricUnit.Count, value=1
            )

        except Exception as e:
            logger.exception(f"Error in delete_asset: {bucket}/{key}, error: {e}")
            metrics.add_metric(
                name="AssetDeletionErrors", unit=MetricUnit.Count, value=1
            )
            raise

    def _should_process_deletion(
        self,
        bucket: str,
        key: str,
        version_id: str = None,
        is_delete_event: bool = True,
    ) -> bool:
        """
        Determine if a deletion should be processed based on versioning.
        Only process deletions for the latest version if versioning is enabled.
        """
        try:
            # Check if the bucket has versioning enabled
            try:
                versioning_response = self.s3.get_bucket_versioning(Bucket=bucket)
                versioning_status = versioning_response.get("Status", "Suspended")
                logger.info(f"Bucket {bucket} versioning status: {versioning_status}")

                # If versioning is not enabled or suspended, proceed with normal deletion
                if versioning_status not in ["Enabled"]:
                    logger.info(
                        f"Versioning not enabled for bucket {bucket}, proceeding with deletion"
                    )
                    return True

            except Exception as e:
                logger.warning(
                    f"Could not check versioning status for bucket {bucket}: {str(e)}"
                )
                # If we can't check versioning, proceed with caution but allow deletion
                return True

            # If we have a version_id from the event, check if it's the latest
            if version_id and version_id != "null":
                try:
                    # List object versions to get versions for this specific key
                    versions_response = self.s3.list_object_versions(
                        Bucket=bucket,
                        Prefix=key,
                        MaxKeys=10,  # Get more versions to ensure we find the exact match
                    )

                    # Filter versions to match exact key (since Prefix can return other keys)
                    exact_versions = [
                        v
                        for v in versions_response.get("Versions", [])
                        if v.get("Key") == key
                    ]

                    if exact_versions:
                        # Sort by LastModified to get the latest version first
                        exact_versions.sort(
                            key=lambda x: x.get("LastModified", datetime.min),
                            reverse=True,
                        )
                        latest_version = exact_versions[0]
                        latest_version_id = latest_version.get("VersionId")

                        logger.info(
                            f"Latest version ID: {latest_version_id}, deletion version ID: {version_id}"
                        )

                        # Only process if this is the latest version
                        if version_id == latest_version_id:
                            logger.info(f"Deletion is for latest version, proceeding")
                            return True
                        else:
                            logger.info(
                                f"Deletion is for older version {version_id}, skipping"
                            )
                            metrics.add_metric(
                                name="OlderVersionDeletionSkipped",
                                unit=MetricUnit.Count,
                                value=1,
                            )
                            return False
                    else:
                        logger.warning(
                            f"No versions found for exact key {bucket}/{key}"
                        )
                        return True

                except Exception as e:
                    logger.warning(
                        f"Error checking object versions for {bucket}/{key}: {str(e)}"
                    )
                    # If we can't check versions, be conservative and skip
                    return False
            else:
                # No version ID provided, this might be a non-versioned deletion or delete marker
                logger.info(
                    f"No version ID provided for deletion, treating as latest version"
                )
                return True

        except Exception as e:
            logger.exception(
                f"Error in _should_process_deletion for {bucket}/{key}: {str(e)}"
            )
            # If there's an error in the check, err on the side of caution and skip
            return False

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
                logger.error(
                    f"Deletion event publish failed: {json_serialize(response)}"
                )
            else:
                logger.info(f"Deletion event published successfully")

            # Add metrics
            metrics.add_metric(
                name="DeletionEventsPublished", unit=MetricUnit.Count, value=1
            )

        except Exception as e:
            logger.exception(f"Error publishing deletion event: {str(e)}")
            metrics.add_metric(
                name="DeletionEventPublishErrors", unit=MetricUnit.Count, value=1
            )
            raise


# Process records in parallel with improved logging
def process_records_in_parallel(
    processor: AssetProcessor, records: List[Dict], max_workers: int = 5
):
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
                bucket, key, event_name, version_id = extract_s3_details_from_event(
                    record
                )

                if bucket and key:
                    # Debug log for keys containing special characters
                    if "+" in key or "%" in key:
                        logger.info(f"Key with special characters: {key}")

                    logger.info(
                        f"Submitting task for bucket: {bucket}, key: {key}, event: {event_name}, version: {version_id}"
                    )
                    futures.append(
                        executor.submit(
                            process_s3_event,
                            processor,
                            bucket,
                            key,
                            event_name,
                            version_id,
                        )
                    )
                else:
                    logger.warning(f"Could not extract bucket/key from record {i}")
                    skipped_records += 1
            except Exception as e:
                logger.exception(
                    f"Error preparing record {i} for parallel processing: {e}"
                )
                skipped_records += 1

        # Log summary of submitted tasks
        logger.info(
            f"Submitted {len(futures)} tasks for parallel processing, skipped {skipped_records} records"
        )

        if not futures:
            logger.warning(
                "No tasks were submitted for processing! Check record format."
            )
            # Safe serialization for the sample record
            if len(records) > 0:
                sample_record = records[0]
                if isinstance(sample_record, dict):
                    # Fix: Avoid using __name__ attribute for str type
                    sample_str = json_serialize(
                        {
                            k: (
                                type(v).__name__
                                if hasattr(type(v), "__name__")
                                else str(type(v))
                            )
                            for k, v in sample_record.items()
                        }
                    )
                else:
                    # Fix: Avoid using __name__ attribute for str type
                    sample_str = (
                        type(sample_record).__name__
                        if hasattr(type(sample_record), "__name__")
                        else str(type(sample_record))
                    )
            else:
                sample_str = "empty"

            event_format_data = {
                "type": (
                    type(records).__name__
                    if hasattr(type(records), "__name__")
                    else str(type(records))
                ),
                "length": len(records) if hasattr(records, "__len__") else "unknown",
                "sample_structure": sample_str,
            }
            logger.info(f"Full event format: {json_serialize(event_format_data)}")
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

        logger.info(
            f"Parallel processing complete: {success_count} succeeded, {error_count} failed, {skipped_records} skipped"
        )

        # Add metrics
        metrics.add_metric(
            name="RecordsProcessedSuccessfully",
            unit=MetricUnit.Count,
            value=success_count,
        )
        metrics.add_metric(
            name="RecordsSkipped", unit=MetricUnit.Count, value=skipped_records
        )
        if error_count > 0:
            metrics.add_metric(
                name="RecordsProcessedWithErrors",
                unit=MetricUnit.Count,
                value=error_count,
            )


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
            if event["Records"]:
                logger.info(f"First record type: {type(event['Records'][0]).__name__}")
                if isinstance(event["Records"][0], dict):
                    logger.info(
                        f"First record keys: {list(event['Records'][0].keys())}"
                    )
                    # Check if it's an SQS event
                    if (
                        "eventSource" in event["Records"][0]
                        and event["Records"][0]["eventSource"] == "aws:sqs"
                    ):
                        logger.info("Detected SQS event source")

    # Create processor without using batch_writer
    processor = AssetProcessor()

    # Log environment variables at debug level
    logger.debug(
        f"Environment variables: ASSETS_TABLE={os.environ.get('ASSETS_TABLE')}, "
        f"EVENT_BUS_NAME={os.environ.get('EVENT_BUS_NAME')}"
    )

    # Initialize global clients
    initialize_global_clients()

    # Check DynamoDB table exists
    try:
        table_info = dynamodb_client.describe_table(
            TableName=os.environ["ASSETS_TABLE"]
        )
        logger.debug(
            f"DynamoDB table info available - Table Status: {dynamo_client.describe_table(TableName=table_name).get('Table', {}).get('TableStatus')}"
        )
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
                    if event["Records"]:
                        logger.info(
                            f"First record keys: {list(event['Records'][0].keys())}"
                        )
                        if "s3" in event["Records"][0]:
                            logger.info(
                                f"S3 structure: {json_serialize(event['Records'][0]['s3'])}"
                            )
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
            logger.info(
                f"Processing standard S3 event with {len(event['Records'])} records"
            )
            total_records = len(event["Records"])

            # Process records in parallel
            s3_records = []
            for record in event["Records"]:
                if (
                    "body" in record
                    and "eventSource" in record
                    and record["eventSource"] == "aws:sqs"
                ):
                    # This is an SQS message, parse the body
                    try:
                        body = json.loads(record["body"])
                        if "Records" in body and isinstance(body["Records"], list):
                            # Extract S3 records from SQS message body
                            for s3_record in body["Records"]:
                                # Validate that this is a proper S3 record
                                if "s3" in s3_record and "eventSource" in s3_record:
                                    valid_sources = [
                                        "aws:s3",
                                        "medialake.AssetSyncProcessor",
                                    ]
                                    if s3_record.get("eventSource") in valid_sources:
                                        s3_records.append(s3_record)
                                        logger.info(
                                            f"Extracted S3 record from SQS: {s3_record.get('eventSource')} - {s3_record['s3']['bucket']['name']}/{s3_record['s3']['object']['key']}"
                                        )
                        else:
                            logger.warning(
                                f"SQS message body does not contain Records array"
                            )
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SQS message body: {str(e)}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing SQS message: {str(e)}")
                        continue
                elif "s3" in record:
                    # Direct S3 record (not from SQS)
                    s3_records.append(record)
                else:
                    logger.warning(
                        f"Unrecognized record format: {json_serialize(record)}"
                    )

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
            version_id = None

            # Check all possible locations for bucket
            if isinstance(detail.get("bucket"), dict):
                bucket = detail["bucket"].get("name")
            elif isinstance(detail.get("bucket"), str):
                bucket = detail["bucket"]

            # Check all possible locations for key
            if isinstance(detail.get("object"), dict):
                key = detail["object"].get("key")
                version_id = detail["object"].get("version-id") or detail["object"].get(
                    "versionId"
                )
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
                "CopyObject": "ObjectCreated:Copy",  # Add mapping for CopyObject events
            }

            event_name = event_type_mapping.get(detail_type, "")

            # If we have valid bucket and key, process the event
            if bucket and key:
                logger.info(
                    f"Processing EventBridge event for {bucket}/{key} with event type: {event_name}, version: {version_id}"
                )
                process_s3_event(processor, bucket, key, event_name, version_id)
            else:
                logger.warning(
                    f"Missing bucket or key in EventBridge event: {json_serialize(detail)}"
                )

        # Calculate memory usage metrics
        final_memory = get_memory_usage()
        memory_used = final_memory - initial_memory

        metrics.add_metric(
            name="MemoryUsedMB", unit=MetricUnit.Megabytes, value=memory_used
        )
        metrics.add_metric(
            name="RecordsProcessed", unit=MetricUnit.Count, value=total_records
        )
        logger.info(
            f"Finished processing {total_records} records, memory used: {memory_used}MB"
        )

        return {
            "statusCode": 200,
            "body": f"Processed {total_records} records successfully",
        }

    except Exception:
        logger.exception("Error in handler")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        raise


def process_s3_event(
    processor: AssetProcessor,
    bucket: str,
    key: str,
    event_name: str,
    version_id: str = None,
):
    """Process a single S3 event with improved performance"""
    # Skip processing if event type not relevant (quick filtering)
    if not is_relevant_event(event_name):
        logger.info(f"Skipping irrelevant event type: {event_name} for {bucket}/{key}")
        return

    logger.info(
        f"Processing {event_name} event for asset: {bucket}/{key}, version: {version_id}"
    )

    # Record start time for duration tracking
    start_time = datetime.now()

    try:
        if event_name.startswith("ObjectRemoved:"):
            # Handle deletion - only delete from DynamoDB, don't try to delete the S3 object again
            logger.info(
                f"Processing deletion event for {bucket}/{key}, version: {version_id}"
            )
            processor.delete_asset(
                bucket, key, is_delete_event=True, version_id=version_id
            )
            metrics.add_metric(name="DeletedAssets", unit=MetricUnit.Count, value=1)
            logger.info(f"Asset deletion processed: {key}")
        else:
            # Handle creation/modification/copy events - process all ObjectCreated events the same way
            logger.info(f"Processing ObjectCreated event for {bucket}/{key}")

            # Store original key for fallback in error handling
            original_event_key = key

            # Verify object exists in S3 before processing
            try:
                # Try to get tags to identify asset early for logging
                try:
                    tag_response = processor.s3.get_object_tagging(
                        Bucket=bucket, Key=key
                    )
                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in tag_response.get("TagSet", [])
                    }

                    if "AssetID" in tags and "InventoryID" in tags:
                        # Add asset context for early logging
                        logger.append_keys(
                            assetID=tags["AssetID"], inventoryID=tags["InventoryID"]
                        )
                        logger.info(
                            f"Processing existing tagged asset: {tags['AssetID']}"
                        )
                except Exception:
                    # Continue without tags, not critical
                    pass

                processor.s3.head_object(Bucket=bucket, Key=key)
            except Exception as s3_error:
                logger.error(
                    f"S3 object verification failed for {bucket}/{key}: {str(s3_error)}"
                )
                # Log exact key for debugging to see if there are encoding issues
                logger.error(
                    f"Failed key details - length: {len(key)}, contains '+': {'+' in key}, raw key: {repr(key)}"
                )

                # Try alternative key encodings to help diagnose the issue
                alternative_found = False
                try:
                    # Try with '+' decoded as literal '+' (no space replacement)
                    alt_key = urllib.parse.unquote(key)
                    if alt_key != key:
                        logger.info(
                            f"Trying alternative key without space replacement: {repr(alt_key)}"
                        )
                        processor.s3.head_object(Bucket=bucket, Key=alt_key)
                        logger.warning(
                            f"Object found with alternative key encoding. Using: {repr(alt_key)}"
                        )
                        key = alt_key
                        alternative_found = True
                except Exception as alt_error:
                    logger.debug(
                        f"Alternative key without space replacement failed: {str(alt_error)}"
                    )

                if not alternative_found:
                    try:
                        # Try with original key from event (before any decoding)
                        logger.info(
                            f"Trying original undecoded key: {repr(original_event_key)}"
                        )
                        processor.s3.head_object(Bucket=bucket, Key=original_event_key)
                        logger.warning(
                            f"Object found with original key. Using: {repr(original_event_key)}"
                        )
                        key = original_event_key
                        alternative_found = True
                    except Exception as orig_error:
                        logger.debug(f"Original key also failed: {str(orig_error)}")

                if not alternative_found:
                    logger.error(
                        f"All key variations failed. Object may not exist or there's a different encoding issue."
                    )
                    raise s3_error

            # Process all ObjectCreated events (including Copy) the same way
            result = processor.process_asset(bucket, key)
            if result:
                # Add asset information to context for logging
                logger.append_keys(
                    assetID=result["DigitalSourceAsset"]["ID"],
                    inventoryID=result["InventoryID"],
                )
                metrics.add_metric(
                    name="ProcessedAssets", unit=MetricUnit.Count, value=1
                )
                metrics.add_metric(
                    name="CreationEvents", unit=MetricUnit.Count, value=1
                )
                logger.info(
                    f"Asset processed successfully: {result['DigitalSourceAsset']['ID']}"
                )
            else:
                logger.info(f"Asset already processed or skipped: {key}")

        # Track processing duration
        duration = (datetime.now() - start_time).total_seconds()
        metrics.add_metric(
            name="EventProcessingTime", unit=MetricUnit.Seconds, value=duration
        )

    except Exception as e:
        logger.exception(f"Error in process_s3_event for {bucket}/{key}: {str(e)}")
        # Log key details for troubleshooting
        logger.error(
            f"Key details - length: {len(key)}, contains '+': {'+' in key}, raw key: {repr(key)}"
        )
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        # Track error duration too
        duration = (datetime.now() - start_time).total_seconds()
        metrics.add_metric(
            name="FailedEventProcessingTime", unit=MetricUnit.Seconds, value=duration
        )
        raise


# Helper function to get memory usage
def get_memory_usage() -> float:
    """Get current memory usage in MB"""
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except (ImportError, AttributeError):
        # If resource module not available (e.g., on Windows), return 0
        return 0


def extract_s3_details_from_event(
    event_record: Dict,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extract S3 bucket, key, event type, and version ID from various event structures
    Returns: (bucket, key, event_name, version_id)
    """
    # Direct S3 event structure
    if "s3" in event_record:
        if "bucket" in event_record["s3"] and "object" in event_record["s3"]:
            bucket = event_record["s3"]["bucket"]["name"]
            # Decode S3 key properly - handle both URL encoding and '+' as spaces
            raw_key = event_record["s3"]["object"]["key"]
            key = urllib.parse.unquote(raw_key).replace("+", " ")
            event_name = event_record.get("eventName", "ObjectCreated:")
            version_id = event_record["s3"]["object"].get("versionId")
            # Log the source for debugging
            event_source = event_record.get("eventSource", "unknown")
            logger.info(
                f"Processing direct S3 record from {event_source}: {bucket}/{key}, version: {version_id}"
            )
            logger.info(f"Key transformation: '{raw_key}' -> '{key}'")
            return bucket, key, event_name, version_id

    # SQS message with EventBridge payload
    if (
        "body" in event_record
        and "eventSource" in event_record
        and event_record["eventSource"] == "aws:sqs"
    ):
        try:
            body = json.loads(event_record["body"])

            # Check if this is an S3 event (might be in Records array)
            if (
                "Records" in body
                and isinstance(body["Records"], list)
                and len(body["Records"]) > 0
            ):
                for record in body["Records"]:
                    # Accept both real S3 events and simulated events from AssetSyncProcessor
                    valid_sources = ["aws:s3", "medialake.AssetSyncProcessor"]
                    if record.get("eventSource") in valid_sources and "s3" in record:
                        bucket = record["s3"]["bucket"]["name"]
                        # Decode S3 key properly - handle both URL encoding and '+' as spaces
                        raw_key = record["s3"]["object"]["key"]
                        key = urllib.parse.unquote(raw_key).replace("+", " ")
                        event_name = record.get("eventName", "ObjectCreated:")
                        version_id = record["s3"]["object"].get("versionId")
                        # Log the extracted details for debugging
                        logger.info(
                            f"Extracted from SQS S3 record (source: {record.get('eventSource')}): bucket={bucket}, key={key}, event={event_name}, version={version_id}"
                        )
                        logger.info(f"Key transformation: '{raw_key}' -> '{key}'")
                        return bucket, key, event_name, version_id

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

                # Extract version ID
                version_id = None
                if "object" in detail and isinstance(detail["object"], dict):
                    version_id = detail["object"].get("version-id") or detail[
                        "object"
                    ].get("versionId")

                # Apply URL decoding to the key if it exists - handle both URL encoding and '+' as spaces
                if key:
                    raw_key = key
                    key = urllib.parse.unquote(key).replace("+", " ")
                    if raw_key != key:
                        logger.info(
                            f"EventBridge key transformation: '{raw_key}' -> '{key}'"
                        )

                # Determine event type
                event_name = "ObjectCreated:"
                if body.get("detail-type") == "Object Deleted":
                    event_name = "ObjectRemoved:"

                return bucket, key, event_name, version_id
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SQS message body: {str(e)}")

    # Log unrecognized event structure to help diagnose issues
    logger.warning(f"Unrecognized event structure: {json_serialize(event_record)}")

    return None, None, None, None
