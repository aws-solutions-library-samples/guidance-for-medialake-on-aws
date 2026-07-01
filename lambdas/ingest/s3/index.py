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
from datetime import datetime, timezone
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
from collection_activity import record_collection_activity

# Import shared helpers from common_libraries layer for collection association
from collections_utils import get_user_collection_role

# Import centralized file extension constants from common_libraries layer
from file_extensions import SUPPORTED_EXTENSIONS


def utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# OpenSearch configuration
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("INDEX_NAME", "media")
OPENSEARCH_SERVICE = os.environ.get("OPENSEARCH_SERVICE", "es")
AWS_REGION = os.environ.get("REGION", "")

# S3 Vector Store configuration
VECTOR_BUCKET_NAME = os.environ.get("VECTOR_BUCKET_NAME", "")
VECTOR_INDEX_NAME = os.environ.get("VECTOR_INDEX_NAME", "media-vectors")

# Connector table configuration for bucket→connector lookup
CONNECTOR_TABLE_NAME = os.environ.get("MEDIALAKE_CONNECTOR_TABLE_NAME", "")
CONNECTOR_TABLE_REGION = os.environ.get("CONNECTOR_TABLE_REGION", "") or AWS_REGION
CONNECTOR_STORAGE_IDENTIFIER_INDEX = os.environ.get(
    "CONNECTOR_STORAGE_IDENTIFIER_INDEX", "StorageIdentifierIndex"
)

# Collections table — used by the upload-portal collection-add automation
# (Layer C). When unset, the automation is a silent no-op so this critical
# ingest path is never affected by the portal feature being unconfigured.
# See .kiro/specs/multi-page-upload-portals/portal-metadata-automation-design.md
COLLECTIONS_TABLE_NAME = os.environ.get("COLLECTIONS_TABLE_NAME", "")

# Re-use boto3's session credentials
_session = boto3.Session()
_credentials = _session.get_credentials()

# Global clients - initialized once for Lambda container reuse
s3_client = None
dynamodb_resource = None
dynamodb_client = None
eventbridge_client = None
s3_vector_client = None
connector_dynamodb_client = None
# Lazily-initialized DynamoDB Table resource for the collections table (Layer C
# upload-portal collection-add). Cached for container reuse.
collections_table = None


# ---------------------------------------------------------------------------
# Upload collection association (generalized Layer C)
#
# When an object uploaded through an upload portal OR the standard upload page
# carries server-stamped `ml-source` + `ml-collection-ids` (or an overflow
# reference) user-metadata directives, add the freshly-created asset to those
# collections. This runs AFTER the asset id exists. For the `upload` source,
# per-uploader permission and per-collection existence checks are enforced;
# for the legacy `upload-portal` source, associations remain pre-authorized.
# It is idempotent and SILENT-FAIL: any error is logged and ingest continues.
# ---------------------------------------------------------------------------

PORTAL_SOURCE_VALUE = "upload-portal"
UPLOAD_SOURCE_VALUE = "upload"
ML_SOURCE_KEY = "ml-source"
ML_COLLECTION_IDS_KEY = "ml-collection-ids"
ML_USER_ID_KEY = "ml-user-id"
ML_OVERFLOW_KEY = "ml-collection-overflow"
COLLECTION_PK_PREFIX = "COLL#"
ASSET_SK_PREFIX = "ASSET#"
# Full-file membership SK suffix used by the collections API (clip-less item):
# `ASSET#{inventoryId}#FULL`. Mirrors `generate_asset_sk` in collections_api.
ASSET_SK_FULL_SUFFIX = "#FULL"

# Upload directives table — used to resolve overflow side-records when the
# inline collection-ids metadata exceeds the S3 user-metadata budget (§6.5).
UPLOAD_DIRECTIVES_TABLE_NAME = os.environ.get("UPLOAD_DIRECTIVES_TABLE_NAME", "")


def _find_portal_user_metadata(obj) -> Dict[str, str]:
    """Locate the S3 user-metadata dict carrying the portal directives.

    The asset metadata structure nests the raw S3 user metadata under varying
    paths across code paths, so we recursively search for the dict that
    contains the `ml-source` marker key (case-insensitive) and return it. S3
    lowercases user-metadata keys, so a case-insensitive match is robust.
    Returns an empty dict when no portal directives are present.
    """
    if isinstance(obj, dict):
        # Direct hit: this dict carries the portal directives.
        lowered = {k.lower(): v for k, v in obj.items() if isinstance(k, str)}
        if ML_SOURCE_KEY in lowered:
            return lowered
        for value in obj.values():
            found = _find_portal_user_metadata(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_portal_user_metadata(value)
            if found:
                return found
    return {}


def _collections_table():
    """Return the lazily-initialized DynamoDB Table resource for the collections table."""
    global collections_table
    if collections_table is None:
        collections_table = boto3.resource("dynamodb").Table(COLLECTIONS_TABLE_NAME)
    return collections_table


def _resolve_collection_ids(user_md, asset_metadata) -> list:
    """Resolve collection ids from inline metadata or overflow side-record.

    Tries the inline ``ml-collection-ids`` first (comma-separated). Falls back
    to reading the overflow directive table when ``ml-collection-overflow=1``.
    Returns an empty list when neither is present (Req 9.3).
    """
    raw = user_md.get(ML_COLLECTION_IDS_KEY, "")
    if raw:
        return [c.strip() for c in str(raw).split(",") if c.strip()]
    if user_md.get(ML_OVERFLOW_KEY) == "1":
        bucket, key = _object_location(asset_metadata)
        if bucket and key:
            return _read_overflow_directive(bucket, key)
    return []


def _object_location(asset_metadata) -> tuple:
    """Extract (bucket, key) from asset metadata StorageInfo.PrimaryLocation."""
    try:
        primary = asset_metadata.get("StorageInfo", {}).get("PrimaryLocation", {})
        bucket = primary.get("Bucket", "")
        key = primary.get("ObjectKey", {}).get("FullPath", "")
        return bucket, key
    except Exception:
        return "", ""


def _read_overflow_directive(bucket: str, key: str) -> list:
    """Resolve an overflow directive from the dedicated Upload directives table.

    Read-only access — the upload API (§6.5) writes these side-records.
    """
    if not UPLOAD_DIRECTIVES_TABLE_NAME:
        logger.warning(
            "UPLOAD_DIRECTIVES_TABLE_NAME not configured; cannot resolve overflow directive"
        )
        return []
    try:
        resp = (
            boto3.resource("dynamodb")
            .Table(UPLOAD_DIRECTIVES_TABLE_NAME)
            .get_item(Key={"PK": f"UPLOADDIR#{bucket}#{key}"})
        )
        item = resp.get("Item") or {}
        return [c for c in item.get("collectionIds", []) if c]
    except Exception as e:
        logger.warning(f"Failed to read overflow directive for {bucket}/{key}: {e}")
        return []


def _collection_exists(collection_id: str) -> bool:
    """Check if a collection exists and is not deleted (Req 10.3)."""
    try:
        resp = _collections_table().get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": "METADATA"}
        )
        item = resp.get("Item")
        return bool(item) and item.get("status", "ACTIVE") != "DELETED"
    except Exception as e:
        logger.warning(f"Failed to check collection existence {collection_id}: {e}")
        return False


def _is_addable(collection_id: str, user_id: str) -> bool:
    """Check if user has Addable rights on a collection (Req 10.4).

    Addable = role in {OWNER, EDITOR, ADMIN}.
    """
    try:
        resp = _collections_table().get_item(
            Key={"PK": f"{COLLECTION_PK_PREFIX}{collection_id}", "SK": "METADATA"}
        )
        collection = resp.get("Item")
        if not collection:
            return False
        role = get_user_collection_role(collection, user_id)
        return role in ("OWNER", "EDITOR", "ADMIN")
    except Exception as e:
        logger.warning(
            f"Failed to check addable status for {user_id} on {collection_id}: {e}"
        )
        return False


def _put_membership(collection_id: str, inventory_id: str, added_by: str) -> None:
    """Write an idempotent membership row in the collections-API shape (Req 9.5).

    PutItem on a deterministic PK/SK overwrites rather than duplicates, so
    adding an asset already in the collection leaves membership unchanged.
    """
    asset_sk = f"{ASSET_SK_PREFIX}{inventory_id}{ASSET_SK_FULL_SUFFIX}"
    _collections_table().put_item(
        Item={
            "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
            "SK": asset_sk,
            "itemType": "asset",
            "assetId": inventory_id,
            "clipBoundary": {},
            "sortOrder": 0,
            "metadata": {},
            "addedAt": utc_now_z(),
            "addedBy": added_by,
            "GSI2_PK": asset_sk,
            "GSI2_SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
        }
    )


