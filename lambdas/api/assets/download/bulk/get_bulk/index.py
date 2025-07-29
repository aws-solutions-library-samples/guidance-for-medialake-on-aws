"""
Bulk Download Status Lambda

This Lambda function retrieves the status of a bulk download job by:
1. Retrieving job details from DynamoDB
2. Returning job status, progress, and download URLs if available
3. Handling different API endpoints for single job status and user job listing

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
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
logger = Logger(service="bulk-download-status")
tracer = Tracer(service="bulk-download-status")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-status")

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
def get_user_jobs(
    user_id: str, limit: int = 10, next_token: str = None
) -> Dict[str, Any]:
    """
    Retrieve all bulk download jobs for a user using user table pattern.

    Args:
        user_id: ID of the user
        limit: Maximum number of jobs to return
        next_token: Token for pagination

    Returns:
        Dictionary containing jobs and pagination token

    Raises:
        BulkDownloadError: If job retrieval fails
    """
    try:
        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        query_params = {
            "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
            "ExpressionAttributeValues": {
                ":userId": formatted_user_id,
                ":prefix": "BULK_DOWNLOAD#",
            },
            "ScanIndexForward": False,  # Sort by reverse timestamp (newest first)
            "Limit": limit,
        }

        # Add pagination token if provided
        if next_token:
            try:
                query_params["ExclusiveStartKey"] = json.loads(next_token)
            except json.JSONDecodeError:
                raise BulkDownloadError("Invalid pagination token", 400)

        response = user_table.query(**query_params)

        # Prepare pagination token for next request
        pagination_token = None
        if "LastEvaluatedKey" in response:
            pagination_token = json.dumps(response["LastEvaluatedKey"])

        return {"jobs": response.get("Items", []), "nextToken": pagination_token}

    except ClientError as e:
        logger.error(
            "Failed to retrieve user jobs",
            extra={
                "error": str(e),
                "userId": user_id,
            },
        )
        raise BulkDownloadError(f"Failed to retrieve user jobs: {str(e)}", 500)


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


@tracer.capture_method
def format_job_response(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format job details for API response.

    Args:
        job: Raw job details from DynamoDB

    Returns:
        Formatted job details
    """
    # Calculate time remaining until expiration
    expires_at = job.get("expiresAt", 0)
    current_time = int(datetime.utcnow().timestamp())
    expires_in = max(0, expires_at - current_time) if expires_at else 0

    # Format response
    response = {
        "jobId": job.get("jobId"),
        "status": job.get("status"),
        "progress": job.get("progress", 0),
        "createdAt": job.get("createdAt"),
        "updatedAt": job.get("updatedAt"),
        "totalSize": job.get("totalSize", 0),
        "smallFilesCount": job.get("smallFilesCount", 0),
        "largeFilesCount": job.get("largeFilesCount", 0),
    }

    # Add found and missing assets if available
    found_assets = job.get("foundAssets")
    if found_assets:
        response["foundAssets"] = found_assets
        response["foundAssetsCount"] = len(found_assets)

    missing_assets = job.get("missingAssets")
    if missing_assets:
        response["missingAssets"] = missing_assets
        response["missingAssetsCount"] = len(missing_assets)

    # Add download URLs if available
    if job.get("status") == "COMPLETED" and job.get("downloadUrls"):
        download_urls = job.get("downloadUrls")

        # Convert old format (flat array) to new format (structured object) if needed
        if isinstance(download_urls, list):
            # Old format - convert to new structured format based on job type
            job_type = job.get("jobType", "")
            small_files_count = job.get("smallFilesCount", 0)
            large_files_count = job.get("largeFilesCount", 0)

            if job_type == "MIXED" or (small_files_count > 0 and large_files_count > 0):
                # For mixed jobs, first URL is ZIP, rest are large files
                structured_urls = {
                    "zippedFiles": download_urls[0] if download_urls else None,
                    "files": download_urls[1:] if len(download_urls) > 1 else [],
                }
            elif job_type == "LARGE_INDIVIDUAL" or (
                large_files_count > 0 and small_files_count == 0
            ):
                # All URLs are large files
                structured_urls = {"files": download_urls}
            elif job_type == "SMALL" or (
                small_files_count > 0 and large_files_count == 0
            ):
                # Only small files (ZIP)
                structured_urls = {
                    "zippedFiles": download_urls[0] if download_urls else None
                }
            elif job_type == "SINGLE_FILE":
                # Single file treated as large file
                structured_urls = {"singleFiles": download_urls}
            else:
                # Unknown job type, try to infer from counts or keep as is for backward compatibility
                if small_files_count > 0 and large_files_count > 0:
                    structured_urls = {
                        "zippedFiles": download_urls[0] if download_urls else None,
                        "files": download_urls[1:] if len(download_urls) > 1 else [],
                    }
                elif large_files_count > 0:
                    structured_urls = {"files": download_urls}
                elif small_files_count > 0:
                    structured_urls = {
                        "zippedFiles": download_urls[0] if download_urls else None
                    }
                else:
                    structured_urls = download_urls

            response["downloadUrls"] = structured_urls
        else:
            # New format - already structured
            response["downloadUrls"] = download_urls

        # Count total URLs for backward compatibility
        if isinstance(download_urls, list):
            response["downloadUrlsCount"] = len(download_urls)
        else:
            # Count URLs in structured format
            total_count = 0
            if isinstance(download_urls, dict):
                if download_urls.get("zippedFiles"):
                    total_count += 1
                if download_urls.get("files"):
                    total_count += len(download_urls.get("files", []))
            response["downloadUrlsCount"] = total_count

        response["expiresAt"] = job.get("expiresAt")
        response["expiresIn"] = expires_in

        # Add job type specific information based on file counts
        small_files_count = job.get("smallFilesCount", 0)
        large_files_count = job.get("largeFilesCount", 0)

        if small_files_count > 0 and large_files_count > 0:
            response["description"] = (
                f"Mixed download: {small_files_count} zipped files + {large_files_count} large files"
            )
        elif large_files_count > 0 and small_files_count == 0:
            if large_files_count == 1:
                response["description"] = "Single file download"
            else:
                response["description"] = (
                    f"Individual downloads: {large_files_count} large files"
                )
        elif small_files_count > 0 and large_files_count == 0:
            response["description"] = f"Zip download: {small_files_count} zipped files"

    # Add error if available
    if job.get("error"):
        response["error"] = job.get("error")

    return response


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler for retrieving bulk download job status.

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

        # Check if this is a request for a specific job or a list of user jobs
        path = event.get("path", "")

        if path.endswith("/user"):
            # Get query parameters
            query_params = event.get("queryStringParameters", {}) or {}
            limit = int(query_params.get("limit", "10"))
            next_token = query_params.get("nextToken")

            # Get user jobs
            result = get_user_jobs(user_id, limit, next_token)

            # Format response
            jobs = [format_job_response(job) for job in result["jobs"]]

            return create_response(
                200,
                {
                    "status": "success",
                    "message": "User jobs retrieved successfully",
                    "data": {
                        "jobs": jobs,
                        "nextToken": result["nextToken"],
                    },
                },
            )
        else:
            # Get job ID from path parameters
            job_id = event.get("pathParameters", {}).get("jobId")
            if not job_id:
                raise BulkDownloadError("Missing job ID", 400)

            # Get job details
            job = get_job_details(job_id, user_id)

            # Format response
            formatted_job = format_job_response(job)

            return create_response(
                200,
                {
                    "status": "success",
                    "message": "Job status retrieved successfully",
                    "data": formatted_job,
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
