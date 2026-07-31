"""
Pipeline Group Finalizer

Consumes the pipeline-groups DynamoDB table stream. When a group META item
makes its OPEN → terminal transition (all member executions resolved, or the
sweeper timed the group out), this Lambda:

1. Claims the transition with a conditional write (at-most-once across
   stream retries — mirrors the upload-session stream emission claim).
2. Resolves the output artifacts the group's successful executions produced.
   Two modes, decided by the pipeline definition at submit time:
     - COLLECTOR: the pipeline contains a Download Collector node, which
       registered each artifact it routed as a COLLECTED# row on the group.
       Those rows are the manifest — exactly what the graph declared is
       delivered, and nothing else.
     - AUTO_DISCOVER (legacy): no collector node, so outputs are inferred as
       the derived representations that appeared on each member asset after
       the baseline snapshot taken at submit time, optionally narrowed by the
       group's configured purposes.
3. Creates a standard bulk-download job (user-table record + Step Functions
   execution) that zips those artifacts, so delivery rides the existing
   notification/status flow with zero UI changes.
4. Publishes a "Pipeline Group Completed" event to the pipelines event bus
   so future trigger nodes / automations can react to group completion.

Failure semantics: errors before the packaging job exists roll back the
claim and report a batch item failure so the stream retries. Errors after
the job record exists are recorded on the group (packagingError) without
retrying, to avoid duplicate jobs.
"""

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer

logger = Logger(service="pipeline_group_finalizer")
metrics = Metrics(namespace="MediaLake/PipelineGroups", service="finalizer")

dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")
step_functions = boto3.client("stepfunctions")

GROUPS_TABLE_NAME = os.environ["PIPELINE_GROUPS_TABLE_NAME"]
ASSET_TABLE_NAME = os.environ["MEDIALAKE_ASSET_TABLE"]
USER_TABLE_NAME = os.environ["USER_TABLE_NAME"]
BULK_DOWNLOAD_STATE_MACHINE_ARN = os.environ.get("BULK_DOWNLOAD_STATE_MACHINE_ARN", "")
PIPELINES_EVENT_BUS_NAME = os.environ.get("PIPELINES_EVENT_BUS_NAME", "default")

JOB_EXPIRATION_DAYS = int(os.environ.get("JOB_EXPIRATION_DAYS", "7"))

GROUP_STATUS_OPEN = "OPEN"
TERMINAL_GROUP_STATUSES = ("COMPLETED", "COMPLETED_WITH_FAILURES", "FAILED")

# How the group's artifacts are determined, decided at submit time from the
# pipeline definition (see trigger_pipeline._packaging_mode).
MODE_COLLECTOR = "COLLECTOR"
MODE_AUTO_DISCOVER = "AUTO_DISCOVER"

_deserializer = TypeDeserializer()


