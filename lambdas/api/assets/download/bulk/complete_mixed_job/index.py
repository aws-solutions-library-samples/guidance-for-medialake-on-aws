"""
Bulk Download Complete Mixed Job Lambda

This Lambda function completes mixed jobs by:
1. Combining small file zip URL with large file individual URLs
2. Updating the job record with all download URLs
3. Marking the job as completed

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-complete-mixed-job")
tracer = Tracer(service="bulk-download-complete-mixed-job")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-complete-mixed-job")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)


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
def update_job_completed(job_id: str, download_urls: List[str]) -> None:
    """
    Update the job record with all download URLs and mark as completed.
    
    Args:
        job_id: ID of the job to update
        download_urls: List of all download URLs (zip + individual files)
        
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
            "Updated job as completed with mixed download URLs",
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


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for completing mixed jobs with combined download URLs.
    
    Args:
        event: Event containing job details and URLs
        context: Lambda context
        
    Returns:
        Updated job details with all download URLs
    """
    try:
        # Get job ID from event
        job_id = event.get("jobId")
        if not job_id:
            raise ValueError("Missing jobId in event")
        
        logger.info("Completing mixed job", extra={"jobId": job_id})
        
        # Get current job details to retrieve existing URLs
        job = get_job_details(job_id)
        
        # Collect download URLs in structured format
        small_file_zip_url = event.get("smallFileZipUrl")
        large_file_urls = event.get("largeFileUrls", [])
        
        # Also check if URLs are stored in the job record already
        existing_large_file_urls = job.get("largeFileUrls", [])
        if existing_large_file_urls:
            large_file_urls.extend(existing_large_file_urls)
        
        # Remove duplicates from large file URLs while preserving order
        seen = set()
        unique_large_urls = []
        for url in large_file_urls:
            if url not in seen:
                seen.add(url)
                unique_large_urls.append(url)
        
        # Create structured download URLs
        download_urls_structured = {}
        
        if small_file_zip_url:
            download_urls_structured["zippedFiles"] = small_file_zip_url
            logger.info(
                "Added small files zip URL",
                extra={"jobId": job_id, "url": small_file_zip_url}
            )
        
        if unique_large_urls:
            download_urls_structured["files"] = unique_large_urls
            logger.info(
                "Added large file individual URLs",
                extra={
                    "jobId": job_id,
                    "urlCount": len(unique_large_urls),
                }
            )
        
        if not download_urls_structured:
            raise ValueError("No download URLs found to complete the job")
        
        # Create flat list for database storage (backward compatibility)
        flat_urls = []
        if small_file_zip_url:
            flat_urls.append(small_file_zip_url)
        flat_urls.extend(unique_large_urls)
        
        # Update job as completed
        update_job_completed(job_id, flat_urls)
        
        # Add metrics
        metrics.add_metric(name="MixedJobsCompleted", unit=MetricUnit.Count, value=1)
        metrics.add_metric(name="TotalDownloadUrls", unit=MetricUnit.Count, value=len(flat_urls))
        
        # Return updated job details
        return {
            "jobId": job_id,
            "userId": job.get("userId"),
            "status": "COMPLETED",
            "downloadUrls": download_urls_structured,
        }
    
    except Exception as e:
        logger.error(
            f"Error completing mixed job: {str(e)}",
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
                        ":error": f"Failed to complete mixed job: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"jobId": event.get("jobId")},
            )
        
        metrics.add_metric(name="MixedJobCompletionErrors", unit=MetricUnit.Count, value=1)
        
        # Re-raise the exception to be handled by Step Functions
        raise