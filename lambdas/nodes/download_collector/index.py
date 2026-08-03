"""Download Collector pipeline node.

Marks the outputs of the branch it sits on as deliverables. When a pipeline is
launched as an execution *group* (the bin's "package outputs for download"
submission), every artifact this node registers is zipped and handed to the
user once the last member execution finishes; the node is inert on ungrouped
runs.

Why a node instead of automatic discovery
-----------------------------------------
Packaging used to infer a group's outputs by diffing the asset's
``DerivedRepresentations`` against a snapshot taken at submit time. That is
uniform but blind in two ways:

1. It cannot express intent. Every representation a run happened to add was
   packaged, so a pipeline that writes a proxy *and* a deliverable rendition
   shipped both, and a pipeline whose outputs were never meant to leave the
   system shipped them anyway.
2. It cannot see re-runs. Most nodes mint deterministic representation IDs
   (``<asset>:proxy``, ``<asset>:smartcrop``), so regenerating an artifact the
   asset already had produced an ID that was already in the baseline — the
   diff resolved nothing and the user got an empty zip.

Placing this node on a specific branch fixes both: participation is declared
in the graph, scope is declared by the node's purposes, and artifacts are
recorded by identity rather than by novelty. Anything a pipeline records as a
derived representation can be collected — reframed renditions, transcodes,
proxies, extracted stills — so the same node serves any workflow.

Contract
--------
Input: the standardized pipeline payload from ``lambda_middleware``
(``payload.assets`` carries the asset record the upstream node just updated).
Output: a ``downloadCollection`` summary that becomes the next state's
``payload.data``. The asset is not modified, so ``payload.assets`` flows
through untouched.

Placement: put this node on the success path, after the node that creates the
artifact. On a polling loop (submit → check → choice) that means the branch
leaving the choice, not between check and choice — otherwise it runs on every
poll and on the failure branch too.
"""

import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from boto3.dynamodb.conditions import Key
from lambda_middleware import lambda_middleware

logger = Logger(service="download-collector-node")
tracer = Tracer(service="download-collector-node")

dynamodb = boto3.resource("dynamodb")

# Set for every node lambda by the pipeline deployer.
GROUPS_TABLE_NAME = os.environ.get("PIPELINE_GROUPS_TABLE_NAME", "")
ASSET_TABLE_NAME = os.environ.get("MEDIALAKE_ASSET_TABLE", "")
EXECUTION_INDEX_NAME = os.environ.get(
    "PIPELINE_GROUPS_EXECUTION_INDEX", "executionId-index"
)

DEFAULT_TTL_DAYS = 7
COLLECTED_SK_PREFIX = "COLLECTED#"

# The group member row is written by the trigger immediately after
# start_execution. A pipeline that reaches this node within milliseconds could
# in principle outrun that write, so the lookup gets a couple of short retries.
_GROUP_LOOKUP_ATTEMPTS = 3
_GROUP_LOOKUP_DELAY_SECONDS = 1

# Node parameters arrive as environment variables (label uppercased, spaces to
# underscores); ``event["parameters"]`` is the direct-invocation/test fallback.
_PARAM_ENV = {
    "Purposes": "PURPOSES",
    "Require Artifacts": "REQUIRE_ARTIFACTS",
}


