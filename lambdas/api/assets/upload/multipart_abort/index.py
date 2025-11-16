"""
Lambda handler for aborting multipart uploads.

This Lambda function aborts a multipart upload by:
1. Validating the request
2. Getting connector details from DynamoDB
3. Aborting the multipart upload in S3
4. Returning success response

Note: S3 lifecycle policies (configured in base_infrastructure.py) automatically
clean up incomplete multipart uploads after 7 days, so abort failures are not critical.
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
from pydantic import BaseModel

# Initialize AWS Lambda Powertools
tracer = Tracer(service="upload-multipart-abort-service")
metrics = Metrics(namespace="upload-service")
logger = Logger(
    service="upload-multipart-abort-api", level=os.getenv("LOG_LEVEL", "WARNING")
)

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")

# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
    connect_timeout=5,
    read_timeout=30,  # Timeout for aborting multipart uploads
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}


# Request validation model
class AbortMultipartRequest(BaseModel):
    """Request model for aborting multipart upload."""

    connector_id: str
    upload_id: str
    key: str


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
    Lambda handler for aborting multipart uploads.

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
        request = AbortMultipartRequest(**body)

        logger.append_keys(
            connector_id=request.connector_id,
            upload_id=request.upload_id,
            key=request.key,
        )

        logger.info(
            f"Starting multipart upload abort - connector_id: {request.connector_id}, "
            f"upload_id: {request.upload_id}, key: {request.key}"
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
            f"Aborting multipart upload - bucket: {bucket}, key: {request.key}, "
            f"upload_id: {request.upload_id}, region: {s3_client.meta.region_name}"
        )

        try:
            # Abort the multipart upload
            s3_client.abort_multipart_upload(
                Bucket=bucket,
                Key=request.key,
                UploadId=request.upload_id,
            )

            logger.info(
                f"Multipart upload aborted successfully - bucket: {bucket}, "
                f"key: {request.key}, upload_id: {request.upload_id}"
            )

            # Add success metrics
            metrics.add_metric(name="MultipartUploadAborted", value=1, unit="Count")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "success",
                        "message": "Multipart upload aborted successfully",
                    }
                ),
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # NoSuchUpload means the upload was already aborted or completed
            if error_code == "NoSuchUpload":
                logger.warning(
                    f"Upload already aborted or completed - bucket: {bucket}, "
                    f"key: {request.key}, upload_id: {request.upload_id}"
                )

                metrics.add_metric(name="MultipartUploadAborted", value=1, unit="Count")

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "status": "success",
                            "message": "Multipart upload already aborted or completed",
                        }
                    ),
                }

            # Re-raise other ClientErrors
            raise

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
            name="MultipartUploadAbortTimeoutErrors", value=1, unit="Count"
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
            f"Client error aborting multipart upload - error: {error_msg}",
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartUploadAbortErrors", value=1, unit="Count")

        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to abort multipart upload: {error_msg}",
                }
            ),
        }

    except Exception as e:
        # Server errors (500)
        error_msg = str(e)
        logger.error(
            f"Unexpected error aborting multipart upload - error: {error_msg}",
            exc_info=True,
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartUploadAbortErrors", value=1, unit="Count")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {error_msg}",
                }
            ),
        }
