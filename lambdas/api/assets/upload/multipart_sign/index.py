"""
Lambda handler that presigns the S3 requests of an in-flight multipart upload.

The browser (Uppy 6, @uppy/aws-s3 in signRequest mode) drives the multipart upload itself
and asks this endpoint for one presigned URL per S3 request:

- ``part``      → UploadPart                (PUT,    needs ``part_number``)
- ``list``      → ListParts                 (GET;    used to resume after a page refresh)
- ``complete``  → CompleteMultipartUpload   (POST;   the browser sends the parts XML)
- ``abort``     → AbortMultipartUpload      (DELETE)

Signing on demand, one URL per request, keeps the number of live URLs bounded and lets a
500 GB upload with thousands of parts run for hours without a batch of URLs expiring. The
server never sees the parts list or the completion — S3's ObjectCreated event is what tells
the ingest pipeline that the object landed.

Only ``host`` is a signed header on these URLs, which matches what the browser sends: no
custom headers on UploadPart/ListParts/Abort, and an unsigned ``Content-Type: application/xml``
on Complete.
"""

import json
import os
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from pydantic import BaseModel, Field, ValidationError, model_validator

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
# 6 hours — large files (500GB) can take many hours; parts are signed on-demand
# but may still queue behind other concurrent uploads before being PUT to S3.
DEFAULT_EXPIRATION = 21600

OPERATION_PART = "part"
OPERATION_LIST = "list"
OPERATION_COMPLETE = "complete"
OPERATION_ABORT = "abort"
OPERATIONS = (OPERATION_PART, OPERATION_LIST, OPERATION_COMPLETE, OPERATION_ABORT)

# boto3 client method and HTTP verb for each operation. The verb is returned so the caller
# can assert it matches the request it is about to make.
_OPERATION_SPEC = {
    OPERATION_PART: ("upload_part", "PUT"),
    OPERATION_LIST: ("list_parts", "GET"),
    OPERATION_COMPLETE: ("complete_multipart_upload", "POST"),
    OPERATION_ABORT: ("abort_multipart_upload", "DELETE"),
}

# Objects under this prefix belong to one user each; see _enforce_personal_prefix.
PERSONAL_PREFIX = "personal/"


