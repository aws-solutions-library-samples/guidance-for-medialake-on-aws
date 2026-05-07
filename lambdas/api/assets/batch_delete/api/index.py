"""
Batch Asset Deletion API Handler
=================================
Handles batch deletion operations:
- DELETE /assets/batch - Create a new batch delete job
- GET /assets/batch/user - List user's batch delete jobs
- PUT /assets/batch/{jobId}/cancel - Cancel a running batch delete job

DELETE Request Body: {
    "assetIds": ["id1", "id2", ...],
    "confirmationToken": "DELETE"
}

GET Response: {
    "status": "success",
    "data": {
        "jobs": [...]
    }
}

PUT /assets/batch/{jobId}/cancel Response: {
    "status": "success",
    "message": "Job cancelled successfully"
}
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, validator

logger = Logger(service="batch-delete-api")
tracer = Tracer(service="batch-delete-api")
metrics = Metrics(namespace="BatchDeleteAPI", service="batch-delete-api")

dynamodb = boto3.resource("dynamodb")
stepfunctions = boto3.client("stepfunctions")

JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "")
STEP_FUNCTION_ARN = os.environ.get("BATCH_DELETE_STATE_MACHINE_ARN", "")
ASSET_TABLE_NAME = os.environ.get("MEDIALAKE_ASSET_TABLE", "")
MAX_ASSETS_PER_JOB = int(os.environ.get("MAX_ASSETS_PER_JOB", "10000"))

jobs_table = dynamodb.Table(JOBS_TABLE_NAME) if JOBS_TABLE_NAME else None
asset_table = dynamodb.Table(ASSET_TABLE_NAME) if ASSET_TABLE_NAME else None


class BatchDeleteRequest(BaseModel):
    """Request model for batch delete"""

    assetIds: List[str] = Field(
        ..., description="List of asset inventory IDs to delete"
    )
    confirmationToken: str = Field(
        ..., description="Confirmation token (must be 'DELETE')"
    )

    @validator("assetIds")
    def validate_asset_ids(cls, v):
        if not v:
            raise ValueError("assetIds cannot be empty")
        if len(v) > MAX_ASSETS_PER_JOB:
            raise ValueError(
                f"Cannot delete more than {MAX_ASSETS_PER_JOB} assets at once"
            )
        return list(set(v))

    @validator("confirmationToken")
    def validate_confirmation(cls, v):
        if v != "DELETE":
            raise ValueError("confirmationToken must be 'DELETE'")
        return v


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


class BatchDeleteError(Exception):
    """Custom exception for batch delete errors"""

    def __init__(
        self, message: str, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        super().__init__(message)
        self.status_code = status_code


def decimal_to_int(obj: Any) -> Any:
    """Recursively convert Decimal to int/float"""
    if isinstance(obj, list):
        return [decimal_to_int(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: decimal_to_int(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def get_user_id_from_event(event: Dict[str, Any]) -> str:
    """Extract user ID from API Gateway event"""
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    user_id = authorizer.get("sub") or authorizer.get("principalId")

    if not user_id:
        logger.warning("No user ID found in event", extra={"event": event})
        raise ValueError("User ID not found in request context")

    return user_id


@tracer.capture_method
def validate_permissions(
    user_id: str, asset_ids: List[str]
) -> tuple[List[str], List[str]]:
    """
    Validate user has permission to delete each asset.
    Returns: (authorized_ids, unauthorized_ids)
    """
    authorized = []
    unauthorized = []

    for asset_id in asset_ids:
        try:
            response = asset_table.get_item(Key={"InventoryID": asset_id})
            if "Item" in response:
                authorized.append(asset_id)
            else:
                logger.warning(f"Asset not found: {asset_id}")
                unauthorized.append(asset_id)
        except ClientError as e:
            logger.error(f"Error checking asset {asset_id}: {e}")
            unauthorized.append(asset_id)

    return authorized, unauthorized


@tracer.capture_method
def create_job(user_id: str, asset_ids: List[str]) -> Dict[str, Any]:
    """Create a batch delete job record in DynamoDB"""
    job_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()
    timestamp_iso = timestamp.isoformat()

    reverse_timestamp = 9999999999999999 - int(timestamp.timestamp() * 1000000)
    item_key = f"BATCH_DELETE#{job_id}#{reverse_timestamp}"

    # Format userId to match table schema (USER#{user_id})
    formatted_user_id = f"USER#{user_id}"

    job_record = {
        "itemKey": item_key,
        "userId": formatted_user_id,
        "jobId": job_id,
        "type": "BATCH_DELETE",
        "status": "PENDING",
        "totalAssets": len(asset_ids),
        "processedAssets": 0,
        "successfulAssets": 0,
        "failedAssets": 0,
        "createdAt": timestamp_iso,
        "updatedAt": timestamp_iso,
        "assetIds": asset_ids,
        "results": {"successful": [], "failed": []},
    }

    try:
        jobs_table.put_item(Item=job_record)
        logger.info(f"Created batch delete job: {job_id} for {len(asset_ids)} assets")
        metrics.add_metric("BatchDeleteJobsCreated", MetricUnit.Count, 1)
        metrics.add_metric("AssetsQueuedForDeletion", MetricUnit.Count, len(asset_ids))

        return {
            "jobId": job_id,
            "itemKey": item_key,
            "userId": formatted_user_id,
            "status": "PENDING",
            "totalAssets": len(asset_ids),
            "createdAt": timestamp_iso,
        }
    except ClientError as e:
        logger.error(f"Failed to create job record: {e}")
        raise BatchDeleteError(f"Failed to create job: {e}")


@tracer.capture_method
def update_job_execution_arn(
    job_id: str, user_id: str, item_key: str, execution_arn: str
) -> None:
    """Update job record with Step Functions execution ARN"""
    try:
        jobs_table.update_item(
            Key={"userId": user_id, "itemKey": item_key},
            UpdateExpression="SET executionArn = :arn, updatedAt = :updated_at",
            ExpressionAttributeValues={
                ":arn": execution_arn,
                ":updated_at": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"Updated job {job_id} with execution ARN")
    except ClientError as e:
        logger.error(f"Failed to update job with execution ARN: {e}")


@tracer.capture_method
def start_step_function_execution(
    job_id: str, user_id: str, asset_ids: List[str]
) -> str:
    """Start Step Functions execution for batch deletion"""
    try:
        execution_name = f"batch-delete-{job_id}"
        execution_input = {
            "jobId": job_id,
            "userId": user_id,
            "assetIds": asset_ids,
            "totalAssets": len(asset_ids),
        }

        response = stepfunctions.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=execution_name,
            input=json.dumps(execution_input),
        )

        execution_arn = response["executionArn"]
        logger.info(
            f"Started Step Functions execution for job {job_id}",
            extra={"execution_arn": execution_arn, "asset_count": len(asset_ids)},
        )
        metrics.add_metric("StepFunctionsExecutionsStarted", MetricUnit.Count, 1)

        return execution_arn

    except ClientError as e:
        logger.error(f"Failed to start Step Functions execution: {e}")
        raise BatchDeleteError(f"Failed to start deletion workflow: {e}")


@tracer.capture_method
def query_user_delete_jobs(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Query all batch delete jobs for a user"""
    try:
        # Format userId to match table schema (USER#{user_id})
        formatted_user_id = f"USER#{user_id}"

        response = jobs_table.query(
            KeyConditionExpression="userId = :userId AND begins_with(itemKey, :prefix)",
            ExpressionAttributeValues={
                ":userId": formatted_user_id,
                ":prefix": "BATCH_DELETE#",
            },
            ScanIndexForward=False,
            Limit=limit,
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} batch delete jobs for user {user_id}")

        jobs = []
        for item in items:
            job = {
                "jobId": item.get("jobId"),
                "status": item.get("status", "UNKNOWN"),
                "totalAssets": item.get("totalAssets", 0),
                "processedAssets": item.get("processedAssets", 0),
                "failedAssets": item.get("failedAssets", 0),
                "createdAt": item.get("createdAt"),
                "updatedAt": item.get("updatedAt"),
                "executionArn": item.get("executionArn"),
            }

            if item.get("completedAt"):
                job["completedAt"] = item["completedAt"]

            if item.get("error"):
                job["error"] = item["error"]

            job["progress"] = 0
            if job["status"] in ["PROCESSING", "COMPLETED", "FAILED"]:
                total = job.get("totalAssets", 0)
                if total > 0:
                    processed = job.get("processedAssets", 0)
                    job["progress"] = int((processed / total) * 100)

            jobs.append(decimal_to_int(job))

        jobs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return jobs

    except Exception as e:
        logger.error(f"Error querying batch delete jobs: {str(e)}", exc_info=True)
        raise


