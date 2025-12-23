"""
Bulk Delete Results Aggregator
===============================
Aggregates results from Step Functions Distributed Map execution.
Updates final job status and creates notification.

Input from Step Functions:
{
    "jobId": "uuid",
    "userId": "user-id",
    "results": [
        {"assetId": "id1", "status": "success", ...},
        {"assetId": "id2", "status": "error", "error": "..."},
        ...
    ]
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Powertools
logger = Logger(service="bulk-delete-aggregator")
tracer = Tracer(service="bulk-delete-aggregator")
metrics = Metrics(namespace="BulkDeleteAggregator", service="bulk-delete-aggregator")

# AWS clients
dynamodb = boto3.resource("dynamodb")

# Environment variables
JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "")

jobs_table = dynamodb.Table(JOBS_TABLE_NAME) if JOBS_TABLE_NAME else None


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


@tracer.capture_method
def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate results from distributed map execution.

    Returns:
    {
        "total": 100,
        "successful": 95,
        "failed": 5,
        "successfulAssets": ["id1", "id2", ...],
        "failedAssets": [
            {"assetId": "id3", "error": "...", "timestamp": "..."},
            ...
        ]
    }
    """
    successful_assets = []
    failed_assets = []

    for result in results:
        asset_id = result.get("assetId")
        status = result.get("status")

        if status == "success":
            successful_assets.append(asset_id)
        else:
            failed_assets.append(
                {
                    "assetId": asset_id,
                    "error": result.get("error", "Unknown error"),
                    "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
                }
            )

    return {
        "total": len(results),
        "successful": len(successful_assets),
        "failed": len(failed_assets),
        "successfulAssets": successful_assets,
        "failedAssets": failed_assets,
    }


@tracer.capture_method
def get_job_key(job_id: str, user_id: str) -> Dict[str, str]:
    """
    Query to find the job's itemKey.

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
    except ClientError as e:
        logger.error(f"Failed to query job key: {e}")
        raise


@tracer.capture_method
def update_job_status(
    job_id: str, user_id: str, aggregated_results: Dict[str, Any]
) -> None:
    """Update job with final status and results"""
    try:
        timestamp = datetime.utcnow().isoformat()

        # Determine final status
        failed_count = aggregated_results["failed"]
        final_status = "COMPLETED" if failed_count == 0 else "COMPLETED_WITH_ERRORS"

        # Get the correct DynamoDB keys
        job_key = get_job_key(job_id, user_id)

        # Update job record
        jobs_table.update_item(
            Key=job_key,
            UpdateExpression="""
                SET #status = :status,
                    processedAssets = :total,
                    successfulAssets = :successful,
                    failedAssets = :failed,
                    results = :results,
                    completedAt = :timestamp,
                    updatedAt = :timestamp
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": final_status,
                ":total": aggregated_results["total"],
                ":successful": aggregated_results["successful"],
                ":failed": aggregated_results["failed"],
                ":results": {
                    "successful": aggregated_results["successfulAssets"],
                    "failed": aggregated_results["failedAssets"],
                },
                ":timestamp": timestamp,
            },
        )

        logger.info(
            f"Updated job {job_id} with final status",
            extra={
                "status": final_status,
                "total": aggregated_results["total"],
                "successful": aggregated_results["successful"],
                "failed": aggregated_results["failed"],
            },
        )

        # Record metrics
        metrics.add_metric("BulkDeleteJobsCompleted", MetricUnit.Count, 1)
        metrics.add_metric(
            "TotalAssetsDeleted", MetricUnit.Count, aggregated_results["successful"]
        )

        if failed_count > 0:
            metrics.add_metric(
                "TotalAssetDeletionFailures", MetricUnit.Count, failed_count
            )

    except ClientError as e:
        logger.error(f"Failed to update job status: {e}")
        metrics.add_metric("JobUpdateErrors", MetricUnit.Count, 1)
        raise


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], _ctx: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for aggregating bulk delete results.

    Reads final state from DynamoDB since Step Functions results are discarded
    to avoid 256KB output limit with large batches.

    Input from Step Functions:
    {
        "jobId": "uuid",
        "userId": "user-id",
        "totalAssets": 793
    }

    Output:
    {
        "jobId": "uuid",
        "status": "COMPLETED" | "COMPLETED_WITH_ERRORS",
        "summary": {
            "total": 793,
            "successful": 788,
            "failed": 5
        }
    }
    """
    try:
        job_id = event.get("jobId")
        user_id = event.get("userId")
        total_assets = event.get("totalAssets", 0)

        logger.info(
            f"Finalizing job {job_id}",
            extra={"job_id": job_id, "user_id": user_id, "total_assets": total_assets},
        )

        # Get job key
        job_key = get_job_key(job_id, user_id)

        # Read current state from DynamoDB
        response = jobs_table.get_item(Key=job_key)
        job_item = response.get("Item", {})

        # Extract counters from DynamoDB
        processed = int(job_item.get("processedAssets", 0))
        successful = int(job_item.get("successfulAssets", 0))
        failed = int(job_item.get("failedAssets", 0))

        logger.info(
            f"Job {job_id} final counts from DynamoDB",
            extra={
                "processed": processed,
                "successful": successful,
                "failed": failed,
                "expected_total": total_assets,
            },
        )

        # Validate counts
        if processed != total_assets:
            logger.warning(
                f"Processed count mismatch for job {job_id}",
                extra={"expected": total_assets, "actual": processed},
            )

        # Determine final status
        final_status = "COMPLETED" if failed == 0 else "COMPLETED_WITH_ERRORS"

        # Update job with final status and completion time
        timestamp = datetime.utcnow().isoformat()
        jobs_table.update_item(
            Key=job_key,
            UpdateExpression="""
                SET #status = :status,
                    completedAt = :timestamp,
                    updatedAt = :timestamp,
                    progress = :progress
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": final_status,
                ":timestamp": timestamp,
                ":progress": Decimal("100.0"),
            },
        )

        logger.info(
            f"Finalized job {job_id}",
            extra={
                "status": final_status,
                "processed": processed,
                "successful": successful,
                "failed": failed,
            },
        )

        # Record metrics
        metrics.add_metric("BulkDeleteJobsCompleted", MetricUnit.Count, 1)
        metrics.add_metric("TotalAssetsDeleted", MetricUnit.Count, successful)
        if failed > 0:
            metrics.add_metric("TotalAssetDeletionFailures", MetricUnit.Count, failed)

        # Return summary
        return {
            "jobId": job_id,
            "userId": user_id,
            "status": final_status,
            "summary": {
                "total": processed,
                "successful": successful,
                "failed": failed,
            },
            "completedAt": timestamp,
        }

    except Exception as e:
        logger.error(
            "Error aggregating results", extra={"error": str(e)}, exc_info=True
        )
        metrics.add_metric("AggregationErrors", MetricUnit.Count, 1)

        # Try to mark job as failed
        try:
            job_id = event.get("jobId")
            user_id = event.get("userId")
            if job_id and user_id:
                job_key = get_job_key(job_id, user_id)
                jobs_table.update_item(
                    Key=job_key,
                    UpdateExpression="""
                        SET #status = :status,
                            updatedAt = :timestamp,
                            error = :error
                    """,
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "FAILED",
                        ":timestamp": datetime.utcnow().isoformat(),
                        ":error": str(e),
                    },
                )
        except Exception as update_error:
            logger.error(f"Failed to mark job as failed: {update_error}")

        raise
