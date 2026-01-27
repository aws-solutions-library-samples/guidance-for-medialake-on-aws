"""S3-based configuration loader for normalizers.

This module provides functionality to load normalizer configurations from S3,
allowing large configurations to be stored externally rather than inline in
the node configuration.

Features:
- Load configuration from S3 with LRU caching
- Support for hybrid configuration (S3 base + inline overrides)
- Clear error messages for common failure scenarios

Usage:
    from normalizers.config_loader import resolve_normalizer_config

    # In node handler:
    normalizer_config = node_config.get("normalizer", {})
    resolved_config = resolve_normalizer_config(normalizer_config)
    normalizer = MetadataNormalizer(
        source_type=normalizer_config.get("source_type"),
        config=resolved_config
    )
"""

import json
import os
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Module-level S3 client for Lambda warm starts
_s3_client: Any = None


def get_s3_client() -> Any:
    """Get or create S3 client (reused across invocations).

    Returns:
        boto3 S3 client instance
    """
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


@lru_cache(maxsize=10)
def load_config_from_s3(bucket: str, key: str) -> dict[str, Any]:
    """Load and cache configuration from S3.

    Uses LRU cache to avoid repeated S3 fetches within the same
    Lambda invocation. Cache is cleared on cold starts.

    Args:
        bucket: S3 bucket name (IAC assets bucket)
        key: S3 object key (e.g., "normalizer-configs/customer-config.json")

    Returns:
        Parsed configuration dictionary

    Raises:
        ValueError: If config file not found or invalid JSON
    """
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code in ("NoSuchKey", "404"):
            raise ValueError(
                f"Configuration file not found: s3://{bucket}/{key}"
            ) from e
        raise ValueError(
            f"Failed to load configuration from s3://{bucket}/{key}: {e}"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in configuration file s3://{bucket}/{key}: {e}"
        ) from e


def resolve_normalizer_config(node_config: dict[str, Any]) -> dict[str, Any]:
    """Resolve normalizer configuration from node config.

    Supports both inline config and S3-based config loading.
    If both are provided, inline config takes precedence (allows overrides).

    Configuration resolution order:
    1. If config_s3_path is provided, load base config from S3
    2. If inline config is provided, merge it on top (overrides S3 values)
    3. Return the merged configuration

    Args:
        node_config: The normalizer section of node configuration.
                    Expected structure:
                    {
                        "source_type": "generic_xml",
                        "config_s3_path": "normalizer-configs/customer-config.json",
                        "config": {...}  # Optional inline overrides
                    }

    Returns:
        Resolved configuration dictionary

    Raises:
        ValueError: If S3 path is provided but IAC_ASSETS_BUCKET env var is not set,
                   or if S3 config file is not found or invalid
    """
    inline_config = node_config.get("config", {})
    s3_path = node_config.get("config_s3_path")

    if s3_path:
        # Load from S3
        bucket = os.environ.get("IAC_ASSETS_BUCKET")
        if not bucket:
            raise ValueError(
                "IAC_ASSETS_BUCKET environment variable not set. "
                "Cannot load configuration from S3."
            )

        s3_config = load_config_from_s3(bucket, s3_path)

        # Merge: inline config overrides S3 config
        if inline_config:
            merged_config = dict(s3_config)
            merged_config.update(inline_config)
            return merged_config

        return s3_config

    return inline_config


def clear_config_cache() -> None:
    """Clear the LRU cache for S3 configurations.

    Useful for testing or when configurations need to be reloaded.
    """
    load_config_from_s3.cache_clear()