@tracer.capture_method
def get_job(user_id: str, job_id: str) -> Dict[str, Any]:
    """Get a specific batch delete job for a user"""
    try:
        formatted_user_id = f"USER#{user_id}"

        response = jobs_table.query(
            KeyConditionExpression="userId = :userId AND begins_with(itemKey, :prefix)",
            ExpressionAttributeValues={
                ":userId": formatted_user_id,
                ":prefix": f"BATCH_DELETE#{job_id}#",
            },
            Limit=1,
        )

        items = response.get("Items", [])
        if not items:
            raise BatchDeleteError(f"Job {job_id} not found", HTTPStatus.NOT_FOUND)

        return items[0]
    except BatchDeleteError:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {str(e)}", exc_info=True)
        raise BatchDeleteError(f"Failed to fetch job: {str(e)}")


@tracer.capture_method
def cancel_job(user_id: str, job_id: str) -> Dict[str, Any]:
    """Cancel a running batch delete job"""
    try:
        job = get_job(user_id, job_id)

        current_status = job.get("status")
        if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
            return {
                "status": "info",
                "message": f"Job is already {current_status.lower()}",
                "job": {
                    "jobId": job_id,
                    "status": current_status,
                },
            }

        execution_arn = job.get("executionArn")
        if not execution_arn:
            raise BatchDeleteError(
                "Job execution ARN not found", HTTPStatus.BAD_REQUEST
            )

        try:
            stepfunctions.stop_execution(
                executionArn=execution_arn,
                error="UserCancelled",
                cause="User requested cancellation",
            )
            logger.info(f"Stopped Step Functions execution for job {job_id}")
            metrics.add_metric("BatchDeleteJobsCancelled", MetricUnit.Count, 1)
        except stepfunctions.exceptions.ExecutionDoesNotExist:
            logger.warning(
                f"Execution {execution_arn} does not exist or already stopped"
            )
        except ClientError as e:
            logger.error(f"Error stopping execution: {e}")
            raise BatchDeleteError(f"Failed to stop execution: {e}")

        jobs_table.update_item(
            Key={
                "userId": job["userId"],
                "itemKey": job["itemKey"],
            },
            UpdateExpression="SET #status = :cancelled, updatedAt = :updated_at, cancelledAt = :cancelled_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":cancelled": "CANCELLED",
                ":updated_at": datetime.utcnow().isoformat(),
                ":cancelled_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"Marked job {job_id} as cancelled")

        return {
            "status": "success",
            "message": "Job cancelled successfully",
            "job": {
                "jobId": job_id,
                "status": "CANCELLED",
                "processedAssets": job.get("processedAssets", 0),
                "totalAssets": job.get("totalAssets", 0),
            },
        }

    except BatchDeleteError:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}", exc_info=True)
        raise BatchDeleteError(f"Failed to cancel job: {str(e)}")


