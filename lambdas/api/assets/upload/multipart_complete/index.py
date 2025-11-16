"""
Lambda handler for completing multipart uploads.

This Lambda function completes a multipart upload by:
1. Validating the request
2. Getting connector details from DynamoDB
3. Completing the multipart upload in S3
4. Returning success response with file location
"""

import json
import os
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from pydantic import BaseModel, Field, validator

# Initialize AWS Lambda Powertools
tracer = Tracer(service="upload-multipart-complete-service")
metrics = Metrics(namespace="upload-service")
logger = Logger(
    service="upload-multipart-complete-api", level=os.getenv("LOG_LEVEL", "WARNING")
)

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")

# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
    connect_timeout=5,
    read_timeout=60,  # Longer timeout for completing multipart uploads
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}


# Request validation models
class Part(BaseModel):
    """Model for a completed part."""

    PartNumber: int = Field(alias="PartNumber", ge=1, le=10000)
    ETag: str = Field(alias="ETag")

    class Config:
        populate_by_name = True


class CompleteMultipartRequest(BaseModel):
    """Request model for completing multipart upload."""

    connector_id: str
    upload_id: str
    key: str
    parts: List[Part]

    @validator("parts")
    @classmethod
    def validate_parts(cls, v):
        if not v:
            raise ValueError("Parts array cannot be empty")
        if len(v) > 10000:
            raise ValueError("Parts array cannot exceed 10,000 parts")
        return v


def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client pinned to the bucket's actual region.
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
            raise ValueError(
                "MEDIALAKE_CONNECTOR_TABLE environment variable is not set"
            )

        table = dynamodb.Table(connector_table)
        response = table.get_item(Key={"id": connector_id})

        if "Item" not in response:
            raise ValueError(f"Connector not found with ID: {connector_id}")

        return response["Item"]
    except Exception as e:
        logger.error(f"Error retrieving connector details: {str(e)}")
        raise


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler for completing multipart uploads.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    body = {}
    try:
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        request = CompleteMultipartRequest(**body)

        logger.append_keys(
            connector_id=request.connector_id,
            upload_id=request.upload_id,
            key=request.key,
            parts_count=len(request.parts),
        )

        logger.info(
            f"Starting multipart upload completion - connector_id: {request.connector_id}, "
            f"upload_id: {request.upload_id}, key: {request.key}, parts: {len(request.parts)}"
        )

        # Get connector details
        connector = get_connector_details(request.connector_id)

        # Extract S3 bucket information
        bucket = connector.get("storageIdentifier")
        if not bucket:
            raise ValueError("Invalid connector configuration: missing bucket")

        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        logger.info(
            f"Completing multipart upload - bucket: {bucket}, key: {request.key}, "
            f"upload_id: {request.upload_id}, region: {s3_client.meta.region_name}"
        )

        # Complete the multipart upload
        response = s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=request.key,
            UploadId=request.upload_id,
            MultipartUpload={
                "Parts": [part.dict(by_alias=True) for part in request.parts]
            },
        )

        location = f"s3://{bucket}/{request.key}"

        logger.info(
            f"Multipart upload completed successfully - location: {location}, "
            f"etag: {response.get('ETag', 'N/A')}"
        )

        # Add success metrics
        metrics.add_metric(name="MultipartUploadCompleted", value=1, unit="Count")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "Multipart upload completed",
                    "data": {
                        "location": location,
                        "bucket": bucket,
                        "key": request.key,
                    },
                }
            ),
        }

    except (ReadTimeoutError, ConnectTimeoutError) as e:
        # Timeout errors
        error_msg = str(e)
        logger.error(
            f"AWS service call timed out - error: {error_msg}",
            exc_info=True,
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
            },
        )

        metrics.add_metric(
            name="MultipartUploadCompletionTimeoutErrors", value=1, unit="Count"
        )

        return {
            "statusCode": 504,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": "AWS service call timed out. Please try again.",
                }
            ),
        }

    except (ValueError, ClientError) as e:
        # Client errors (400)
        error_msg = str(e)
        logger.warning(
            f"Client error completing multipart upload - error: {error_msg}",
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
            },
        )

        metrics.add_metric(
            name="MultipartUploadCompletionErrors", value=1, unit="Count"
        )

        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to complete multipart upload: {error_msg}",
                }
            ),
        }

    except Exception as e:
        # Server errors (500)
        error_msg = str(e)
        logger.error(
            f"Unexpected error completing multipart upload - error: {error_msg}",
            exc_info=True,
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
            },
        )

        metrics.add_metric(
            name="MultipartUploadCompletionErrors", value=1, unit="Count"
        )

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {error_msg}",
                }
            ),
        }
