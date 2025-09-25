import decimal
import json
import uuid
from typing import Any, Optional

import boto3
from aws_lambda_powertools import Logger
from botocore.config import Config

logger = Logger(service="asset-details-service-utils")
s3_client = boto3.client("s3", config=Config(signature_version="s3v4"))


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
    """Generate a presigned URL for an S3 object"""
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expiration,
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
