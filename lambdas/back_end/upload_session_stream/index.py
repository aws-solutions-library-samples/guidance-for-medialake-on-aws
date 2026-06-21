"""Upload Session Stream Processor Lambda.

Processes DynamoDB Streams events from the upload-sessions table. Filters for
OPEN → terminal status transitions (COMPLETE or COMPLETE_WITH_ERRORS), claims
at-most-once emission via a conditional write, and publishes an
UploadBatchCompleted event to the pipelines EventBridge bus.

Requirements: 6.2, 6.4, 6.5, 6.6, 8.4
"""

import json
import os
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="upload_session_stream")
metrics = Metrics(namespace="medialake", service="upload_session_stream")

# Environment variables
PIPELINES_EVENT_BUS_NAME = os.environ.get("PIPELINES_EVENT_BUS_NAME", "")
UPLOAD_SESSIONS_TABLE_NAME = os.environ.get("UPLOAD_SESSIONS_TABLE_NAME", "")

# Clients
dynamodb_client = boto3.client("dynamodb")
events_client = boto3.client("events")

# Terminal statuses that trigger emission
TERMINAL_STATUSES = {"COMPLETE", "COMPLETE_WITH_ERRORS"}


def _is_terminal_transition(record: dict) -> bool:
    """Check if a stream record represents an OPEN → terminal status transition.

    Only MODIFY events where OldImage.status == "OPEN" and NewImage.status is
    one of the terminal statuses are considered.
    """
    if record.get("eventName") != "MODIFY":
        return False

    dynamodb_data = record.get("dynamodb", {})
    old_image = dynamodb_data.get("OldImage", {})
    new_image = dynamodb_data.get("NewImage", {})

    old_status = old_image.get("status", {}).get("S", "")
    new_status = new_image.get("status", {}).get("S", "")

    return old_status == "OPEN" and new_status in TERMINAL_STATUSES


def _claim_emission(session_id: str) -> bool:
    """Attempt to claim emission for a session via conditional UpdateItem.

    Sets `emittedAt` only if it does not already exist. Returns True if this
    invocation won the claim (first to emit), False if another actor already
    claimed it (ConditionalCheckFailedException).

    This ensures at-most-once emission per session (R6.4).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dynamodb_client.update_item(
            TableName=UPLOAD_SESSIONS_TABLE_NAME,
            Key={
                "PK": {"S": f"SESSION#{session_id}"},
                "SK": {"S": "META"},
            },
            UpdateExpression="SET emittedAt = :now",
            ConditionExpression="attribute_not_exists(emittedAt)",
            ExpressionAttributeValues={
                ":now": {"S": now},
            },
        )
        return True
    except dynamodb_client.exceptions.ConditionalCheckFailedException:
        logger.info(
            "Emission already claimed for session, skipping",
            extra={"session_id": session_id},
        )
        return False


def _extract_event_detail(new_image: dict) -> dict:
    """Extract the UploadBatchCompleted event detail from the NewImage.

    Carries sessionId, portalId, automationTag, expectedCount, completedCount,
    failedCount, completedAt, and outcome (= terminal status) as required by R6.5.
    """

    def _get_s(key: str) -> str:
        return new_image.get(key, {}).get("S", "")

    def _get_n(key: str) -> int:
        val = new_image.get(key, {}).get("N", "0")
        return int(val)

    return {
        "sessionId": _get_s("sessionId"),
        "portalId": _get_s("portalId"),
        "automationTag": _get_s("automationTag"),
        "expectedCount": _get_n("expectedCount"),
        "completedCount": _get_n("completedCount"),
        "failedCount": _get_n("failedCount"),
        "completedAt": _get_s("completedAt"),
        "outcome": _get_s("status"),
    }


def _publish_event(detail: dict) -> bool:
    """Publish the UploadBatchCompleted event to EventBridge.

    Returns True on success, False if PutEvents fails or reports failed entries.
    Publishes with Source="medialake.pipeline" and DetailType="Upload Batch Completed"
    on the configured PIPELINES_EVENT_BUS_NAME (R6.6).
    """
    try:
        response = events_client.put_events(
            Entries=[
                {
                    "Source": "medialake.pipeline",
                    "DetailType": "Upload Batch Completed",
                    "Detail": json.dumps(detail),
                    "EventBusName": PIPELINES_EVENT_BUS_NAME,
                }
            ]
        )
        failed_count = response.get("FailedEntryCount", 0)
        if failed_count > 0:
            logger.error(
                "PutEvents reported failed entries",
                extra={
                    "failed_count": failed_count,
                    "entries": response.get("Entries", []),
                    "session_id": detail.get("sessionId"),
                },
            )
            return False
        return True
    except Exception as e:
        logger.error(
            "PutEvents call failed",
            extra={
                "error": str(e),
                "session_id": detail.get("sessionId"),
            },
        )
        return False


@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    """Process DynamoDB stream records for upload session terminal transitions.

    For each record that represents an OPEN → terminal transition:
    1. Claim emission (conditional write — at-most-once guarantee)
    2. On successful claim, publish UploadBatchCompleted to EventBridge
    3. On PutEvents failure, report the record as a batch-item failure for retry

    Returns {"batchItemFailures": [...]} for partial-batch retry support.
    """
    records = event.get("Records", [])
    batch_item_failures = []

    logger.info(
        "Processing stream records",
        extra={"record_count": len(records)},
    )

    for record in records:
        # Only process MODIFY events with OPEN → terminal transition
        if not _is_terminal_transition(record):
            continue

        event_id = record.get("eventID", "")
        dynamodb_data = record.get("dynamodb", {})
        new_image = dynamodb_data.get("NewImage", {})
        session_id = new_image.get("sessionId", {}).get("S", "")

        logger.info(
            "Detected terminal transition",
            extra={
                "session_id": session_id,
                "new_status": new_image.get("status", {}).get("S", ""),
                "event_id": event_id,
            },
        )

        # Step 1: Claim emission (at-most-once via conditional write)
        claimed = _claim_emission(session_id)
        if not claimed:
            # Already emitted by another invocation — idempotent skip
            continue

        # Step 2: Publish the event to EventBridge
        detail = _extract_event_detail(new_image)
        success = _publish_event(detail)

        if not success:
            # PutEvents failed — emit error metric and report as batch-item failure for retry
            metrics.add_dimension(
                name="portalId", value=detail.get("portalId", "unknown")
            )
            metrics.add_metric(
                name="UploadBatchEmissionError", unit=MetricUnit.Count, value=1
            )
            logger.warning(
                "Adding record to batch item failures due to PutEvents failure",
                extra={"session_id": session_id, "event_id": event_id},
            )
            batch_item_failures.append({"itemIdentifier": event_id})

    logger.info(
        "Stream processing complete",
        extra={
            "total_records": len(records),
            "batch_item_failures": len(batch_item_failures),
        },
    )

    return {"batchItemFailures": batch_item_failures}
