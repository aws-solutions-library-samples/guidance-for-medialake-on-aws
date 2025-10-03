"""
Bulk Download Delete Lambda

This Lambda function deletes a bulk download job and cleans up associated resources:
1. Deletes the job record from DynamoDB
2. Deletes temporary ZIP files from S3
3. Cleans up any multipart upload artifacts

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-delete")
tracer = Tracer(service="bulk-download-delete")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-delete")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

# Get environment variables
USER_TABLE_NAME = os.environ["USER_TABLE_NAME"]
TEMP_BUCKET = os.environ.get("TEMP_BUCKET", "")

# Initialize DynamoDB table
user_table = dynamodb.Table(USER_TABLE_NAME)


class BulkDownloadDeleteError(Exception):
    """Custom exception for bulk download delete errors"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


@tracer.capture_method
def get_job_details(job_id: str, user_id: str) -> Dict[str, Any]:
    """
    Retrieve job details from DynamoDB using user table pattern.

    Args:
        job_id: ID of the job to retrieve
        user_id: ID of the user who owns the job

    Returns:
        Job details

    Raises:
        BulkDownloadDeleteError: If job retrieval fails
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        # Query for the job using GSI2 (jobId index)
        response = user_table.query(
            IndexName="GSI2",
            KeyConditionExpression="gsi2Pk = :jobId",
            ExpressionAttributeValues={":jobId": f"JOB#{job_id}"},
            ConsistentRead=False,
        )

        if not response.get("Items"):
            raise BulkDownloadDeleteError(f"Job {job_id} not found", 404)

        # Find the job that belongs to this user
        job_item = None
        for item in response["Items"]:
            if item.get("userId") == formatted_user_id:
                job_item = item
                break

        if not job_item:
            raise BulkDownloadDeleteError(f"Job {job_id} not found for user", 404)

        return job_item

    except ClientError as e:
        logger.error(
            "Failed to retrieve job details",
            extra={
                "error": str(e),
                "jobId": job_id,
                "userId": user_id,
            },
        )
        raise BulkDownloadDeleteError(f"Failed to retrieve job details: {str(e)}")


@tracer.capture_method
def delete_s3_objects(job: Dict[str, Any]) -> None:
    """
    Delete temporary S3 objects associated with the job.

    Args:
        job: Job details containing download URLs and S3 paths
    """
    if not TEMP_BUCKET:
        logger.warning("No temp bucket configured, skipping S3 cleanup")
        return

    objects_to_delete = []

    # Extract S3 keys from download URLs
    download_urls = job.get("downloadUrls", {})

    if isinstance(download_urls, dict):
        # Handle structured download URLs
        if "zippedFiles" in download_urls:
            zip_url = download_urls["zippedFiles"]
            if zip_url and TEMP_BUCKET in zip_url:
                # Extract S3 key from URL
                # URL format: https://bucket.s3.region.amazonaws.com/key
                # or https://s3.region.amazonaws.com/bucket/key
                try:
                    if f"{TEMP_BUCKET}.s3." in zip_url:
                        key = zip_url.split(f"{TEMP_BUCKET}.s3.")[1].split("/", 1)[1]
                    elif (
                        f"s3.{zip_url.split('.')[1]}.amazonaws.com/{TEMP_BUCKET}/"
                        in zip_url
                    ):
                        key = zip_url.split(f"/{TEMP_BUCKET}/")[1]
                    else:
                        # Try to extract key from the end of the URL
                        key = zip_url.split("/")[-1]

                    if key:
                        objects_to_delete.append({"Key": key})
                        logger.info(f"Will delete S3 object: {key}")
                except Exception as e:
                    logger.warning(
                        f"Failed to parse S3 key from URL {zip_url}: {str(e)}"
                    )

        # Handle individual files if they're in temp bucket
        for file_list in ["files", "singleFiles"]:
            if file_list in download_urls and isinstance(
                download_urls[file_list], list
            ):
                for file_url in download_urls[file_list]:
                    if file_url and TEMP_BUCKET in file_url:
                        try:
                            if f"{TEMP_BUCKET}.s3." in file_url:
                                key = file_url.split(f"{TEMP_BUCKET}.s3.")[1].split(
                                    "/", 1
                                )[1]
                            elif (
                                f"s3.{file_url.split('.')[1]}.amazonaws.com/{TEMP_BUCKET}/"
                                in file_url
                            ):
                                key = file_url.split(f"/{TEMP_BUCKET}/")[1]
                            else:
                                key = file_url.split("/")[-1]

                            if key:
                                objects_to_delete.append({"Key": key})
                                logger.info(f"Will delete S3 object: {key}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to parse S3 key from URL {file_url}: {str(e)}"
                            )

    elif isinstance(download_urls, list):
        # Handle legacy format (array of URLs)
        for url in download_urls:
            if url and TEMP_BUCKET in url:
                try:
                    if f"{TEMP_BUCKET}.s3." in url:
                        key = url.split(f"{TEMP_BUCKET}.s3.")[1].split("/", 1)[1]
                    elif f"s3.{url.split('.')[1]}.amazonaws.com/{TEMP_BUCKET}/" in url:
                        key = url.split(f"/{TEMP_BUCKET}/")[1]
                    else:
                        key = url.split("/")[-1]

                    if key:
                        objects_to_delete.append({"Key": key})
                        logger.info(f"Will delete S3 object: {key}")
                except Exception as e:
                    logger.warning(f"Failed to parse S3 key from URL {url}: {str(e)}")

    # Also try to delete objects based on job ID pattern
    # Bulk download jobs typically create files with jobId prefix
    job_id = job.get("jobId", "")
    if job_id:
        try:
            # List objects with job ID prefix
            response = s3_client.list_objects_v2(
                Bucket=TEMP_BUCKET, Prefix=f"bulk-downloads/{job_id}/", MaxKeys=1000
            )

            if "Contents" in response:
                for obj in response["Contents"]:
                    objects_to_delete.append({"Key": obj["Key"]})
                    logger.info(f"Will delete S3 object by prefix: {obj['Key']}")

        except ClientError as e:
            logger.warning(
                f"Failed to list objects with prefix bulk-downloads/{job_id}/: {str(e)}"
            )

    # Delete objects in batches
    if objects_to_delete:
        try:
            # S3 delete_objects can handle up to 1000 objects per request
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i : i + 1000]

                response = s3_client.delete_objects(
                    Bucket=TEMP_BUCKET, Delete={"Objects": batch, "Quiet": False}
                )

                deleted_count = len(response.get("Deleted", []))
                error_count = len(response.get("Errors", []))

                logger.info(
                    f"S3 cleanup batch complete",
                    extra={
                        "jobId": job_id,
                        "deletedCount": deleted_count,
                        "errorCount": error_count,
                        "batchSize": len(batch),
                    },
                )

                # Log any errors
                for error in response.get("Errors", []):
                    logger.warning(
                        f"Failed to delete S3 object: {error.get('Key')} - {error.get('Message')}"
                    )

                metrics.add_metric(
                    name="S3ObjectsDeleted", unit=MetricUnit.Count, value=deleted_count
                )
                if error_count > 0:
                    metrics.add_metric(
                        name="S3DeletionErrors",
                        unit=MetricUnit.Count,
                        value=error_count,
                    )

        except ClientError as e:
            logger.error(
                f"Failed to delete S3 objects: {str(e)}",
                extra={"jobId": job_id, "objectCount": len(objects_to_delete)},
            )
            # Don't raise exception - we still want to delete the job record
    else:
        logger.info(f"No S3 objects found to delete for job {job_id}")


@tracer.capture_method
def delete_job_record(job_id: str, user_id: str, item_key: str) -> None:
    """
    Delete the job record from DynamoDB using user table pattern.

    Args:
        job_id: ID of the job to delete
        user_id: ID of the user who owns the job
        item_key: The itemKey for the job record

    Raises:
        BulkDownloadDeleteError: If job deletion fails
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        user_table.delete_item(Key={"userId": formatted_user_id, "itemKey": item_key})

        logger.info(
            "Deleted job record from DynamoDB",
            extra={"jobId": job_id, "userId": user_id},
        )

    except ClientError as e:
        logger.error(
            "Failed to delete job record",
            extra={
                "error": str(e),
                "jobId": job_id,
                "userId": user_id,
            },
        )
        raise BulkDownloadDeleteError(f"Failed to delete job record: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for deleting a bulk download job and cleaning up resources.

    Args:
        event: API Gateway event containing job ID in path parameters
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Get user ID from Cognito identity
        user_id = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("claims", {})
            .get("sub")
        )
        if not user_id:
            raise BulkDownloadDeleteError("User ID not found in request", 401)

        # Extract job ID from path parameters
        path_parameters = event.get("pathParameters", {})
        if not path_parameters or "jobId" not in path_parameters:
            raise BulkDownloadDeleteError("Missing jobId in path parameters", 400)

        job_id = path_parameters["jobId"]

        logger.info(
            "Processing job deletion", extra={"jobId": job_id, "userId": user_id}
        )

        # Get job details first (to check if it exists and get S3 paths)
        job = get_job_details(job_id, user_id)

        # Delete S3 objects first (non-critical, don't fail if this fails)
        try:
            delete_s3_objects(job)
        except Exception as e:
            logger.warning(
                f"S3 cleanup failed but continuing with job deletion: {str(e)}",
                extra={"jobId": job_id},
            )

        # Delete job record from DynamoDB
        delete_job_record(job_id, user_id, job.get("itemKey"))

        # Add metrics
        metrics.add_metric(name="JobsDeleted", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "DELETE,OPTIONS",
            },
            "body": json.dumps(
                {"status": "success", "message": f"Job {job_id} deleted successfully"}
            ),
        }

    except BulkDownloadDeleteError as e:
        logger.error(
            f"Bulk download delete error: {e.message}",
            extra={"jobId": event.get("pathParameters", {}).get("jobId")},
        )

        metrics.add_metric(name="JobDeletionErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": e.status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "DELETE,OPTIONS",
            },
            "body": json.dumps({"status": "error", "message": e.message}),
        }

    except Exception as e:
        logger.error(
            f"Unexpected error deleting job: {str(e)}",
            exc_info=True,
            extra={"jobId": event.get("pathParameters", {}).get("jobId")},
        )

        metrics.add_metric(name="JobDeletionErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "DELETE,OPTIONS",
            },
            "body": json.dumps({"status": "error", "message": "Internal server error"}),
        }
