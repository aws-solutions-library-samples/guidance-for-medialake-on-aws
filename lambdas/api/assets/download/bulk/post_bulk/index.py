"""
Bulk Download Kickoff Lambda

This Lambda function initiates a bulk download job by:
1. Validating the request
2. Creating a job record in the user table using the pattern BULK_DOWNLOAD#{job_id}#{reverse_timestamp}
3. Starting a Step Functions execution to process the download

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Input validation and error handling
- Metrics and monitoring
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-kickoff")
tracer = Tracer(service="bulk-download-kickoff")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-kickoff")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
step_functions = boto3.client("stepfunctions")

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
STEP_FUNCTION_ARN = os.environ["STEP_FUNCTION_ARN"]

# Initialize DynamoDB table
user_table = dynamodb.Table(USER_TABLE_NAME)

# Constants
MAX_ASSETS_PER_JOB = 1000  # Maximum number of assets per job
JOB_EXPIRATION_DAYS = 7  # Number of days until job expires


class BulkDownloadError(Exception):
    """Custom exception for bulk download errors"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def timecode_to_frames(timecode: str) -> int:
    """Convert timecode string to total frame count."""
    normalized = timecode.replace(";", ":")
    parts = normalized.split(":")
    hours, minutes, seconds, frames = (
        int(parts[0]),
        int(parts[1]),
        int(parts[2]),
        int(parts[3]),
    )
    # This below math isn't strictly accurate from a frame-count perspective,
    # since the length of time a frame represents changes depending on the framerate
    # of the source (e.g. each frame in 30fps content contains twice the time of 60fps content).
    # Doesn't matter for this though, we just need a rough absolute int value for comparison
    # since the start/end times for a single piece of source content will resolve to the
    # framerate of that source.
    return (hours * 3600 + minutes * 60 + seconds) + frames


def is_start_before_end(start_time: str, end_time: str) -> bool:
    """Compare two timecodes to verify start is before end."""
    return timecode_to_frames(start_time) < timecode_to_frames(end_time)


