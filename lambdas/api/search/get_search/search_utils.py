import json
import uuid
import decimal
import re
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import boto3
from botocore.config import Config
from aws_lambda_powertools import Logger

logger = Logger()

# Signature style & virtual-host addressing are required for every region
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: dict[str, boto3.client] = {}       # {region → client}

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
        region = (generic.get_bucket_location(Bucket=bucket)
                        .get("LocationConstraint") or "us-east-1")
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
    'type': r'type:(\w+)',
    'format': r'format:(\w+)',
    'size': r'size:([<>]=?\d+(?:\.\d+)?(?:B|KB|MB|GB|TB))',
    'date': r'date:([<>]=?\d{4}-\d{2}-\d{2})',
    'metadata': r'metadata:(\w+:\w+)',
    'storageIdentifier': r'storageIdentifier:([a-zA-Z0-9._\-*/]+)',
    'extension': r'extension:([a-zA-Z0-9]+)',
    'filename': r'filename:([a-zA-Z0-9._\-]+)'
}

def parse_size_value(size_str: str) -> Optional[Dict[str, Any]]:
    """Convert size string (e.g., '1GB', '500MB', '1024B') to bytes"""
    try:
        pattern = r'([<>]=?)(\d+(?:\.\d+)?)(B|KB|MB|GB|TB)'
        match = re.match(pattern, size_str)
        if not match:
            return None
            
        operator, value, unit = match.groups()
        value = float(value)
        
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4
        }
        
        bytes_value = int(value * multipliers[unit])
        return {
            'operator': operator,
            'value': bytes_value
        }
    except Exception as e:
        logger.warning(f"Error parsing size value: {str(e)}")
        return None

def parse_date_value(date_str: str) -> Optional[Dict]:
    """Parse date string with operator (e.g., '>2024-01-01')"""
    try:
        pattern = r'([<>]=?)(\d{4}-\d{2}-\d{2})'
        match = re.match(pattern, date_str)
        if not match:
            return None
            
        operator, date = match.groups()
        parsed_date = datetime.strptime(date, '%Y-%m-%d')
        
        return {
            'operator': operator,
            'value': parsed_date.isoformat()
        }
    except Exception as e:
        logger.warning(f"Error parsing date value: {str(e)}")
        return None

def parse_metadata_value(metadata_str: str) -> Optional[Dict]:
    """Parse metadata filter (e.g., 'resolution:1080p')"""
    try:
        key, value = metadata_str.split(':')
        return {
            'key': key,
            'value': value
        }
    except Exception as e:
        logger.warning(f"Error parsing metadata value: {str(e)}")
        return None

def parse_extension_value(extension_str: str) -> Optional[str]:
    """Parse file extension (e.g., 'jpg', 'mp4')"""
    try:
        # Simple validation to ensure it's a valid extension
        if re.match(r'^[a-zA-Z0-9]+$', extension_str):
            return extension_str.lower()
        return None
    except Exception as e:
        logger.warning(f"Error parsing extension value: {str(e)}")
        return None

def parse_filename_value(filename_str: str) -> Optional[str]:
    """Parse filename search term"""
    try:
        # Basic validation for filename
        if re.match(r'^[a-zA-Z0-9._\-]+$', filename_str):
            return filename_str
        return None
    except Exception as e:
        logger.warning(f"Error parsing filename value: {str(e)}")
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
            if keyword == 'size':
                parsed_value = parse_size_value(value)
            elif keyword == 'date':
                parsed_value = parse_date_value(value)
            elif keyword == 'metadata':
                parsed_value = parse_metadata_value(value)
            elif keyword == 'extension':
                parsed_value = parse_extension_value(value)
            elif keyword == 'filename':
                parsed_value = parse_filename_value(value)
            else:
                parsed_value = value
                
            if parsed_value:
                keyword_values.append(parsed_value)
                # Remove the keyword:value from the clean query
                clean_query = clean_query.replace(match.group(0), '').strip()
        
        if keyword_values:
            filters[keyword] = keyword_values

    # Clean up extra spaces
    clean_query = ' '.join(clean_query.split())
    
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
        
        logger.info(
            "Generated presigned URL for s3://%s/%s (region %s)",
            bucket, key, s3_client.meta.region_name,
        )
        
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None
