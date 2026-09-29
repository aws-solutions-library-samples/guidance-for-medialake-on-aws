"""
Bulk Download Mark Failed Lambda

Invoked by an EventBridge rule when a bulk-download Step Functions execution
ends FAILED, TIMED_OUT or ABORTED. It marks the job record FAILED with the
execution's error so the UI stops showing it as in progress.

Before this existed, a failure in a state that is not one of the job's
Lambdas (for example the MediaConvert sub-clip task, or a Map/Pass state)
ended the execution without ever touching the job record: the job sat at
its last status (e.g. GENERATING_SUB_CLIPS, 0 %) forever and no error or
notification was ever produced.

Jobs that already reached COMPLETED or FAILED are left alone, so a more
specific error written by one of the job's own Lambdas is kept.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

logger = Logger(service="bulk-download-mark-failed")
tracer = Tracer(service="bulk-download-mark-failed")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-mark-failed")

USER_TABLE_NAME = os.environ["USER_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
step_functions = boto3.client("stepfunctions")
user_table = dynamodb.Table(USER_TABLE_NAME)

EXECUTION_NAME_PREFIX = "bulk-download-"
FINAL_JOB_STATUSES = ("COMPLETED", "FAILED")
MAX_ERROR_LENGTH = 1000


def _job_id_from_execution(detail: Dict[str, Any]) -> Optional[str]:
    """Job id from the execution input, falling back to the execution name."""
    raw_input = detail.get("input")
    if raw_input is None and detail.get("executionArn"):
        # EventBridge omits large inputs; fetch them from Step Functions.
        try:
            raw_input = step_functions.describe_execution(
                executionArn=detail["executionArn"]
            ).get("input")
        except ClientError as e:
            logger.warning("DescribeExecution failed", extra={"error": str(e)})
    if raw_input:
        try:
            job_id = json.loads(raw_input).get("jobId")
            if job_id:
                return str(job_id)
        except (TypeError, ValueError, AttributeError):
            logger.warning("Execution input is not a JSON object")
    name = detail.get("name") or ""
    if name.startswith(EXECUTION_NAME_PREFIX):
        return name[len(EXECUTION_NAME_PREFIX) :]
    return None


def _cause_message(cause: Any) -> str:
    """Pull the human-readable message out of a Step Functions cause string.

    Lambda failures carry a JSON object with errorMessage; service
    integrations (MediaConvert) usually carry plain text or a JSON object
    with Message/message.
    """
    if not cause:
        return ""
    text = str(cause)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return text
    if isinstance(parsed, dict):
        for key in ("errorMessage", "ErrorMessage", "Message", "message"):
            if parsed.get(key):
                return str(parsed[key])
    return text


def build_error_message(detail: Dict[str, Any]) -> str:
    """User-facing error for the job record, bounded in length."""
    status = detail.get("status")
    if status == "TIMED_OUT":
        message = "The download job timed out before it finished."
    elif status == "ABORTED":
        message = "The download job was stopped before it finished."
    else:
        error = detail.get("error") or "Download processing failed"
        cause = _cause_message(detail.get("cause"))
        message = f"{error}: {cause}" if cause else str(error)
    if len(message) > MAX_ERROR_LENGTH:
        message = message[: MAX_ERROR_LENGTH - 3] + "..."
    return message


def _find_job_key(job_id: str) -> Optional[Dict[str, str]]:
    response = user_table.query(
        IndexName="GSI3",
        KeyConditionExpression="gsi3Pk = :pk",
        ExpressionAttributeValues={":pk": f"JOB#{job_id}"},
        Limit=1,
    )
    items = response.get("Items") or []
    if not items:
        return None
    return {"userId": items[0]["userId"], "itemKey": items[0]["itemKey"]}


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    detail = event.get("detail") or {}
    status = detail.get("status")
    job_id = _job_id_from_execution(detail)
    log_extra = {
        "executionArn": detail.get("executionArn"),
        "executionStatus": status,
        "jobId": job_id,
    }

    if not job_id:
        logger.error("Could not determine the job for this execution", extra=log_extra)
        return {"updated": False, "reason": "no-job-id"}

    key = _find_job_key(job_id)
    if not key:
        logger.warning("Job record not found (expired or deleted)", extra=log_extra)
        return {"updated": False, "reason": "job-not-found"}

    error_message = build_error_message(detail)
    try:
        user_table.update_item(
            Key=key,
            UpdateExpression="SET #status = :failed, #error = :error, #updatedAt = :now",
            ConditionExpression=(
                "attribute_exists(itemKey) AND NOT #status IN (:completed, :failed)"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#error": "error",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":failed": "FAILED",
                ":completed": FINAL_JOB_STATUSES[0],
                ":error": error_message,
                ":now": datetime.utcnow().isoformat(),
            },
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info("Job already in a final state; left unchanged", extra=log_extra)
            return {"updated": False, "reason": "already-final"}
        raise

    logger.warning(
        "Marked bulk download job FAILED after execution ended",
        extra={**log_extra, "error": error_message},
    )
    metrics.add_metric(name="JobsMarkedFailed", unit=MetricUnit.Count, value=1)
    return {"updated": True, "jobId": job_id}