@tracer.capture_method
def validate_request(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate the bulk download request.

    Args:
        body: Request body containing assetIds and options

    Returns:
        List of validated asset IDs

    Raises:
        BulkDownloadError: If validation fails
    """
    # Check if assetIds is present and is a list
    if "assetIds" not in body or not isinstance(body["assetIds"], list):
        raise BulkDownloadError(
            "Missing or invalid assetIds. Must be a list of objects.", 400
        )

    # Check if assetIds is empty
    if len(body["assetIds"]) == 0:
        raise BulkDownloadError("assetIds list cannot be empty.", 400)

    # Check if assetIds is list of objects
    if not all(isinstance(item, dict) for item in body["assetIds"]):
        raise BulkDownloadError("Each item in assetIds list must be an object.", 400)

    # Check if assetIds exceeds maximum limit
    if len(body["assetIds"]) > MAX_ASSETS_PER_JOB:
        raise BulkDownloadError(
            f"Too many assets requested. Maximum is {MAX_ASSETS_PER_JOB}.", 400
        )

    # Validate each asset ID
    assets = []
    for asset in body["assetIds"]:
        if (
            not isinstance(asset.get("assetId", None), str)
            or not asset.get("assetId", "").strip()
        ):
            raise BulkDownloadError("Each assetId must be a non-empty string.", 400)

        # Validate clipBoundary if present
        if "clipBoundary" in asset:
            clip = asset["clipBoundary"]
            if not isinstance(clip, dict):
                raise BulkDownloadError("clipBoundary must be an object.", 400)

            # Skip validation if clipBoundary is empty (indicates whole file operation)
            if clip:
                # Verify that both startTime and endTime keys are present for subclip operations
                if "startTime" not in clip or "endTime" not in clip:
                    raise BulkDownloadError(
                        "clipBoundary must contain both 'startTime' and 'endTime' keys.",
                        400,
                    )

                start_time = clip["startTime"]
                end_time = clip["endTime"]

                # Verify timecode format matches HH:MM:SS:FF or HH:MM:SS;FF
                timecode_pattern = r"^\d{2}:\d{2}:\d{2}[:;]\d{2}$"
                if not isinstance(start_time, str) or not re.match(
                    timecode_pattern, start_time
                ):
                    raise BulkDownloadError(
                        "startTime must be a string of numbers in format 'HH:MM:SS:FF' or 'HH:MM:SS;FF'.",
                        400,
                    )
                if not isinstance(end_time, str) or not re.match(
                    timecode_pattern, end_time
                ):
                    raise BulkDownloadError(
                        "endTime must be a string of numbers in format 'HH:MM:SS:FF' or 'HH:MM:SS;FF'.",
                        400,
                    )

                # Verify that startTime and endTime are not identical
                if start_time == end_time:
                    raise BulkDownloadError(
                        "startTime and endTime cannot be the same.", 400
                    )

                # Verify that endTime is not earlier than startTime
                if not is_start_before_end(start_time, end_time):
                    raise BulkDownloadError(
                        "endTime must be later than startTime.", 400
                    )
        else:
            raise BulkDownloadError("clipBoundary must be an object.", 400)
        assets.append(asset)

    # Removed to support multiple sub-clips from the same source asset
    # # Check for duplicates
    # if len(asset_ids) != len(set(asset_ids)):
    #     logger.warning("Duplicate asset IDs found. Removing duplicates.")
    #     asset_ids = list(set(asset_ids))

    return assets


@tracer.capture_method
def create_job_record(
    user_id: str, assets: List[Dict[str, Any]], options: Dict[str, Any]
) -> str:
    """
    Create a new bulk download job record in the user table.

    Args:
        user_id: ID of the user requesting the download
        asset_ids: List of asset IDs to download
        options: Download options

    Returns:
        Job ID of the created job

    Raises:
        BulkDownloadError: If job creation fails
    """
    job_id = str(uuid.uuid4())
    current_time = datetime.utcnow()
    expiration_time = current_time + timedelta(days=JOB_EXPIRATION_DAYS)

    # Generate a reverse timestamp for sorting (newest first)
    current_time_ms = int(time.time() * 1000)
    reverse_timestamp = str(9999999999999 - current_time_ms)

    # Format keys according to user table pattern
    formatted_user_id = f"USER#{user_id}"
    item_key = f"BULK_DOWNLOAD#{job_id}#{reverse_timestamp}"
    gsi1_sk = f"ITEM_TYPE#BULK_DOWNLOAD#{reverse_timestamp}"
    gsi2_pk = f"JOB#{job_id}"
    gsi2_sk = reverse_timestamp
    gsi3_pk = f"JOB#{job_id}"
    gsi3_sk = formatted_user_id

    try:
        # Create job record in user table
        user_table.put_item(
            Item={
                # Primary key
                "userId": formatted_user_id,
                "itemKey": item_key,
                # Job data
                "itemType": "BULK_DOWNLOAD",
                "jobId": job_id,
                "status": "INITIATED",
                "assetIds": assets,
                "options": options,
                "progress": 0,
                "totalFiles": len(assets),
                "createdAt": current_time.isoformat(),
                "updatedAt": current_time.isoformat(),
                "expiresAt": int(expiration_time.timestamp()),
                # GSI keys for querying
                "gsi1Sk": gsi1_sk,
                "gsi2Pk": gsi2_pk,
                "gsi2Sk": gsi2_sk,
                "gsi3Pk": gsi3_pk,
                "gsi3Sk": gsi3_sk,
            }
        )

        logger.info(
            "Created bulk download job in user table",
            extra={
                "jobId": job_id,
                "userId": user_id,
                "assetCount": len(assets),
                "itemKey": item_key,
            },
        )

        metrics.add_metric(name="JobsCreated", unit=MetricUnit.Count, value=1)

        return job_id

    except ClientError as e:
        logger.error(
            "Failed to create job record in user table",
            extra={
                "error": str(e),
                "userId": user_id,
                "assetCount": len(assets),
            },
        )
        metrics.add_metric(name="JobCreationErrors", unit=MetricUnit.Count, value=1)
        raise BulkDownloadError("Failed to create download job", 500)


@tracer.capture_method
def start_step_function(
    job_id: str, user_id: str, assets: List[Dict[str, Any]], options: Dict[str, Any]
) -> str:
    """
    Start a Step Functions execution to process the bulk download.

    Args:
        job_id: ID of the job to process
        user_id: ID of the user requesting the download
        asset_ids: List of asset IDs to download
        options: Download options

    Returns:
        Execution ARN of the started Step Functions execution

    Raises:
        BulkDownloadError: If starting the execution fails
    """
    try:
        # Prepare input for Step Functions
        step_function_input = {
            "jobId": job_id,
            "userId": user_id,
            "assetIds": assets,
            "options": options,
            "timestamp": int(time.time()),
            # Add empty arrays for Map states
            "smallFiles": [],
            "largeFiles": [],
        }

        # Start execution
        response = step_functions.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=f"bulk-download-{job_id}",
            input=json.dumps(step_function_input),
        )

        logger.info(
            "Started Step Functions execution",
            extra={
                "jobId": job_id,
                "executionArn": response["executionArn"],
            },
        )

        metrics.add_metric(
            name="StepFunctionsExecutionsStarted", unit=MetricUnit.Count, value=1
        )

        return response["executionArn"]

    except ClientError as e:
        logger.error(
            "Failed to start Step Functions execution",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )

        # Update job status to FAILED in user table
        try:
            formatted_user_id = f"USER#{user_id}"
            # We need to find the job by querying with jobId
            # For now, we'll use a simple approach - in production, you might want to store jobId in a separate GSI
            current_time_ms = int(time.time() * 1000)
            reverse_timestamp = str(9999999999999 - current_time_ms)
            item_key = f"BULK_DOWNLOAD#{job_id}#{reverse_timestamp}"

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
                    ":error": f"Failed to start processing: {str(e)}",
                    ":updatedAt": datetime.utcnow().isoformat(),
                },
            )
        except Exception as update_error:
            logger.error(
                "Failed to update job status after Step Functions error",
                extra={
                    "error": str(update_error),
                    "jobId": job_id,
                },
            )

        metrics.add_metric(
            name="StepFunctionsExecutionErrors", unit=MetricUnit.Count, value=1
        )
        raise BulkDownloadError("Failed to start download processing", 500)


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler for initiating a bulk download job.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Parse request body
        if not event.get("body"):
            raise BulkDownloadError("Missing request body", 400)

        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            raise BulkDownloadError("Invalid JSON in request body", 400)

        # Extract user ID from Cognito authorizer context
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # Get the user ID directly from the authorizer context
        user_id = authorizer.get("userId")

        if not user_id:
            logger.error("Missing user_id in authorizer context")
            raise BulkDownloadError("User ID not found in request", 401)

        # Validate request
        assets = validate_request(body)

        # Get download options
        options = body.get("options", {})

        # Create job record
        job_id = create_job_record(user_id, assets, options)

        # Start Step Functions execution
        execution_arn = start_step_function(job_id, user_id, assets, options)

        # Return success response
        return create_response(
            202,
            {
                "status": "success",
                "message": "Bulk download job initiated",
                "data": {
                    "jobId": job_id,
                    "status": "INITIATED",
                    "totalFiles": len(assets),
                    "executionArn": execution_arn,
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
