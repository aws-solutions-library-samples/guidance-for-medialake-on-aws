"""
Lambda handler for signing individual multipart upload parts on-demand.

This Lambda function signs a single part of a multipart upload by:
1. Validating the request
2. Getting connector details from DynamoDB
3. Generating a presigned URL for the specific part
4. Returning the presigned URL

This on-demand approach eliminates the need to pre-generate thousands of URLs
and avoids the S3 limit of 10,000 parts by only generating URLs as needed.
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from pydantic import BaseModel, Field

# Initialize AWS Lambda Powertools
tracer = Tracer(service="upload-multipart-sign-service")
metrics = Metrics(namespace="upload-service")
logger = Logger(
    service="upload-multipart-sign-api", level=os.getenv("LOG_LEVEL", "WARNING")
)

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")

# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
    connect_timeout=5,
    read_timeout=30,  # Timeout for signing part URLs
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}

# Define constants
DEFAULT_EXPIRATION = 3600  # 1 hour in seconds


# Request validation model
class SignPartRequest(BaseModel):
    """Request model for signing a multipart upload part."""

    connector_id: str
    upload_id: str
    key: str
    part_number: int = Field(ge=1, le=10000)


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
    Lambda handler for signing individual multipart upload parts.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response with presigned URL
    """
    body = {}
    try:
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        request = SignPartRequest(**body)

        logger.append_keys(
            connector_id=request.connector_id,
            upload_id=request.upload_id,
            key=request.key,
            part_number=request.part_number,
        )

        logger.info(
            f"Signing part - connector_id: {request.connector_id}, "
            f"upload_id: {request.upload_id}, key: {request.key}, part: {request.part_number}"
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
            f"Generating presigned URL for part - bucket: {bucket}, key: {request.key}, "
            f"upload_id: {request.upload_id}, part: {request.part_number}, "
            f"region: {s3_client.meta.region_name}"
        )

        # Generate presigned URL for the part
        presigned_url = s3_client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": bucket,
                "Key": request.key,
                "UploadId": request.upload_id,
                "PartNumber": request.part_number,
            },
            ExpiresIn=DEFAULT_EXPIRATION,
        )

        logger.info(
            f"Presigned URL generated for part {request.part_number} - "
            f"expires_in: {DEFAULT_EXPIRATION}s"
        )

        # Add success metrics
        metrics.add_metric(name="MultipartPartSigned", value=1, unit="Count")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "Part signed successfully",
                    "data": {
                        "part_number": request.part_number,
                        "presigned_url": presigned_url,
                        "expires_in": DEFAULT_EXPIRATION,
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
                "part_number": body.get("part_number", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartPartSignTimeoutErrors", value=1, unit="Count")

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
            f"Client error signing part - error: {error_msg}",
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
                "part_number": body.get("part_number", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartPartSignErrors", value=1, unit="Count")

        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to sign part: {error_msg}",
                }
            ),
        }

    except Exception as e:
        # Server errors (500)
        error_msg = str(e)
        logger.error(
            f"Unexpected error signing part - error: {error_msg}",
            exc_info=True,
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
                "part_number": body.get("part_number", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartPartSignErrors", value=1, unit="Count")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {error_msg}",
                }
            ),
        }
