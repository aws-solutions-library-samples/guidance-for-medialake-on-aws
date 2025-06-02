"""
Bulk Download Finalize Zip Lambda

This Lambda function finalizes a zip file on shared storage (EFS) by:
1. Uploading the final zip file to S3 with a 7-day expiration policy
2. Generating a presigned URL for the zip file
3. Updating the job record with the download URL
4. Cleaning up temporary files

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
- Metrics and monitoring
"""

import os
import time
import shutil
from typing import Dict, Any, List
from datetime import datetime, timedelta
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from botocore.config import Config

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-finalize-zip")
tracer = Tracer(service="bulk-download-finalize-zip")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-finalize-zip")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
# Configure S3 client with Signature Version 4 for KMS encryption support
s3 = boto3.client("s3", config=Config(signature_version='s3v4'))

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB table
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)

# Constants
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds
FINAL_ZIP_PREFIX = "temp/zip/final"


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
def upload_to_s3_with_expiration(local_path: str, job_id: str) -> str:
    """
    Upload a file to S3 with a 7-day expiration policy.
    
    Args:
        local_path: Local path of the file to upload
        job_id: Job ID for naming
        
    Returns:
        S3 key of the uploaded file
    """
    try:
        # Generate a unique key
        file_name = os.path.basename(local_path)
        s3_key = f"{FINAL_ZIP_PREFIX}/{job_id}/{file_name}"
        
        # Upload file
        s3.upload_file(
            local_path,
            MEDIA_ASSETS_BUCKET,
            s3_key,
            ExtraArgs={
                'Metadata': {
                    'job-id': job_id,
                    'expiration': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                }
            }
        )
        
        return s3_key
    
    except Exception as e:
        logger.error(
            "Failed to upload file to S3",
            extra={
                "error": str(e),
                "localPath": local_path,
                "jobId": job_id,
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
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': f'attachment; filename="{os.path.basename(key)}"',
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
def update_job_completed(job_id: str, download_urls: List[str]) -> None:
    """
    Update the job record with download URLs and mark as completed.
    
    Args:
        job_id: ID of the job to update
        download_urls: List of presigned download URLs
        
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
                ":downloadUrls": download_urls,
                ":expiresAt": int(expiration_time.timestamp()),
                ":progress": 100,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        logger.info(
            "Updated job as completed",
            extra={
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
            logger.info(f"Removed job directory: {job_dir}")
    
    except Exception as e:
        logger.warning(
            f"Error cleaning up temporary files: {str(e)}",
            extra={"jobId": job_id}
        )


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for finalizing a zip file.
    
    Args:
        event: Event containing job details
        context: Lambda context
        
    Returns:
        Dictionary containing the download URL for the final zip file
    """
    job_id = event.get("jobId")
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    try:
        # Get job details
        job = get_job_details(job_id)
        
        # Get the zip path from the job
        zip_path = job.get("zipPath")
        if not zip_path:
            raise ValueError(f"No zip path found for job {job_id}")
        
        # Ensure the zip file exists
        if not os.path.exists(zip_path):
            raise ValueError(f"Zip file not found at {zip_path}")
        
        # Upload the zip file to S3
        s3_key = upload_to_s3_with_expiration(zip_path, job_id)
        
        # Generate a presigned URL for the zip file
        download_url = generate_presigned_url(MEDIA_ASSETS_BUCKET, s3_key)
        
        # Update the job record with the download URL
        update_job_completed(job_id, [download_url])
        
        # Clean up temporary files
        cleanup_temp_files(job_id)
        
        # Add metrics
        metrics.add_metric(name="ZipFilesFinalized", unit=MetricUnit.Count, value=1)
        
        return {
            "jobId": job_id,
            "status": "COMPLETED",
            "downloadUrl": download_url,
        }
    
    except Exception as e:
        logger.error(
            f"Error finalizing zip file: {str(e)}",
            exc_info=True,
            extra={"jobId": job_id},
        )
        
        # Add metrics
        metrics.add_metric(name="ZipFinalizationErrors", unit=MetricUnit.Count, value=1)
        
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
                    ":error": f"Failed to finalize zip file: {str(e)}",
                    ":updatedAt": datetime.utcnow().isoformat(),
                },
            )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"jobId": job_id},
            )
        
        # Re-raise the exception to be handled by Step Functions
        raise