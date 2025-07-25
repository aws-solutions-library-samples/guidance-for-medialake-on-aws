"""
Utility functions for asset processing.

This module contains general-purpose utility functions and helpers
used throughout the asset processing system.
"""

import hashlib
import mimetypes
import os
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from aws_lambda_powertools import Logger

logger = Logger()


def generate_inventory_id() -> str:
    """Generate a unique inventory ID for assets."""
    return str(uuid4())


def parse_s3_event_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse S3 event record to extract relevant information.

    Args:
        record: S3 event record from Lambda event

    Returns:
        Dict containing parsed S3 event information
    """
    try:
        s3_info = record.get("s3", {})
        bucket_info = s3_info.get("bucket", {})
        object_info = s3_info.get("object", {})

        # URL decode the object key
        object_key = urllib.parse.unquote_plus(
            object_info.get("key", ""), encoding="utf-8"
        )

        return {
            "event_name": record.get("eventName", ""),
            "event_source": record.get("eventSource", ""),
            "event_time": record.get("eventTime", ""),
            "bucket_name": bucket_info.get("name", ""),
            "bucket_arn": bucket_info.get("arn", ""),
            "object_key": object_key,
            "object_size": object_info.get("size", 0),
            "object_etag": object_info.get("eTag", "").strip('"'),
            "object_version_id": object_info.get("versionId"),
            "object_sequencer": object_info.get("sequencer", ""),
            "request_id": record.get("responseElements", {}).get(
                "x-amz-request-id", ""
            ),
            "requester": record.get("requestParameters", {}).get("principalId", ""),
            "source_ip": record.get("requestParameters", {}).get("sourceIPAddress", ""),
        }
    except Exception as e:
        logger.exception(
            "Error parsing S3 event record", extra={"record": record, "error": str(e)}
        )
        raise


def determine_asset_type(object_key: str, content_type: Optional[str] = None) -> str:
    """
    Determine asset type based on file extension and content type.

    Args:
        object_key: S3 object key (file path)
        content_type: MIME content type (optional)

    Returns:
        Asset type string
    """
    # Get file extension
    _, ext = os.path.splitext(object_key.lower())

    # If no content type provided, guess from extension
    if not content_type:
        content_type, _ = mimetypes.guess_type(object_key)

    # Image types
    image_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
        ".svg",
    }
    if ext in image_extensions or (content_type and content_type.startswith("image/")):
        return "image"

    # Video types
    video_extensions = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv", ".m4v"}
    if ext in video_extensions or (content_type and content_type.startswith("video/")):
        return "video"

    # Audio types
    audio_extensions = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"}
    if ext in audio_extensions or (content_type and content_type.startswith("audio/")):
        return "audio"

    # Document types
    document_extensions = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".rtf",
    }
    if ext in document_extensions or (content_type and "document" in content_type):
        return "document"

    # Archive types
    archive_extensions = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
    if ext in archive_extensions or (content_type and "archive" in content_type):
        return "archive"

    # Default to 'file' for unknown types
    return "file"


def extract_metadata_from_tags(tags: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract and normalize metadata from S3 object tags.

    Args:
        tags: Dictionary of S3 object tags

    Returns:
        Normalized metadata dictionary
    """
    metadata = {}

    # Common tag mappings
    tag_mappings = {
        "title": "title",
        "description": "description",
        "author": "author",
        "creator": "creator",
        "subject": "subject",
        "keywords": "keywords",
        "category": "category",
        "project": "project",
        "department": "department",
        "classification": "classification",
        "confidentiality": "confidentiality",
        "retention": "retention_period",
        "source": "source_system",
    }

    for tag_key, tag_value in tags.items():
        # Normalize tag key to lowercase
        normalized_key = tag_key.lower()

        # Map to standard metadata field if available
        if normalized_key in tag_mappings:
            metadata[tag_mappings[normalized_key]] = tag_value
        else:
            # Keep original tag with 'tag_' prefix
            metadata[f"tag_{normalized_key}"] = tag_value

    return metadata


