"""
Bulk Download Single File Lambda

This Lambda function handles single file downloads by:
1. Retrieving asset details from DynamoDB
2. Generating a presigned URL for direct download
3. Updating the job record with the download URL

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""
import unicodedata
import json
import os
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from botocore.config import Config

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-single-file")
tracer = Tracer(service="bulk-download-single-file")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-single-file")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version='s3v4'))

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
ASSET_TABLE = os.environ["ASSET_TABLE"]

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds
MAX_RETRIES = 3  # Maximum number of retries for operations


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
            unicodedata
                .normalize('NFKD', raw)
                .encode('ascii', 'ignore')
                .decode('ascii')
            )
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': f'attachment; filename="{safe}"',
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
def update_job_completed(job_id: str, download_url: str) -> None:
    """
    Update the job record with download URL and mark as completed.
    
    Args:
        job_id: ID of the job to update
        download_url: Presigned download URL
        
    Raises:
        Exception: If job update fails
    """
    try:
        # Calculate expiration time (7 days from now)
        expiration_time = datetime.utcnow() + timedelta(days=7)
        
        bulk_download_table.update_item(
            Key={"jobId": job_id},
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
                ":downloadUrls": [download_url],
                ":expiresAt": int(expiration_time.timestamp()),
                ":progress": 100,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        logger.info(
            "Updated job as completed with single file URL",
            extra={
                "jobId": job_id,
                "expiresAt": expiration_time.isoformat(),
            },
        )
    
    except ClientError as e:
        logger.error(
            "Failed to update job as completed",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job as completed: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for generating a presigned URL for a single file download.
    
    Args:
        event: Event containing job details
        context: Lambda context
        
    Returns:
        Updated job details with download URL
    """
    try:
        # Get job ID from event
        job_id = event.get("jobId")
        if not job_id:
            raise ValueError("Missing jobId in event")
        
        logger.info("Processing single file download job", extra={"jobId": job_id})
        
        # Get job details
        job = get_job_details(job_id)
        
        # Get asset IDs from job - should be just one
        asset_ids = job.get("foundAssets", [])
        if not asset_ids or len(asset_ids) != 1:
            raise ValueError(f"Expected exactly one asset, found {len(asset_ids)}")
        
        asset_id = asset_ids[0]
        
        # Get download options
        options = job.get("options", {})
        quality = options.get("quality", "original")  # original or proxy
        
        # Get asset details
        asset = get_asset_details(asset_id)
        
        # Determine file path based on quality option
        file_path = None
        bucket = None
        
        if quality == "proxy":
            # Look for proxy representation
            for rep in asset.get("DerivedRepresentations", []):
                if rep.get("Purpose") == "proxy":
                    storage_info = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                    bucket = storage_info.get("Bucket")
                    file_path = storage_info.get("ObjectKey", {}).get("FullPath")
                    break
            
            # If no proxy found, use original
            if not file_path:
                logger.warning(
                    "No proxy representation found, using original",
                    extra={"assetId": asset_id}
                )
                main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
                storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                bucket = storage_info.get("Bucket")
                file_path = storage_info.get("ObjectKey", {}).get("FullPath")
        else:
            # Use original representation
            main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
            storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            bucket = storage_info.get("Bucket")
            file_path = storage_info.get("ObjectKey", {}).get("FullPath")
        
        if not file_path or not bucket:
            raise ValueError(f"Could not determine file path or bucket for asset {asset_id}")
        
        # Get file name from path
        file_name = os.path.basename(file_path)
        
        # Generate presigned URL
        download_url = generate_presigned_url(bucket, file_path, file_name)
        
        # Update job as completed
        update_job_completed(job_id, download_url)
        
        # Add metrics
        metrics.add_metric(name="SingleFileDownloads", unit=MetricUnit.Count, value=1)
        
        # Return updated job details
        return {
            "jobId": job_id,
            "userId": job.get("userId"),
            "status": "COMPLETED",
            "downloadUrls": [download_url],
        }
    
    except Exception as e:
        logger.error(
            f"Error processing single file download: {str(e)}",
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
                        ":error": f"Failed to process single file download: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"jobId": event.get("jobId")},
            )
        
        metrics.add_metric(name="SingleFileDownloadErrors", unit=MetricUnit.Count, value=1)
        
        # Re-raise the exception to be handled by Step Functions
        raise