def _resolve_params(event: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve node parameters from env vars, falling back to event params."""
    event_params = event.get("parameters") or {}
    resolved: Dict[str, Any] = {}
    for label, env_key in _PARAM_ENV.items():
        value = os.environ.get(env_key)
        if value is None or value == "":
            value = event_params.get(label)
        resolved[label] = value
    return resolved


def _parse_purposes(raw: Any) -> List[str]:
    """Parse the Purposes parameter into a lowercased list."""
    if isinstance(raw, list):
        values = [str(p).strip() for p in raw]
    elif isinstance(raw, str):
        values = [p.strip() for p in raw.split(",")]
    else:
        return []
    return [p.lower() for p in values if p]


def _is_true(raw: Any) -> bool:
    return str(raw).strip().lower() in ("true", "yes", "1")


def _to_int(value: Any) -> int:
    """Coerce a DynamoDB number (or anything numeric) to int."""
    if isinstance(value, (int, Decimal, float)):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _find_group_id_in_payload(payload: Dict[str, Any]) -> Optional[str]:
    """
    Look for the group key the trigger stamped onto the asset's params.

    The middleware only carries a step's own ``data`` plus one level of
    ``payload_history``, so this hits when the collector runs early in the
    graph (or under direct invocation). Later positions fall back to the
    execution-id lookup.
    """
    candidates: List[Any] = [payload.get("data"), payload.get("payload_history")]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        params = candidate.get("params")
        if isinstance(params, dict) and params.get("group_id"):
            return str(params["group_id"])
        if candidate.get("group_id"):
            return str(candidate["group_id"])
    return None


def _lookup_member_by_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """
    Find this execution's group member row via the executionId index.

    The index is sparse — only member (``EXEC#``) items carry ``executionId``
    — so a hit is unambiguous. Returns None when the execution is not part of
    a group, which is the common case for event-driven runs.
    """
    if not (GROUPS_TABLE_NAME and execution_id):
        return None

    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    for attempt in range(_GROUP_LOOKUP_ATTEMPTS):
        try:
            response = groups_table.query(
                IndexName=EXECUTION_INDEX_NAME,
                KeyConditionExpression=Key("executionId").eq(execution_id),
                Limit=1,
            )
            items = response.get("Items", [])
            if items:
                return items[0]
        except Exception as e:
            logger.warning(
                "Group member lookup failed",
                extra={"execution_id": execution_id, "error": str(e)},
            )
            return None
        if attempt < _GROUP_LOOKUP_ATTEMPTS - 1:
            time.sleep(_GROUP_LOOKUP_DELAY_SECONDS)
    return None


def _get_member(group_id: str, execution_id: str) -> Optional[Dict[str, Any]]:
    """Read a member row directly when the group key came from the payload."""
    if not (GROUPS_TABLE_NAME and group_id and execution_id):
        return None
    try:
        return (
            dynamodb.Table(GROUPS_TABLE_NAME)
            .get_item(Key={"PK": f"GROUP#{group_id}", "SK": f"EXEC#{execution_id}"})
            .get("Item")
        )
    except Exception as e:
        logger.warning(
            "Failed to read group member row",
            extra={"group_id": group_id, "execution_id": execution_id, "error": str(e)},
        )
        return None


def _resolve_group(
    payload: Dict[str, Any], execution_id: str
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Resolve (group_id, member_row) for this execution, or (None, None)."""
    group_id = _find_group_id_in_payload(payload)
    if group_id:
        return group_id, _get_member(group_id, execution_id)

    member = _lookup_member_by_execution(execution_id)
    if member:
        return str(member.get("groupId") or ""), member
    return None, None


def _resolve_asset(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get the asset record whose representations should be collected.

    Prefers the record already in the payload (the upstream node returns it as
    ``updatedAsset``, so it reflects the artifact just created) and falls back
    to a read when the payload was offloaded or trimmed.
    """
    assets = payload.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if isinstance(asset, dict) and asset.get("DerivedRepresentations"):
                return asset
        for asset in assets:
            if isinstance(asset, dict) and asset.get("InventoryID"):
                return asset

    inventory_id = None
    data = payload.get("data")
    if isinstance(data, dict):
        inventory_id = data.get("inventory_id") or data.get("InventoryID")
    if not (inventory_id and ASSET_TABLE_NAME):
        return None

    try:
        return (
            dynamodb.Table(ASSET_TABLE_NAME)
            .get_item(Key={"InventoryID": inventory_id})
            .get("Item")
        )
    except Exception as e:
        logger.warning(
            "Failed to load asset record",
            extra={"inventory_id": inventory_id, "error": str(e)},
        )
        return None


def _select_representations(
    asset: Dict[str, Any],
    purposes: List[str],
    baseline_rep_ids: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Choose which of the asset's derived representations to collect.

    With purposes configured, selection is by purpose: the pipeline author has
    declared what this branch delivers, and a re-run that overwrites an
    existing representation still yields the freshly produced file. Without
    purposes, selection falls back to representations the run added (not in
    the submit-time baseline) so an unconfigured node cannot quietly package
    an asset's entire representation set.

    Returns (selected, skipped) where each skipped entry explains itself.
    """
    baseline = set(baseline_rep_ids or [])
    selected: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    seen: set = set()

    for rep in asset.get("DerivedRepresentations", []) or []:
        if not isinstance(rep, dict):
            continue
        rep_id = rep.get("ID")
        purpose = str(rep.get("Purpose", "")).lower()
        if not rep_id or rep_id in seen:
            continue

        if purposes:
            if purpose not in purposes:
                continue
        elif rep_id in baseline:
            continue

        location = (rep.get("StorageInfo", {}) or {}).get("PrimaryLocation", {}) or {}
        bucket = location.get("Bucket")
        key = (location.get("ObjectKey", {}) or {}).get("FullPath")
        if not (bucket and key):
            # Metadata-only representations (embeddings, transcript pointers)
            # have nothing to download. Reported rather than dropped silently.
            skipped.append(
                {
                    "representationId": str(rep_id),
                    "purpose": purpose,
                    "reason": "NO_STORAGE_LOCATION",
                }
            )
            continue

        seen.add(rep_id)
        selected.append(
            {
                "representationId": str(rep_id),
                "purpose": purpose,
                "s3Uri": f"s3://{bucket}/{key}",
                "size": _to_int((location.get("FileInfo", {}) or {}).get("Size", 0)),
            }
        )

    return selected, skipped


def _group_ttl(group_id: str) -> Optional[int]:
    """Mirror the group's TTL so manifest rows expire with their group."""
    try:
        meta = (
            dynamodb.Table(GROUPS_TABLE_NAME)
            .get_item(Key={"PK": f"GROUP#{group_id}", "SK": "META"})
            .get("Item")
        )
    except Exception:
        meta = None
    if meta and meta.get("ttl"):
        return _to_int(meta["ttl"])
    return int(datetime.now(timezone.utc).timestamp()) + DEFAULT_TTL_DAYS * 24 * 3600


def _write_manifest(
    group_id: str,
    inventory_id: str,
    execution_id: str,
    step_name: str,
    artifacts: List[Dict[str, Any]],
) -> int:
    """
    Record the collected artifacts on the group.

    One item per (asset, representation) keyed ``COLLECTED#<asset>#<rep>``, so
    a retried execution overwrites its own rows instead of duplicating them.
    The finalizer reads these rows and packages exactly what it finds.
    """
    groups_table = dynamodb.Table(GROUPS_TABLE_NAME)
    ttl = _group_ttl(group_id)
    now = datetime.now(timezone.utc).isoformat()
    written = 0

    for artifact in artifacts:
        item = {
            "PK": f"GROUP#{group_id}",
            "SK": f"{COLLECTED_SK_PREFIX}{inventory_id}#{artifact['representationId']}",
            "groupId": group_id,
            "assetId": inventory_id,
            "representationId": artifact["representationId"],
            "purpose": artifact["purpose"],
            "s3Uri": artifact["s3Uri"],
            "size": artifact["size"],
            "collectedBy": step_name,
            "collectedAt": now,
        }
        # The index is sparse on executionId and must stay member-only, so the
        # execution is recorded under a different attribute name.
        if execution_id:
            item["collectedByExecutionId"] = execution_id
        if ttl:
            item["ttl"] = ttl
        groups_table.put_item(Item=item)
        written += 1

    return written


def _record_member_collection(group_id: str, execution_id: str, count: int) -> None:
    """Note the collected count on the member row (observability only)."""
    if not execution_id:
        return
    try:
        dynamodb.Table(GROUPS_TABLE_NAME).update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": f"EXEC#{execution_id}"},
            UpdateExpression="SET collectedCount = :n, collectedAt = :now",
            ExpressionAttributeValues={
                ":n": count,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.warning(
            "Failed to record collected count on member row",
            extra={"group_id": group_id, "execution_id": execution_id, "error": str(e)},
        )


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Register this branch's artifacts against the run's download group."""
    parameters = _resolve_params(event)
    purposes = _parse_purposes(parameters.get("Purposes"))
    require_artifacts = _is_true(parameters.get("Require Artifacts"))

    payload = event.get("payload", {}) or {}
    metadata = event.get("metadata", {}) or {}
    execution_id = str(metadata.get("pipelineExecutionId") or "")
    # This node's own label, from the deployer-set env var. metadata.stepName is
    # the UPSTREAM step's name (the middleware stamps it on the way out), so
    # reading it first would attribute every collected artifact to the previous
    # node.
    step_name = str(
        os.environ.get("STEP_NAME") or metadata.get("stepName") or "collect"
    )

    def _result(status: str, **extra: Any) -> Dict[str, Any]:
        summary = {
            "status": status,
            "collected": 0,
            "purposes": purposes,
            "executionId": execution_id,
        }
        summary.update(extra)
        return {"downloadCollection": summary}

    if not GROUPS_TABLE_NAME:
        # Deployment predates the group feature — nothing to collect against.
        logger.info("PIPELINE_GROUPS_TABLE_NAME not set; collection skipped")
        return _result("SKIPPED_NOT_CONFIGURED")

    group_id, member = _resolve_group(payload, execution_id)
    if not group_id:
        # The overwhelmingly common case for event-driven runs: the pipeline
        # was not launched as a download group, so the node is a no-op.
        logger.info(
            "Execution is not part of a download group; collection skipped",
            extra={"execution_id": execution_id},
        )
        return _result("SKIPPED_NOT_GROUPED")

    asset = _resolve_asset(payload)
    if not asset or not asset.get("InventoryID"):
        message = "Download Collector could not resolve the asset to collect from"
        if require_artifacts:
            raise RuntimeError(message)
        logger.warning(message, extra={"group_id": group_id})
        return _result("SKIPPED_NO_ASSET", groupId=group_id)

    inventory_id = str(asset["InventoryID"])
    baseline_rep_ids = [str(r) for r in (member or {}).get("baselineRepIds", []) or []]
    if not purposes and not member:
        logger.warning(
            "No purposes configured and no baseline snapshot available; "
            "collecting every derived representation on the asset. Set the "
            "node's Purposes to declare what this branch delivers.",
            extra={"group_id": group_id, "inventory_id": inventory_id},
        )

    artifacts, skipped = _select_representations(asset, purposes, baseline_rep_ids)

    if not artifacts:
        message = (
            "Download Collector found no artifacts to collect. The node "
            "collects derived representations recorded on the asset — a node "
            "that writes files to S3 without recording a "
            "DerivedRepresentation (with StorageInfo.PrimaryLocation) leaves "
            "nothing to collect."
        )
        if require_artifacts:
            raise RuntimeError(message)
        logger.warning(
            message,
            extra={
                "group_id": group_id,
                "inventory_id": inventory_id,
                "purposes_filter": purposes or "NEW_REPRESENTATIONS",
                "skipped": skipped,
            },
        )
        return _result(
            "NO_ARTIFACTS",
            groupId=group_id,
            assetId=inventory_id,
            skipped=skipped,
        )

    written = _write_manifest(
        group_id, inventory_id, execution_id, step_name, artifacts
    )
    _record_member_collection(group_id, execution_id, written)

    logger.info(
        "Collected artifacts for download packaging",
        extra={
            "group_id": group_id,
            "inventory_id": inventory_id,
            "collected": written,
            "purposes_filter": purposes or "NEW_REPRESENTATIONS",
        },
    )

    return {
        "downloadCollection": {
            "status": "COLLECTED",
            "groupId": group_id,
            "assetId": inventory_id,
            "collected": written,
            "purposes": purposes,
            "executionId": execution_id,
            "artifacts": artifacts,
            "skipped": skipped,
        }
    }
