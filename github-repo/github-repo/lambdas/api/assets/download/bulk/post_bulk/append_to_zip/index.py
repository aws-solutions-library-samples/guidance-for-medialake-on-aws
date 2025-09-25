"""
Bulk Download Append to Zip Lambda

This Lambda function appends files to an existing zip file on shared storage (EFS) by:
1. Downloading the file from S3
2. Appending it to the existing zip file using streaming
3. Updating the job progress in DynamoDB

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
import time
import zipfile
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-append-to-zip")
tracer = Tracer(service="bulk-download-append-to-zip")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-append-to-zip"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
s3_resource = boto3.resource("s3")

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
ASSET_TABLE = os.environ["ASSET_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB tables
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_RETRIES = 3  # Maximum number of retries for S3 operations
CHUNK_SIZE_MB = int(os.environ.get("CHUNK_SIZE_MB", "100"))
CHUNK_SIZE = CHUNK_SIZE_MB * 1024 * 1024  # Convert MB to bytes for streaming


@tracer.capture_method
def get_job_details(job_id: str, user_id: str) -> Dict[str, Any]:
    """
    Retrieve job details from the user table.

    Args:
        job_id: ID of the job to retrieve
        user_id: ID of the user who owns the job

    Returns:
        Job details

    Raises:
        Exception: If job retrieval fails
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        # Query for the job using GSI2 (jobId index) for consistency with other functions
        response = user_table.query(
            IndexName="GSI2",
            KeyConditionExpression="gsi2Pk = :jobId",
            ExpressionAttributeValues={":jobId": f"JOB#{job_id}"},
            ConsistentRead=False,
        )

        if not response.get("Items"):
            raise Exception(f"Job {job_id} not found")

        # Find the job that belongs to this user
        job_item = None
        for item in response["Items"]:
            if item.get("userId") == formatted_user_id:
                job_item = item
                break

        if not job_item:
            raise Exception(f"Job {job_id} not found for user {user_id}")

        return job_item

    except ClientError as e:
        logger.error(
            "Failed to retrieve job details from user table",
            extra={
                "error": str(e),
                "jobId": job_id,
                "userId": user_id,
            },
        )
        raise Exception(f"Failed to retrieve job details: {str(e)}")


@tracer.capture_method
def get_asset_details(asset_id: str) -> Dict[str, Any]:
    """
    Retrieve asset details from DynamoDB.

    Args:
        asset_id: ID of the asset to retrieve

    Returns:
        Asset details

    Raises:
        Exception: If asset retrieval fails
    """
    try:
        response = asset_table.get_item(
            Key={"InventoryID": asset_id},
            ConsistentRead=True,
        )

        if "Item" not in response:
            raise Exception(f"Asset {asset_id} not found")

        return response["Item"]

    except ClientError as e:
        logger.error(
            "Failed to retrieve asset details",
            extra={
                "error": str(e),
                "assetId": asset_id,
            },
        )
        raise Exception(f"Failed to retrieve asset details: {str(e)}")


