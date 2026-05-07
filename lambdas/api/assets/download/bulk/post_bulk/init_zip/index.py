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
import zipfile
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-init-zip")
tracer = Tracer(service="bulk-download-init-zip")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-init-zip")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB table
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs


@tracer.capture_method
def update_job_with_zip_path(user_id: str, job_id: str, zip_path: str) -> None:
    """
    Update the job record with the zip file path.

    Args:
        user_id: ID of the user who owns the job
        job_id: ID of the job to update
        zip_path: Path to the zip file

    Raises:
        Exception: If job update fails
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        # First, get the existing job record to find the correct itemKey
        response = user_table.query(
            IndexName="GSI2",
            KeyConditionExpression="gsi2Pk = :jobId",
            ExpressionAttributeValues={":jobId": f"JOB#{job_id}"},
            ConsistentRead=False,
        )

        if not response.get("Items"):
            logger.error(f"Job {job_id} not found for zip init")
            raise Exception(f"Job {job_id} not found")

        # Find the job that belongs to this user
        job_item = None
        for item in response["Items"]:
            if item.get("userId") == formatted_user_id:
                job_item = item
                break

        if not job_item:
            logger.error(f"Job {job_id} not found for user {user_id}")
            raise Exception(f"Job {job_id} not found for user")

        item_key = job_item.get("itemKey")
        if not item_key:
            logger.error(f"No itemKey found for job {job_id}")
            raise Exception(f"No itemKey found for job {job_id}")

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
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
                "userId": user_id,
                "jobId": job_id,
                "zipPath": zip_path,
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to update job with zip path",
            extra={
                "error": str(e),
                "userId": user_id,
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
    user_id = event.get("userId")

    if not job_id:
        raise ValueError("Missing jobId in event")
    if not user_id:
        raise ValueError("Missing userId in event")

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
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as _:
            pass

        # Update job record with zip path
        update_job_with_zip_path(user_id, job_id, zip_path)

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
        metrics.add_metric(
            name="ZipInitializationErrors", unit=MetricUnit.Count, value=1
        )

        # Update job status to FAILED
        try:
            # Format user_id only if it doesn't already have the USER# prefix
            formatted_user_id = (
                user_id if user_id.startswith("USER#") else f"USER#{user_id}"
            )

            # Get the existing job record to find the correct itemKey
            response = user_table.query(
                IndexName="GSI2",
                KeyConditionExpression="gsi2Pk = :jobId",
                ExpressionAttributeValues={":jobId": f"JOB#{job_id}"},
                ConsistentRead=False,
            )

            if response.get("Items"):
                # Find the job that belongs to this user
                job_item = None
                for item in response["Items"]:
                    if item.get("userId") == formatted_user_id:
                        job_item = item
                        break

                if job_item and job_item.get("itemKey"):
                    item_key = job_item.get("itemKey")

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
                            ":error": f"Failed to initialize zip file: {str(e)}",
                            ":updatedAt": datetime.utcnow().isoformat(),
                        },
                    )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"userId": user_id, "jobId": job_id},
            )

        # Re-raise the exception to be handled by Step Functions
        raise
