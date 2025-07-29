"""
Bulk Download Handle Small Files Lambda

This Lambda function processes small files for bulk download by:
1. Mounting the EFS filesystem
2. Creating a temporary working directory
3. Downloading each small file from S3 to EFS
4. Creating zip files in chunks
5. Updating job progress in DynamoDB

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
import shutil
import time
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-handle-small")
tracer = Tracer(service="bulk-download-handle-small")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-handle-small")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
ASSET_TABLE = os.environ["ASSET_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_FILES_PER_ZIP = 100  # Maximum number of files per zip
MAX_RETRIES = 3  # Maximum number of retries for S3 downloads
PROGRESS_UPDATE_FREQUENCY = 5  # Update progress every N files


@tracer.capture_method
def get_job_details(job_id: str) -> Dict[str, Any]:
    """
    Retrieve job details from DynamoDB.

    Args:
        job_id: ID of the job to retrieve

    Returns:
        Job details

    Raises:
        Exception: If job retrieval fails
    """
    try:
        response = bulk_download_table.get_item(
            Key={"jobId": job_id},
            ConsistentRead=True,
        )

        if "Item" not in response:
            raise Exception(f"Job {job_id} not found")

        return response["Item"]

    except ClientError as e:
        logger.error(
            "Failed to retrieve job details",
            extra={
                "error": str(e),
                "jobId": job_id,
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
def download_file_from_s3(bucket: str, key: str, destination: str) -> bool:
    """
    Download a file from S3 with retries.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        destination: Local destination path

    Returns:
        True if download was successful, False otherwise
    """
    for attempt in range(MAX_RETRIES):
        try:
            s3.download_file(bucket, key, destination)
            return True
        except ClientError as e:
            logger.warning(
                f"S3 download attempt {attempt + 1}/{MAX_RETRIES} failed",
                extra={
                    "error": str(e),
                    "bucket": bucket,
                    "key": key,
                },
            )

            if attempt < MAX_RETRIES - 1:
                # Exponential backoff
                time.sleep(2**attempt)
            else:
                logger.error(
                    "S3 download failed after maximum retries",
                    extra={
                        "bucket": bucket,
                        "key": key,
                    },
                )
                return False

    return False


@tracer.capture_method
def update_job_progress(
    job_id: str, processed_count: int, total_count: int, zip_files: List[str] = None
) -> None:
    """
    Update job progress in DynamoDB.

    Args:
        job_id: ID of the job to update
        processed_count: Number of files processed
        total_count: Total number of files to process
        zip_files: List of created zip files

    Raises:
        Exception: If job update fails
    """
    progress = int((processed_count / total_count) * 100) if total_count > 0 else 0

    update_expression = "SET #status = :status, #progress = :progress, #processedFiles = :processedFiles, #updatedAt = :updatedAt"
    expression_attribute_names = {
        "#status": "status",
        "#progress": "progress",
        "#processedFiles": "processedFiles",
        "#updatedAt": "updatedAt",
    }
    expression_attribute_values = {
        ":status": "PROCESSING",
        ":progress": progress,
        ":processedFiles": processed_count,
        ":updatedAt": datetime.utcnow().isoformat(),
    }

    # Add zip files if provided
    if zip_files:
        update_expression += ", #smallZipFiles = :smallZipFiles"
        expression_attribute_names["#smallZipFiles"] = "smallZipFiles"
        expression_attribute_values[":smallZipFiles"] = zip_files

    try:
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )

        logger.info(
            "Updated job progress",
            extra={
                "jobId": job_id,
                "progress": progress,
                "processedFiles": processed_count,
                "totalFiles": total_count,
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job progress",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        # Continue processing even if update fails


@tracer.capture_method
def create_zip_file(files: List[Tuple[str, str]], zip_path: str) -> bool:
    """
    Create a zip file containing the specified files.

    Args:
        files: List of (file_path, archive_name) tuples
        zip_path: Path where the zip file should be created

    Returns:
        True if zip creation was successful, False otherwise
    """
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path, archive_name in files:
                zipf.write(file_path, archive_name)

        return True

    except Exception as e:
        logger.error(
            "Failed to create zip file",
            extra={
                "error": str(e),
                "zipPath": zip_path,
                "fileCount": len(files),
            },
        )
        return False


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for processing small files for bulk download.

    Args:
        event: Event containing job details
        context: Lambda context

    Returns:
        Updated job details with paths to created zip files
    """
    # Create EFS working directory
    job_id = event.get("jobId")
    if not job_id:
        raise ValueError("Missing jobId in event")

    # Create a unique working directory for this job
    working_dir = os.path.join(EFS_MOUNT_PATH, job_id)
    os.makedirs(working_dir, exist_ok=True)

    # Create a temporary directory for downloaded files
    download_dir = os.path.join(working_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)

    # Create a directory for zip files
    zip_dir = os.path.join(working_dir, "zips")
    os.makedirs(zip_dir, exist_ok=True)

    try:
        logger.info("Processing small files job", extra={"jobId": job_id})

        # Get job details
        job = get_job_details(job_id)

        # Get asset IDs from job
        asset_ids = job.get("foundAssets", [])
        if not asset_ids:
            logger.warning("No assets found for job", extra={"jobId": job_id})
            return {
                "jobId": job_id,
                "userId": job.get("userId"),
                "smallZipFiles": [],
                "processedFiles": 0,
                "totalFiles": 0,
            }

        # Get download options
        options = job.get("options", {})
        quality = options.get("quality", "original")  # original or proxy

        # Process files in batches and create zip files
        zip_files = []
        current_batch = []
        processed_count = 0
        total_count = len(asset_ids)

        for asset_id in asset_ids:
            try:
                # Get asset details
                asset = get_asset_details(asset_id)

                # Determine file path based on quality option
                if quality == "proxy":
                    # Look for proxy representation
                    file_path = None
                    bucket = None

                    for rep in asset.get("DerivedRepresentations", []):
                        if rep.get("Purpose") == "proxy":
                            storage_info = rep.get("StorageInfo", {}).get(
                                "PrimaryLocation", {}
                            )
                            bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
                            file_path = storage_info.get("ObjectKey", {}).get(
                                "FullPath"
                            )
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
                    main_rep = asset.get("DigitalSourceAsset", {}).get(
                        "MainRepresentation", {}
                    )
                    storage_info = main_rep.get("StorageInfo", {}).get(
                        "PrimaryLocation", {}
                    )
                    bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
                    file_path = storage_info.get("ObjectKey", {}).get("FullPath")

                if not file_path:
                    logger.warning(
                        "No file path found for asset", extra={"assetId": asset_id}
                    )
                    continue

                # Get file name from path
                file_name = os.path.basename(file_path)

                # Create local file path
                local_file_path = os.path.join(download_dir, file_name)

                # Download file from S3
                if download_file_from_s3(bucket, file_path, local_file_path):
                    # Add file to current batch
                    current_batch.append((local_file_path, file_name))
                    processed_count += 1

                    # Create zip file when batch is full
                    if len(current_batch) >= MAX_FILES_PER_ZIP:
                        zip_file_name = f"part_{len(zip_files) + 1}.zip"
                        zip_file_path = os.path.join(zip_dir, zip_file_name)

                        if create_zip_file(current_batch, zip_file_path):
                            zip_files.append(zip_file_path)

                            # Clear batch and downloaded files to save space
                            for file_path, _ in current_batch:
                                try:
                                    os.remove(file_path)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to remove temporary file: {str(e)}",
                                        extra={"filePath": file_path},
                                    )

                            current_batch = []

                # Update progress periodically
                if processed_count % PROGRESS_UPDATE_FREQUENCY == 0:
                    update_job_progress(job_id, processed_count, total_count)

            except Exception as e:
                logger.error(
                    f"Error processing asset {asset_id}: {str(e)}", exc_info=True
                )
                # Continue with next asset

        # Create final zip file if there are remaining files
        if current_batch:
            zip_file_name = f"part_{len(zip_files) + 1}.zip"
            zip_file_path = os.path.join(zip_dir, zip_file_name)

            if create_zip_file(current_batch, zip_file_path):
                zip_files.append(zip_file_path)

                # Clear downloaded files
                for file_path, _ in current_batch:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning(
                            f"Failed to remove temporary file: {str(e)}",
                            extra={"filePath": file_path},
                        )

        # Update job progress with final count and zip files
        update_job_progress(job_id, processed_count, total_count, zip_files)

        # Add metrics
        metrics.add_metric(
            name="SmallFilesProcessed", unit=MetricUnit.Count, value=processed_count
        )
        metrics.add_metric(
            name="ZipFilesCreated", unit=MetricUnit.Count, value=len(zip_files)
        )

        # Return updated job details for the next step
        return {
            "jobId": job_id,
            "userId": job.get("userId"),
            "smallZipFiles": zip_files,
            "processedFiles": processed_count,
            "totalFiles": total_count,
        }

    except Exception as e:
        logger.error(
            f"Error processing small files: {str(e)}",
            exc_info=True,
            extra={"jobId": job_id},
        )

        # Update job status to FAILED
        try:
            bulk_download_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#error": "error",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":status": "FAILED",
                    ":error": f"Failed to process small files: {str(e)}",
                    ":updatedAt": datetime.utcnow().isoformat(),
                },
            )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"jobId": job_id},
            )

        metrics.add_metric(
            name="SmallFilesProcessingErrors", unit=MetricUnit.Count, value=1
        )

        # Clean up working directory
        try:
            shutil.rmtree(working_dir)
        except Exception as cleanup_error:
            logger.error(
                f"Failed to clean up working directory: {str(cleanup_error)}",
                extra={"workingDir": working_dir},
            )

        # Re-raise the exception to be handled by Step Functions
        raise
