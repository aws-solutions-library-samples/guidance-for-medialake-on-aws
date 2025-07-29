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
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
ASSET_TABLE = os.environ["ASSET_TABLE"]
SMALL_FILE_THRESHOLD_MB = int(os.environ.get("SMALL_FILE_THRESHOLD_MB", "1024"))  # MB
SMALL_FILE_THRESHOLD = SMALL_FILE_THRESHOLD_MB  # For backward compatibility
LARGE_JOB_THRESHOLD = int(os.environ.get("LARGE_JOB_THRESHOLD", "1000"))  # MB
SINGLE_FILE_CHECK = os.environ.get("SINGLE_FILE_CHECK", "false").lower() == "true"

# Initialize DynamoDB tables
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MB = 1024 * 1024  # 1 MB in bytes
MAX_BATCH_SIZE = 25  # Maximum batch size for DynamoDB BatchGetItem


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

    # Check if this is a single file job
    if SINGLE_FILE_CHECK and len(assets) == 1:
        job_type = "SINGLE_FILE"

        # Still calculate the size for logging purposes
        asset = assets[0]
        main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
        storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
        file_info = storage_info.get("FileInfo", {})

        # Get file size in bytes
        file_size = file_info.get("Size", 0)
        total_size = file_size

        # Determine if this is a small or large file for metrics
        if file_size <= SMALL_FILE_THRESHOLD * MB:
            small_files_count = 1
        else:
            large_files_count = 1

        logger.info(
            "Single file job detected",
            extra={
                "totalSize": total_size,
                "totalSizeMB": total_size / MB,
                "jobType": job_type,
                "assetId": asset.get("InventoryID", "unknown"),
            },
        )
    else:
        # Multiple files - process normally
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

        # Determine job type based on file composition
        if large_files_count > 0 and small_files_count > 0:
            # Mixed files: small files get zipped, large files get individual presigned URLs
            job_type = "MIXED"
        elif large_files_count > 0:
            # Only large files: each gets individual presigned URLs
            job_type = "LARGE_INDIVIDUAL"
        else:
            # Only small files: all get zipped together
            job_type = "SMALL"

    logger.info(
        "Job size calculation complete",
        extra={
            "totalSize": total_size,
            "totalSizeMB": total_size / MB,
            "smallFilesCount": small_files_count,
            "largeFilesCount": large_files_count,
            "jobType": job_type,
            "assetCount": len(assets),
        },
    )

    return total_size, small_files_count, large_files_count, job_type


@tracer.capture_method
def update_job_record(
    user_id: str,
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
        user_id: ID of the user who owns the job
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
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        # Get the existing job's itemKey
        item_key = get_existing_job_item_key(job_id)

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
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
        # Get job ID and user ID from event
        job_id = event.get("jobId")
        user_id = event.get("userId")

        if not job_id:
            raise ValueError("Missing jobId in event")
        if not user_id:
            raise ValueError("Missing userId in event")

        logger.info("Processing job", extra={"userId": user_id, "jobId": job_id})

        # Get job details
        job = get_job_details(user_id, job_id)

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
            user_id,
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

        # Prepare data for Map states
        small_files = []
        large_files = []

        # For SINGLE_FILE job type, we don't need to prepare arrays as it's handled separately
        if job_type != "SINGLE_FILE":
            for asset in assets:
                asset_id = asset.get("InventoryID")
                if asset_id in found_asset_ids:
                    main_rep = asset.get("DigitalSourceAsset", {}).get(
                        "MainRepresentation", {}
                    )
                    storage_info = main_rep.get("StorageInfo", {}).get(
                        "PrimaryLocation", {}
                    )
                    file_info = storage_info.get("FileInfo", {})
                    file_size = file_info.get("Size", 0)

                    # If it's a small file, add to small_files for zipping
                    if file_size <= SMALL_FILE_THRESHOLD_MB * 1024 * 1024:
                        small_files.append(
                            {
                                "jobId": job_id,
                                "userId": job.get("userId"),
                                "assetId": asset_id,
                                "options": job.get("options", {}),
                            }
                        )
                    # If it's a large file, add to large_files for individual presigned URLs
                    else:
                        large_files.append(
                            {
                                "jobId": job_id,
                                "userId": job.get("userId"),
                                "assetId": asset_id,
                                "options": job.get("options", {}),
                            }
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
            "smallFiles": small_files,
            "largeFiles": large_files,
        }

    except Exception as e:
        logger.error(
            f"Error assessing job scale: {str(e)}",
            exc_info=True,
            extra={"jobId": event.get("jobId")},
        )

        # Update job status to FAILED
        try:
            if "jobId" in event and "userId" in event:
                # Format user_id only if it doesn't already have the USER# prefix
                formatted_user_id = (
                    event["userId"]
                    if event["userId"].startswith("USER#")
                    else f"USER#{event['userId']}"
                )

                # Get the existing job's itemKey and update status to FAILED
                try:
                    item_key = get_existing_job_item_key(event["jobId"])

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
                            ":error": f"Failed to assess job scale: {str(e)}",
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
                extra={"jobId": event.get("jobId")},
            )

        metrics.add_metric(name="JobAssessmentErrors", unit=MetricUnit.Count, value=1)

        # Re-raise the exception to be handled by Step Functions
        raise
