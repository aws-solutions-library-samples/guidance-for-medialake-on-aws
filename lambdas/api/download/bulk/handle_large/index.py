"""
Bulk Download Handle Large Files Lambda

This Lambda function processes large files for bulk download by:
1. Streaming files directly from S3 to zip files
2. Using S3 multipart uploads for efficient transfer
3. Processing files in batches to manage memory usage
4. Updating job progress in DynamoDB

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-handle-large")
tracer = Tracer(service="bulk-download-handle-large")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-handle-large")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
s3_resource = boto3.resource("s3")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
ASSET_TABLE = os.environ["ASSET_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_FILES_PER_ZIP = 10  # Maximum number of large files per zip
MAX_RETRIES = 3  # Maximum number of retries for S3 operations
PROGRESS_UPDATE_FREQUENCY = 2  # Update progress every N files
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks for streaming


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
def update_job_progress(
    job_id: str,
    processed_count: int,
    total_count: int,
    large_zip_files: List[str] = None,
) -> None:
    """
    Update job progress in DynamoDB.

    Args:
        job_id: ID of the job to update
        processed_count: Number of files processed
        total_count: Total number of files to process
        large_zip_files: List of created zip files

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
    if large_zip_files:
        update_expression += ", #largeZipFiles = :largeZipFiles"
        expression_attribute_names["#largeZipFiles"] = "largeZipFiles"
        expression_attribute_values[":largeZipFiles"] = large_zip_files

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
def stream_s3_object_to_zip(
    bucket: str, key: str, zip_file: zipfile.ZipFile, archive_name: str
) -> bool:
    """
    Stream an S3 object directly into a zip file without downloading the entire file.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        zip_file: Open ZipFile object
        archive_name: Name to use in the archive

    Returns:
        True if streaming was successful, False otherwise
    """
    try:
        # Get object size
        response = s3.head_object(Bucket=bucket, Key=key)
        content_length = response.get("ContentLength", 0)

        logger.info(
            "Streaming file from S3 to zip",
            extra={
                "bucket": bucket,
                "key": key,
                "size": content_length,
                "archiveName": archive_name,
            },
        )

        # Create a ZipInfo object to store file info
        zip_info = zipfile.ZipInfo(archive_name)
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        zip_info.date_time = time.localtime(time.time())[:6]

        # Stream the file in chunks
        with zip_file.open(zip_info, "w") as dest_file:
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

        return True

    except Exception as e:
        logger.error(
            "Failed to stream S3 object to zip",
            extra={
                "error": str(e),
                "bucket": bucket,
                "key": key,
            },
        )
        return False


@tracer.capture_method
def create_zip_with_large_files(
    asset_batch: List[Dict[str, Any]], quality: str, temp_dir: str, job_id: str
) -> str:
    """
    Create a zip file containing large files streamed directly from S3.

    Args:
        asset_batch: List of asset details
        quality: Quality option (original or proxy)
        temp_dir: Temporary directory for zip creation
        job_id: Job ID for naming

    Returns:
        Path to the created zip file, or None if creation failed
    """
    # Create a unique zip file name
    zip_file_name = f"large_{job_id}_{uuid.uuid4()}.zip"
    zip_file_path = os.path.join(temp_dir, zip_file_name)

    try:
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for asset in asset_batch:
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
                            extra={"assetId": asset.get("InventoryID")},
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
                        "No file path found for asset",
                        extra={"assetId": asset.get("InventoryID")},
                    )
                    continue

                # Get file name from path
                file_name = os.path.basename(file_path)

                # Stream file directly from S3 to zip
                stream_s3_object_to_zip(bucket, file_path, zipf, file_name)

        # Upload zip file to S3
        s3_key = f"temp/zip/{job_id}/{zip_file_name}"
        s3.upload_file(zip_file_path, MEDIA_ASSETS_BUCKET, s3_key)

        # Return the S3 path
        return f"s3://{MEDIA_ASSETS_BUCKET}/{s3_key}"

    except Exception as e:
        logger.error(
            "Failed to create zip with large files",
            extra={
                "error": str(e),
                "zipPath": zip_file_path,
                "assetCount": len(asset_batch),
            },
        )
        return None
    finally:
        # Clean up the local zip file
        try:
            if os.path.exists(zip_file_path):
                os.remove(zip_file_path)
        except Exception as e:
            logger.warning(
                f"Failed to remove temporary zip file: {str(e)}",
                extra={"zipPath": zip_file_path},
            )


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for processing large files for bulk download.

    Args:
        event: Event containing job details
        context: Lambda context

    Returns:
        Updated job details with paths to created zip files
    """
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        job_id = event.get("jobId")
        if not job_id:
            raise ValueError("Missing jobId in event")

        try:
            logger.info("Processing large files job", extra={"jobId": job_id})

            # Get job details
            job = get_job_details(job_id)

            # Get asset IDs from job
            asset_ids = job.get("foundAssets", [])
            if not asset_ids:
                logger.warning("No assets found for job", extra={"jobId": job_id})
                return {
                    "jobId": job_id,
                    "userId": job.get("userId"),
                    "largeZipFiles": [],
                    "processedFiles": 0,
                    "totalFiles": 0,
                }

            # Get download options
            options = job.get("options", {})
            quality = options.get("quality", "original")  # original or proxy

            # Process files in batches and create zip files
            zip_files = []
            processed_count = 0
            total_count = len(asset_ids)

            # Process assets in batches
            for i in range(0, len(asset_ids), MAX_FILES_PER_ZIP):
                batch_asset_ids = asset_ids[i : i + MAX_FILES_PER_ZIP]
                batch_assets = []

                # Get asset details for the batch
                for asset_id in batch_asset_ids:
                    try:
                        asset = get_asset_details(asset_id)
                        batch_assets.append(asset)
                    except Exception as e:
                        logger.error(
                            f"Error retrieving asset {asset_id}: {str(e)}",
                            exc_info=True,
                        )
                        # Continue with next asset

                # Create zip file for the batch
                if batch_assets:
                    zip_file_path = create_zip_with_large_files(
                        batch_assets, quality, temp_dir, job_id
                    )

                    if zip_file_path:
                        zip_files.append(zip_file_path)
                        processed_count += len(batch_assets)

                    # Update progress
                    update_job_progress(job_id, processed_count, total_count, zip_files)

            # Add metrics
            metrics.add_metric(
                name="LargeFilesProcessed", unit=MetricUnit.Count, value=processed_count
            )
            metrics.add_metric(
                name="LargeZipFilesCreated", unit=MetricUnit.Count, value=len(zip_files)
            )

            # Return updated job details for the next step
            return {
                "jobId": job_id,
                "userId": job.get("userId"),
                "largeZipFiles": zip_files,
                "processedFiles": processed_count,
                "totalFiles": total_count,
            }

        except Exception as e:
            logger.error(
                f"Error processing large files: {str(e)}",
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
                        ":error": f"Failed to process large files: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as update_error:
                logger.error(
                    f"Failed to update job status after error: {str(update_error)}",
                    extra={"jobId": job_id},
                )

            metrics.add_metric(
                name="LargeFilesProcessingErrors", unit=MetricUnit.Count, value=1
            )

            # Re-raise the exception to be handled by Step Functions
            raise