def _deserialize_image(image: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a DynamoDB stream image into a plain Python dict."""
    return {k: _deserializer.deserialize(v) for k, v in image.items()}


def is_terminal_transition(record: Dict[str, Any]) -> bool:
    """True when the record is a group META item moving OPEN → terminal."""
    if record.get("eventName") != "MODIFY":
        return False
    stream_data = record.get("dynamodb", {})
    old_image = stream_data.get("OldImage", {})
    new_image = stream_data.get("NewImage", {})
    if new_image.get("SK", {}).get("S") != "META":
        return False
    old_status = old_image.get("status", {}).get("S", "")
    new_status = new_image.get("status", {}).get("S", "")
    return old_status == GROUP_STATUS_OPEN and new_status in TERMINAL_GROUP_STATUSES


def claim_finalization(group_id: str) -> bool:
    """
    Claim the group's finalization with a conditional write.

    Streams deliver at-least-once; the claim guarantees packaging and event
    emission happen at most once per group. Returns True when this invocation
    won the claim.
    """
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    try:
        groups_table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            UpdateExpression="SET packagingClaimedAt = :now",
            ConditionExpression="attribute_not_exists(packagingClaimedAt)",
            ExpressionAttributeValues={":now": datetime.now(timezone.utc).isoformat()},
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.info("Finalization already claimed", extra={"group_id": group_id})
        return False


def rollback_claim(group_id: str) -> None:
    """Release the claim so a stream retry can re-attempt finalization."""
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    try:
        groups_table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            UpdateExpression="REMOVE packagingClaimedAt",
            ConditionExpression="attribute_not_exists(packagingJobId)",
        )
    except Exception as e:
        logger.warning(
            f"Failed to roll back finalization claim: {e}",
            extra={"group_id": group_id},
        )


def get_group_members(group_id: str) -> List[Dict[str, Any]]:
    """Return all member (EXEC#) items for a group."""
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    members: List[Dict[str, Any]] = []
    query_kwargs: Dict[str, Any] = {
        "KeyConditionExpression": (
            Key("PK").eq(f"GROUP#{group_id}") & Key("SK").begins_with("EXEC#")
        )
    }
    while True:
        response = groups_table.query(**query_kwargs)
        members.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    return members


def get_collected_artifacts(group_id: str) -> List[Dict[str, Any]]:
    """
    Read the manifest written by the pipeline's Download Collector node.

    Each COLLECTED# row is one artifact a node explicitly routed to download,
    so no inference is involved: the graph decided what ships. Rows are keyed
    by (asset, representation), which makes a retried execution idempotent,
    and de-duplicated here by S3 URI in case two executions collected the same
    output (e.g. two segments of one asset resolving to the same rendition).

    Returns bulk-download asset entries:
        {"assetId", "clipBoundary": {}, "s3Uri", "size", "representationId"}
    """
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    artifacts: List[Dict[str, Any]] = []
    seen_uris: set = set()

    query_kwargs: Dict[str, Any] = {
        "KeyConditionExpression": (
            Key("PK").eq(f"GROUP#{group_id}") & Key("SK").begins_with("COLLECTED#")
        )
    }
    while True:
        response = groups_table.query(**query_kwargs)
        for item in response.get("Items", []):
            s3_uri = item.get("s3Uri")
            asset_id = item.get("assetId")
            if not s3_uri or not asset_id or s3_uri in seen_uris:
                continue
            seen_uris.add(s3_uri)
            size = item.get("size", 0)
            artifacts.append(
                {
                    "assetId": asset_id,
                    "clipBoundary": {},
                    "s3Uri": s3_uri,
                    "size": int(size) if size else 0,
                    "representationId": item.get("representationId", ""),
                }
            )
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    return artifacts


def resolve_group_artifacts(
    members: List[Dict[str, Any]], purposes: List[str]
) -> List[Dict[str, Any]]:
    """
    Infer the output artifacts the group's successful executions produced.

    Used only for pipelines with no Download Collector node. An artifact is
    any derived representation that was NOT on the asset when the group was
    submitted.

    Two known blind spots motivate the collector node: a pipeline that also
    writes incidental representations (proxy, thumbnail) ships them too, and a
    node that reuses a deterministic representation ID resolves to nothing on
    a re-run because the ID is already in the baseline.
    Whatever a pipeline records on the asset — a reframed rendition, a proxy,
    a transcode, an extracted still — is packaged the same way, with no
    per-pipeline configuration.

    ``purposes`` is an optional narrowing filter; empty means "every new
    representation". Members that share an asset (e.g. two segments of one
    video) also share the baseline snapshot, so artifacts are computed once
    per unique asset.

    Returns bulk-download asset entries carrying explicit S3 locations:
        {"assetId", "clipBoundary": {}, "s3Uri", "size", "representationId"}
    """
    asset_table = dynamodb.Table(ASSET_TABLE_NAME)
    purposes_set = {p.lower() for p in purposes if p}

    # Unique successful assets with their baselines
    baseline_by_asset: Dict[str, set] = {}
    for member in members:
        if member.get("status") != "SUCCEEDED":
            continue
        inv_id = member.get("inventoryId")
        if not inv_id or inv_id == "unknown":
            continue
        baseline = set(member.get("baselineRepIds", []) or [])
        if inv_id in baseline_by_asset:
            # Baselines for the same asset are snapshotted together; keep the
            # intersection so a missing snapshot on one member can't hide
            # artifacts recorded on another.
            baseline_by_asset[inv_id] &= baseline
        else:
            baseline_by_asset[inv_id] = baseline

    artifacts: List[Dict[str, Any]] = []
    seen_rep_ids: set = set()

    for inv_id, baseline in baseline_by_asset.items():
        try:
            asset = asset_table.get_item(Key={"InventoryID": inv_id}).get("Item")
        except Exception as e:
            logger.warning(
                f"Failed to load asset for artifact resolution: {e}",
                extra={"inventory_id": inv_id},
            )
            continue
        if not asset:
            continue

        for rep in asset.get("DerivedRepresentations", []) or []:
            rep_id = rep.get("ID")
            purpose = str(rep.get("Purpose", "")).lower()
            if not rep_id or rep_id in seen_rep_ids:
                continue
            # Already present at submit time — not an output of this group.
            if rep_id in baseline:
                continue
            # An empty filter packages every new representation.
            if purposes_set and purpose not in purposes_set:
                continue

            location = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            bucket = location.get("Bucket")
            key = location.get("ObjectKey", {}).get("FullPath")
            if not bucket or not key:
                continue

            size = location.get("FileInfo", {}).get("Size", 0)
            artifacts.append(
                {
                    "assetId": inv_id,
                    "clipBoundary": {},
                    "s3Uri": f"s3://{bucket}/{key}",
                    "size": int(size) if size else 0,
                    "representationId": rep_id,
                }
            )
            seen_rep_ids.add(rep_id)

    return artifacts


def create_packaging_job(group: Dict[str, Any], artifacts: List[Dict[str, Any]]) -> str:
    """
    Create a bulk-download job for the group's artifacts and start the
    packaging Step Functions workflow.

    Mirrors the job record and execution input produced by
    POST /assets/download/bulk so status polling, notifications, and the
    download link all work through the existing flow.
    """
    if not BULK_DOWNLOAD_STATE_MACHINE_ARN:
        raise RuntimeError(
            "Bulk download workflow is not configured "
            "(BULK_DOWNLOAD_STATE_MACHINE_ARN missing)"
        )

    user_table = dynamodb.Table(USER_TABLE_NAME)
    user_id = group["userId"]
    group_id = group["groupId"]
    pipeline_name = group.get("pipelineName", "pipeline")
    group_name = group.get("groupName") or pipeline_name

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(days=JOB_EXPIRATION_DAYS)
    reverse_timestamp = str(9999999999999 - int(time.time() * 1000))

    options = {"format": "zip", "includeMetadata": False}

    user_table.put_item(
        Item={
            "userId": f"USER#{user_id}",
            "itemKey": f"BULK_DOWNLOAD#{job_id}#{reverse_timestamp}",
            "itemType": "BULK_DOWNLOAD",
            "jobId": job_id,
            "status": "INITIATED",
            "assetIds": artifacts,
            "options": options,
            "progress": 0,
            "totalFiles": len(artifacts),
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
            "expiresAt": int(expiration.timestamp()),
            "description": (
                f"Pipeline outputs ready: {group_name} "
                f"({len(artifacts)} file{'s' if len(artifacts) != 1 else ''})"
            ),
            "groupId": group_id,
            "gsi1Sk": f"ITEM_TYPE#BULK_DOWNLOAD#{reverse_timestamp}",
            "gsi2Pk": f"JOB#{job_id}",
            "gsi2Sk": reverse_timestamp,
            "gsi3Pk": f"JOB#{job_id}",
            "gsi3Sk": f"USER#{user_id}",
        }
    )

    try:
        step_functions.start_execution(
            stateMachineArn=BULK_DOWNLOAD_STATE_MACHINE_ARN,
            name=f"bulk-download-{job_id}",
            input=json.dumps(
                {
                    "jobId": job_id,
                    "userId": user_id,
                    "assetIds": artifacts,
                    "options": options,
                    "timestamp": int(time.time()),
                    "smallFiles": [],
                    "largeFiles": [],
                }
            ),
        )
    except Exception as e:
        # Mark the job failed so the user sees the failure instead of a
        # perpetually-initiated job.
        logger.error(
            f"Failed to start packaging workflow: {e}",
            extra={"job_id": job_id, "group_id": group_id},
        )
        try:
            user_table.update_item(
                Key={
                    "userId": f"USER#{user_id}",
                    "itemKey": f"BULK_DOWNLOAD#{job_id}#{reverse_timestamp}",
                },
                UpdateExpression=(
                    "SET #status = :status, #error = :error, " "#updatedAt = :updatedAt"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#error": "error",
                    "#updatedAt": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":status": "FAILED",
                    ":error": f"Failed to start packaging: {str(e)}",
                    ":updatedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as update_error:
            logger.error(
                f"Failed to mark packaging job as failed: {update_error}",
                extra={"job_id": job_id},
            )
        raise

    logger.info(
        "Started packaging job for group",
        extra={
            "group_id": group_id,
            "job_id": job_id,
            "artifact_count": len(artifacts),
        },
    )
    metrics.add_metric(name="PackagingJobsStarted", unit=MetricUnit.Count, value=1)
    return job_id


def publish_group_completed_event(
    group: Dict[str, Any], packaging_job_id: Optional[str]
) -> None:
    """
    Publish "Pipeline Group Completed" to the pipelines event bus.

    Branchable signals ride as the STRINGS "true"/"false" (EventBridge
    patterns match strings), following the Upload Batch Completed convention,
    so a future trigger node can filter on them.
    """
    failed_count = int(group.get("failedCount", 0))
    package_cfg = group.get("package", {}) or {}
    detail = {
        "groupId": group.get("groupId", ""),
        "userId": group.get("userId", ""),
        "pipelineId": group.get("pipelineId", ""),
        "pipelineName": group.get("pipelineName", ""),
        "groupName": group.get("groupName", ""),
        "status": group.get("status", ""),
        "expectedCount": int(group.get("expectedCount", 0)),
        "completedCount": int(group.get("completedCount", 0)),
        "failedCount": failed_count,
        "allSucceeded": "true" if failed_count == 0 else "false",
        "packageRequested": ("true" if package_cfg.get("enabled", False) else "false"),
        "packagingMode": str(package_cfg.get("mode", MODE_AUTO_DISCOVER)),
        "packagingJobId": packaging_job_id or "",
        "timedOut": "true" if group.get("timedOut") else "false",
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = events_client.put_events(
            Entries=[
                {
                    "Source": "medialake.pipeline",
                    "DetailType": "Pipeline Group Completed",
                    "Detail": json.dumps(detail),
                    "EventBusName": PIPELINES_EVENT_BUS_NAME,
                }
            ]
        )
        if response.get("FailedEntryCount", 0) > 0:
            logger.error(
                "PutEvents reported failed entries",
                extra={"entries": response.get("Entries", [])},
            )
    except Exception as e:
        # The event is informational in Phase 1 — never fail finalization
        # (and re-run packaging) because of it.
        logger.error(
            f"Failed to publish group completed event: {e}",
            extra={"group_id": group.get("groupId", "")},
        )


def record_finalization_outcome(
    group_id: str,
    packaging_job_id: Optional[str],
    skipped_reason: Optional[str] = None,
    error: Optional[str] = None,
    artifact_source: Optional[str] = None,
) -> None:
    """Record the packaging outcome on the group META item (best effort)."""
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    updates = ["updatedAt = :now"]
    values: Dict[str, Any] = {":now": datetime.now(timezone.utc).isoformat()}
    if packaging_job_id:
        updates.append("packagingJobId = :job")
        values[":job"] = packaging_job_id
    if artifact_source:
        updates.append("artifactSource = :src")
        values[":src"] = artifact_source
    if skipped_reason:
        updates.append("packagingSkippedReason = :skip")
        values[":skip"] = skipped_reason
    if error:
        updates.append("packagingError = :err")
        values[":err"] = error
    try:
        groups_table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            UpdateExpression="SET " + ", ".join(updates),
            ExpressionAttributeValues=values,
        )
    except Exception as e:
        logger.warning(
            f"Failed to record finalization outcome: {e}",
            extra={"group_id": group_id},
        )


def finalize_group(group: Dict[str, Any]) -> None:
    """
    Package the group's artifacts and announce completion.

    Raises before any job exists to signal a retryable failure (caller rolls
    back the claim). Once a job record exists, errors are recorded instead.
    """
    group_id = group["groupId"]
    package_cfg = group.get("package", {}) or {}
    packaging_job_id: Optional[str] = None
    skipped_reason: Optional[str] = None

    artifact_source: Optional[str] = None

    if not package_cfg.get("enabled", False):
        skipped_reason = "PACKAGING_NOT_REQUESTED"
    elif int(group.get("completedCount", 0)) == 0:
        skipped_reason = "NO_SUCCESSFUL_EXECUTIONS"
    else:
        # Retryable section: no side effects beyond reads until the job
        # record is written inside create_packaging_job.
        mode = str(package_cfg.get("mode", MODE_AUTO_DISCOVER)).upper()
        artifacts = get_collected_artifacts(group_id)

        if artifacts:
            artifact_source = "COLLECTOR"
        elif mode == MODE_COLLECTOR:
            # The pipeline declares a Download Collector, so its manifest is
            # the whole story. Falling back to inference here would package
            # representations the graph deliberately did not route.
            skipped_reason = "NO_ARTIFACTS_COLLECTED"
            logger.warning(
                "Pipeline declares a Download Collector node but the group's "
                "executions collected nothing. Either the collector sits on a "
                "branch this run did not take, or its Representation Purposes "
                "do not match what the upstream node recorded on the asset.",
                extra={
                    "group_id": group_id,
                    "pipeline_name": group.get("pipelineName", ""),
                },
            )
        else:
            members = get_group_members(group_id)
            # No purposes configured = package every new representation.
            purposes = list(package_cfg.get("purposes", []) or [])
            artifacts = resolve_group_artifacts(members, purposes)
            artifact_source = "AUTO_DISCOVER" if artifacts else None

            if not artifacts:
                skipped_reason = "NO_ARTIFACTS_FOUND"
                logger.warning(
                    "No artifacts resolved for completed group — nothing to "
                    "package. Without a Download Collector node, packaging "
                    "infers outputs as derived representations added to the "
                    "asset during the run, so a pipeline whose nodes write "
                    "files to S3 without recording a DerivedRepresentation "
                    "(with StorageInfo.PrimaryLocation) — or that re-created "
                    "a representation the asset already had — produces "
                    "nothing to collect. Adding a Download Collector node to "
                    "the pipeline makes the outputs explicit. See "
                    "assets/docs/pipeline-output-packaging.md.",
                    extra={
                        "group_id": group_id,
                        "pipeline_name": group.get("pipelineName", ""),
                        "purposes_filter": purposes or "ALL",
                        "member_count": len(members),
                    },
                )

        if artifacts:
            packaging_job_id = create_packaging_job(group, artifacts)

    publish_group_completed_event(group, packaging_job_id)
    record_finalization_outcome(
        group_id, packaging_job_id, skipped_reason, artifact_source=artifact_source
    )
    metrics.add_metric(name="GroupsFinalized", unit=MetricUnit.Count, value=1)


@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process group-table stream records; finalize terminal transitions."""
    batch_item_failures: List[Dict[str, str]] = []

    for record in event.get("Records", []):
        if not is_terminal_transition(record):
            continue

        group = _deserialize_image(record["dynamodb"]["NewImage"])
        group_id = group.get("groupId") or group.get("PK", "").replace("GROUP#", "")
        logger.info(
            "Group reached terminal status",
            extra={"group_id": group_id, "status": group.get("status")},
        )

        if not claim_finalization(group_id):
            continue

        try:
            finalize_group(group)
        except Exception as e:
            # Failure before a packaging job existed — release the claim and
            # let the stream retry this record.
            logger.exception(
                f"Finalization failed, releasing claim for retry: {e}",
                extra={"group_id": group_id},
            )
            rollback_claim(group_id)
            record_finalization_outcome(group_id, None, error=str(e))
            batch_item_failures.append({"itemIdentifier": record.get("eventID", "")})

    return {"batchItemFailures": batch_item_failures}
