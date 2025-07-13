"""
Bulk Download Assess Scale Lambda

This Lambda function assesses the scale of a bulk download job by:
1. Retrieving metadata for all requested assets
2. Calculating total size and number of files
3. Determining if the job should be processed as "small" or "large"
4. Updating the job record with size information

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-assess-scale")
tracer = Tracer(service="bulk-download-assess-scale")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-assess-scale")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
ASSET_TABLE = os.environ["ASSET_TABLE"]
SMALL_FILE_THRESHOLD = int(os.environ.get("SMALL_FILE_THRESHOLD", "100"))  # MB
LARGE_JOB_THRESHOLD = int(os.environ.get("LARGE_JOB_THRESHOLD", "1000"))  # MB

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MB = 1024 * 1024  # 1 MB in bytes
MAX_BATCH_SIZE = 25  # Maximum batch size for DynamoDB BatchGetItem


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
def get_assets_metadata(asset_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve metadata for multiple assets using BatchGetItem.

    Args:
        asset_ids: List of asset IDs to retrieve

    Returns:
        List of asset metadata
    """
    assets = []

    # Process in batches of MAX_BATCH_SIZE
    for i in range(0, len(asset_ids), MAX_BATCH_SIZE):
        batch = asset_ids[i : i + MAX_BATCH_SIZE]

        try:
            response = dynamodb.batch_get_item(
                RequestItems={
                    ASSET_TABLE: {
                        "Keys": [{"InventoryID": asset_id} for asset_id in batch]
                    }
                }
            )

            # Add retrieved items to the assets list
            if ASSET_TABLE in response.get("Responses", {}):
                assets.extend(response["Responses"][ASSET_TABLE])

            # Handle unprocessed keys with exponential backoff
            unprocessed_keys = response.get("UnprocessedKeys", {})
            retry_count = 0
            max_retries = 3

            while (
                unprocessed_keys
                and ASSET_TABLE in unprocessed_keys
                and retry_count < max_retries
            ):
                retry_count += 1
                wait_time = 2**retry_count * 100  # Exponential backoff
                time.sleep(wait_time / 1000)  # Convert to seconds

                logger.info(
                    f"Retrying batch_get_item for {len(unprocessed_keys[ASSET_TABLE]['Keys'])} unprocessed keys",
                    extra={"retry": retry_count, "maxRetries": max_retries},
                )

                response = dynamodb.batch_get_item(RequestItems=unprocessed_keys)

                if ASSET_TABLE in response.get("Responses", {}):
                    assets.extend(response["Responses"][ASSET_TABLE])

                unprocessed_keys = response.get("UnprocessedKeys", {})

            # Log warning if there are still unprocessed keys after max retries
            if unprocessed_keys and ASSET_TABLE in unprocessed_keys:
                unprocessed_count = len(unprocessed_keys[ASSET_TABLE]["Keys"])
                logger.warning(
                    f"Failed to retrieve {unprocessed_count} assets after {max_retries} retries",
                    extra={"unprocessedCount": unprocessed_count},
                )

        except ClientError as e:
            logger.error(
                "Error retrieving asset metadata batch",
                extra={
                    "error": str(e),
                    "batchSize": len(batch),
                    "startIndex": i,
                },
            )

    return assets


@tracer.capture_method
def calculate_job_size(assets: List[Dict[str, Any]]) -> Tuple[int, int, int, str]:
    """
    Calculate the total size and determine job type.

    Args:
        assets: List of asset metadata

    Returns:
        Tuple of (total_size, small_files_count, large_files_count, job_type)
    """
    total_size = 0
    small_files_count = 0
    large_files_count = 0

    for asset in assets:
        # Get the main representation size
        main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
        storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
        file_info = storage_info.get("FileInfo", {})

        # Get file size in bytes
        file_size = file_info.get("Size", 0)
        total_size += file_size

        # Determine if this is a small or large file
        if file_size <= SMALL_FILE_THRESHOLD * MB:
            small_files_count += 1
        else:
            large_files_count += 1

    # Determine job type based on total size
    job_type = "SMALL" if total_size <= LARGE_JOB_THRESHOLD * MB else "LARGE"

    logger.info(
        "Job size calculation complete",
        extra={
            "totalSize": total_size,
            "totalSizeMB": total_size / MB,
            "smallFilesCount": small_files_count,
            "largeFilesCount": large_files_count,
            "jobType": job_type,
        },
    )

    return total_size, small_files_count, large_files_count, job_type


