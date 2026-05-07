"""
Distributed Map Utilities for AWS Step Functions

Provides standardized tools for handling S3 external payload offloading
in AWS Step Functions Distributed Map patterns.
"""

import json
from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger

logger = Logger(child=True)


def download_s3_external_payload(
    s3_client,
    reference: Dict[str, Any],
    logger_instance: Optional[Logger] = None,
) -> Any:
    """
    Download and process S3 external payload with smart list handling.

    For Distributed Map patterns with S3 external payload offloading, this handles:
    - Direct index-based extraction when index is specified
    - Auto-extraction of single-item lists when no index specified
    - Pass-through of non-list payloads

    Args:
        s3_client: Boto3 S3 client instance
        reference: Dict containing 's3_bucket', 's3_key', and optional 'index'
        logger_instance: Optional logger instance for debugging

    Returns:
        Extracted payload data (dict, list, or primitive)

    Raises:
        RuntimeError: If S3 download fails or data structure is invalid

    Example:
        >>> # With index (for distributed map items)
        >>> ref = {"s3_bucket": "bucket", "s3_key": "key", "index": 0}
        >>> data = download_s3_external_payload(s3, ref, logger)
        >>>
        >>> # Without index (auto-extracts single-item lists)
        >>> ref = {"s3_bucket": "bucket", "s3_key": "key"}
        >>> data = download_s3_external_payload(s3, ref, logger)
    """
    log = logger_instance or logger

    bucket = reference.get("s3_bucket")
    key = reference.get("s3_key")
    index = reference.get("index")

    if not bucket or not key:
        raise RuntimeError(
            f"Invalid S3 reference: missing bucket or key. Got: {reference}"
        )

    try:
        log.info(f"Downloading S3 external payload: s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        payload_data = response["Body"].read().decode("utf-8")
        parsed_data = json.loads(payload_data)

        if not isinstance(parsed_data, (dict, list)):
            raise RuntimeError(
                f"Expected dict or list from S3, got {type(parsed_data)}"
            )

        # Handle indexed access (distributed map with specific item)
        if index is not None:
            if not isinstance(parsed_data, list):
                raise RuntimeError(
                    f"Index {index} specified but payload is not a list: {type(parsed_data)}"
                )
            if index < 0 or index >= len(parsed_data):
                raise RuntimeError(
                    f"Index {index} out of range for {len(parsed_data)} items"
                )
            log.info(f"Extracted item at index {index} from S3 payload")
            return parsed_data[index]

        # Auto-extract single-item lists for cleaner downstream processing
        if isinstance(parsed_data, list):
            if len(parsed_data) == 1:
                log.info("Auto-extracted single item from list payload")
                return parsed_data[0]
            log.warning(
                f"Multiple items ({len(parsed_data)}) in S3 payload but no index specified - returning full list"
            )

        return parsed_data

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse JSON from s3://{bucket}/{key}: {e}")
        raise RuntimeError(f"Failed to parse S3 payload as JSON: {e}") from e
    except Exception as e:
        log.error(f"Failed to download S3 payload from s3://{bucket}/{key}: {e}")
        raise RuntimeError(f"Failed to download S3 external payload: {e}") from e


def extract_s3_reference(data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extract S3 reference from various data structures.

    Handles common patterns where S3 references appear in different locations:
    - Direct keys: s3_bucket, s3_key, index
    - Nested in 'data': data.s3_bucket, data.s3_key, data.index
    - Nested in 'item': item.s3_bucket, item.s3_key, item.index

    Args:
        data: Dictionary containing potential S3 reference

    Returns:
        Dict with s3_bucket, s3_key, and optional index, or None if not found

    Example:
        >>> data = {"s3_bucket": "my-bucket", "s3_key": "path/to/file.json", "index": 0}
        >>> ref = extract_s3_reference(data)
        >>> print(ref)
        {'s3_bucket': 'my-bucket', 's3_key': 'path/to/file.json', 'index': 0}
    """
    # Check direct keys
    if data.get("s3_bucket") and data.get("s3_key"):
        return {
            "s3_bucket": data["s3_bucket"],
            "s3_key": data["s3_key"],
            "index": data.get("index"),
        }

    # Check nested in 'data'
    if isinstance(data.get("data"), dict):
        nested_data = data["data"]
        if nested_data.get("s3_bucket") and nested_data.get("s3_key"):
            return {
                "s3_bucket": nested_data["s3_bucket"],
                "s3_key": nested_data["s3_key"],
                "index": nested_data.get("index"),
            }

    # Check nested in 'item'
    if isinstance(data.get("item"), dict):
        item = data["item"]
        if item.get("s3_bucket") and item.get("s3_key"):
            return {
                "s3_bucket": item["s3_bucket"],
                "s3_key": item["s3_key"],
                "index": item.get("index"),
            }

    return None


def is_s3_reference(data: Dict[str, Any]) -> bool:
    """
    Check if data contains an S3 external payload reference.

    Args:
        data: Dictionary to check

    Returns:
        True if data contains S3 reference pattern

    Example:
        >>> data = {"s3_bucket": "my-bucket", "s3_key": "file.json"}
        >>> is_s3_reference(data)
        True
    """
    return extract_s3_reference(data) is not None
