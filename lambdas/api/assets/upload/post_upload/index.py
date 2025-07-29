import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate
from botocore.config import Config
from pydantic import BaseModel, Field, validator

# Initialize AWS X-Ray, metrics, and logger
tracer = Tracer(service="upload-service")
metrics = Metrics(namespace="upload-service")
logger = Logger(service="upload-api", level=os.getenv("LOG_LEVEL", "WARNING"))

# Initialize DynamoDB and S3
dynamodb = boto3.resource("dynamodb")

# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}

# Define constants
DEFAULT_EXPIRATION = 3600  # 1 hour in seconds
ALLOWED_CONTENT_TYPES = [
    "audio/*",
    "video/*",
    "application/x-mpegURL",  # HLS
    "application/dash+xml",  # MPEG-DASH
]
FILENAME_REGEX = r"^[a-zA-Z0-9!\-_.*'()]+$"  # S3-compatible filename regex

# Schema for request validation
request_schema = {
    "type": "object",
    "properties": {
        "connector_id": {"type": "string"},
        "filename": {"type": "string", "pattern": FILENAME_REGEX},
        "content_type": {"type": "string"},
        "file_size": {"type": "integer", "minimum": 1},
        "path": {"type": "string", "default": ""},
    },
    "required": ["connector_id", "filename", "content_type", "file_size"],
}


class RequestBody(BaseModel):
    connector_id: str
    filename: str
    content_type: str
    file_size: int = Field(gt=0)
    path: str = ""

    @validator("filename")
    @classmethod
    def validate_filename(cls, v):
        if not re.match(FILENAME_REGEX, v):
            raise ValueError(f"Filename must match pattern: {FILENAME_REGEX}")
        return v

    @validator("content_type")
    @classmethod
    def validate_content_type(cls, v):
        # Check if content type matches any of the allowed patterns
        for allowed_type in ALLOWED_CONTENT_TYPES:
            if allowed_type.endswith("*"):
                prefix = allowed_type[:-1]
                if v.startswith(prefix):
                    return v
            elif v == allowed_type:
                return v
        raise ValueError(
            f"Content type not allowed. Must be one of: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    @validator("path")
    @classmethod
    def validate_path(cls, v):
        # Normalize path to prevent path traversal attacks
        normalized_path = os.path.normpath(v)
        if normalized_path.startswith("..") or "//" in normalized_path:
            raise ValueError("Invalid path - potential path traversal attempt")

        # Strip leading slashes to avoid absolute paths
        normalized_path = normalized_path.lstrip("/")
        return normalized_path


class APIError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


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


@tracer.capture_method
def get_connector_details(connector_id: str) -> Dict[str, Any]:
    """Retrieve connector details from DynamoDB."""
    try:
        connector_table = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not connector_table:
            raise APIError(
                "MEDIALAKE_CONNECTOR_TABLE environment variable is not set", 500
            )

        table = dynamodb.Table(connector_table)
        response = table.get_item(Key={"id": connector_id})

        if "Item" not in response:
            raise APIError(f"Connector not found with ID: {connector_id}", 404)

        return response["Item"]
    except Exception as e:
        logger.error(f"Error retrieving connector details: {str(e)}")
        raise APIError(f"Error retrieving connector details: {str(e)}", 500)


@tracer.capture_method
def is_multipart_upload_required(file_size: int) -> bool:
    """Determine if multipart upload is required based on file size."""
    # 100MB threshold for multipart upload
    return file_size > 100 * 1024 * 1024


@tracer.capture_method
def generate_presigned_post_url(
    bucket: str, key: str, content_type: str, expiration: int = DEFAULT_EXPIRATION
) -> Dict[str, Any]:
    """Generate a presigned POST URL for the S3 object using region-aware S3 client."""
    try:
        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        conditions = [
            {"bucket": bucket},
            {"key": key},
            ["content-length-range", 1, 10 * 1024 * 1024 * 1024],  # 1 byte to 10GB
            {"Content-Type": content_type},
        ]

        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={
                "Content-Type": content_type,
            },
            Conditions=conditions,
            ExpiresIn=expiration,
        )

        logger.info(
            f"Generated presigned POST URL for s3://{bucket}/{key} (region {s3_client.meta.region_name}) valid {expiration}s"
        )

        return presigned_post
    except Exception as e:
        logger.error(f"Error generating presigned POST URL: {str(e)}")
        raise APIError(f"Error generating presigned POST URL: {str(e)}", 500)


