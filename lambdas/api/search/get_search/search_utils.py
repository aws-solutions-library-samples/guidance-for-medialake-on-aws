import decimal
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger
from botocore.config import Config

logger = Logger()

# Signature style & virtual-host addressing are required for every region
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: dict[str, boto3.client] = {}  # {region → client}


# ─────────────────────────────────────────────────────────────────────────────
def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client **pinned to the bucket's actual region**.
    Clients are cached to reuse TCP connections across warm invocations.
    """
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )

    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
    except generic.exceptions.NoSuchBucket:
        raise ValueError(f"S3 bucket {bucket!r} does not exist")

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=_ENDPOINT_TMPL.format(region=region),
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


# Supported special keywords for search
KEYWORDS = {
    "type": r"type:(\w+)",
    "asset_size_gte": r"asset_size_gte:([<>]=?\d+(?:\.\d+)?(?:KB|MB|GB|TB))",
    "asset_size_lte": r"asset_size_lte:([<>]=?\d+(?:\.\d+)?(?:KB|MB|GB|TB))",
    "extension": r"extension:([a-zA-Z0-9._\-*/]+)",
    "ingested_date_gte": r"ingested_date_gte:([<>]=?\d{4}-\d{2}-\d{2})",
    "ingested_date_lte": r"ingested_date_lte:([<>]=?\d{4}-\d{2}-\d{2})",
}

# KEYWORDS = {
#    'content_type': r'type:(\w+)',
#    'format': r'format:(\w+)',
#    'size': r'size:([<>]=?\d+(?:\.\d+)?(?:KB|MB|GB|TB))',
#    'date': r'date:([<>]=?\d{4}-\d{2}-\d{2})',
#    'metadata': r'metadata:(\w+:\w+)',
# 	'storageIdentifier': r'storageIdentifier:([a-zA-Z0-9._\-*/]+)'
# }


def parse_size_value(size_str: str) -> Optional[Dict[str, Any]]:
    """Convert size string (e.g., '1GB', '500MB') to bytes"""
    try:
        pattern = r"([<>]=?)(\d+(?:\.\d+)?)(KB|MB|GB|TB)"
        match = re.match(pattern, size_str)
        if not match:
            return None

        operator, value, unit = match.groups()
        value = float(value)

        multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

        bytes_value = int(value * multipliers[unit])
        return {"operator": operator, "value": bytes_value}
    except Exception as e:
        logger.warning(f"Error parsing size value: {str(e)}")
        return None


def parse_date_value(date_str: str) -> Optional[Dict]:
    """Parse date string with operator (e.g., '>2024-01-01')"""
    try:
        pattern = r"([<>]=?)(\d{4}-\d{2}-\d{2})"
        match = re.match(pattern, date_str)
        if not match:
            return None

        operator, date = match.groups()
        parsed_date = datetime.strptime(date, "%Y-%m-%d")

        return {"operator": operator, "value": parsed_date.isoformat()}
    except Exception as e:
        logger.warning(f"Error parsing date value: {str(e)}")
        return None


def parse_metadata_value(metadata_str: str) -> Optional[Dict]:
    """Parse metadata filter (e.g., 'resolution:1080p')"""
    try:
        key, value = metadata_str.split(":")
        return {"key": key, "value": value}
    except Exception as e:
        logger.warning(f"Error parsing metadata value: {str(e)}")
        return None


def parse_search_query(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parse search query to extract filters and clean search term
    Returns tuple of (clean_query, filters)
    """
    filters = {}
    clean_query = query

    # Extract special keywords
    for keyword, pattern in KEYWORDS.items():
        matches = re.finditer(pattern, query)
        keyword_values = []

        for match in matches:
            value = match.group(1)

            # Process value based on keyword type
            if keyword == "asset_size_gte":
                parsed_value = parse_size_value(value)
            elif keyword == "asset_size_lte":
                parsed_value = parse_size_value(value)
            elif keyword == "ingested_date_gte":
                parsed_value = parse_date_value(value)
            elif keyword == "ingested_date_lte":
                parsed_value = parse_date_value(value)
            elif keyword == "extension":
                parsed_value = parse_metadata_value(value)
            elif keyword == "type":
                parsed_value = parse_metadata_value(value)
            else:
                parsed_value = value

            if parsed_value:
                keyword_values.append(parsed_value)
                # Remove the keyword:value from the clean query
                clean_query = clean_query.replace(match.group(0), "").strip()

        if keyword_values:
            filters[keyword] = keyword_values

    # Clean up extra spaces
    clean_query = " ".join(clean_query.split())

    return clean_query, filters


def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            if obj % 1 > 0:
                return float(obj)
            else:
                return int(obj)

        if isinstance(obj, uuid.UUID):
            return str(obj)

        if callable(obj):  # Check if the object is a function
            return None  # Ignore function objects

        return super(CustomEncoder, self).default(obj)


def generate_presigned_url(
    bucket: str, key: str, expiration: int = 3600
) -> Optional[str]:
    """
    Generate a presigned URL for an S3 object with region-aware client.
    The URL is signed in the bucket's own region, preventing
    SignatureDoesNotMatch errors outside us-east-1.
    """
    try:
        # Use region-aware S3 client
        s3_client = _get_s3_client_for_bucket(bucket)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expiration,
        )

        logger.debug(
            "Generated presigned URL for s3://%s/%s (region %s)",
            bucket,
            key,
            s3_client.meta.region_name,
        )

        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None


def generate_presigned_urls_batch(
    url_requests: List[Dict[str, str]], expiration: int = 3600
) -> Dict[str, Optional[str]]:
    """
    Generate multiple presigned URLs in parallel for better performance.

    Args:
        url_requests: List of dicts with 'bucket', 'key', and 'request_id' keys
        expiration: URL expiration time in seconds

    Returns:
        Dict mapping request_id to presigned URL (or None if failed)
    """
    import concurrent.futures
    import time

    start_time = time.time()
    logger.info(
        f"[PERF] Starting batch presigned URL generation for {len(url_requests)} URLs"
    )

    def generate_single_url(request):
        try:
            return {
                "request_id": request["request_id"],
                "url": generate_presigned_url(
                    request["bucket"], request["key"], expiration
                ),
            }
        except Exception as e:
            logger.warning(
                f"Failed to generate presigned URL for {request['request_id']}: {str(e)}"
            )
            return {"request_id": request["request_id"], "url": None}

    results = {}

    # Use ThreadPoolExecutor for I/O-bound operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_request = {
            executor.submit(generate_single_url, request): request
            for request in url_requests
        }

        for future in concurrent.futures.as_completed(future_to_request):
            try:
                result = future.result()
                results[result["request_id"]] = result["url"]
            except Exception as e:
                request = future_to_request[future]
                logger.warning(
                    f"Exception generating presigned URL for {request['request_id']}: {str(e)}"
                )
                results[request["request_id"]] = None

    batch_time = time.time() - start_time
    logger.info(f"[PERF] Batch presigned URL generation completed in {batch_time:.3f}s")

    return results


def normalize_distance(dist: float) -> float:
    """
    Convert a raw embedding distance into a similarity on (0, 1],
    monotonically decreasing as distance ↑.
    """
    return 1.0 / (1.0 + dist)
