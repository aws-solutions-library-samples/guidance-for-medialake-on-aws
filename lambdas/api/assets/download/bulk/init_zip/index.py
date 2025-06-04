"""
Bulk Download Initialize Zip Lambda

This Lambda function initializes a zip file on shared storage (EFS) by:
1. Creating a directory structure for the job
2. Creating an empty zip file
3. Updating the job record with the zip file path

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
- Metrics and monitoring
"""

import os
import time
import zipfile
import tempfile
from typing import Dict, Any
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-init-zip")
tracer = Tracer(service="bulk-download-init-zip")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-init-zip")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB table
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)


@tracer.capture_method
def update_job_with_zip_path(job_id: str, zip_path: str) -> None:
    """
    Update the job record with the zip file path.
    
    Args:
        job_id: ID of the job to update
        zip_path: Path to the zip file
        
    Raises:
        Exception: If job update fails
    """
    try:
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #zipPath = :zipPath, #completedParts = :completedParts, #updatedAt = :updatedAt",
            ExpressionAttributeNames={
                "#zipPath": "zipPath",
                "#completedParts": "completedParts",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":zipPath": zip_path,
                ":completedParts": 0,  # Initialize completed parts counter for multipart upload tracking
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        logger.info(
            "Updated job with zip path",
            extra={
                "jobId": job_id,
                "zipPath": zip_path,
            },
        )
    
    except ClientError as e:
        logger.error(
            "Failed to update job with zip path",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job with zip path: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for initializing a zip file on shared storage.
    
    Args:
        event: Event containing job details
        context: Lambda context
        
    Returns:
        Dictionary containing the path to the initialized zip file
    """
    job_id = event.get("jobId")
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    # Create job directory on EFS
    job_dir = os.path.join(EFS_MOUNT_PATH, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Create zip directory
    zip_dir = os.path.join(job_dir, "zip")
    os.makedirs(zip_dir, exist_ok=True)
    
    # Create an empty zip file
    zip_path = os.path.join(zip_dir, f"{job_id}.zip")
    
    try:
        # Create an empty zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as _:
            pass
        
        # Update job record with zip path
        update_job_with_zip_path(job_id, zip_path)
        
        # Add metrics
        metrics.add_metric(name="ZipInitialized", unit=MetricUnit.Count, value=1)
        
        return {
            "jobId": job_id,
            "zipPath": zip_path,
            "status": "INITIALIZED",
        }
    
    except Exception as e:
        logger.error(
            f"Error initializing zip file: {str(e)}",
            exc_info=True,
            extra={"jobId": job_id},
        )
        
        # Add metrics
        metrics.add_metric(name="ZipInitializationErrors", unit=MetricUnit.Count, value=1)
        
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
                    ":error": f"Failed to initialize zip file: {str(e)}",
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