def associate_upload_collections(inventory_id: str, asset_metadata) -> None:
    """Add the freshly-created asset to each directive collection.

    Serves both the ``upload-portal`` source (unchanged, pre-authorized) and the
    new ``upload`` source (with per-uploader permission checks). Silent-fail and
    isolated: never raises into ingest (Req 10.1).

    Gate on ``ml-source``; for the ``upload`` source, read uploader id from
    ``ml-user-id`` and enforce permission checks. When an ``upload``-source
    object has no ``ml-user-id``, log a warning and continue fail-closed — every
    permission check denies, so all associations are skipped.

    Each collection is wrapped in its own try/except for failure isolation
    (Req 10.2) inside an outer try/except so ingestion always completes (Req 10.1).
    """
    if not COLLECTIONS_TABLE_NAME:
        # Automation not configured for this deployment — no-op.
        return
    try:
        user_md = _find_portal_user_metadata(asset_metadata)
        source = user_md.get(ML_SOURCE_KEY)
        if source not in (PORTAL_SOURCE_VALUE, UPLOAD_SOURCE_VALUE):
            return

        collection_ids = _resolve_collection_ids(user_md, asset_metadata)
        if not collection_ids:
            # No collection ids present — nothing to associate (Req 9.3).
            return

        uploader_id = user_md.get(ML_USER_ID_KEY, "")
        enforce_permissions = source == UPLOAD_SOURCE_VALUE

        if enforce_permissions and not uploader_id:
            # Fail-closed: without an uploader identity, permission checks
            # will deny every association. Log once and let the loop proceed —
            # _is_addable("", ...) returns False for all collections.
            logger.warning(
                f"'{UPLOAD_SOURCE_VALUE}'-source object for asset {inventory_id} has no "
                f"{ML_USER_ID_KEY}; permission checks will deny every association (fail-closed)"
            )

        added_by = uploader_id if uploader_id else source

        for collection_id in collection_ids:
            try:
                if not _collection_exists(collection_id):
                    logger.info(
                        f"Skip association: collection {collection_id} does not exist or is deleted"
                    )
                    continue
                if enforce_permissions and not _is_addable(collection_id, uploader_id):
                    logger.info(
                        f"Skip association: user {uploader_id} not addable on collection {collection_id}"
                    )
                    continue
                _put_membership(collection_id, inventory_id, added_by)
                logger.info(
                    f"Added asset {inventory_id} to collection {collection_id} (source={source})"
                )
                # Record activity for the upload source when uploader is known (Req 11.3)
                if source == UPLOAD_SOURCE_VALUE and uploader_id:
                    record_collection_activity(uploader_id, collection_id)
            except (
                Exception
            ) as item_err:  # noqa: BLE001 — failure isolation per item (Req 10.2, 10.5)
                logger.warning(
                    f"Association failed asset={inventory_id} collection={collection_id}: {item_err}"
                )
    except Exception as e:  # noqa: BLE001 — never break ingest (Req 10.1)
        logger.warning(f"Upload collection-add skipped for asset {inventory_id}: {e}")


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


def acquire_processing_lock(
    bucket: str, key: str, version_id: Optional[str] = None
) -> bool:
    """
    Atomically acquire a processing lock for an S3 object to prevent race conditions.

    This prevents multiple Lambda invocations from processing the same object simultaneously
    by using DynamoDB conditional writes.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        version_id: S3 object version ID (optional)

    Returns:
        True if lock acquired successfully, False if object is already being processed
    """
    # Ensure dynamodb_client is initialized
    if dynamodb_client is None:
        logger.error("DynamoDB client not initialized")
        return True  # Fail-open to allow processing

    try:
        # Create a composite lock key that uniquely identifies this object
        # Include version_id if provided to handle versioned buckets
        version_suffix = f"#{version_id}" if version_id and version_id != "null" else ""
        lock_key = f"LOCK#{bucket}#{key}{version_suffix}"

        # Use current timestamp for lock expiry (locks expire after 5 minutes)
        current_time = int(datetime.utcnow().timestamp())
        lock_expiry = current_time + 300  # 5 minutes

        # Attempt to write a processing lock record with conditional expression
        # This is atomic - only one Lambda can succeed if multiple try simultaneously
        dynamodb_client.put_item(
            TableName=os.environ["ASSETS_TABLE"],
            Item={
                "InventoryID": {"S": lock_key},
                "ProcessingStatus": {"S": "in-progress"},
                "ProcessingStartTime": {"N": str(current_time)},
                "LockExpiry": {"N": str(lock_expiry)},
                "StoragePath": {"S": f"LOCK::{bucket}:{key}"},
            },
            ConditionExpression="attribute_not_exists(InventoryID) OR LockExpiry < :current_time",
            ExpressionAttributeValues={":current_time": {"N": str(current_time)}},
        )

        logger.info(f"Processing lock acquired for {bucket}/{key}")
        metrics.add_metric(
            name="ProcessingLockAcquired", unit=MetricUnit.Count, value=1
        )
        return True

    except dynamodb_client.exceptions.ConditionalCheckFailedException:
        # Another Lambda is currently processing this object
        logger.warning(
            f"Race condition detected: {bucket}/{key} is already being processed by another invocation"
        )
        metrics.add_metric(name="RaceConditionDetected", unit=MetricUnit.Count, value=1)
        metrics.add_metric(
            name="DuplicatesPreventedByAtomicLock", unit=MetricUnit.Count, value=1
        )
        return False

    except Exception as e:
        # If we can't acquire the lock due to an error, log it but allow processing
        # This is fail-open behavior to prevent blocking legitimate processing
        logger.error(f"Error acquiring processing lock for {bucket}/{key}: {str(e)}")
        metrics.add_metric(name="ProcessingLockErrors", unit=MetricUnit.Count, value=1)
        # Return True to continue processing - better to risk a duplicate than fail
        return True


def release_processing_lock(
    bucket: str, key: str, version_id: Optional[str] = None
) -> None:
    """
    Release a processing lock after successfully processing an object.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        version_id: S3 object version ID (optional)
    """
    # Ensure dynamodb_client is initialized
    if dynamodb_client is None:
        logger.warning("DynamoDB client not initialized, cannot release lock")
        return

    try:
        version_suffix = f"#{version_id}" if version_id and version_id != "null" else ""
        lock_key = f"LOCK#{bucket}#{key}{version_suffix}"

        # Delete the lock record
        dynamodb_client.delete_item(
            TableName=os.environ["ASSETS_TABLE"], Key={"InventoryID": {"S": lock_key}}
        )

        logger.info(f"Processing lock released for {bucket}/{key}")
        metrics.add_metric(
            name="ProcessingLockReleased", unit=MetricUnit.Count, value=1
        )

    except Exception as e:
        # Lock release failure is not critical - locks will expire automatically
        logger.warning(f"Error releasing processing lock for {bucket}/{key}: {str(e)}")


def initialize_global_clients():
    """Initialize global AWS clients for container reuse"""
    global s3_client, dynamodb_resource, dynamodb_client, eventbridge_client, s3_vector_client, connector_dynamodb_client

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
            # Configure retry strategy for transient errors
            retry_config = Config(
                retries={
                    "max_attempts": 10,
                    "mode": "adaptive",
                },
                connect_timeout=5,
                read_timeout=60,
            )

            s3_vector_client = boto3.client(
                "s3vectors", region_name=AWS_REGION, config=retry_config
            )
            logger.info(
                "Initialized global S3 Vector Store client with retry configuration",
                extra={"max_attempts": 10, "retry_mode": "adaptive"},
            )
        except Exception as e:
            logger.warning(f"Failed to initialize S3 Vector Store client: {e}")
            s3_vector_client = None

    if connector_dynamodb_client is None and CONNECTOR_TABLE_NAME:
        connector_dynamodb_client = boto3.client(
            "dynamodb", region_name=CONNECTOR_TABLE_REGION
        )
        logger.info(
            "Initialized global connector DynamoDB client",
            extra={"region": CONNECTOR_TABLE_REGION},
        )


# Improved JSON serialization
class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects and Decimal types from DynamoDB"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat().replace("+00:00", "Z")
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

    # MIME type prefixes for classification
    image_mimes = ["image/", "application/photoshop", "application/illustrator"]
    video_mimes = ["video/"]
    audio_mimes = ["audio/"]

    # Use centralized extension lists from constants
    image_extensions = SUPPORTED_EXTENSIONS["Image"]
    video_extensions = SUPPORTED_EXTENSIONS["Video"]
    audio_extensions = SUPPORTED_EXTENSIONS["Audio"]

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
    event_name: str,
    allowed_prefixes=(
        "ObjectCreated:",
        "ObjectRemoved:",
        "ObjectStorageClassChanged",
        "ObjectRestore:Post",
        "ObjectRestore:Completed",
        "ObjectRestore:Delete",
    ),
) -> bool:
    """Quick check if event should be processed"""
    return any(event_name.startswith(prefix) for prefix in allowed_prefixes)


def _parse_string_list(attr: dict | None) -> tuple:
    """Parse a DynamoDB list-of-strings attribute into a normalized tuple."""
    if not attr:
        return ()
    values = attr.get("L", [])
    return tuple(
        v.get("S", "").strip().lower()
        for v in values
        if isinstance(v, dict) and v.get("S", "").strip()
    )


def _parse_file_filter(attr: dict | None) -> dict | None:
    """Parse the DynamoDB ``fileFilter`` map into a normalized dict.

    Returns ``None`` when no usable filter is present (missing, NULL, or empty),
    which downstream means "allow all".
    """
    if not attr or "M" not in attr:
        return None
    m = attr["M"]
    mode = m.get("mode", {}).get("S", "allow").strip().lower()
    if mode not in ("allow", "deny"):
        mode = "allow"
    extensions = tuple(e.lstrip(".") for e in _parse_string_list(m.get("extensions")))
    mime_types = _parse_string_list(m.get("mimeTypes"))
    if not extensions and not mime_types:
        return None
    return {"mode": mode, "extensions": extensions, "mimeTypes": mime_types}


