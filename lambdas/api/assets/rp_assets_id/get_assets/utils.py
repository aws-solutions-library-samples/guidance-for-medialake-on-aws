import json
import uuid
import decimal
from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger
import boto3
from botocore.config import Config

logger = Logger(service="asset-details-service-utils")

# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}


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


def replace_decimals(obj):
    """
    Recursively replace Decimal objects with int or float for JSON serialization.
    """
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
    """Generate a presigned URL for an S3 object using region-aware S3 client"""
    try:
        # Get region-specific S3 client
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
            f"Generated presigned URL for s3://{bucket}/{key} (region {s3_client.meta.region_name}) valid {expiration}s"
        )
        
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None


def replace_binary_data(data: Any) -> Any:
    """Recursively replace binary data with "BINARY DATA" text."""
    if isinstance(data, dict):
        return {k: replace_binary_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_binary_data(item) for item in data]
    elif isinstance(data, bytes):
        return "BINARY DATA"
    elif isinstance(data, boto3.dynamodb.types.Binary):
        return "BINARY DATA"
    elif isinstance(data, boto3.dynamodb.types.Decimal):
        return float(data)  # Convert Decimal to float for JSON serialization
    else:
        return data