@tracer.capture_method
def update_job_record(
    job_id: str,
    total_size: int,
    small_files_count: int,
    large_files_count: int,
    job_type: str,
    found_assets: List[str],
    missing_assets: List[str],
) -> None:
    """
    Update the job record with size information.

    Args:
        job_id: ID of the job to update
        total_size: Total size of all assets in bytes
        small_files_count: Number of small files
        large_files_count: Number of large files
        job_type: Type of job (SMALL or LARGE)
        found_assets: List of asset IDs that were found
        missing_assets: List of asset IDs that were not found

    Raises:
        Exception: If job update fails
    """
    try:
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=(
                "SET #status = :status, "
                "#totalSize = :totalSize, "
                "#smallFilesCount = :smallFilesCount, "
                "#largeFilesCount = :largeFilesCount, "
                "#jobType = :jobType, "
                "#foundAssets = :foundAssets, "
                "#missingAssets = :missingAssets, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#totalSize": "totalSize",
                "#smallFilesCount": "smallFilesCount",
                "#largeFilesCount": "largeFilesCount",
                "#jobType": "jobType",
                "#foundAssets": "foundAssets",
                "#missingAssets": "missingAssets",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "ASSESSED",
                ":totalSize": total_size,
                ":smallFilesCount": small_files_count,
                ":largeFilesCount": large_files_count,
                ":jobType": job_type,
                ":foundAssets": found_assets,
                ":missingAssets": missing_assets,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Updated job record with size information",
            extra={
                "jobId": job_id,
                "jobType": job_type,
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job record",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job record: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for assessing the scale of a bulk download job.

    Args:
        event: Event containing job details
        context: Lambda context

    Returns:
        Updated job details with size information
    """
    try:
        # Get job ID from event
        job_id = event.get("jobId")
        if not job_id:
            raise ValueError("Missing jobId in event")

        logger.info("Processing job", extra={"jobId": job_id})

        # Get job details
        job = get_job_details(job_id)

        # Get asset IDs from job
        asset_ids = job.get("assetIds", [])
        if not asset_ids:
            raise ValueError("No asset IDs found in job")

        # Get asset metadata
        assets = get_assets_metadata(asset_ids)

        # Identify missing assets
        found_asset_ids = [asset.get("InventoryID") for asset in assets]
        missing_asset_ids = [
            asset_id for asset_id in asset_ids if asset_id not in found_asset_ids
        ]

        if missing_asset_ids:
            logger.warning(
                "Some assets were not found",
                extra={
                    "jobId": job_id,
                    "missingCount": len(missing_asset_ids),
                    "missingAssets": missing_asset_ids,
                },
            )

        # Calculate job size
        total_size, small_files_count, large_files_count, job_type = calculate_job_size(
            assets
        )

        # Update job record
        update_job_record(
            job_id,
            total_size,
            small_files_count,
            large_files_count,
            job_type,
            found_asset_ids,
            missing_asset_ids,
        )

        # Add metrics
        metrics.add_metric(name="JobsAssessed", unit=MetricUnit.Count, value=1)
        metrics.add_metric(
            name="TotalDownloadSize", unit=MetricUnit.Megabytes, value=total_size / MB
        )

        # Return updated job details for the next step
        return {
            "jobId": job_id,
            "userId": job.get("userId"),
            "jobType": job_type,
            "totalSize": total_size,
            "smallFilesCount": small_files_count,
            "largeFilesCount": large_files_count,
            "foundAssets": found_asset_ids,
            "missingAssets": missing_asset_ids,
            "options": job.get("options", {}),
        }

    except Exception as e:
        logger.error(
            f"Error assessing job scale: {str(e)}",
            exc_info=True,
            extra={"jobId": event.get("jobId")},
        )

        # Update job status to FAILED
        try:
            if "jobId" in event:
                bulk_download_table.update_item(
                    Key={"jobId": event["jobId"]},
                    UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                        "#updatedAt": "updatedAt",
                    },
                    ExpressionAttributeValues={
                        ":status": "FAILED",
                        ":error": f"Failed to assess job scale: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"jobId": event.get("jobId")},
            )

        metrics.add_metric(name="JobAssessmentErrors", unit=MetricUnit.Count, value=1)

        # Re-raise the exception to be handled by Step Functions
        raise