def extract_metadata_from_s3_metadata(s3_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant metadata from S3 object metadata.

    Args:
        s3_metadata: S3 head_object response metadata

    Returns:
        Extracted metadata dictionary
    """
    metadata = {}

    # Extract standard S3 metadata
    if "ContentType" in s3_metadata:
        metadata["content_type"] = s3_metadata["ContentType"]

    if "ContentLength" in s3_metadata:
        metadata["content_length"] = s3_metadata["ContentLength"]

    if "LastModified" in s3_metadata:
        metadata["last_modified"] = s3_metadata["LastModified"].isoformat()

    if "ETag" in s3_metadata:
        metadata["etag"] = s3_metadata["ETag"].strip('"')

    # Extract user-defined metadata (prefixed with 'x-amz-meta-')
    user_metadata = s3_metadata.get("Metadata", {})
    for key, value in user_metadata.items():
        metadata[f"user_{key}"] = value

    # Extract other relevant fields
    optional_fields = [
        "CacheControl",
        "ContentDisposition",
        "ContentEncoding",
        "ContentLanguage",
        "Expires",
        "StorageClass",
        "ServerSideEncryption",
    ]

    for field in optional_fields:
        if field in s3_metadata:
            # Convert to snake_case
            snake_case_field = re.sub("([A-Z])", r"_\1", field).lower().lstrip("_")
            metadata[snake_case_field] = s3_metadata[field]

    return metadata


def create_asset_record(
    inventory_id: str,
    bucket: str,
    object_key: str,
    file_hash: str,
    file_size: int,
    asset_type: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a standardized asset record for storage.

    Args:
        inventory_id: Unique asset identifier
        bucket: S3 bucket name
        object_key: S3 object key
        file_hash: MD5 hash of the file
        file_size: File size in bytes
        asset_type: Type of asset (image, video, etc.)
        metadata: Additional metadata

    Returns:
        Standardized asset record dictionary
    """
    now = datetime.utcnow().isoformat()

    return {
        "InventoryID": inventory_id,
        "Bucket": bucket,
        "ObjectKey": object_key,
        "FileHash": file_hash,
        "FileSize": file_size,
        "AssetType": asset_type,
        "CreatedAt": now,
        "UpdatedAt": now,
        "Metadata": metadata,
        "Status": "active",
        "Version": 1,
    }


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing or replacing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove control characters
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", sanitized)

    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        max_name_length = 255 - len(ext)
        sanitized = name[:max_name_length] + ext

    return sanitized


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted file size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def is_valid_s3_key(key: str) -> bool:
    """
    Validate S3 object key format.

    Args:
        key: S3 object key to validate

    Returns:
        True if valid, False otherwise
    """
    if not key or len(key) > 1024:
        return False

    # Check for invalid characters
    invalid_chars = ["\x00", "\x08", "\x0b", "\x0c", "\x0e", "\x0f"]
    if any(char in key for char in invalid_chars):
        return False

    # Check for problematic patterns
    if key.startswith("/") or key.endswith("/") or "//" in key:
        return False

    return True


def extract_path_components(object_key: str) -> Dict[str, str]:
    """
    Extract path components from S3 object key.

    Args:
        object_key: S3 object key

    Returns:
        Dictionary with path components
    """
    # Normalize path separators
    normalized_key = object_key.replace("\\", "/")

    # Split into directory and filename
    directory = os.path.dirname(normalized_key)
    filename = os.path.basename(normalized_key)

    # Extract name and extension
    name, extension = os.path.splitext(filename)

    return {
        "directory": directory,
        "filename": filename,
        "name": name,
        "extension": extension.lstrip(".").lower() if extension else "",
        "full_path": normalized_key,
    }


def calculate_checksum(data: Union[str, bytes], algorithm: str = "md5") -> str:
    """
    Calculate checksum for data using specified algorithm.

    Args:
        data: Data to calculate checksum for
        algorithm: Hash algorithm to use (md5, sha1, sha256)

    Returns:
        Hexadecimal checksum string
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    if algorithm.lower() == "md5":
        return hashlib.md5(data, usedforsecurity=False).hexdigest()
    elif algorithm.lower() == "sha1":
        return hashlib.sha1(data, usedforsecurity=False).hexdigest()
    elif algorithm.lower() == "sha256":
        return hashlib.sha256(data).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def batch_items(items: List[Any], batch_size: int = 25) -> List[List[Any]]:
    """
    Split items into batches of specified size.

    Args:
        items: List of items to batch
        batch_size: Maximum size of each batch

    Returns:
        List of batches
    """
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i : i + batch_size])
    return batches


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds

    Returns:
        Decorated function
    """
    import random
    import time

    def wrapper(*args, **kwargs):
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    raise

                # Calculate delay with jitter
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                    extra={"error": str(e), "function": func.__name__},
                )
                time.sleep(delay)

    return wrapper


def validate_environment_variables(required_vars: List[str]) -> Dict[str, str]:
    """
    Validate that required environment variables are set.

    Args:
        required_vars: List of required environment variable names

    Returns:
        Dictionary of environment variables

    Raises:
        ValueError: If any required variables are missing
    """
    env_vars = {}
    missing_vars = []

    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        else:
            env_vars[var] = value

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return env_vars


def safe_json_serialize(obj: Any) -> Any:
    """
    Safely serialize object to JSON-compatible format.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable object
    """
    if isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, "__dict__"):
        return safe_json_serialize(obj.__dict__)
    else:
        try:
            import json

            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)
