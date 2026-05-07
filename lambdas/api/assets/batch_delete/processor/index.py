"""
Bulk Delete Step Functions Worker
==================================
Processes single asset deletion within Step Functions Distributed Map.
Called by Step Functions for each asset in parallel.

Input:
{
    "jobId": "uuid",
    "assetId": "inventory-id",
    "userId": "user-id"
}

Output:
{
    "jobId": "uuid",
    "assetId": "inventory-id",
    "status": "success" | "error",
    "error": "error message" (optional)
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import boto3
from asset_deletion_service import AssetDeletionError, AssetDeletionService
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Powertools
logger = Logger(service="bulk-delete-worker")
tracer = Tracer(service="bulk-delete-worker")
metrics = Metrics(namespace="BulkDeleteWorker", service="bulk-delete-worker")

# AWS clients
dynamodb = boto3.resource("dynamodb")

# Environment variables
JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "")
ASSET_TABLE_NAME = os.environ.get("MEDIALAKE_ASSET_TABLE", "")

jobs_table = dynamodb.Table(JOBS_TABLE_NAME) if JOBS_TABLE_NAME else None


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


@tracer.capture_method
def get_job_key(job_id: str, user_id: str) -> Dict[str, str]:
    """
    Query to find the job's itemKey for DynamoDB operations.

    Args:
        job_id: The job ID
        user_id: The user ID (will be formatted as USER#{user_id})

    Returns:
        Dictionary with userId and itemKey for DynamoDB operations
    """
    formatted_user_id = f"USER#{user_id}"

    try:
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
            raise ValueError(f"Job {job_id} not found for user {user_id}")

        item = items[0]
        return {
            "userId": item["userId"],
            "itemKey": item["itemKey"],
        }
    except Exception as e:
        logger.error(f"Failed to query job key: {e}")
        raise


@tracer.capture_method
@tracer.capture_method
def update_job_progress(
    job_id: str, user_id: str, success: bool, total_assets: int
) -> None:
    """
    Atomically increment job progress counters after processing an asset.

    Args:
        job_id: The job ID
        user_id: The user ID
        success: Whether the asset was successfully deleted
        total_assets: Total number of assets in the job
    """
    try:
        # Get the correct DynamoDB keys
        job_key = get_job_key(job_id, user_id)
        timestamp = datetime.utcnow().isoformat()

        # First, atomically increment the counters
        update_expr_parts = [
            "SET #status = :status",
            "updatedAt = :timestamp",
            "processedAssets = if_not_exists(processedAssets, :zero) + :one",
        ]

        expr_attr_names = {"#status": "status"}
        expr_attr_values = {
            ":status": "PROCESSING",
            ":timestamp": timestamp,
            ":zero": 0,
            ":one": 1,
        }

        # Increment success or failure counter
        if success:
            update_expr_parts.append(
                "successfulAssets = if_not_exists(successfulAssets, :zero) + :one"
            )
        else:
            update_expr_parts.append(
                "failedAssets = if_not_exists(failedAssets, :zero) + :one"
            )

        update_expression = ", ".join(update_expr_parts)

        # Perform atomic update and get the new processedAssets value
        response = jobs_table.update_item(
            Key=job_key,
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW",
        )

        # Calculate progress percentage from the updated values
        processed_assets = int(response["Attributes"].get("processedAssets", 0))
        if total_assets > 0:
            progress = round((processed_assets / total_assets) * 100, 2)

            # Update progress in a separate operation
            jobs_table.update_item(
                Key=job_key,
                UpdateExpression="SET progress = :progress",
                ExpressionAttributeValues={":progress": Decimal(str(progress))},
            )

        logger.info(
            f"Updated job {job_id} progress",
            extra={
                "job_id": job_id,
                "success": success,
                "progress": progress if total_assets > 0 else 0,
            },
        )

    except Exception as e:
        # Don't fail the deletion if progress update fails
        logger.error(f"Failed to update job progress: {e}", exc_info=True)
        metrics.add_metric("ProgressUpdateErrors", MetricUnit.Count, 1)


@tracer.capture_method
def check_job_cancelled(job_id: str, user_id: str) -> bool:
    """
    Check if the job has been cancelled before processing.

    Args:
        job_id: The job ID
        user_id: The user ID

    Returns:
        True if job is cancelled, False otherwise
    """
    try:
        job_key = get_job_key(job_id, user_id)
        response = jobs_table.get_item(Key=job_key)

        item = response.get("Item")
        if not item:
            logger.warning(f"Job {job_id} not found during cancellation check")
            return False

        status = item.get("status")
        if status == "CANCELLED":
            logger.info(f"Job {job_id} is cancelled, skipping deletion")
            return True

        return False
    except Exception as e:
        logger.error(f"Error checking job cancellation status: {e}")
        # If we can't check, don't assume it's cancelled
        return False


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], _ctx: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for processing single asset deletion in Step Functions.

    Input from Step Functions Distributed Map:
    {
        "jobId": "uuid",
        "assetId": "inventory-id",
        "userId": "user-id"
    }

    Output:
    {
        "jobId": "uuid",
        "assetId": "inventory-id",
        "status": "success" | "error" | "skipped",
        "error": "error message" (optional)
    }
    """
    job_id = event.get("jobId")
    asset_id = event.get("assetId")
    user_id = event.get("userId")
    total_assets = event.get("totalAssets", 0)

    try:
        logger.info(
            f"Processing deletion for asset {asset_id} in job {job_id}",
            extra={"job_id": job_id, "asset_id": asset_id, "user_id": user_id},
        )

        # Check if job has been cancelled before proceeding
        if check_job_cancelled(job_id, user_id):
            logger.info(f"Skipping deletion of asset {asset_id} - job cancelled")
            metrics.add_metric("AssetDeletionsSkipped", MetricUnit.Count, 1)

            return {
                "jobId": job_id,
                "assetId": asset_id,
                "userId": user_id,
                "status": "skipped",
                "reason": "Job cancelled",
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Use centralized deletion service
        deletion_service = AssetDeletionService(
            dynamodb_table_name=ASSET_TABLE_NAME,
            logger=logger,
            metrics=metrics,
            tracer=tracer,
        )

        # Perform deletion
        result = deletion_service.delete_asset(
            inventory_id=asset_id, publish_event=True
        )

        logger.info(
            f"Successfully deleted asset {asset_id}",
            extra={
                "s3_objects": result.s3_objects_deleted,
                "opensearch_docs": result.opensearch_docs_deleted,
                "vectors": result.vectors_deleted,
            },
        )

        metrics.add_metric("AssetDeletionsProcessed", MetricUnit.Count, 1)

        # Update job progress in DynamoDB
        if jobs_table and job_id and user_id:
            update_job_progress(
                job_id, user_id, success=True, total_assets=total_assets
            )

        # Return success result
        return {
            "jobId": job_id,
            "assetId": asset_id,
            "userId": user_id,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "s3ObjectsDeleted": result.s3_objects_deleted,
                "openSearchDocsDeleted": result.opensearch_docs_deleted,
                "vectorsDeleted": result.vectors_deleted,
            },
        }

    except AssetDeletionError as e:
        logger.error(f"Deletion error for asset {asset_id}: {e}", exc_info=True)
        metrics.add_metric("AssetDeletionErrors", MetricUnit.Count, 1)

        # Update job progress in DynamoDB (mark as failed)
        if jobs_table and job_id and user_id:
            update_job_progress(
                job_id, user_id, success=False, total_assets=total_assets
            )

        # Return error result
        return {
            "jobId": job_id,
            "assetId": asset_id,
            "userId": user_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Unexpected error deleting asset {asset_id}: {e}", exc_info=True)
        metrics.add_metric("ProcessorErrors", MetricUnit.Count, 1)

        # Update job progress in DynamoDB (mark as failed)
        if jobs_table and job_id and user_id:
            update_job_progress(
                job_id, user_id, success=False, total_assets=total_assets
            )

        # Return error result
        return {
            "jobId": job_id,
            "assetId": asset_id,
            "userId": user_id,
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }
