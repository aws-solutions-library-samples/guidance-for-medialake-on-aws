"""
Bulk Download Complete Multipart Upload Lambda

This Lambda function completes a multipart upload for a zip file by:
1. Retrieving the parts manifest from S3
2. Completing the multipart upload with the ETags of all parts
3. Generating a presigned URL for the completed file
4. Updating the job record with the download URL
5. Cleaning up temporary files and resources

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
- Metrics and monitoring
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-complete-multipart")
tracer = Tracer(service="bulk-download-complete-multipart")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-complete-multipart"
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
FINAL_ZIP_PREFIX = "temp/zip/final"
MULTIPART_WORKING_PREFIX = "temp/zip/multipart"
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds


@tracer.capture_method
def get_existing_job_item_key(job_id: str) -> str:
    """
    Get the existing itemKey for a job by querying GSI3.

    Args:
        job_id: The job ID to find

    Returns:
        The itemKey of the existing job record

    Raises:
        ValueError: If job is not found
    """
    try:
        response = user_table.query(
            IndexName="GSI3",
            KeyConditionExpression="gsi3Pk = :gsi3_pk",
            ExpressionAttributeValues={":gsi3_pk": f"JOB#{job_id}"},
            Limit=1,
        )

        if not response.get("Items"):
            raise ValueError(f"Job {job_id} not found")

        return response["Items"][0]["itemKey"]

    except Exception as e:
        logger.error(f"Failed to find existing job record: {str(e)}")
        raise


@tracer.capture_method
def get_job_details(user_id: str, job_id: str) -> Dict[str, Any]:
    """
    Retrieve job details from user table.

    Args:
        user_id: ID of the user who owns the job
        job_id: ID of the job to retrieve

    Returns:
        Job details

    Raises:
        Exception: If job retrieval fails
    """
    try:
        # Query user table for bulk download jobs
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        response = user_table.query(
            KeyConditionExpression="userId = :userId AND begins_with(itemKey, :prefix)",
            ExpressionAttributeValues={
                ":userId": formatted_user_id,
                ":prefix": f"BULK_DOWNLOAD#{job_id}#",
            },
            ConsistentRead=True,
            Limit=1,
        )

        if not response.get("Items"):
            raise Exception(f"Job {job_id} not found for user {user_id}")

        return response["Items"][0]

    except ClientError as e:
        logger.error(
            "Failed to retrieve job details",
            extra={
                "error": str(e),
                "userId": user_id,
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to retrieve job details: {str(e)}")


@tracer.capture_method
def get_parts_manifest(manifest_key: str) -> List[Dict[str, Any]]:
    """
    Retrieve the parts manifest from S3.

    Args:
        manifest_key: S3 key of the manifest file

    Returns:
        List of part details
    """
    try:
        response = s3.get_object(
            Bucket=MEDIA_ASSETS_BUCKET,
            Key=manifest_key,
        )

        manifest = json.loads(response["Body"].read().decode("utf-8"))

        return manifest

    except Exception as e:
        logger.error(
            "Failed to retrieve parts manifest",
            extra={
                "error": str(e),
                "manifestKey": manifest_key,
            },
        )
        raise


@tracer.capture_method
def get_completed_parts_from_s3(
    manifest_key: str, completed_parts_info: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Get the full list of completed parts from S3 manifest and merge with the ETags from completed_parts_info.

    Args:
        manifest_key: S3 key of the manifest file
        completed_parts_info: List of completed parts with ETags from Step Functions

    Returns:
        List of completed parts with ETags
    """
    try:
        # Get the full manifest from S3
        full_manifest = get_parts_manifest(manifest_key)

        # Create a dictionary of part numbers to ETags from the completed_parts_info
        etag_map = {}
        for part in completed_parts_info:
            if isinstance(part, dict) and "PartNumber" in part and "ETag" in part:
                etag_map[part["PartNumber"]] = part["ETag"]
            elif isinstance(part, dict) and "partNumber" in part and "ETag" in part:
                etag_map[part["partNumber"]] = part["ETag"]

        # Create the complete list of parts with ETags
        completed_parts = []
        for part in full_manifest:
            part_number = part.get("partNumber") or part.get("PartNumber")
            if part_number in etag_map:
                completed_parts.append(
                    {"PartNumber": part_number, "ETag": etag_map[part_number]}
                )
            else:
                logger.warning(
                    f"Missing ETag for part {part_number}",
                    extra={"manifestKey": manifest_key, "partNumber": part_number},
                )

        # Sort parts by part number
        completed_parts.sort(key=lambda x: x["PartNumber"])

        logger.info(
            f"Prepared {len(completed_parts)} parts for completion",
            extra={"manifestKey": manifest_key, "totalParts": len(full_manifest)},
        )

        return completed_parts

    except Exception as e:
        logger.error(
            "Failed to get completed parts from S3",
            extra={
                "error": str(e),
                "manifestKey": manifest_key,
            },
        )
        raise