@functools.lru_cache(maxsize=50)
def lookup_connector_by_bucket(bucket_name: str) -> dict | None:
    """Cached lookup of connector record by bucket name using GSI query."""
    if not CONNECTOR_TABLE_NAME or connector_dynamodb_client is None:
        return None
    try:
        resp = connector_dynamodb_client.query(
            TableName=CONNECTOR_TABLE_NAME,
            IndexName=CONNECTOR_STORAGE_IDENTIFIER_INDEX,
            KeyConditionExpression="storageIdentifier = :b",
            ExpressionAttributeValues={":b": {"S": bucket_name}},
            ProjectionExpression=(
                "id, integrationMethod, allowedFileExtensions, fileFilter"
            ),
            Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None
        item = items[0]
        # Parse both the structured `fileFilter` (canonical) and the legacy
        # `allowedFileExtensions` allow-list. Missing/empty on both means
        # "allow all" — what every connector created before filtering looks
        # like, so existing connectors keep ingesting everything unchanged.
        allowed_raw = item.get("allowedFileExtensions", {}).get("L", [])
        allowed_exts = tuple(
            ext.get("S", "").strip().lower().lstrip(".")
            for ext in allowed_raw
            if ext.get("S", "").strip()
        )
        return {
            "id": item["id"]["S"],
            "integrationMethod": item.get("integrationMethod", {}).get("S", ""),
            "allowedFileExtensions": allowed_exts,
            "fileFilter": _parse_file_filter(item.get("fileFilter")),
        }
    except Exception as e:
        logger.warning(f"Connector lookup failed for bucket {bucket_name}: {e}")
        return None


def _mime_type_matches(content_type: str, patterns: tuple) -> bool:
    """Return True if ``content_type`` matches any MIME pattern.

    Supports exact matches ("video/mp4"), subtype wildcards ("image/*"), and
    the universal wildcards ("*" / "*/*").
    """
    if not content_type or not patterns:
        return False
    ct = content_type.lower().split(";")[0].strip()
    main_type = ct.split("/")[0] if "/" in ct else ct
    for pattern in patterns:
        if pattern in ("*", "*/*"):
            return True
        if pattern == ct:
            return True
        if pattern.endswith("/*") and pattern[:-2] == main_type:
            return True
    return False


@functools.lru_cache(maxsize=1)
def _env_file_filter() -> dict | None:
    """Parse the connector's file filter from its own environment variable.

    The ``CONNECTOR_FILE_FILTER`` env var is set on each per-connector Lambda at
    creation time from the connector configuration, so the connector is driven
    entirely by its own configuration without a DynamoDB read on the hot path.

    Returns the normalized filter dict, or ``None`` when the env var is absent
    or empty (meaning "allow all" / fall back to the connector record).
    """
    raw = os.environ.get("CONNECTOR_FILE_FILTER", "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("Invalid CONNECTOR_FILE_FILTER env var; ignoring it")
        return None
    if not isinstance(data, dict):
        return None
    mode = str(data.get("mode", "allow")).strip().lower()
    if mode not in ("allow", "deny"):
        mode = "allow"
    extensions = tuple(
        str(e).strip().lower().lstrip(".")
        for e in (data.get("extensions") or [])
        if str(e).strip()
    )
    mime_types = tuple(
        str(m).strip().lower() for m in (data.get("mimeTypes") or []) if str(m).strip()
    )
    if not extensions and not mime_types:
        return None
    return {"mode": mode, "extensions": extensions, "mimeTypes": mime_types}


_CONTENT_CATEGORY_BY_EXT = {
    # documents
    "pdf": "document",
    "doc": "document",
    "docx": "document",
    "txt": "document",
    "rtf": "document",
    "odt": "document",
    "md": "document",
    "ppt": "document",
    "pptx": "document",
    "xls": "document",
    "xlsx": "document",
    "pages": "document",
    # structured data
    "csv": "data",
    "json": "data",
    "xml": "data",
    "yaml": "data",
    "yml": "data",
    "tsv": "data",
    "parquet": "data",
    # archives
    "zip": "archive",
    "tar": "archive",
    "gz": "archive",
    "tgz": "archive",
    "rar": "archive",
    "7z": "archive",
    "bz2": "archive",
    # code / text
    "py": "code",
    "js": "code",
    "ts": "code",
    "tsx": "code",
    "jsx": "code",
    "java": "code",
    "c": "code",
    "cpp": "code",
    "h": "code",
    "hpp": "code",
    "go": "code",
    "rs": "code",
    "rb": "code",
    "sh": "code",
    "html": "code",
    "css": "code",
    "sql": "code",
}


def get_content_category(asset_type: str, file_ext: str) -> str:
    """Coarse content category for non-media badges and search facets.

    Supported media maps to its kind (image/video/audio); everything else maps
    to a lightweight category derived from the extension
    (document/data/archive/code/other).
    """
    if asset_type in ("Image", "Video", "Audio"):
        return asset_type.lower()
    return _CONTENT_CATEGORY_BY_EXT.get(
        (file_ext or "").strip().lower().lstrip("."), "other"
    )


def _resolve_file_filter(bucket_name: str) -> dict | None:
    """Resolve the active file filter for a bucket's connector.

    Prefers the Lambda's own ``CONNECTOR_FILE_FILTER`` env var, then the
    connector record's structured ``fileFilter``, then the legacy
    ``allowedFileExtensions`` allow-list. Returns ``None`` when no filter is
    configured (meaning "allow all" for supported media).
    """
    file_filter = _env_file_filter()
    if file_filter is not None:
        return file_filter
    info = lookup_connector_by_bucket(bucket_name)
    if info is None:
        return None
    file_filter = info.get("fileFilter")
    if file_filter:
        return file_filter
    allowed = info.get("allowedFileExtensions", ())
    if allowed:
        return {"mode": "allow", "extensions": tuple(allowed), "mimeTypes": ()}
    return None


def _filter_matches(file_filter: dict, file_ext: str, content_type: str) -> bool:
    """True if the object matches the filter's extensions or MIME patterns."""
    extensions = file_filter.get("extensions", ())
    mime_types = file_filter.get("mimeTypes", ())
    return bool(
        (file_ext and file_ext in extensions)
        or _mime_type_matches(content_type, mime_types)
    )


def should_ingest_file(bucket_name: str, file_ext: str, content_type: str) -> bool:
    """Decide whether a SUPPORTED-MEDIA object should be ingested per the filter.

    No filter / empty filter -> ingest (allow all). Allow mode -> ingest only
    matches; deny mode -> ingest everything except matches.
    """
    file_ext = (file_ext or "").strip().lower().lstrip(".")
    file_filter = _resolve_file_filter(bucket_name)
    if file_filter is None:
        return True
    extensions = file_filter.get("extensions", ())
    mime_types = file_filter.get("mimeTypes", ())
    if not extensions and not mime_types:
        return True
    matched = _filter_matches(file_filter, file_ext, content_type)
    if file_filter.get("mode") == "deny":
        return not matched
    return matched


def is_explicitly_allowed(bucket_name: str, file_ext: str, content_type: str) -> bool:
    """True only when an allow-mode filter explicitly lists this file.

    Drives whether a NON-MEDIA ("Other") object is ingested: only when the
    connector opted in by allow-listing its extension or MIME type. Deny mode
    and an absent filter never opt non-media in (so behavior is unchanged for
    connectors that don't configure an allow-list).
    """
    file_ext = (file_ext or "").strip().lower().lstrip(".")
    file_filter = _resolve_file_filter(bucket_name)
    if not file_filter or file_filter.get("mode") != "allow":
        return False
    return _filter_matches(file_filter, file_ext, content_type)


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
    StorageClass: str
    RestoreStatus: Optional[str]


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


class S3EventContext(TypedDict):
    event_type: str
    bucket: str
    key: str
    version_id: Optional[str]
    destination_storage_class: Optional[str]
    # Deletion kind for ObjectRemoved events, normalized to the S3 vocabulary
    # ("Delete Marker Created" / "Permanently Deleted"). None for non-deletion
    # events. See DELETION_TYPE_* constants.
    deletion_type: Optional[str]


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

    def delete_opensearch_docs(self, inventory_id: str) -> None:
        """Delete all OpenSearch docs for a given InventoryID."""
        if not OPENSEARCH_ENDPOINT:
            logger.info("OPENSEARCH_ENDPOINT not set – skipping OpenSearch deletion.")
            return

        host = OPENSEARCH_ENDPOINT.lstrip("https://").lstrip("http://")
        url = f"https://{host}/{OPENSEARCH_INDEX}/_delete_by_query?refresh=true&conflicts=proceed"
        query = {"query": {"match_phrase": {"InventoryID": inventory_id}}}

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
                f"OpenSearch deletion complete – deleted {deleted} docs for {inventory_id}"
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
    def _check_existing_file(
        self, md5_hash: str, bucket: str = None, key: str = None
    ) -> Tuple[Optional[Dict], bool]:
        """
        Check if file with same MD5 hash exists with pagination support.
        Returns: (existing_file, is_exact_match)
        - existing_file: First file with matching hash (or None if no matches)
        - is_exact_match: True if the file has same hash AND same storage path/key
        """
        try:
            all_items = []
            last_evaluated_key = None
            page_count = 0

            # Paginate through all results
            while True:
                query_params = {
                    "IndexName": "FileHashIndex",
                    "KeyConditionExpression": "FileHash = :hash",
                    "ExpressionAttributeValues": {":hash": md5_hash},
                }

                if last_evaluated_key:
                    query_params["ExclusiveStartKey"] = last_evaluated_key

                response = self.dynamodb.query(**query_params)
                page_count += 1
                all_items.extend(response["Items"])

                # Log pagination progress for large result sets
                if page_count > 1:
                    logger.info(
                        f"Retrieved page {page_count} with {len(response['Items'])} items for hash {md5_hash}"
                    )

                # Check if there are more pages
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break

            logger.info(
                f"Found {len(all_items)} total items with hash {md5_hash} across {page_count} page(s)"
            )

            if not all_items:
                return None, False

            # If bucket and key provided, check if any item is an exact match
            is_exact_match = False
            if bucket and key:
                storage_path = f"{bucket}:{key}"
                logger.info(
                    f"Checking for exact match with storage path: {storage_path}"
                )

                for item in all_items:
                    item_storage_path = item.get("StoragePath")
                    item_object_key = (
                        item.get("DigitalSourceAsset", {})
                        .get("MainRepresentation", {})
                        .get("StorageInfo", {})
                        .get("PrimaryLocation", {})
                        .get("ObjectKey", {})
                        .get("FullPath")
                    )

                    # Check if both storage path AND object key match
                    if item_storage_path == storage_path and item_object_key == key:
                        logger.info(
                            f"Found exact match: StoragePath={item_storage_path}, ObjectKey={item_object_key}"
                        )
                        is_exact_match = True
                        break

                if not is_exact_match:
                    logger.info(
                        f"No exact match found for storage path {storage_path} - but returning first duplicate for hash match"
                    )

            # Always return first item with matching hash for duplicate detection
            return all_items[0], is_exact_match

        except Exception as e:
            logger.exception(f"Error querying DynamoDB for hash {md5_hash}, error {e}")
            raise

    @tracer.capture_method
    def process_asset(
        self, bucket: str, key: str, version_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Process new asset from S3 with optimized performance and race condition prevention"""
        original_key = key
        key = self._decode_s3_event_key(key)

        # Log key transformation for debugging
        if original_key != key:
            logger.info(f"Key decoded from '{original_key}' to '{key}'")

        try:
            # CRITICAL: Acquire processing lock FIRST to prevent race conditions
            # This MUST be the first operation to ensure only one Lambda processes this object
            lock_acquired = acquire_processing_lock(bucket, key, version_id)
            if not lock_acquired:
                # Another Lambda invocation is already processing this object
                logger.info(
                    f"Skipping {bucket}/{key} - already being processed by another invocation"
                )
                metrics.add_metric(
                    name="AssetsSkippedDueToRaceLock", unit=MetricUnit.Count, value=1
                )
                return None

            # Now we have exclusive lock on this object - safe to proceed
            logger.info(f"Processing lock acquired for {bucket}/{key}")

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
                    # Release lock before raising
                    release_processing_lock(bucket, key, version_id)
                    raise

                try:
                    existing_tags = tag_future.result()
                except Exception as e:
                    logger.exception(f"Error getting S3 object tags: {str(e)}")
                    # Release lock before raising
                    release_processing_lock(bucket, key, version_id)
                    raise

            # Early check for asset type
            content_type = response.get("ContentType", "")
            file_ext = self._extract_file_extension(key)
            asset_type = determine_asset_type(content_type, file_ext)

            # Get S3 object's last modified date
            s3_last_modified = response.get("LastModified", datetime.now(timezone.utc))
            if isinstance(s3_last_modified, datetime):
                s3_last_modified_str = s3_last_modified.isoformat().replace(
                    "+00:00", "Z"
                )
            else:
                s3_last_modified_str = s3_last_modified

            # Log the type determination for debugging
            logger.info(
                f"Asset type determination for {key}: content_type={content_type}, file_ext={file_ext}, determined_type={asset_type}"
            )

            # Gate the object: supported media goes through the connector's
            # file filter; non-media ("Other") is ingested ONLY when the
            # connector explicitly allow-lists it (preview-only, no pipeline).
            is_supported_media = asset_type in ["Image", "Video", "Audio"]

            if is_supported_media:
                if not should_ingest_file(bucket, file_ext, content_type):
                    logger.info(
                        f"Skipping {bucket}/{key}: file extension '{file_ext}' / "
                        f"content type '{content_type}' excluded by the connector's "
                        f"file filter"
                    )
                    metrics.add_metric(
                        name="ConnectorFileTypeFiltered",
                        unit=MetricUnit.Count,
                        value=1,
                    )
                    release_processing_lock(bucket, key, version_id)
                    return None
            else:
                if not is_explicitly_allowed(bucket, file_ext, content_type):
                    logger.info(
                        f"Skipping processing for unsupported asset type: "
                        f"{asset_type} for {bucket}/{key}"
                    )
                    metrics.add_metric(
                        name="UnsupportedAssetTypeSkipped",
                        unit=MetricUnit.Count,
                        value=1,
                    )
                    release_processing_lock(bucket, key, version_id)
                    return None
                logger.info(
                    f"Ingesting non-media asset (preview-only, no pipeline): "
                    f"{bucket}/{key} type={asset_type} ext={file_ext}"
                )
                metrics.add_metric(
                    name="NonMediaAssetIngested", unit=MetricUnit.Count, value=1
                )

            tags = {tag["Key"]: tag["Value"] for tag in existing_tags.get("TagSet", [])}

            # Check existing tags first - but MUST verify hash hasn't changed (file replacement scenario)
            if "InventoryID" in tags and "AssetID" in tags:
                # Don't release lock yet - need to verify this isn't a file replacement

                # Use the asset context for consistent logging
                with self.asset_context(
                    asset_id=tags["AssetID"], inventory_id=tags["InventoryID"]
                ):
                    self._log_with_asset_context(
                        f"Found tagged asset: {tags['AssetID']} - verifying hash to detect replacements"
                    )

                    # CRITICAL: Calculate hash to detect if file content changed
                    current_md5_hash = self._calculate_md5(bucket, key)

                    # Add logging to check if the record exists in DynamoDB
                    try:
                        existing_record = self.dynamodb.get_item(
                            Key={"InventoryID": tags["InventoryID"]}
                        )
                        if "Item" in existing_record:
                            stored_hash = existing_record["Item"].get("FileHash")

                            # Check if hash has changed - this indicates file replacement
                            if stored_hash and stored_hash != current_md5_hash:
                                logger.warning(
                                    f"FILE REPLACEMENT DETECTED (tagged asset): "
                                    f"StoragePath={bucket}:{key}, "
                                    f"Old hash={stored_hash}, New hash={current_md5_hash}, "
                                    f"Old InventoryID={tags['InventoryID']}. "
                                    f"Deleting old asset and creating new one."
                                )

                                # Delete the old asset completely
                                try:
                                    old_inventory_id = tags["InventoryID"]

                                    # Delete associated S3 files
                                    self._delete_associated_s3_files(
                                        existing_record["Item"], bucket, key
                                    )

                                    # Delete from DynamoDB
                                    self.dynamodb.delete_item(
                                        Key={"InventoryID": old_inventory_id}
                                    )
                                    logger.info(
                                        f"Deleted old DynamoDB record: {old_inventory_id}"
                                    )

                                    # Delete OpenSearch documents
                                    self.delete_opensearch_docs(old_inventory_id)

                                    # Delete S3 vectors
                                    vector_count = self.delete_s3_vectors(
                                        old_inventory_id
                                    )
                                    logger.info(
                                        f"Deleted {vector_count} vectors for old asset {old_inventory_id}"
                                    )

                                    # Publish deletion event
                                    self.publish_deletion_event(old_inventory_id)

                                    metrics.add_metric(
                                        name="TaggedFileReplacementDetected",
                                        unit=MetricUnit.Count,
                                        value=1,
                                    )

                                    logger.info(
                                        f"Successfully deleted old tagged asset {old_inventory_id} - will create new asset"
                                    )

                                    # Clear tags dict so we process as new asset below
                                    # (Don't remove from S3 yet - will be retagged with new IDs)
                                    tags.clear()

                                    # Keep the lock - we're continuing to process this as a new asset
                                    # Lock will be released at the end of process_asset

                                    # Fall through to process as new asset
                                    # by NOT returning here

                                except Exception as e:
                                    logger.error(
                                        f"Error during tagged file replacement cleanup: {str(e)}"
                                    )
                                    metrics.add_metric(
                                        name="TaggedFileReplacementCleanupErrors",
                                        unit=MetricUnit.Count,
                                        value=1,
                                    )
                                    # Release lock before raising
                                    release_processing_lock(bucket, key, version_id)
                                    raise

                                # Continue processing below as a new file (don't return)

                            else:
                                # Hash matches - this is the same file, just update timestamp
                                self._log_with_asset_context(
                                    f"Hash matches ({current_md5_hash}) - same file, updating lastModifiedDate only"
                                )

                                # Update only the lastModifiedDate
                                update_expression = "SET DigitalSourceAsset.lastModifiedDate = :lastModDate"
                                expression_attribute_values = {
                                    ":lastModDate": s3_last_modified_str
                                }

                                self.dynamodb.update_item(
                                    Key={"InventoryID": tags["InventoryID"]},
                                    UpdateExpression=update_expression,
                                    ExpressionAttributeValues=expression_attribute_values,
                                )
                                self._log_with_asset_context(
                                    f"Updated lastModifiedDate to {s3_last_modified_str} for existing asset: {tags['AssetID']}"
                                )

                                # Release lock and exit
                                release_processing_lock(bucket, key, version_id)
                                return None
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
                            current_time = utc_now_z()

                            # Create the item structure
                            item = {
                                "InventoryID": inventory_id,
                                "FileHash": md5_hash,
                                "StoragePath": f"{bucket}:{key}",
                                "DigitalSourceAsset": {
                                    "ID": asset_id,
                                    "Type": asset_type,
                                    "CreateDate": utc_now_z(),
                                    "IngestedAt": utc_now_z(),
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

                                # Release lock after successful recreation
                                release_processing_lock(bucket, key, version_id)
                                return item
                            except Exception as e:
                                self._log_with_asset_context(
                                    f"Error recreating DynamoDB record: {str(e)}",
                                    level="ERROR",
                                )
                                logger.exception(
                                    f"Error recreating DynamoDB record: {str(e)}"
                                )
                                # Release lock before raising
                                release_processing_lock(bucket, key, version_id)
                    except Exception as e:
                        self._log_with_asset_context(
                            f"Error checking existing record in DynamoDB: {str(e)}",
                            level="ERROR",
                        )
                        logger.exception(
                            f"Error checking existing record in DynamoDB: {str(e)}"
                        )
                        # Release lock before returning
                        release_processing_lock(bucket, key, version_id)

                    return None

            # Calculate MD5 hash for duplicate checking
            md5_hash = self._calculate_md5(bucket, key)

            # CRITICAL: First check if there's already a record at this StoragePath
            # This handles the file replacement scenario (same path, different hash)
            storage_path = f"{bucket}:{key}"
            existing_at_path = None

            try:
                path_query_response = self.dynamodb.query(
                    IndexName="S3PathIndex",
                    KeyConditionExpression="StoragePath = :path",
                    ExpressionAttributeValues={":path": storage_path},
                )
                if path_query_response.get("Items"):
                    # Filter out LOCK records - they are processing locks, not real assets
                    real_items = [
                        item
                        for item in path_query_response["Items"]
                        if not item["InventoryID"].startswith("LOCK#")
                    ]
                    existing_at_path = real_items[0] if real_items else None
                    if existing_at_path:
                        logger.info(
                            f"Found existing record at StoragePath {storage_path}: InventoryID={existing_at_path['InventoryID']}, FileHash={existing_at_path.get('FileHash')}"
                        )
                    elif path_query_response["Items"]:
                        logger.info(
                            f"Only LOCK records found at StoragePath {storage_path} - no real asset record"
                        )
            except Exception as e:
                logger.warning(f"Error checking StoragePath index: {str(e)}")

            # If there's a file at this path with a DIFFERENT hash, it's a replacement
            if existing_at_path and existing_at_path.get("FileHash") != md5_hash:
                old_inventory_id = existing_at_path["InventoryID"]
                old_hash = existing_at_path.get("FileHash")

                logger.warning(
                    f"FILE REPLACEMENT DETECTED at {storage_path}: "
                    f"Old hash={old_hash}, New hash={md5_hash}. "
                    f"Deleting old record {old_inventory_id} and creating new asset."
                )

                # Delete the old record and all associated resources
                try:
                    # Delete associated S3 files (derived representations, transcripts, etc.)
                    self._delete_associated_s3_files(existing_at_path, bucket, key)

                    # Delete from DynamoDB
                    self.dynamodb.delete_item(Key={"InventoryID": old_inventory_id})
                    logger.info(f"Deleted old DynamoDB record: {old_inventory_id}")

                    # Delete OpenSearch documents
                    self.delete_opensearch_docs(old_inventory_id)

                    # Delete S3 vectors
                    vector_count = self.delete_s3_vectors(old_inventory_id)
                    logger.info(
                        f"Deleted {vector_count} vectors for old asset {old_inventory_id}"
                    )

                    # Publish deletion event for old asset
                    self.publish_deletion_event(old_inventory_id)

                    metrics.add_metric(
                        name="FileReplacementDetected", unit=MetricUnit.Count, value=1
                    )
                    metrics.add_metric(
                        name="OldAssetDeletedDueToReplacement",
                        unit=MetricUnit.Count,
                        value=1,
                    )

                    logger.info(
                        f"Successfully cleaned up old asset {old_inventory_id} - proceeding to create new asset"
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting old asset during file replacement: {str(e)}"
                    )
                    # Continue to create new record even if old deletion fails
                    metrics.add_metric(
                        name="FileReplacementCleanupErrors",
                        unit=MetricUnit.Count,
                        value=1,
                    )

                # Clear existing_at_path so we proceed to create new record
                existing_at_path = None

            # If there's a file at this path with the SAME hash, it's already processed
            elif existing_at_path and existing_at_path.get("FileHash") == md5_hash:
                logger.info(
                    f"File at {storage_path} already exists with same hash {md5_hash} - updating lastModifiedDate only"
                )
                # Update lastModifiedDate
                self.dynamodb.update_item(
                    Key={"InventoryID": existing_at_path["InventoryID"]},
                    UpdateExpression="SET DigitalSourceAsset.lastModifiedDate = :lastModDate",
                    ExpressionAttributeValues={":lastModDate": s3_last_modified_str},
                )
                # Release lock and exit
                release_processing_lock(bucket, key, version_id)
                return None

            # Now check if file with same hash exists at DIFFERENT locations
            # Pass bucket and key to check for both hash matches and exact matches
            existing_file, is_exact_match = self._check_existing_file(
                md5_hash, bucket, key
            )

            if existing_file:
                if is_exact_match:
                    logger.info(
                        f"Found existing file with hash {md5_hash} - EXACT MATCH (same storage path/key)"
                    )
                else:
                    logger.info(
                        f"Found existing file with hash {md5_hash} - DIFFERENT path/key (duplicate hash)"
                    )
                metrics.add_metric(
                    name="DuplicateCheckPerformed", unit=MetricUnit.Count, value=1
                )
            else:
                logger.info(
                    f"No existing file found with hash {md5_hash} - this is a unique file"
                )
                metrics.add_metric(
                    name="DuplicateCheckPerformed", unit=MetricUnit.Count, value=1
                )

            # Handle duplicate logic based on DO_NOT_INGEST_DUPLICATES setting
            if existing_file:
                logger.info(f"Duplicate file found with hash {md5_hash}")

                # Check if it's the exact same file (same hash + same storage path + same key)
                if is_exact_match:
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

                    # Release lock before returning
                    release_processing_lock(bucket, key, version_id)
                    return None

                # Different object key but same hash - behavior depends on DO_NOT_INGEST_DUPLICATES
                if DO_NOT_INGEST_DUPLICATES:
                    logger.info(
                        "DO_NOT_INGEST_DUPLICATES=True: Hash match found - tagging as duplicate without creating new asset"
                    )

                    # For ANY hash match when DO_NOT_INGEST_DUPLICATES is True:
                    # - Tag with EXISTING InventoryID and AssetID (no new IDs)
                    # - Mark as DuplicateHash=true
                    # - Do NOT create any new DynamoDB entries
                    # - Do NOT generate new AssetIDs

                    logger.info(
                        f"Tagging duplicate file with existing IDs - InventoryID: {existing_file['InventoryID']}, AssetID: {existing_file['DigitalSourceAsset']['ID']}"
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
                                    "Value": existing_file["DigitalSourceAsset"]["ID"],
                                },
                                {"Key": "FileHash", "Value": md5_hash},
                                {"Key": "DuplicateHash", "Value": "true"},
                            ]
                        },
                    )

                    logger.info(
                        f"Duplicate marked successfully - no new asset created. Original asset: {existing_file['DigitalSourceAsset']['ID']}"
                    )

                    metrics.add_metric(
                        name="DuplicatesTaggedNotIngested",
                        unit=MetricUnit.Count,
                        value=1,
                    )

                    # Release lock before returning
                    release_processing_lock(bucket, key, version_id)
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

            # Supported media triggers the default pipelines via EventBridge.
            # Non-media is searchable (DynamoDB stream -> OpenSearch) but gets no
            # pipeline processing, so we skip the AssetCreated event for it.
            if is_supported_media:
                self.publish_event(
                    dynamo_entry["InventoryID"],
                    dynamo_entry["DigitalSourceAsset"]["ID"],
                    metadata,
                )
            else:
                logger.info(
                    f"Skipping pipeline event for non-media asset "
                    f"{dynamo_entry['InventoryID']} (preview-only)"
                )

            # Release lock after successful processing
            release_processing_lock(bucket, key, version_id)
            return dynamo_entry

        except Exception as e:
            logger.exception(f"Error processing asset: {key}, error: {e}")
            metrics.add_metric(
                name="AssetProcessingErrors", unit=MetricUnit.Count, value=1
            )
            # Release lock before raising
            release_processing_lock(bucket, key, version_id)
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
        _lm = s3_response.get("LastModified", datetime.now(timezone.utc))
        last_modified = _lm.isoformat().replace("+00:00", "Z")
        content_type = s3_response.get("ContentType", "")
        storage_class = s3_response.get("StorageClass") or "STANDARD"

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
                    "StorageClass": storage_class,
                    "RestoreStatus": None,
                }
            },
            "Metadata": {
                "ObjectMetadata": {
                    "ExtractedDate": utc_now_z(),
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
            timestamp = utc_now_z()

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
                    "contentCategory": get_content_category(asset_type, file_ext),
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
            # Upload collection association (generalized Layer C): if this asset
            # arrived through an upload portal or the standard upload page with
            # server-stamped `ml-collection-ids` / overflow directives, add it
            # to those collections now that the asset's inventory_id exists.
            # Silent-fail — never blocks event publication or ingest.
            associate_upload_collections(inventory_id, metadata)
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
                timestamp = utc_now_z()

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
        deletion_type: str = None,
    ) -> bool:
        """
        Delete asset record from DynamoDB based on S3 object deletion.
        Uses centralized AssetDeletionService for actual deletion.

        Returns ``True`` when the deletion was processed (the version check
        allowed it and the deletion flow ran), or ``False`` when it was
        intentionally skipped by the version check. Raises on unexpected errors.
        """
        try:
            # Check if this deletion should be processed based on versioning
            if not self._should_process_deletion(
                bucket, key, version_id, is_delete_event, deletion_type
            ):
                # _should_process_deletion has already logged the SPECIFIC
                # reason (intentional skip at INFO; errors at WARNING/EXCEPTION
                # with a full traceback). Keep this line unambiguous.
                logger.info(
                    f"Deletion not processed for {bucket}/{key} "
                    f"(version_id={version_id}, deletion_type={deletion_type}); "
                    f"see the preceding log line for the specific reason"
                )
                return False

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
            asset_data = None

            # Filter out LOCK records - they are processing locks, not real assets
            real_items = [
                item
                for item in response.get("Items", [])
                if not item["InventoryID"].startswith("LOCK#")
            ]

            if real_items:
                # Found the item in DynamoDB
                asset_data = real_items[0]
                inventory_id = asset_data["InventoryID"]
                logger.info(f"Found item in DynamoDB by S3 path: {inventory_id}")

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

            # If we found an inventory_id, use centralized deletion service
            if inventory_id:
                # Delete associated S3 files BEFORE using deletion service
                if asset_data:
                    self._delete_associated_s3_files(asset_data, bucket, key)

                # Import and use centralized deletion service
                from asset_deletion_service import AssetDeletionService

                deletion_service = AssetDeletionService(
                    dynamodb_table_name=os.environ.get("MEDIALAKE_ASSET_TABLE"),
                    logger=logger,
                    metrics=metrics,
                    tracer=tracer,
                )

                # Perform deletion using centralized service
                result = deletion_service.delete_asset(
                    inventory_id=inventory_id,
                    asset_data=asset_data,  # Pass pre-fetched data if available
                    publish_event=True,
                )

                logger.info(
                    f"Successfully deleted asset {inventory_id} using centralized service",
                    extra={
                        "s3_objects": result.s3_objects_deleted,
                        "opensearch_docs": result.opensearch_docs_deleted,
                        "vectors": result.vectors_deleted,
                    },
                )

                # Add metrics
                metrics.add_metric(
                    name="AssetDeletionProcessed", unit=MetricUnit.Count, value=1
                )
            else:
                logger.warning(f"No asset found for deletion: {bucket}/{key}")

            # Reached the end of the deletion flow without being skipped by the
            # version check, so report it as processed.
            return True

        except Exception as e:
            logger.exception(f"Error in delete_asset: {bucket}/{key}, error: {e}")
            metrics.add_metric(
                name="AssetDeletionErrors", unit=MetricUnit.Count, value=1
            )
            raise

    def _get_latest_version_entry(self, bucket: str, key: str) -> Optional[Dict]:
        """Return the CURRENT (latest) version or delete marker for an exact key.

        ``list_object_versions`` returns object versions and delete markers in
        two SEPARATE arrays (``Versions`` and ``DeleteMarkers``). A normal delete
        on a versioned bucket adds a delete marker that lives ONLY in
        ``DeleteMarkers`` — so any logic that inspects only ``Versions`` can
        never see that the object is now logically deleted. To know the object's
        current state we must consider both arrays.

        Returns a dict ``{"version_id", "is_delete_marker", "is_latest",
        "last_modified"}`` for the entry S3 flags ``IsLatest`` (falling back to
        the most recently modified entry), or ``None`` when the key has neither
        versions nor delete markers. Raises on API error so the caller can apply
        its own fail policy.
        """
        response = self.s3.list_object_versions(
            Bucket=bucket,
            Prefix=key,
            # Generous page size: the exact key sorts first among prefix matches,
            # so its current entry is always on the first page.
            MaxKeys=100,
        )

        candidates: List[Dict] = []
        for version in response.get("Versions", []):
            if version.get("Key") == key:
                candidates.append(
                    {
                        "version_id": version.get("VersionId"),
                        "is_delete_marker": False,
                        "is_latest": bool(version.get("IsLatest", False)),
                        "last_modified": version.get("LastModified"),
                    }
                )
        for marker in response.get("DeleteMarkers", []):
            if marker.get("Key") == key:
                candidates.append(
                    {
                        "version_id": marker.get("VersionId"),
                        "is_delete_marker": True,
                        "is_latest": bool(marker.get("IsLatest", False)),
                        "last_modified": marker.get("LastModified"),
                    }
                )

        if not candidates:
            return None

        # S3 flags exactly one entry (version or delete marker) as IsLatest.
        for candidate in candidates:
            if candidate["is_latest"]:
                return candidate

        # Fallback if IsLatest is somehow absent: newest by LastModified. Use a
        # tz-aware floor so the sort never mixes naive/aware datetimes.
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        candidates.sort(key=lambda c: c["last_modified"] or epoch, reverse=True)
        return candidates[0]

    def _should_process_deletion(
        self,
        bucket: str,
        key: str,
        version_id: str = None,
        is_delete_event: bool = True,
        deletion_type: str = None,
    ) -> bool:
        """Decide whether an S3 deletion event should remove the MediaLake asset.

        Goal: delete the asset when the object is no longer retrievable at its
        key (its live version is gone), and keep it when only a non-current
        version was permanently purged.

        Decision order (each branch logs a specific, self-explanatory reason):
          1. Delete-marker creation -> the object's current version is now a
             delete marker, so it is logically deleted. The event is
             authoritative, so process it WITHOUT an S3 call. This is the common
             case for a plain delete on a versioned bucket — and exactly the case
             the previous version-id comparison wrongly skipped.
          2. Versioning not Enabled (or unreadable) -> a plain delete really
             removed the object, so process it (fail-OPEN on read error).
          3. No version id -> treat as a current-object delete -> process.
          4. Versioned permanent delete -> inspect the key's CURRENT state via
             list_object_versions across BOTH Versions and DeleteMarkers:
               - delete marker on top, or nothing left -> object gone -> process
               - a live (non-marker) version still current -> this was an
                 older/non-current version purge -> skip
             (fail-CLOSED on list error: don't delete an asset whose live object
             may still exist).

        Every skip and every error is logged with its reason; errors include a
        full traceback via ``logger.exception``.
        """
        try:
            # (1) Delete-marker creation is authoritative — the object is gone.
            if deletion_type == DELETION_TYPE_DELETE_MARKER:
                logger.info(
                    f"Processing deletion for {bucket}/{key}: a delete marker was "
                    f"created (deletion_type='{deletion_type}', "
                    f"version_id={version_id}), so the object is logically deleted"
                )
                return True

            # (2) Versioning status. Fail OPEN on read error: on a non-versioned
            # bucket a delete genuinely removes the object, so we must not drop a
            # real deletion just because we couldn't read the bucket config.
            try:
                versioning_response = self.s3.get_bucket_versioning(Bucket=bucket)
                versioning_status = versioning_response.get("Status", "Suspended")
            except Exception as e:
                logger.exception(
                    f"Could not read bucket versioning for {bucket} while deciding "
                    f"deletion of {key} (version_id={version_id}, "
                    f"deletion_type={deletion_type}): {e}. Proceeding with deletion "
                    f"(fail-open) so a real delete is not silently dropped"
                )
                metrics.add_metric(
                    name="DeletionVersioningCheckError",
                    unit=MetricUnit.Count,
                    value=1,
                )
                return True

            logger.info(f"Bucket {bucket} versioning status: {versioning_status}")
            if versioning_status != "Enabled":
                logger.info(
                    f"Processing deletion for {bucket}/{key}: versioning is "
                    f"'{versioning_status}' (not Enabled), so the delete removed "
                    f"the object"
                )
                return True

            # (3) No version id on a versioned bucket is unusual; without one we
            # cannot reason about versions, so treat it as a current-object delete.
            if not version_id or version_id == "null":
                logger.info(
                    f"Processing deletion for {bucket}/{key}: event carried no "
                    f"version id (deletion_type={deletion_type}); treating as a "
                    f"current-object delete"
                )
                return True

            # (4) Versioned permanent delete: decide from the key's CURRENT state.
            # Fail CLOSED on list error: skip rather than risk deleting an asset
            # whose live object still exists.
            try:
                latest = self._get_latest_version_entry(bucket, key)
            except Exception as e:
                logger.exception(
                    f"Failed to list object versions for {bucket}/{key} while "
                    f"deciding deletion (version_id={version_id}, "
                    f"deletion_type={deletion_type}): {e}. Skipping deletion "
                    f"(fail-closed) to avoid removing an asset whose live object "
                    f"may still exist"
                )
                metrics.add_metric(
                    name="DeletionVersionListError", unit=MetricUnit.Count, value=1
                )
                return False

            if latest is None:
                logger.info(
                    f"Processing deletion for {bucket}/{key}: no remaining "
                    f"versions or delete markers for the key, so the object is "
                    f"fully gone (event version_id={version_id})"
                )
                return True

            if latest["is_delete_marker"]:
                logger.info(
                    f"Processing deletion for {bucket}/{key}: the current version "
                    f"is a delete marker (id={latest['version_id']}), so the "
                    f"object is logically deleted (event version_id={version_id})"
                )
                return True

            # A live, non-marker version is still current -> this event was for a
            # non-current version. Keep the asset.
            logger.info(
                f"Skipping deletion for {bucket}/{key}: a live current version "
                f"still exists (current id={latest['version_id']}), so the "
                f"deletion of version {version_id} was for a non-current version "
                f"(deletion_type={deletion_type})"
            )
            metrics.add_metric(
                name="OlderVersionDeletionSkipped", unit=MetricUnit.Count, value=1
            )
            return False

        except Exception as e:
            # Truly unexpected (a code bug, not an AWS read failure). Log loudly
            # with a traceback and fail CLOSED — we don't know the state, so we
            # don't delete; the traceback makes the skip diagnosable.
            logger.exception(
                f"Unexpected error in _should_process_deletion for {bucket}/{key} "
                f"(version_id={version_id}, deletion_type={deletion_type}): {e}. "
                f"Skipping deletion (fail-closed); investigate the traceback above"
            )
            metrics.add_metric(
                name="DeletionDecisionUnexpectedError", unit=MetricUnit.Count, value=1
            )
            return False

    @tracer.capture_method
    def publish_deletion_event(self, inventory_id: str):
        """Publish asset deletion event to EventBridge with optimized serialization"""
        try:
            event_detail = {
                "InventoryID": inventory_id,
                "DeletedAt": utc_now_z(),
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


def _lookup_asset_by_storage_path(table, bucket: str, key: str) -> Optional[Dict]:
    """Query S3PathIndex for an asset record, filtering out LOCK# items."""
    storage_path = f"{bucket}:{key}"
    try:
        response = table.query(
            IndexName="S3PathIndex",
            KeyConditionExpression="StoragePath = :path",
            ExpressionAttributeValues={":path": storage_path},
        )
        for item in response.get("Items", []):
            if not item.get("InventoryID", "").startswith("LOCK#"):
                return item
    except Exception as e:
        logger.exception(f"Error querying S3PathIndex for {storage_path}: {e}")
    return None


def update_storage_class(
    table, s3, bucket: str, key: str, destination_storage_class: Optional[str]
) -> None:
    """Update StorageClass on an existing asset record."""
    storage_class = destination_storage_class
    if not storage_class:
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            storage_class = head.get("StorageClass", "STANDARD")
            if storage_class == "STANDARD" and "StorageClass" not in head:
                logger.warning(
                    f"Defaulting to STANDARD for {bucket}/{key} — StorageClass absent from head_object"
                )
                metrics.add_metric(
                    name="unknown-storage-class", unit=MetricUnit.Count, value=1
                )
        except Exception as e:
            logger.warning(
                f"head_object failed for {bucket}/{key}: {e}, defaulting to STANDARD"
            )
            metrics.add_metric(
                name="unknown-storage-class", unit=MetricUnit.Count, value=1
            )
            storage_class = "STANDARD"

    item = _lookup_asset_by_storage_path(table, bucket, key)
    if not item:
        logger.info(
            f"No asset record found for {bucket}/{key} — ignoring storage class change"
        )
        metrics.add_metric(
            name="lifecycle-ignored-record-missing", unit=MetricUnit.Count, value=1
        )
        return

    table.update_item(
        Key={"InventoryID": item["InventoryID"]},
        UpdateExpression="SET DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.StorageClass = :sc",
        ExpressionAttributeValues={":sc": storage_class},
    )
    logger.info(f"Updated StorageClass to {storage_class} for {bucket}/{key}")
    metrics.add_metric(name="lifecycle-updated", unit=MetricUnit.Count, value=1)


def update_restore_status(
    table, bucket: str, key: str, restore_status: Optional[str]
) -> None:
    """Update or remove RestoreStatus on an existing asset record."""
    item = _lookup_asset_by_storage_path(table, bucket, key)
    if not item:
        logger.info(
            f"No asset record found for {bucket}/{key} — ignoring restore status change"
        )
        metrics.add_metric(
            name="lifecycle-ignored-record-missing", unit=MetricUnit.Count, value=1
        )
        return

    if restore_status is None:
        table.update_item(
            Key={"InventoryID": item["InventoryID"]},
            UpdateExpression="SET DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.RestoreStatus = :rs",
            ExpressionAttributeValues={":rs": None},
        )
    else:
        table.update_item(
            Key={"InventoryID": item["InventoryID"]},
            UpdateExpression="SET DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.RestoreStatus = :rs",
            ExpressionAttributeValues={":rs": restore_status},
        )
    logger.info(f"Updated RestoreStatus to {restore_status} for {bucket}/{key}")
    metrics.add_metric(name="lifecycle-updated", unit=MetricUnit.Count, value=1)


# Process records in parallel with improved logging
def process_records_in_parallel(
    processor: AssetProcessor, records: List[Dict], max_workers: Optional[int] = None
):
    """Process records in parallel using a ThreadPoolExecutor.

    Concurrency defaults to the ``INGEST_MAX_WORKERS`` env var (falling back to
    5). Raising it is memory-safe: each record is processed by streaming its S3
    object (chunked MD5 + head/metadata), never loading the whole file, so more
    concurrent records does not risk large-file OOM on this Lambda.
    """
    if max_workers is None:
        try:
            max_workers = int(os.environ.get("INGEST_MAX_WORKERS", "5"))
        except (TypeError, ValueError):
            max_workers = 5
    max_workers = max(1, max_workers)

    # Add logging for initial record count
    logger.info(
        f"Starting parallel processing with {len(records)} records "
        f"(max_workers={max_workers})"
    )

    # Debug log the first record structure
    if records and len(records) > 0:
        logger.info(f"First record structure: {json_serialize(records[0])}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        skipped_records = 0

        for i, record in enumerate(records):
            try:
                contexts = normalize_event_contexts(record)

                if contexts:
                    for ctx in contexts:
                        # Debug log for keys containing special characters
                        if "+" in ctx["key"] or "%" in ctx["key"]:
                            logger.info(f"Key with special characters: {ctx['key']}")

                        logger.info(
                            f"Submitting task for bucket: {ctx['bucket']}, key: {ctx['key']}, event: {ctx['event_type']}, version: {ctx.get('version_id')}"
                        )
                        futures.append(
                            executor.submit(
                                process_s3_event,
                                processor,
                                ctx,
                            )
                        )
                else:
                    logger.warning(f"Could not extract context from record {i}")
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
            f"DynamoDB table info available - Table Status: {dynamodb_client.describe_table(TableName=os.environ['ASSETS_TABLE']).get('Table', {}).get('TableStatus')}"
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

            # Pass raw records directly to process_records_in_parallel;
            # normalize_event_context handles all shapes (S3, SQS-wrapped S3,
            # SQS-wrapped EventBridge, direct EventBridge).
            process_records_in_parallel(processor, event["Records"])

        elif isinstance(event, dict) and "detail-type" in event:
            # EventBridge event format - single event
            logger.info("Processing EventBridge event")
            total_records = 1

            ctx = normalize_event_context(event)
            if ctx:
                logger.info(
                    f"Processing EventBridge event for {ctx['bucket']}/{ctx['key']} with event type: {ctx['event_type']}, version: {ctx.get('version_id')}"
                )
                process_s3_event(processor, ctx)
            else:
                logger.warning(
                    f"Could not normalize EventBridge event: {json_serialize(event)}"
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
    ctx: S3EventContext,
):
    """Process a single S3 event with improved performance"""
    bucket = ctx["bucket"]
    key = ctx["key"]
    event_name = ctx["event_type"]
    version_id = ctx.get("version_id")

    # Skip processing if event type not relevant (quick filtering)
    if not is_relevant_event(event_name):
        logger.info(f"Skipping irrelevant event type: {event_name} for {bucket}/{key}")
        return

    # Lookup connector for telemetry
    connector_info = lookup_connector_by_bucket(bucket)
    if connector_info:
        if connector_info["integrationMethod"] != "eventbridge":
            logger.append_keys(
                connectorId=connector_info["id"],
                integrationMethod=connector_info["integrationMethod"],
            )
            metrics.add_dimension(name="ConnectorId", value=connector_info["id"])
            metrics.add_dimension(
                name="IntegrationMethod", value=connector_info["integrationMethod"]
            )
            metrics.add_metric(
                name="CapabilityLimitationDetected", unit=MetricUnit.Count, value=1
            )
            # Flush the limitation metric with connector dimensions immediately,
            # then remove dimensions so they don't leak to unrelated metrics.
            metrics.flush_metrics()
            logger.remove_keys(["connectorId", "integrationMethod"])

    logger.info(
        f"Processing {event_name} event for asset: {bucket}/{key}, version: {version_id}"
    )

    # Record start time for duration tracking
    start_time = datetime.now()

    _RESTORE_STATUS_MAP = {
        "ObjectRestore:Post": "RESTORING",
        "ObjectRestore:Completed": "RESTORED",
        "ObjectRestore:Delete": None,
    }

    try:
        if event_name.startswith("ObjectRemoved:"):
            # Handle deletion - only delete from DynamoDB, don't try to delete the S3 object again
            deletion_type = ctx.get("deletion_type")
            logger.info(
                f"Processing deletion event for {bucket}/{key}, "
                f"version: {version_id}, deletion_type: {deletion_type}"
            )
            processed = processor.delete_asset(
                bucket,
                key,
                is_delete_event=True,
                version_id=version_id,
                deletion_type=deletion_type,
            )
            if processed:
                metrics.add_metric(name="DeletedAssets", unit=MetricUnit.Count, value=1)
                logger.info(f"Asset deletion processed: {key}")
            else:
                # Intentionally skipped (e.g. non-current version delete). The
                # specific reason was logged by _should_process_deletion.
                metrics.add_metric(
                    name="DeletionSkipped", unit=MetricUnit.Count, value=1
                )
                logger.info(
                    f"Asset deletion skipped (reason logged above): {bucket}/{key}"
                )
        elif event_name == "ObjectStorageClassChanged":
            update_storage_class(
                processor.table,
                processor.s3,
                bucket,
                key,
                ctx.get("destination_storage_class"),
            )
        elif event_name in _RESTORE_STATUS_MAP:
            update_restore_status(
                processor.table, bucket, key, _RESTORE_STATUS_MAP[event_name]
            )
        elif event_name.startswith("ObjectCreated:"):
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
            result = processor.process_asset(bucket, key, version_id)
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
        else:
            logger.warning(
                f"Unknown event type in dispatch: {event_name} for {bucket}/{key}"
            )
            metrics.add_metric(
                name="unknown-event-type", unit=MetricUnit.Count, value=1
            )

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
    DEPRECATED: Use normalize_event_context() instead.
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


# EventBridge detail-type to S3 event type mapping
_EVENTBRIDGE_DETAIL_TYPE_MAP = {
    "Object Created": "ObjectCreated:",
    "Object Deleted": "ObjectRemoved:",
    "Object Storage Class Changed": "ObjectStorageClassChanged",
    "Object Restore Initiated": "ObjectRestore:Post",
    "Object Restore Completed": "ObjectRestore:Completed",
    "Object Restore Expired": "ObjectRestore:Delete",
    "PutObject": "ObjectCreated:Put",
    "CompleteMultipartUpload": "ObjectCreated:CompleteMultipartUpload",
    "DeleteObject": "ObjectRemoved:Delete",
    "CopyObject": "ObjectCreated:Copy",
}


def _decode_s3_key(raw_key: str) -> str:
    """Decode S3 key — URL-decode and replace '+' with space."""
    return urllib.parse.unquote(raw_key).replace("+", " ")


# S3 deletion-type vocabulary. EventBridge "Object Deleted" events carry these
# values verbatim in detail["deletion-type"]. For raw S3 notifications we derive
# the same values from the event-name subtype (see _deletion_type_from_event_name)
# so the deletion logic can stay source-agnostic.
DELETION_TYPE_DELETE_MARKER = "Delete Marker Created"
DELETION_TYPE_PERMANENT = "Permanently Deleted"


def _deletion_type_from_event_name(event_name: str) -> Optional[str]:
    """Map a raw S3 ``ObjectRemoved:*`` event name to a deletion-type value.

    Raw S3 notifications encode the deletion kind in the event-name subtype,
    whereas EventBridge puts it in ``detail["deletion-type"]``. Normalizing both
    to the same vocabulary lets ``_should_process_deletion`` reason about
    deletions without caring which source delivered the event. Returns ``None``
    for non-deletion events or the generic ``ObjectRemoved:`` (EventBridge),
    where the subtype is unknown and the deletion-type comes from the detail.
    """
    if event_name == "ObjectRemoved:DeleteMarkerCreated":
        return DELETION_TYPE_DELETE_MARKER
    if event_name == "ObjectRemoved:Delete":
        return DELETION_TYPE_PERMANENT
    return None


def _extract_eventbridge_context(event_data: Dict) -> Optional[S3EventContext]:
    """Extract S3EventContext from an EventBridge-shaped payload."""
    if event_data.get("source") != "aws.s3":
        return None

    detail = event_data.get("detail", {})
    detail_type = event_data.get("detail-type", "")

    event_type = _EVENTBRIDGE_DETAIL_TYPE_MAP.get(detail_type)
    if event_type is None:
        logger.warning(f"Unknown EventBridge detail-type: {detail_type}")
        metrics.add_metric(name="unknown-event-type", unit=MetricUnit.Count, value=1)
        return None

    # Extract bucket
    bucket = None
    if isinstance(detail.get("bucket"), dict):
        bucket = detail["bucket"].get("name")
    elif isinstance(detail.get("bucket"), str):
        bucket = detail["bucket"]

    # Extract key and version_id
    key = None
    version_id = None
    if isinstance(detail.get("object"), dict):
        key = detail["object"].get("key")
        version_id = detail["object"].get("version-id") or detail["object"].get(
            "versionId"
        )
    elif isinstance(detail.get("object"), str):
        key = detail["object"]
    elif "key" in detail:
        key = detail["key"]

    if not bucket or not key:
        logger.warning(
            f"Missing bucket or key in EventBridge detail: {json_serialize(detail)}"
        )
        return None

    key = _decode_s3_key(key)

    destination_storage_class = None
    if detail_type == "Object Storage Class Changed":
        destination_storage_class = detail.get("destination-storage-class")

    # Deletion kind: S3 EventBridge "Object Deleted" events carry the exact
    # vocabulary ("Delete Marker Created" / "Permanently Deleted") in
    # detail["deletion-type"]. Absent (None) for non-deletion events.
    deletion_type = detail.get("deletion-type")

    return S3EventContext(
        event_type=event_type,
        bucket=bucket,
        key=key,
        version_id=version_id,
        destination_storage_class=destination_storage_class,
        deletion_type=deletion_type,
    )


def normalize_event_context(event_record: Dict) -> Optional[S3EventContext]:
    """Normalize any inbound event shape into an S3EventContext."""
    # Direct S3 record
    if "s3" in event_record:
        s3_info = event_record["s3"]
        if "bucket" in s3_info and "object" in s3_info:
            return S3EventContext(
                event_type=event_record.get("eventName", "ObjectCreated:"),
                bucket=s3_info["bucket"]["name"],
                key=_decode_s3_key(s3_info["object"]["key"]),
                version_id=s3_info["object"].get("versionId"),
                destination_storage_class=None,
                deletion_type=_deletion_type_from_event_name(
                    event_record.get("eventName", "")
                ),
            )

    # SQS-wrapped record
    if event_record.get("eventSource") == "aws:sqs" and "body" in event_record:
        try:
            body = json.loads(event_record["body"])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SQS message body: {e}")
            metrics.add_metric(name="parse-failure", unit=MetricUnit.Count, value=1)
            return None

        # SQS-wrapped EventBridge
        if body.get("source") == "aws.s3" and "detail" in body:
            return _extract_eventbridge_context(body)

        # SQS-wrapped S3 records
        if "Records" in body and isinstance(body["Records"], list):
            for record in body["Records"]:
                valid_sources = ["aws:s3", "medialake.AssetSyncProcessor"]
                if record.get("eventSource") in valid_sources and "s3" in record:
                    return S3EventContext(
                        event_type=record.get("eventName", "ObjectCreated:"),
                        bucket=record["s3"]["bucket"]["name"],
                        key=_decode_s3_key(record["s3"]["object"]["key"]),
                        version_id=record["s3"]["object"].get("versionId"),
                        destination_storage_class=None,
                        deletion_type=_deletion_type_from_event_name(
                            record.get("eventName", "")
                        ),
                    )

    # EventBridge direct
    if "detail-type" in event_record and "source" in event_record:
        return _extract_eventbridge_context(event_record)

    logger.warning(
        f"Unrecognized event structure in normalize_event_context: {json_serialize(event_record)}"
    )
    return None


def normalize_event_contexts(event_record: Dict) -> List[S3EventContext]:
    """Normalize any inbound event shape into a list of S3EventContext.

    Unlike normalize_event_context (singular), this correctly yields ALL nested
    S3 records when an SQS message body contains multiple Records entries.
    """
    # Direct S3 record
    if "s3" in event_record:
        s3_info = event_record["s3"]
        if "bucket" in s3_info and "object" in s3_info:
            return [
                S3EventContext(
                    event_type=event_record.get("eventName", "ObjectCreated:"),
                    bucket=s3_info["bucket"]["name"],
                    key=_decode_s3_key(s3_info["object"]["key"]),
                    version_id=s3_info["object"].get("versionId"),
                    destination_storage_class=None,
                    deletion_type=_deletion_type_from_event_name(
                        event_record.get("eventName", "")
                    ),
                )
            ]

    # SQS-wrapped record
    if event_record.get("eventSource") == "aws:sqs" and "body" in event_record:
        try:
            body = json.loads(event_record["body"])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SQS message body: {e}")
            metrics.add_metric(name="parse-failure", unit=MetricUnit.Count, value=1)
            return []

        # SQS-wrapped EventBridge
        if body.get("source") == "aws.s3" and "detail" in body:
            ctx = _extract_eventbridge_context(body)
            return [ctx] if ctx else []

        # SQS-wrapped S3 records — collect ALL valid nested records
        if "Records" in body and isinstance(body["Records"], list):
            contexts: List[S3EventContext] = []
            valid_sources = ["aws:s3", "medialake.AssetSyncProcessor"]
            for idx, record in enumerate(body["Records"]):
                try:
                    if (
                        record.get("eventSource") not in valid_sources
                        or "s3" not in record
                    ):
                        logger.warning(
                            f"Skipping unrecognized nested record {idx}: {json_serialize(record)}"
                        )
                        metrics.add_metric(
                            name="unrecognized-nested-record",
                            unit=MetricUnit.Count,
                            value=1,
                        )
                        continue
                    s3_info = record["s3"]
                    if (
                        "bucket" not in s3_info
                        or "name" not in s3_info.get("bucket", {})
                        or "object" not in s3_info
                        or "key" not in s3_info.get("object", {})
                    ):
                        logger.warning(
                            f"Skipping malformed nested record {idx}: missing s3.bucket.name or s3.object.key"
                        )
                        metrics.add_metric(
                            name="malformed-nested-record",
                            unit=MetricUnit.Count,
                            value=1,
                        )
                        continue
                    contexts.append(
                        S3EventContext(
                            event_type=record.get("eventName", "ObjectCreated:"),
                            bucket=s3_info["bucket"]["name"],
                            key=_decode_s3_key(s3_info["object"]["key"]),
                            version_id=s3_info["object"].get("versionId"),
                            destination_storage_class=None,
                            deletion_type=_deletion_type_from_event_name(
                                record.get("eventName", "")
                            ),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Skipping malformed nested record {idx}: {e}")
                    metrics.add_metric(
                        name="malformed-nested-record", unit=MetricUnit.Count, value=1
                    )
            return contexts

    # EventBridge direct
    if "detail-type" in event_record and "source" in event_record:
        ctx = _extract_eventbridge_context(event_record)
        return [ctx] if ctx else []

    logger.warning(
        f"Unrecognized event structure in normalize_event_contexts: {json_serialize(event_record)}"
    )
    return []
