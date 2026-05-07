import json
from typing import Any, Dict

import boto3

# Initialize S3 client
s3_client = boto3.client("s3")


def load_pipeline_from_s3(bucket: str, key: str) -> Dict[str, Any]:
    """
    Load a pipeline definition from an S3 bucket.

    Args:
        bucket: The S3 bucket name
        key: The S3 object key

    Returns:
        The pipeline definition as a dictionary
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as e:
        raise Exception(f"Failed to load pipeline definition from S3: {str(e)}")
