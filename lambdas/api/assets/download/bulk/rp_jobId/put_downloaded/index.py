"""
Bulk Download Mark Downloaded Lambda

This Lambda function marks a bulk download job as downloaded by:
1. Validating the request
2. Updating the job record in DynamoDB
3. Optionally triggering cleanup processes

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Input validation and error handling
- Metrics and monitoring
"""

import json
import os
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-mark-downloaded")
tracer = Tracer(service="bulk-download-mark-downloaded")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-mark-downloaded"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
USER_TABLE_NAME = os.environ["USER_TABLE_NAME"]

# Initialize DynamoDB table
user_table = dynamodb.Table(USER_TABLE_NAME)


class BulkDownloadError(Exception):
    """Custom exception for bulk download errors"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


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
        BulkDownloadError: If job retrieval fails or job not found
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
            raise BulkDownloadError(f"Job {job_id} not found", 404)

        # Find the job that belongs to this user
        job_item = None
        for item in response["Items"]:
            if item.get("userId") == formatted_user_id:
                job_item = item
                break

        if not job_item:
            raise BulkDownloadError(f"Job {job_id} not found for user", 404)

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
        raise BulkDownloadError(f"Failed to retrieve job details: {str(e)}", 500)


@tracer.capture_method
def mark_job_downloaded(job_id: str, user_id: str, item_key: str) -> Dict[str, Any]:
    """
    Mark a job as downloaded in DynamoDB using user table pattern.

    Args:
        job_id: ID of the job to update
        user_id: ID of the user who owns the job
        item_key: The itemKey for the job record

    Returns:
        Updated job details

    Raises:
        BulkDownloadError: If job update fails
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        response = user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression="SET #status = :status, #downloadedAt = :downloadedAt, #updatedAt = :updatedAt",
            ExpressionAttributeNames={
                "#status": "status",
                "#downloadedAt": "downloadedAt",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "DOWNLOADED",
                ":downloadedAt": datetime.utcnow().isoformat(),
                ":updatedAt": datetime.utcnow().isoformat(),
            },
            ReturnValues="ALL_NEW",
        )

        if "Attributes" not in response:
            raise BulkDownloadError(f"Failed to update job {job_id}", 500)

        logger.info(
            "Marked job as downloaded",
            extra={
                "jobId": job_id,
                "userId": user_id,
            },
        )

        metrics.add_metric(name="JobsMarkedDownloaded", unit=MetricUnit.Count, value=1)

        return response["Attributes"]

    except ClientError as e:
        logger.error(
            "Failed to mark job as downloaded",
            extra={
                "error": str(e),
                "jobId": job_id,
                "userId": user_id,
            },
        )
        raise BulkDownloadError(f"Failed to mark job as downloaded: {str(e)}", 500)


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body, default=str),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler for marking a bulk download job as downloaded.

    Args:
        event: API Gateway event
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
            raise BulkDownloadError("User ID not found in request", 401)

        # Get job ID from path parameters
        job_id = event.get("pathParameters", {}).get("jobId")
        if not job_id:
            raise BulkDownloadError("Missing job ID", 400)

        # Get job details
        job = get_job_details(job_id, user_id)

        # Verify that the job is in a valid state to be marked as downloaded
        if job.get("status") != "COMPLETED":
            raise BulkDownloadError(
                f"Job cannot be marked as downloaded. Current status: {job.get('status')}",
                400,
            )

        # Parse request body
        if event.get("body"):
            try:
                json.loads(event["body"])
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in request body")
                # Continue with empty body

        # Mark job as downloaded
        updated_job = mark_job_downloaded(job_id, user_id, job.get("itemKey"))

        # Return success response
        return create_response(
            200,
            {
                "status": "success",
                "message": "Job marked as downloaded",
                "data": {
                    "jobId": job_id,
                    "status": updated_job.get("status"),
                    "downloadedAt": updated_job.get("downloadedAt"),
                },
            },
        )

    except BulkDownloadError as e:
        logger.warning(
            f"Bulk download error: {e.message}",
            extra={"statusCode": e.status_code},
        )
        return create_response(
            e.status_code,
            {
                "status": "error",
                "message": e.message,
                "data": {},
            },
        )

    except Exception as e:
        logger.error(
            f"Unexpected error: {str(e)}",
            exc_info=True,
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return create_response(
            500,
            {
                "status": "error",
                "message": "Internal server error",
                "data": {},
            },
        )