@tracer.capture_method
def get_completed_parts(
    event: Dict[str, Any], manifest_key: str
) -> List[Dict[str, Any]]:
    """
    Retrieve the list of completed parts from the event and S3.

    Args:
        event: Event containing completed parts info
        manifest_key: S3 key of the manifest file

    Returns:
        List of completed parts with ETags
    """
    try:
        # Get the completed parts from the event
        completed_parts_info = event.get("completedParts", [])

        # If we have parts in the event, use them with the full manifest
        if completed_parts_info:
            # Get the full list of parts with ETags from S3 and the completed parts info
            return get_completed_parts_from_s3(manifest_key, completed_parts_info)
        else:
            logger.error(
                "No completed parts found in event", extra={"manifestKey": manifest_key}
            )
            raise ValueError("No completed parts found in event")

    except Exception as e:
        logger.error(
            "Failed to retrieve completed parts",
            extra={
                "error": str(e),
                "manifestKey": manifest_key,
            },
        )
        raise


@tracer.capture_method
def complete_multipart_upload(
    s3_key: str, upload_id: str, parts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Complete a multipart upload in S3.

    Args:
        s3_key: S3 key of the file
        upload_id: Multipart upload ID
        parts: List of completed parts with ETags

    Returns:
        S3 response
    """
    try:
        response = s3.complete_multipart_upload(
            Bucket=MEDIA_ASSETS_BUCKET,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

        logger.info(
            "Completed multipart upload",
            extra={
                "s3Key": s3_key,
                "uploadId": upload_id,
                "numParts": len(parts),
            },
        )

        return response

    except Exception as e:
        logger.error(
            "Failed to complete multipart upload",
            extra={
                "error": str(e),
                "s3Key": s3_key,
                "uploadId": upload_id,
            },
        )
        raise


@tracer.capture_method
def generate_presigned_url(bucket: str, key: str) -> str:
    """
    Generate a presigned URL for an S3 object.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Presigned URL
    """
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{os.path.basename(key)}"',
            },
            ExpiresIn=MAX_PRESIGNED_URL_EXPIRATION,
        )

        return url

    except Exception as e:
        logger.error(
            "Failed to generate presigned URL",
            extra={
                "error": str(e),
                "bucket": bucket,
                "key": key,
            },
        )
        raise


@tracer.capture_method
def update_job_completed(user_id: str, job_id: str, download_urls: List[str]) -> None:
    """
    Update the job record with download URLs and mark as completed.

    Args:
        user_id: ID of the user who owns the job
        job_id: ID of the job to update
        download_urls: List of presigned download URLs
    """
    try:
        # Calculate expiration time (7 days from now)
        expiration_time = datetime.utcnow() + timedelta(days=7)

        # Get the existing job's itemKey
        item_key = get_existing_job_item_key(job_id)

        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=(
                "SET #status = :status, "
                "#downloadUrls = :downloadUrls, "
                "#expiresAt = :expiresAt, "
                "#progress = :progress, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#downloadUrls": "downloadUrls",
                "#expiresAt": "expiresAt",
                "#progress": "progress",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "COMPLETED",
                ":downloadUrls": {
                    "zippedFiles": download_urls[0] if download_urls else None
                },
                ":expiresAt": int(expiration_time.timestamp()),
                ":progress": 100,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Updated job as completed",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "urlCount": len(download_urls),
                "expiresAt": expiration_time.isoformat(),
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job as completed",
            extra={
                "error": str(e),
                "userId": user_id,
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job as completed: {str(e)}")


@tracer.capture_method
def update_job_completed_structured(
    user_id: str, job_id: str, download_urls: Dict[str, Any]
) -> None:
    """
    Update the job record with structured download URLs and mark as completed.

    Args:
        user_id: ID of the user who owns the job
        job_id: ID of the job to update
        download_urls: Structured download URLs (zippedFiles and/or files)

    Raises:
        Exception: If job update fails
    """
    try:
        # Calculate expiration time (7 days from now)
        expiration_time = datetime.utcnow() + timedelta(days=7)

        # Get the existing job's itemKey
        item_key = get_existing_job_item_key(job_id)

        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=(
                "SET #status = :status, "
                "#downloadUrls = :downloadUrls, "
                "#expiresAt = :expiresAt, "
                "#progress = :progress, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#downloadUrls": "downloadUrls",
                "#expiresAt": "expiresAt",
                "#progress": "progress",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "COMPLETED",
                ":downloadUrls": download_urls,
                ":expiresAt": int(expiration_time.timestamp()),
                ":progress": 100,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Updated job as completed with structured URLs",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "downloadUrls": download_urls,
                "expiresAt": expiration_time.isoformat(),
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job as completed",
            extra={
                "error": str(e),
                "userId": user_id,
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job as completed: {str(e)}")


@tracer.capture_method
def cleanup_temp_files(job_id: str) -> None:
    """
    Clean up temporary files after successful processing.

    Args:
        job_id: Job ID
    """
    try:
        # Remove job working directory
        job_dir = os.path.join(EFS_MOUNT_PATH, job_id)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
            logger.info("Removed job directory", extra={"jobDir": job_dir})

    except Exception as e:
        logger.warning(
            "Error cleaning up temporary files",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for completing a multipart upload.

    Args:
        event: Event containing job details and completed parts
        context: Lambda context

    Returns:
        Dictionary containing the download URL for the final file
    """
    try:
        # Extract the necessary information from the event
        job_id = event.get("jobId")
        user_id = event.get("userId")
        upload_id = event.get("uploadId")
        s3_key = event.get("s3Key")
        manifest_key = event.get("manifestKey")

        if not job_id or not user_id or not upload_id or not s3_key or not manifest_key:
            raise ValueError("Missing required parameters in event")

        # Check if completed parts are provided directly in the event
        completed_parts = event.get("completedParts")
        if completed_parts:
            parts = completed_parts
        else:
            # Get the completed parts from the batch results (legacy format)
            batch_results = event.get("batchResults", [])
            all_parts = []

            # Collect parts from all batch results
            for batch_result in batch_results:
                if isinstance(batch_result, list):
                    # Each batch result contains a list of completed parts
                    all_parts.extend(batch_result)
                elif (
                    isinstance(batch_result, dict) and "completedParts" in batch_result
                ):
                    # Alternative structure where parts are in completedParts
                    all_parts.extend(batch_result["completedParts"])

            if all_parts:
                parts = all_parts
            else:
                # Fallback: get completed parts from the event
                parts = get_completed_parts(event, manifest_key)

        # Complete the multipart upload
        complete_multipart_upload(s3_key, upload_id, parts)

        # Delete the manifest file
        s3.delete_object(Bucket=MEDIA_ASSETS_BUCKET, Key=manifest_key)

        # Generate a presigned URL for the file
        download_url = generate_presigned_url(MEDIA_ASSETS_BUCKET, s3_key)

        # Check if we have large file URLs to combine (for MIXED jobs)
        large_file_urls = event.get("largeFileUrls", [])

        # Flatten large file URLs if they're nested
        flattened_large_urls = []
        if large_file_urls:
            for url_item in large_file_urls:
                if isinstance(url_item, list):
                    flattened_large_urls.extend(url_item)
                elif isinstance(url_item, dict) and "largeFileUrls" in url_item:
                    flattened_large_urls.extend(url_item["largeFileUrls"])
                elif isinstance(url_item, str):
                    flattened_large_urls.append(url_item)

        # Determine the structured format based on whether we have large files
        if flattened_large_urls:
            # For MIXED jobs: structured format with both categories
            structured_download_urls = {
                "zippedFiles": download_url,
                "files": flattened_large_urls,
            }
            logger.info(
                "Completed MIXED job with combined URLs",
                extra={
                    "jobId": job_id,
                    "zipUrl": download_url,
                    "largeFileUrls": flattened_large_urls,
                    "totalUrls": len(flattened_large_urls) + 1,
                },
            )
        else:
            # For SMALL jobs: only small files category
            structured_download_urls = {"zippedFiles": download_url}

        # Update the job record with the structured download URLs
        update_job_completed_structured(user_id, job_id, structured_download_urls)

        # Clean up temporary files
        cleanup_temp_files(job_id)

        # Add metrics
        metrics.add_metric(
            name="MultipartUploadsCompleted", unit=MetricUnit.Count, value=1
        )

        return {
            "jobId": job_id,
            "status": "COMPLETED",
            "downloadUrls": structured_download_urls,
        }

    except Exception as e:
        logger.error(
            f"Error completing multipart upload: {str(e)}",
            exc_info=True,
        )

        # Add metrics
        metrics.add_metric(
            name="MultipartUploadCompletionErrors", unit=MetricUnit.Count, value=1
        )

        # Update job status to FAILED if we have a job ID and user ID
        job_id = event.get("jobId")
        user_id = event.get("userId")
        if job_id and user_id:
            try:
                # Format user_id only if it doesn't already have the USER# prefix
                formatted_user_id = (
                    user_id if user_id.startswith("USER#") else f"USER#{user_id}"
                )

                # Get the existing job's itemKey
                try:
                    item_key = get_existing_job_item_key(job_id)

                    user_table.update_item(
                        Key={"userId": formatted_user_id, "itemKey": item_key},
                        UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                        ExpressionAttributeNames={
                            "#status": "status",
                            "#error": "error",
                            "#updatedAt": "updatedAt",
                        },
                        ExpressionAttributeValues={
                            ":status": "FAILED",
                            ":error": f"Failed to complete multipart upload: {str(e)}",
                            ":updatedAt": datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as query_error:
                    logger.error(
                        f"Failed to find job record for error update: {str(query_error)}"
                    )
            except Exception as update_error:
                logger.error(
                    f"Failed to update job status after error: {str(update_error)}",
                    extra={"userId": user_id, "jobId": job_id},
                )

        # Re-raise the exception to be handled by Step Functions
        raise