def create_response(
    status: int, msg: str, data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create standardized API Gateway response"""
    body = {
        "status": "success" if status < 400 else "error",
        "message": msg,
        "data": data or {},
    }

    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,DELETE,PUT,OPTIONS",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


@tracer.capture_method
def handle_create_job(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle DELETE request to create a batch delete job"""
    if not jobs_table:
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Jobs table not configured"
        )

    if not STEP_FUNCTION_ARN:
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Batch delete state machine not configured",
        )

    try:
        body = json.loads(event.get("body", "{}"))
        request = BatchDeleteRequest(**body)
    except ValueError as e:
        return create_response(HTTPStatus.BAD_REQUEST, f"Invalid request: {str(e)}")

    user_id = get_user_id_from_event(event)

    logger.info(
        f"Batch delete request from user {user_id}",
        extra={"asset_count": len(request.assetIds)},
    )

    authorized_ids, unauthorized_ids = validate_permissions(user_id, request.assetIds)

    if not authorized_ids:
        return create_response(
            HTTPStatus.FORBIDDEN,
            "No assets authorized for deletion",
            {"unauthorizedAssets": unauthorized_ids, "authorizedCount": 0},
        )

    if unauthorized_ids:
        logger.warning(
            f"User {user_id} not authorized for {len(unauthorized_ids)} assets",
            extra={"unauthorized": unauthorized_ids[:10]},
        )

    job_info = create_job(user_id, authorized_ids)
    job_id = job_info["jobId"]

    execution_arn = start_step_function_execution(job_id, user_id, authorized_ids)

    update_job_execution_arn(
        job_id, job_info["userId"], job_info["itemKey"], execution_arn
    )

    response_data = {
        "jobId": job_id,
        "status": job_info["status"],
        "totalAssets": job_info["totalAssets"],
        "createdAt": job_info["createdAt"],
        "executionArn": execution_arn,
        "unauthorizedAssets": len(unauthorized_ids) if unauthorized_ids else 0,
    }

    if unauthorized_ids:
        response_data["message"] = (
            f"Job created for {len(authorized_ids)} assets. "
            f"{len(unauthorized_ids)} assets were not authorized or not found."
        )

    return create_response(
        HTTPStatus.OK,
        f"Batch delete job created for {len(authorized_ids)} assets",
        response_data,
    )


