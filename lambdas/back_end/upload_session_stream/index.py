"""Upload Session Stream Processor Lambda.

Processes DynamoDB Streams events from the upload-sessions table. This is the
SINGLE emission point for the pipeline trigger: because the two-signal join in
`try_terminal_transition` can complete from either the submit side or the
asset-processing side (whichever arrives last), emitting off the status
transition is the one place that observes the completed join regardless of which
actor caused it.

Filters for OPEN → terminal-EMITTING status transitions (SUBMITTED_PROCESSED,
SUBMITTED_UNPROCESSED, or UNSUBMITTED_PROCESSED), claims at-most-once emission
via a conditional write, and publishes an UploadBatchCompleted event to the
pipelines EventBridge bus.

UNSUBMITTED_UNPROCESSED is a terminal status but is intentionally EXCLUDED here
(it is not in EMITTING_TERMINAL_STATUSES) — a session that was never submitted
and whose files never all succeeded is the silent false/false corner and must
not trigger a pipeline. The event carries the two branchable signals
(`filesProcessed`, `formSubmissionComplete`) derived from the terminal status,
plus `userMetadata` — the authoritative form snapshot captured at submit — so
downstream nodes can branch on the outcome and the portal form fields.
"""

import json
import os
import sys
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

# Upload session store — vendored into the Lambda package at deploy time. Import
# the canonical emit set and the signal-derivation helper so the event schema
# stays in lockstep with the session model (single source of truth).
try:
    from upload_session.session_store import (
        EMITTING_TERMINAL_STATUSES,
        derive_signals,
    )
except ImportError:
    # Fallback for local development / testing: add the shared dir to path.
    _SHARED_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    )
    if _SHARED_DIR not in sys.path:
        sys.path.insert(0, _SHARED_DIR)
    from upload_session.session_store import (
        EMITTING_TERMINAL_STATUSES,
        derive_signals,
    )

logger = Logger(service="upload_session_stream")
metrics = Metrics(namespace="medialake", service="upload_session_stream")

# Environment variables
PIPELINES_EVENT_BUS_NAME = os.environ.get("PIPELINES_EVENT_BUS_NAME", "")
UPLOAD_SESSIONS_TABLE_NAME = os.environ.get("UPLOAD_SESSIONS_TABLE_NAME", "")

# Clients
dynamodb_client = boto3.client("dynamodb")
events_client = boto3.client("events")

# Terminal statuses that trigger emission. Imported from the session store so
# the silent corner (UNSUBMITTED_UNPROCESSED — never submitted and files never
# all succeeded) is excluded exactly where it is defined.
TERMINAL_STATUSES = EMITTING_TERMINAL_STATUSES


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
    failedCount, completedAt, and the two branchable signals derived from the
    terminal status:

      * ``filesProcessed``         - "true" when every uploaded file succeeded.
      * ``formSubmissionComplete`` - "true" when the user clicked Submit.

    Both are STRINGS ("true"/"false"), not JSON booleans, so the trigger node's
    string-interpolated EventBridge pattern (``["${files_processed}"]``) matches
    them — the same convention the portal form fields (``userMetadata``) use.

    ``userMetadata`` is the batch's user-entered portal form fields. Downstream
    trigger-workflow nodes read ``detail.userMetadata.<slug>`` to branch on form
    fields; values are strings and the map is empty when the session carried no
    user metadata.
    """

    def _get_s(key: str) -> str:
        return new_image.get(key, {}).get("S", "")

    def _get_n(key: str) -> int:
        val = new_image.get(key, {}).get("N", "0")
        return int(val)

    def _get_string_map(key: str) -> dict:
        """Deserialize a DynamoDB Map of string-valued entries to a flat dict.

        The stream Map shape is {"M": {slug: {"S": value}}}; defaults to {} when
        the attribute is absent. Non-string entries are coerced to "".
        """
        raw_map = new_image.get(key, {}).get("M", {})
        return {slug: entry.get("S", "") for slug, entry in raw_map.items()}

    files_processed, form_submission_complete = derive_signals(_get_s("status"))

    return {
        "sessionId": _get_s("sessionId"),
        "portalId": _get_s("portalId"),
        "automationTag": _get_s("automationTag"),
        "expectedCount": _get_n("expectedCount"),
        "completedCount": _get_n("completedCount"),
        "failedCount": _get_n("failedCount"),
        "completedAt": _get_s("completedAt"),
        "filesProcessed": files_processed,
        "formSubmissionComplete": form_submission_complete,
        "userMetadata": _get_string_map("userMetadata"),
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
