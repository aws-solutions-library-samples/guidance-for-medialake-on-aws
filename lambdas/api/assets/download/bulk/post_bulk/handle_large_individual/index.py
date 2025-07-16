"""
Bulk Download Handle Large Individual Lambda

This Lambda function handles large files individually by:
1. Retrieving asset details from DynamoDB
2. Generating presigned URLs for each large file
3. Updating the job record with the download URLs

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-handle-large-individual")
tracer = Tracer(service="bulk-download-handle-large-individual")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-handle-large-individual"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version="s3v4"))

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
ASSET_TABLE = os.environ["ASSET_TABLE"]

# Initialize DynamoDB tables
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds
MAX_RETRIES = 3  # Maximum number of retries for operations


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
def generate_presigned_url(bucket: str, key: str, filename: str) -> str:
    """
    Generate a presigned URL for an S3 object.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        filename: Original filename for content disposition

    Returns:
        Presigned URL
    """
    try:
        raw = os.path.basename(filename)
        # Normalize to NFKD, drop anything that can't be ASCII-encoded:
        safe = (
            unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
        )
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{safe}"',
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
def process_large_files(
    job_id: str, large_files: List[Dict[str, Any]], options: Dict[str, Any]
) -> List[str]:
    """
    Process large files and generate presigned URLs for each.

    Args:
        job_id: ID of the job
        large_files: List of large file asset IDs
        options: Download options

    Returns:
        List of presigned URLs
    """
    download_urls = []
    quality = options.get("quality", "original")  # original or proxy

    for large_file in large_files:
        asset_id = large_file.get("assetId")

        try:
            # Get asset details
            asset = get_asset_details(asset_id)

            # Determine file path based on quality option
            file_path = None
            bucket = None

            if quality == "proxy":
                # Look for proxy representation
                for rep in asset.get("DerivedRepresentations", []):
                    if rep.get("Purpose") == "proxy":
                        storage_info = rep.get("StorageInfo", {}).get(
                            "PrimaryLocation", {}
                        )
                        bucket = storage_info.get("Bucket")
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
                    bucket = storage_info.get("Bucket")
                    file_path = storage_info.get("ObjectKey", {}).get("FullPath")
            else:
                # Use original representation
                main_rep = asset.get("DigitalSourceAsset", {}).get(
                    "MainRepresentation", {}
                )
                storage_info = main_rep.get("StorageInfo", {}).get(
                    "PrimaryLocation", {}
                )
                bucket = storage_info.get("Bucket")
                file_path = storage_info.get("ObjectKey", {}).get("FullPath")

            if not file_path or not bucket:
                logger.error(
                    f"Could not determine file path or bucket for asset {asset_id}",
                    extra={"assetId": asset_id},
                )
                continue

            # Get file name from path
            file_name = os.path.basename(file_path)

            # Generate presigned URL
            download_url = generate_presigned_url(bucket, file_path, file_name)
            download_urls.append(download_url)

            logger.info(
                "Generated presigned URL for large file",
                extra={
                    "assetId": asset_id,
                    "fileName": file_name,
                    "jobId": job_id,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to process large file {asset_id}: {str(e)}",
                extra={
                    "assetId": asset_id,
                    "jobId": job_id,
                },
            )
            # Continue processing other files even if one fails
            continue

    return download_urls


@tracer.capture_method
def update_job_with_large_file_urls(
    user_id: str, job_id: str, large_file_urls: List[str]
) -> None:
    """
    Update the job record with large file URLs.

    Args:
        user_id: ID of the user who owns the job
        job_id: ID of the job to update
        large_file_urls: List of presigned URLs for large files

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
                "SET #largeFileUrls = :largeFileUrls, "
                "#expiresAt = :expiresAt, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#largeFileUrls": "largeFileUrls",
                "#expiresAt": "expiresAt",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":largeFileUrls": large_file_urls,
                ":expiresAt": int(expiration_time.timestamp()),
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Updated job with large file URLs",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "urlCount": len(large_file_urls),
                "expiresAt": expiration_time.isoformat(),
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job with large file URLs",
            extra={
                "error": str(e),
                "userId": user_id,
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job with large file URLs: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for generating presigned URLs for large files.

    Args:
        event: Event containing job details and large files
        context: Lambda context

    Returns:
        Updated job details with large file URLs
    """
    try:
        # Get job ID and user ID from event
        job_id = event.get("jobId")
        user_id = event.get("userId")

        if not job_id:
            raise ValueError("Missing jobId in event")
        if not user_id:
            raise ValueError("Missing userId in event")

        # Get large files from event
        large_files = event.get("largeFiles", [])
        if not large_files:
            logger.info(
                "No large files to process", extra={"userId": user_id, "jobId": job_id}
            )
            return {
                "jobId": job_id,
                "userId": user_id,
                "largeFileUrls": [],
            }

        logger.info(
            "Processing large files for individual download",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "largeFileCount": len(large_files),
            },
        )

        # Get job details for options
        job = get_job_details(user_id, job_id)
        options = job.get("options", {})
        job_type = job.get("jobType", "")

        # Process large files and generate presigned URLs
        large_file_urls = process_large_files(job_id, large_files, options)

        # If this is a LARGE_INDIVIDUAL job (only large files), complete the job
        if job_type == "LARGE_INDIVIDUAL":
            # Calculate expiration time (7 days from now)
            expiration_time = datetime.utcnow() + timedelta(days=7)

            # Store structured format in database for LARGE_INDIVIDUAL jobs
            structured_urls = {"files": large_file_urls}

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
                    ":downloadUrls": structured_urls,
                    ":expiresAt": int(expiration_time.timestamp()),
                    ":progress": 100,
                    ":updatedAt": datetime.utcnow().isoformat(),
                },
            )

            logger.info(
                "Completed LARGE_INDIVIDUAL job with individual file URLs",
                extra={
                    "userId": user_id,
                    "jobId": job_id,
                    "urlCount": len(large_file_urls),
                    "expiresAt": expiration_time.isoformat(),
                },
            )
        else:
            # For mixed jobs, just update with large file URLs (small files will be handled separately)
            update_job_with_large_file_urls(user_id, job_id, large_file_urls)

        # Add metrics
        metrics.add_metric(
            name="LargeFilesProcessed",
            unit=MetricUnit.Count,
            value=len(large_file_urls),
        )

        # Return updated job details with structured format
        response = {
            "jobId": job_id,
            "userId": user_id,
            "largeFileUrls": large_file_urls,  # Keep for internal workflow compatibility
            "status": "COMPLETED" if job_type == "LARGE_INDIVIDUAL" else "PROCESSING",
        }

        # Add structured downloadUrls for LARGE_INDIVIDUAL jobs
        if job_type == "LARGE_INDIVIDUAL":
            response["downloadUrls"] = {"files": large_file_urls}

        return response

    except Exception as e:
        logger.error(
            f"Error processing large files: {str(e)}",
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

                # Get the existing job's itemKey
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
                            ":error": f"Failed to process large files: {str(e)}",
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
                extra={"userId": event.get("userId"), "jobId": event.get("jobId")},
            )

        metrics.add_metric(
            name="LargeFileProcessingErrors", unit=MetricUnit.Count, value=1
        )

        # Re-raise the exception to be handled by Step Functions
        raise