@tracer.capture_method
def handle_list_jobs(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET request to list user's batch delete jobs"""
    try:
        user_id = get_user_id_from_event(event)
        logger.info(f"Fetching batch delete jobs for user: {user_id}")

        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", 50))

        jobs = query_user_delete_jobs(user_id, limit)

        response_body = {
            "status": "success",
            "message": f"Retrieved {len(jobs)} batch delete jobs",
            "data": {"jobs": jobs},
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "GET,DELETE,OPTIONS",
            },
            "body": json.dumps(response_body, cls=DecimalEncoder),
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return create_response(HTTPStatus.UNAUTHORIZED, "Unauthorized")

    except Exception as e:
        logger.error(f"Error in handler: {str(e)}", exc_info=True)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Failed to retrieve batch delete jobs",
        )


@tracer.capture_method
def handle_cancel_job(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PUT request to cancel a batch delete job"""
    try:
        user_id = get_user_id_from_event(event)
        path_params = event.get("pathParameters") or {}
        job_id = path_params.get("jobId")

        if not job_id:
            return create_response(
                HTTPStatus.BAD_REQUEST,
                "Job ID is required",
            )

        logger.info(f"Cancelling batch delete job {job_id} for user {user_id}")

        result = cancel_job(user_id, job_id)

        return {
            "statusCode": HTTPStatus.OK,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "GET,DELETE,PUT,OPTIONS",
            },
            "body": json.dumps(result, cls=DecimalEncoder),
        }

    except BatchDeleteError as e:
        return create_response(e.status_code, str(e))
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return create_response(HTTPStatus.UNAUTHORIZED, "Unauthorized")
    except Exception as e:
        logger.error(f"Error cancelling job: {str(e)}", exc_info=True)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Failed to cancel batch delete job",
        )


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], _ctx: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for batch asset deletion operations.
    Supports:
    - DELETE /assets/batch - Create batch delete job
    - GET /assets/batch/user - List user's jobs
    - PUT /assets/batch/{jobId}/cancel - Cancel a job
    """
    try:
        http_method = event.get("httpMethod", "")
        path = event.get("path", "")

        logger.info(f"Batch delete API: {http_method} {path}")

        if http_method == "DELETE" and not path.endswith("/cancel"):
            return handle_create_job(event)
        elif http_method == "GET" and path.endswith("/user"):
            return handle_list_jobs(event)
        elif http_method == "PUT" and path.endswith("/cancel"):
            return handle_cancel_job(event)
        else:
            return create_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                f"Method {http_method} not allowed for path {path}",
            )

    except BatchDeleteError as e:
        logger.error(f"Batch delete error: {e}")
        return create_response(e.status_code, str(e))

    except Exception as e:
        logger.error(
            "Unexpected error in batch delete", extra={"error": str(e)}, exc_info=True
        )
        metrics.add_metric("BatchDeleteErrors", MetricUnit.Count, 1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, f"An unexpected error occurred: {str(e)}"
        )
