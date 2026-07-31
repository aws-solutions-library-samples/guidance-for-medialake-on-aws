"""
Pipeline Group Sweeper

Safety net for pipeline execution groups whose member executions never emit
a terminal Step Functions event (lost events, executions aborted outside
Step Functions, etc.). Without it, such a group would stay OPEN forever and
its outputs would never be packaged.

Runs on a schedule and transitions any group META item that is still OPEN
but hasn't been updated within GROUP_TIMEOUT_HOURS to a terminal status
(flagged timedOut=true). The OPEN → terminal transition rides the groups
table stream into the finalizer, which packages whatever members completed
before the timeout — the same path a normally-completed group takes.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Attr

logger = Logger(service="pipeline_group_sweeper")
metrics = Metrics(namespace="MediaLake/PipelineGroups", service="sweeper")

dynamodb = boto3.resource("dynamodb")

GROUPS_TABLE_NAME = os.environ["PIPELINE_GROUPS_TABLE_NAME"]
GROUP_TIMEOUT_HOURS = int(os.environ.get("GROUP_TIMEOUT_HOURS", "24"))

GROUP_STATUS_OPEN = "OPEN"
GROUP_STATUS_COMPLETED_WITH_FAILURES = "COMPLETED_WITH_FAILURES"
GROUP_STATUS_FAILED = "FAILED"


def find_stale_open_groups(cutoff_iso: str) -> List[Dict[str, Any]]:
    """Scan for OPEN group META items whose last update predates the cutoff.

    A scan is acceptable here: group records are short-lived (7-day TTL),
    low-volume, and the sweeper runs on a coarse schedule.
    """
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    stale: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {
        "FilterExpression": (
            Attr("SK").eq("META")
            & Attr("status").eq(GROUP_STATUS_OPEN)
            & Attr("updatedAt").lt(cutoff_iso)
        )
    }
    while True:
        response = groups_table.scan(**scan_kwargs)
        stale.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return stale


def time_out_group(group: Dict[str, Any]) -> bool:
    """
    Transition a stale OPEN group to a terminal status with timedOut=true.

    Conditional on the group still being OPEN so a member completing (or
    another sweeper run) between scan and update can't be overwritten.
    Members that never resolved count as failures for status purposes.
    """
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    group_id = group.get("groupId", "")
    completed = int(group.get("completedCount", 0))

    terminal = (
        GROUP_STATUS_COMPLETED_WITH_FAILURES if completed > 0 else GROUP_STATUS_FAILED
    )

    try:
        groups_table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            UpdateExpression=(
                "SET #st = :terminal, timedOut = :true, updatedAt = :now"
            ),
            ConditionExpression="#st = :open",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":terminal": terminal,
                ":true": True,
                ":open": GROUP_STATUS_OPEN,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info(
            "Timed out stale group",
            extra={
                "group_id": group_id,
                "terminal_status": terminal,
                "completed_count": completed,
                "expected_count": int(group.get("expectedCount", 0)),
            },
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return False  # group resolved between scan and update
    except Exception as e:
        logger.warning(f"Failed to time out group: {e}", extra={"group_id": group_id})
        return False


@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=GROUP_TIMEOUT_HOURS)
    cutoff_iso = cutoff.isoformat()

    stale_groups = find_stale_open_groups(cutoff_iso)
    timed_out = sum(1 for group in stale_groups if time_out_group(group))

    if timed_out:
        metrics.add_metric(
            name="GroupsTimedOut", unit=MetricUnit.Count, value=timed_out
        )

    logger.info(
        "Sweep complete",
        extra={"stale_candidates": len(stale_groups), "timed_out": timed_out},
    )
    return {"staleCandidates": len(stale_groups), "timedOut": timed_out}