# Request validation model
class SignPartRequest(BaseModel):
    """One S3 request of a multipart upload to presign."""

    connector_id: str
    upload_id: str
    key: str
    # Defaults to ``part`` so the previous request shape keeps working unchanged.
    operation: str = OPERATION_PART
    part_number: Optional[int] = Field(default=None, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation not in OPERATIONS:
            raise ValueError(
                f"operation must be one of {', '.join(OPERATIONS)}; "
                f"got {self.operation!r}"
            )
        if self.operation == OPERATION_PART and self.part_number is None:
            raise ValueError("part_number is required for the part operation")
        return self


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


def get_user_sub_from_event(event: Dict) -> Optional[str]:
    """The caller's Cognito ``sub`` from the authorizer context, or None."""
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        if not isinstance(authorizer, dict):
            return None
        sub = authorizer.get("sub")
        if sub:
            return sub
        claims = authorizer.get("claims")
        if isinstance(claims, str):
            try:
                claims = json.loads(claims)
            except (json.JSONDecodeError, ValueError):
                return None
        if isinstance(claims, dict):
            return claims.get("sub")
    except Exception:
        pass
    return None


class ForbiddenError(ValueError):
    """The caller may not act on this key."""


def _enforce_personal_prefix(event: Dict, key: str) -> None:
    """Keep users inside their own ``personal/{sub}/`` folder.

    POST /assets/upload already refuses to *create* an upload outside the caller's folder.
    This endpoint now also signs ListParts, Complete and Abort, so the same rule has to hold
    here or a caller who learned another user's key and upload id could complete or abort
    their upload. Keys outside ``personal/`` are governed by connector permissions, which the
    create call enforced.
    """
    if not key.startswith(PERSONAL_PREFIX):
        return
    sub = get_user_sub_from_event(event)
    if not sub or not key.startswith(f"{PERSONAL_PREFIX}{sub}/"):
        raise ForbiddenError("Access denied: key is outside your personal folder")


def presign_operation(
    s3_client,
    bucket: str,
    request: SignPartRequest,
    expiration: int = DEFAULT_EXPIRATION,
) -> str:
    """Presigned URL for the requested multipart operation."""
    client_method, _ = _OPERATION_SPEC[request.operation]
    params: Dict[str, Any] = {
        "Bucket": bucket,
        "Key": request.key,
        "UploadId": request.upload_id,
    }
    if request.operation == OPERATION_PART:
        params["PartNumber"] = request.part_number
    return s3_client.generate_presigned_url(
        client_method, Params=params, ExpiresIn=expiration
    )


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """Presign one S3 request of a multipart upload."""
    body = {}
    try:
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        request = SignPartRequest(**body)

        logger.append_keys(
            connector_id=request.connector_id,
            upload_id=request.upload_id,
            key=request.key,
            operation=request.operation,
            part_number=request.part_number,
        )

        logger.info(
            f"Signing {request.operation} - connector_id: {request.connector_id}, "
            f"upload_id: {request.upload_id}, key: {request.key}, "
            f"part: {request.part_number}"
        )

        _enforce_personal_prefix(event, request.key)

        # Get connector details
        connector = get_connector_details(request.connector_id)

        # Extract S3 bucket information
        bucket = connector.get("storageIdentifier")
        if not bucket:
            raise ValueError("Invalid connector configuration: missing bucket")

        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        presigned_url = presign_operation(s3_client, bucket, request)
        _, http_method = _OPERATION_SPEC[request.operation]

        logger.info(
            f"Presigned URL generated for {request.operation} - "
            f"expires_in: {DEFAULT_EXPIRATION}s"
        )

        metrics.add_metric(
            name=f"Multipart{request.operation.capitalize()}Signed",
            value=1,
            unit="Count",
        )

        data: Dict[str, Any] = {
            "operation": request.operation,
            "method": http_method,
            "presigned_url": presigned_url,
            "expires_in": DEFAULT_EXPIRATION,
        }
        if request.part_number is not None:
            data["part_number"] = request.part_number

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": f"{request.operation} signed successfully",
                    "data": data,
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
                "operation": body.get("operation", "unknown"),
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

    except ForbiddenError as e:
        logger.warning(
            f"Forbidden multipart sign - error: {e}",
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "key": body.get("key", "unknown"),
                "operation": body.get("operation", "unknown"),
            },
        )
        metrics.add_metric(name="MultipartSignForbidden", value=1, unit="Count")
        return {
            "statusCode": 403,
            "body": json.dumps({"status": "error", "message": str(e)}),
        }

    except ValidationError as e:
        # A body that fails the request model is a client error. Return only the validator
        # messages — pydantic's full string also carries the submitted values, the internal
        # error types and a docs URL, none of which belong in an API response.
        reasons = "; ".join(
            err.get("msg", "").removeprefix("Value error, ") for err in e.errors()
        )
        logger.warning(f"Invalid multipart sign request: {str(e)}")

        metrics.add_metric(name="MultipartPartSignErrors", value=1, unit="Count")

        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": (
                        f"Invalid request: {reasons}"
                        if reasons
                        else "Invalid request body."
                    ),
                }
            ),
        }

    except (ValueError, ClientError) as e:
        # Client errors (400)
        error_msg = str(e)
        logger.warning(
            f"Client error signing multipart request - error: {error_msg}",
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
                "operation": body.get("operation", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartPartSignErrors", value=1, unit="Count")

        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to sign multipart request: {error_msg}",
                }
            ),
        }

    except Exception as e:
        # Server errors (500)
        error_msg = str(e)
        logger.error(
            f"Unexpected error signing multipart request - error: {error_msg}",
            exc_info=True,
            extra={
                "connector_id": body.get("connector_id", "unknown"),
                "upload_id": body.get("upload_id", "unknown"),
                "key": body.get("key", "unknown"),
                "operation": body.get("operation", "unknown"),
            },
        )

        metrics.add_metric(name="MultipartPartSignErrors", value=1, unit="Count")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": "An unexpected error occurred while signing the upload request.",
                }
            ),
        }
