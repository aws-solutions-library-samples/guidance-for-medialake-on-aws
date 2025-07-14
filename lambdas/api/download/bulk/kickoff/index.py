"""
Bulk Download Kickoff Lambda

This Lambda function initiates a bulk download job by:
1. Validating the request
2. Creating a job record in DynamoDB
3. Starting a Step Functions execution to process the download

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Input validation and error handling
- Metrics and monitoring
"""

import json
import os
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
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
STEP_FUNCTION_ARN = os.environ["STEP_FUNCTION_ARN"]

# Initialize DynamoDB table
table = dynamodb.Table(BULK_DOWNLOAD_TABLE)

# Constants
MAX_ASSETS_PER_JOB = 1000  # Maximum number of assets per job
JOB_EXPIRATION_DAYS = 7  # Number of days until job expires


class BulkDownloadError(Exception):
    """Custom exception for bulk download errors"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@tracer.capture_method
def validate_request(body: Dict[str, Any]) -> List[str]:
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
        raise BulkDownloadError("Missing or invalid assetIds. Must be a list.", 400)

    # Check if assetIds is empty
    if len(body["assetIds"]) == 0:
        raise BulkDownloadError("assetIds list cannot be empty.", 400)

    # Check if assetIds exceeds maximum limit
    if len(body["assetIds"]) > MAX_ASSETS_PER_JOB:
        raise BulkDownloadError(
            f"Too many assets requested. Maximum is {MAX_ASSETS_PER_JOB}.", 400
        )

    # Validate each asset ID
    asset_ids = []
    for asset_id in body["assetIds"]:
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise BulkDownloadError("Each assetId must be a non-empty string.", 400)
        asset_ids.append(asset_id.strip())

    # Check for duplicates
    if len(asset_ids) != len(set(asset_ids)):
        logger.warning("Duplicate asset IDs found. Removing duplicates.")
        asset_ids = list(set(asset_ids))

    return asset_ids


@tracer.capture_method
def create_job_record(
    user_id: str, asset_ids: List[str], options: Dict[str, Any]
) -> str:
    """
    Create a new bulk download job record in DynamoDB.

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

    try:
        # Create job record
        table.put_item(
            Item={
                "jobId": job_id,
                "userId": user_id,
                "status": "INITIATED",
                "assetIds": asset_ids,
                "options": options,
                "progress": 0,
                "totalFiles": len(asset_ids),
                "createdAt": current_time.isoformat(),
                "updatedAt": current_time.isoformat(),
                "expiresAt": int(expiration_time.timestamp()),
            }
        )

        logger.info(
            "Created bulk download job",
            extra={
                "jobId": job_id,
                "userId": user_id,
                "assetCount": len(asset_ids),
            },
        )

        metrics.add_metric(name="JobsCreated", unit=MetricUnit.Count, value=1)

        return job_id

    except ClientError as e:
        logger.error(
            "Failed to create job record",
            extra={
                "error": str(e),
                "userId": user_id,
                "assetCount": len(asset_ids),
            },
        )
        metrics.add_metric(name="JobCreationErrors", unit=MetricUnit.Count, value=1)
        raise BulkDownloadError("Failed to create download job", 500)


@tracer.capture_method
def start_step_function(
    job_id: str, user_id: str, asset_ids: List[str], options: Dict[str, Any]
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
            "assetIds": asset_ids,
            "options": options,
            "timestamp": int(time.time()),
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

        # Update job status to FAILED
        try:
            table.update_item(
                Key={"jobId": job_id},
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

        # Get user ID from Cognito identity
        user_id = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("claims", {})
            .get("sub")
        )
        if not user_id:
            raise BulkDownloadError("User ID not found in request", 401)

        # Validate request
        asset_ids = validate_request(body)

        # Get download options
        options = body.get("options", {})

        # Create job record
        job_id = create_job_record(user_id, asset_ids, options)

        # Start Step Functions execution
        execution_arn = start_step_function(job_id, user_id, asset_ids, options)

        # Return success response
        return create_response(
            202,
            {
                "status": "success",
                "message": "Bulk download job initiated",
                "data": {
                    "jobId": job_id,
                    "status": "INITIATED",
                    "totalFiles": len(asset_ids),
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