@tracer.capture_method
def create_multipart_upload(bucket: str, key: str, content_type: str) -> Dict[str, Any]:
    """Initiate a multipart upload and return the upload ID using region-aware S3 client."""
    try:
        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        response = s3_client.create_multipart_upload(
            Bucket=bucket,
            Key=key,
            ContentType=content_type,
        )
        return {"upload_id": response["UploadId"]}
    except Exception as e:
        logger.error(f"Error creating multipart upload: {str(e)}")
        raise APIError(f"Error creating multipart upload: {str(e)}", 500)


@tracer.capture_method
def get_presigned_urls_for_parts(
    bucket: str,
    key: str,
    upload_id: str,
    parts: int,
    expiration: int = DEFAULT_EXPIRATION,
) -> List[Dict[str, Any]]:
    """Generate presigned URLs for each part of a multipart upload using region-aware S3 client."""
    try:
        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        presigned_urls = []

        for part_number in range(1, parts + 1):
            url = s3_client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=expiration,
            )
            presigned_urls.append({"part_number": part_number, "presigned_url": url})

        return presigned_urls
    except Exception as e:
        logger.error(f"Error generating presigned URLs for parts: {str(e)}")
        raise APIError(f"Error generating presigned URLs for parts: {str(e)}", 500)


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    try:
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        validate(event=body, schema=request_schema)
        request = RequestBody(**body)

        # Get connector details
        connector = get_connector_details(request.connector_id)

        # Extract S3 bucket information
        bucket = connector.get("storageIdentifier")
        if not bucket:
            raise APIError("Invalid connector configuration: missing bucket", 400)

        # Ensure the path is safe
        safe_path = request.path.strip("/")

        # Construct the object key
        object_prefix = connector.get("objectPrefix", "")
        if object_prefix:
            object_prefix = object_prefix.strip("/")
            key = (
                f"{object_prefix}/{safe_path}/{request.filename}"
                if safe_path
                else f"{object_prefix}/{request.filename}"
            )
        else:
            key = f"{safe_path}/{request.filename}" if safe_path else request.filename

        # Normalize the key to prevent any issues
        key = str(Path(key))

        # Handle multipart upload if file is larger than 100MB
        if is_multipart_upload_required(request.file_size):
            # For multipart uploads, we need to:
            # 1. Create a multipart upload
            # 2. Generate presigned URLs for each part
            multipart_upload_info = create_multipart_upload(
                bucket, key, request.content_type
            )
            upload_id = multipart_upload_info["upload_id"]

            # Calculate number of parts based on file size (5MB per part)
            part_size = 5 * 1024 * 1024  # 5MB
            total_parts = (
                request.file_size + part_size - 1
            ) // part_size  # Ceiling division
            total_parts = min(total_parts, 10000)  # S3 supports up to 10,000 parts

            # Get presigned URLs for all parts
            presigned_urls = get_presigned_urls_for_parts(
                bucket, key, upload_id, total_parts
            )

            metrics.add_metric(name="MultipartUploadCreated", value=1, unit="Count")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "success",
                        "message": "Multipart upload initiated successfully",
                        "data": {
                            "bucket": bucket,
                            "key": key,
                            "upload_id": upload_id,
                            "part_urls": presigned_urls,
                            "expires_in": DEFAULT_EXPIRATION,
                            "multipart": True,
                            "part_size": part_size,
                            "total_parts": total_parts,
                        },
                    }
                ),
            }
        else:
            # For single-part uploads, generate a presigned POST URL
            presigned_post = generate_presigned_post_url(
                bucket, key, request.content_type
            )

            metrics.add_metric(name="PresignedPostUrlGenerated", value=1, unit="Count")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "success",
                        "message": "Presigned POST URL generated successfully",
                        "data": {
                            "bucket": bucket,
                            "key": key,
                            "presigned_post": presigned_post,
                            "expires_in": DEFAULT_EXPIRATION,
                            "multipart": False,
                        },
                    }
                ),
            }

    except APIError as e:
        logger.warning(f"API Error: {str(e)}")
        metrics.add_metric(
            name="UploadUrlGenerationClientErrors", value=1, unit="Count"
        )
        return {
            "statusCode": e.status_code,
            "body": json.dumps({"status": "error", "message": str(e)}),
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        metrics.add_metric(
            name="UploadUrlGenerationServerErrors", value=1, unit="Count"
        )
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}",
                }
            ),
        }
