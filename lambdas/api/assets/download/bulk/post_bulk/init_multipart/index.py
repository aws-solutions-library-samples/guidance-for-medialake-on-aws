"""
Bulk Download Initialize Multipart Upload Lambda

This Lambda function initializes a multipart upload for a zip file by:
1. Creating a multipart upload in S3
2. Calculating the part sizes based on the file size
3. Creating a manifest of parts to be uploaded
4. Returning the upload ID and manifest key

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
- Metrics and monitoring
"""

import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-init-multipart")
tracer = Tracer(service="bulk-download-init-multipart")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-init-multipart"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
# Configure S3 client with Signature Version 4 for KMS encryption support
s3 = boto3.client("s3", config=Config(signature_version="s3v4"))

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB table
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs

# Constants
PART_SIZE_MB = 25  # 25 MB per part
PART_SIZE = PART_SIZE_MB * 1024 * 1024  # Convert to bytes
FINAL_ZIP_PREFIX = "temp/zip/final"
MULTIPART_WORKING_PREFIX = "temp/zip/multipart"


@tracer.capture_method
def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.

    Args:
        file_path: Path to the file

    Returns:
        Size of the file in bytes
    """
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        logger.error(
            "Failed to get file size",
            extra={
                "error": str(e),
                "filePath": file_path,
            },
        )
        raise


@tracer.capture_method
def calculate_parts(file_size: int, part_size: int) -> List[Dict[str, Any]]:
    """
    Calculate the parts for a multipart upload.

    Args:
        file_size: Size of the file in bytes
        part_size: Size of each part in bytes

    Returns:
        List of parts with part number, start byte, and end byte
    """
    num_parts = math.ceil(file_size / part_size)
    parts = []

    for i in range(num_parts):
        part_number = i + 1  # Part numbers start at 1
        start_byte = i * part_size
        end_byte = min((i + 1) * part_size - 1, file_size - 1)

        parts.append(
            {
                "partNumber": part_number,
                "startByte": start_byte,
                "endByte": end_byte,
                "size": end_byte - start_byte + 1,
            }
        )

    return parts


@tracer.capture_method
def create_multipart_upload(s3_key: str) -> str:
    """
    Create a multipart upload in S3.

    Args:
        s3_key: S3 key for the file

    Returns:
        Upload ID for the multipart upload
    """
    try:
        response = s3.create_multipart_upload(
            Bucket=MEDIA_ASSETS_BUCKET,
            Key=s3_key,
            ContentType="application/zip",
            ContentDisposition=f'attachment; filename="{os.path.basename(s3_key)}"',
        )

        upload_id = response["UploadId"]

        logger.info(
            "Created multipart upload",
            extra={
                "s3Key": s3_key,
                "uploadId": upload_id,
            },
        )

        return upload_id

    except Exception as e:
        logger.error(
            "Failed to create multipart upload",
            extra={
                "error": str(e),
                "s3Key": s3_key,
            },
        )
        raise


@tracer.capture_method
def create_parts_manifest(
    job_id: str, parts: List[Dict[str, Any]], local_path: str
) -> str:
    """
    Create a manifest of parts to be uploaded.

    Args:
        job_id: Job ID
        parts: List of parts
        local_path: Local path to the file

    Returns:
        S3 key of the manifest file
    """
    try:
        # Add local path to each part
        for part in parts:
            part["localPath"] = local_path

        # Create the manifest file
        manifest_key = f"{MULTIPART_WORKING_PREFIX}/{job_id}/parts_manifest.json"

        # Upload the manifest to S3
        s3.put_object(
            Bucket=MEDIA_ASSETS_BUCKET,
            Key=manifest_key,
            Body=json.dumps(parts),
            ContentType="application/json",
        )

        logger.info(
            "Created parts manifest",
            extra={
                "jobId": job_id,
                "manifestKey": manifest_key,
                "numParts": len(parts),
            },
        )

        return manifest_key

    except Exception as e:
        logger.error(
            "Failed to create parts manifest",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise


@tracer.capture_method
def update_job_multipart_info(
    user_id: str,
    job_id: str,
    upload_id: str,
    s3_key: str,
    manifest_key: str,
    num_parts: int,
    part_size: int,
    file_size: int,
) -> None:
    """
    Update the job record with multipart upload information.

    Args:
        user_id: ID of the user who owns the job
        job_id: Job ID
        upload_id: Upload ID
        s3_key: S3 key
        manifest_key: Manifest key
        num_parts: Number of parts
        part_size: Size of each part in bytes
        file_size: Size of the file in bytes
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        # First, get the existing job record to find the correct itemKey
        response = user_table.query(
            IndexName="GSI2",
            KeyConditionExpression="gsi2Pk = :jobId",
            ExpressionAttributeValues={":jobId": f"JOB#{job_id}"},
            ConsistentRead=False,
        )

        if not response.get("Items"):
            logger.error(f"Job {job_id} not found for multipart init")
            raise Exception(f"Job {job_id} not found")

        # Find the job that belongs to this user
        job_item = None
        for item in response["Items"]:
            if item.get("userId") == formatted_user_id:
                job_item = item
                break

        if not job_item:
            logger.error(f"Job {job_id} not found for user {user_id}")
            raise Exception(f"Job {job_id} not found for user")

        item_key = job_item.get("itemKey")
        if not item_key:
            logger.error(f"No itemKey found for job {job_id}")
            raise Exception(f"No itemKey found for job {job_id}")

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=(
                "SET #multipartInfo = :multipartInfo, "
                "#status = :status, "
                "#progress = :progress, "
                "#completedParts = :completedParts, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#multipartInfo": "multipartInfo",
                "#status": "status",
                "#progress": "progress",
                "#completedParts": "completedParts",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":multipartInfo": {
                    "uploadId": upload_id,
                    "s3Key": s3_key,
                    "manifestKey": manifest_key,
                    "numParts": num_parts,
                    "partSize": part_size,
                    "fileSize": file_size,
                },
                ":status": "STAGING",
                ":progress": 50,  # 50% progress after initializing multipart upload
                ":completedParts": 0,  # Initialize completed parts counter
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Updated job with multipart info",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "uploadId": upload_id,
                "s3Key": s3_key,
                "manifestKey": manifest_key,
                "numParts": num_parts,
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job with multipart info",
            extra={
                "error": str(e),
                "userId": user_id,
                "jobId": job_id,
                "uploadId": upload_id,
            },
        )
        raise Exception(f"Failed to update job with multipart info: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for initializing a multipart upload.

    Args:
        event: Event containing job details
        context: Lambda context

    Returns:
        Dictionary containing multipart upload information
    """
    try:
        # Extract parameters from the event
        job_id = event.get("jobId")
        user_id = event.get("userId")
        zip_path = event.get("zipPath")

        if not job_id or not user_id or not zip_path:
            raise ValueError("Missing required parameters in event")

        # Get the file size
        file_size = get_file_size(zip_path)

        # Calculate the parts
        parts = calculate_parts(file_size, PART_SIZE)

        # Create a multipart upload in S3
        s3_key = f"{FINAL_ZIP_PREFIX}/{job_id}/{os.path.basename(zip_path)}"
        upload_id = create_multipart_upload(s3_key)

        # Create a manifest of parts to be uploaded
        manifest_key = create_parts_manifest(job_id, parts, zip_path)

        # Update the job record with multipart upload information
        update_job_multipart_info(
            user_id,
            job_id,
            upload_id,
            s3_key,
            manifest_key,
            len(parts),
            PART_SIZE,
            file_size,
        )

        # Add metrics
        metrics.add_metric(
            name="MultipartUploadsInitialized", unit=MetricUnit.Count, value=1
        )

        return {
            "jobId": job_id,
            "userId": user_id,
            "uploadId": upload_id,
            "s3Key": s3_key,
            "manifestKey": manifest_key,
            "numParts": len(parts),
            "partSize": PART_SIZE,
            "fileSize": file_size,
        }

    except Exception as e:
        logger.error(
            f"Error initializing multipart upload: {str(e)}",
            exc_info=True,
        )

        # Add metrics
        metrics.add_metric(
            name="MultipartUploadInitializationErrors", unit=MetricUnit.Count, value=1
        )

        # Re-raise the exception to be handled by Step Functions
        raise