@tracer.capture_method
def update_job_progress(
    job_id: str, user_id: str, processed_count: int, total_count: int
) -> None:
    """
    Update job progress in the user table for zip creation phase (0-50%).

    Args:
        job_id: ID of the job to update
        user_id: ID of the user who owns the job
        processed_count: Number of files processed
        total_count: Total number of files to process

    Raises:
        Exception: If job update fails
    """
    # Calculate zip creation progress (0-50% of total progress)
    zip_phase_progress = (processed_count / total_count) if total_count > 0 else 0
    progress = int(zip_phase_progress * 50)  # Map to 0-50% range

    try:
        # Query to find the job item
        formatted_user_id = f"USER#{user_id}"

        response = user_table.query(
            KeyConditionExpression="userId = :userId AND begins_with(itemKey, :prefix)",
            ExpressionAttributeValues={
                ":userId": formatted_user_id,
                ":prefix": f"BULK_DOWNLOAD#{job_id}#",
            },
            Limit=1,
        )

        if not response.get("Items"):
            logger.error(f"Job {job_id} not found for user {user_id}")
            return

        item = response["Items"][0]
        item_key = item["itemKey"]

        # Update the job progress
        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression="SET #status = :status, #progress = :progress, #processedFiles = :processedFiles, #updatedAt = :updatedAt",
            ExpressionAttributeNames={
                "#status": "status",
                "#progress": "progress",
                "#processedFiles": "processedFiles",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "PROCESSING",
                ":progress": progress,
                ":processedFiles": processed_count,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Updated zip creation progress in user table",
            extra={
                "jobId": job_id,
                "userId": user_id,
                "progress": progress,
                "processedFiles": processed_count,
                "totalFiles": total_count,
                "phase": "ZIP_CREATION",
                "zipPhaseProgress": f"{zip_phase_progress:.2%}",
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job progress in user table",
            extra={
                "error": str(e),
                "jobId": job_id,
                "userId": user_id,
            },
        )
        # Continue processing even if update fails


@tracer.capture_method
def append_file_to_zip(bucket: str, key: str, zip_path: str, archive_name: str) -> bool:
    """
    Append a file from S3 to an existing zip file using streaming with file locking.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        zip_path: Path to the existing zip file
        archive_name: Name to use in the archive

    Returns:
        True if appending was successful, False otherwise
    """
    lock_file_path = f"{zip_path}.lock"
    max_lock_retries = 10
    lock_retry_delay = 0.5  # Start with 500ms delay

    for lock_attempt in range(max_lock_retries):
        try:
            # Try to acquire lock by creating a lock file atomically
            lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)

            try:
                # Write process info to lock file for debugging
                os.write(lock_fd, f"PID: {os.getpid()}, Time: {time.time()}\n".encode())
                os.close(lock_fd)

                # We have the lock, proceed with zip operation
                logger.info(
                    "Acquired zip file lock, appending file",
                    extra={
                        "bucket": bucket,
                        "key": key,
                        "archiveName": archive_name,
                        "zipPath": zip_path,
                        "lockAttempt": lock_attempt + 1,
                    },
                )

                # Get object size
                response = s3.head_object(Bucket=bucket, Key=key)
                content_length = response.get("ContentLength", 0)

                # Ensure the zip file exists and is accessible
                if not os.path.exists(zip_path):
                    logger.error(f"Zip file does not exist: {zip_path}")
                    return False

                # Directly append to the existing zip file
                with zipfile.ZipFile(zip_path, "a", zipfile.ZIP_DEFLATED) as zipf:
                    # Create a ZipInfo object to store file info
                    zip_info = zipfile.ZipInfo(archive_name)
                    zip_info.compress_type = zipfile.ZIP_DEFLATED
                    zip_info.date_time = time.localtime(time.time())[:6]

                    # Stream the file in chunks
                    with zipf.open(zip_info, "w") as dest_file:
                        # Get the S3 object
                        s3_object = s3_resource.Object(bucket, key)

                        # Stream the object in chunks
                        offset = 0
                        while offset < content_length:
                            end = min(offset + CHUNK_SIZE, content_length)
                            range_str = f"bytes={offset}-{end-1}"

                            response = s3_object.get(Range=range_str)
                            data = response["Body"].read()
                            dest_file.write(data)

                            offset = end

                logger.info(
                    "Successfully appended file to zip",
                    extra={
                        "bucket": bucket,
                        "key": key,
                        "archiveName": archive_name,
                        "zipPath": zip_path,
                        "size": content_length,
                    },
                )

                return True

            finally:
                # Always release the lock
                try:
                    os.unlink(lock_file_path)
                    logger.debug(f"Released zip file lock: {lock_file_path}")
                except OSError as e:
                    logger.warning(f"Failed to remove lock file: {e}")

        except OSError as e:
            if e.errno == 17:  # File exists (lock is held by another process)
                logger.info(
                    f"Zip file is locked, retrying in {lock_retry_delay}s (attempt {lock_attempt + 1}/{max_lock_retries})",
                    extra={
                        "zipPath": zip_path,
                        "lockFile": lock_file_path,
                        "attempt": lock_attempt + 1,
                    },
                )
                time.sleep(lock_retry_delay)
                # Exponential backoff with jitter
                lock_retry_delay = min(
                    lock_retry_delay * 1.5 + (time.time() % 0.1), 5.0
                )
                continue
            else:
                logger.error(
                    "Failed to create lock file",
                    extra={
                        "error": str(e),
                        "errno": e.errno,
                        "lockFile": lock_file_path,
                    },
                )
                return False
        except Exception as e:
            logger.error(
                "Failed to append file to zip",
                extra={
                    "error": str(e),
                    "bucket": bucket,
                    "key": key,
                    "zipPath": zip_path,
                },
            )
            # Clean up lock file if we created it
            try:
                os.unlink(lock_file_path)
            except OSError:
                pass
            return False

    # If we get here, we failed to acquire the lock after all retries
    logger.error(
        "Failed to acquire zip file lock after all retries",
        extra={
            "zipPath": zip_path,
            "maxRetries": max_lock_retries,
            "bucket": bucket,
            "key": key,
        },
    )
    return False


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for appending a file to an existing zip file.

    Args:
        event: Event containing job details and asset information
        context: Lambda context

    Returns:
        Dictionary containing the result of the operation
    """
    job_id = event.get("jobId")
    user_id = event.get("userId")
    asset_id = event.get("assetId")

    if not job_id:
        raise ValueError("Missing jobId in event")

    if not user_id:
        raise ValueError("Missing userId in event")

    if not asset_id:
        raise ValueError("Missing assetId in event")

    try:
        logger.info(
            "Starting append operation",
            extra={
                "jobId": job_id,
                "userId": user_id,
                "assetId": asset_id,
                "event": event,
            },
        )

        # Get job details from user table
        job = get_job_details(job_id, user_id)

        # Get the zip path from the job
        zip_path = job.get("zipPath")
        if not zip_path:
            raise ValueError(f"No zip path found for job {job_id}")

        # Ensure the zip file exists
        if not os.path.exists(zip_path):
            raise ValueError(f"Zip file not found at {zip_path}")

        # Log zip file status
        zip_stat = os.stat(zip_path)
        logger.info(
            "Zip file status before append",
            extra={
                "zipPath": zip_path,
                "zipSize": zip_stat.st_size,
                "zipMtime": zip_stat.st_mtime,
                "jobId": job_id,
                "userId": user_id,
                "assetId": asset_id,
            },
        )

        # Get asset details
        asset = get_asset_details(asset_id)

        # Get download options
        options = job.get("options", {})
        quality = options.get("quality", "original")  # original or proxy

        # Determine file path based on quality option
        if quality == "proxy":
            # Look for proxy representation
            file_path = None
            bucket = None

            for rep in asset.get("DerivedRepresentations", []):
                if rep.get("Purpose") == "proxy":
                    storage_info = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                    bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
                    file_path = storage_info.get("ObjectKey", {}).get("FullPath")
                    break

            # If no proxy found, use original
            if not file_path:
                logger.warning(
                    "No proxy representation found, using original",
                    extra={"assetId": asset_id},
                )
                main_rep = asset.get("DigitalSourceAsset", {}).get(
                    "MainRepresentation", {}
                )
                storage_info = main_rep.get("StorageInfo", {}).get(
                    "PrimaryLocation", {}
                )
                bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
                file_path = storage_info.get("ObjectKey", {}).get("FullPath")
        else:
            # Use original representation
            main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
            storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
            file_path = storage_info.get("ObjectKey", {}).get("FullPath")

        if not file_path:
            raise ValueError(f"Could not determine file path for asset {asset_id}")

        # Get file name from path
        file_name = os.path.basename(file_path)

        # Append the file to the zip
        if append_file_to_zip(bucket, file_path, zip_path, file_name):
            # Log zip file status after append
            zip_stat = os.stat(zip_path)
            logger.info(
                "Zip file status after successful append",
                extra={
                    "zipPath": zip_path,
                    "zipSize": zip_stat.st_size,
                    "zipMtime": zip_stat.st_mtime,
                    "jobId": job_id,
                    "userId": user_id,
                    "assetId": asset_id,
                    "fileName": file_name,
                },
            )

            # Update job progress
            processed_count = job.get("processedFiles", 0) + 1
            total_count = job.get("totalFiles", 0)
            update_job_progress(job_id, user_id, processed_count, total_count)

            # Add metrics
            metrics.add_metric(
                name="FilesAppendedToZip", unit=MetricUnit.Count, value=1
            )

            logger.info(
                "Successfully completed append operation",
                extra={
                    "jobId": job_id,
                    "userId": user_id,
                    "assetId": asset_id,
                    "fileName": file_name,
                    "processedCount": processed_count,
                    "totalCount": total_count,
                },
            )

            return {
                "jobId": job_id,
                "userId": user_id,
                "assetId": asset_id,
                "status": "APPENDED",
                "zipPath": zip_path,
                "processedCount": processed_count,
                "totalCount": total_count,
            }
        else:
            raise Exception(f"Failed to append file {file_path} to zip {zip_path}")

    except Exception as e:
        logger.error(
            f"Error appending file to zip: {str(e)}",
            exc_info=True,
            extra={
                "jobId": job_id,
                "userId": user_id,
                "assetId": asset_id,
            },
        )

        # Add metrics
        metrics.add_metric(name="AppendToZipErrors", unit=MetricUnit.Count, value=1)

        # Re-raise the exception to be handled by Step Functions
        raise
