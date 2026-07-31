import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

# Default maximum batch size for pipeline trigger requests
DEFAULT_MAX_BATCH_SIZE = 50

# Days before pipeline-group tracking records expire (DynamoDB TTL).
# Matches the bulk-download job retention window.
DEFAULT_GROUP_TTL_DAYS = 7

# Node template id of the Download Collector node. Its presence in a pipeline
# definition is how a pipeline declares which of its outputs are deliverables.
DOWNLOAD_COLLECTOR_NODE_ID = "download_collector"

# How the finalizer resolves a group's artifacts.
PACKAGING_MODE_COLLECTOR = "COLLECTOR"
PACKAGING_MODE_AUTO_DISCOVER = "AUTO_DISCOVER"

# Artifact selection is purpose-agnostic by default: an empty purposes list
# means "every derived representation this group's executions created", so any
# pipeline that records its outputs on the asset participates without special
# configuration. Supplying purposes narrows the selection (e.g. ["smartcrop"]
# to package only reframed renditions).
DEFAULT_GROUP_PURPOSES: list[str] = []

# Terminal group statuses (mirrors the upload-session terminal model)
GROUP_STATUS_OPEN = "OPEN"
GROUP_STATUS_COMPLETED = "COMPLETED"
GROUP_STATUS_COMPLETED_WITH_FAILURES = "COMPLETED_WITH_FAILURES"
GROUP_STATUS_FAILED = "FAILED"


def _get_cors_headers() -> dict[str, str]:
    """Return standard CORS headers for API responses."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def _error_response(status_code: int, error: str) -> dict[str, Any]:
    """Create a standardized error response."""
    return {
        "statusCode": status_code,
        "headers": _get_cors_headers(),
        "body": json.dumps({"error": error}),
    }


def _parse_request_body(body_str: str) -> tuple[dict | None, str | None]:
    """
    Parse and validate the request body.

    Supports two formats:
    1. New format: {"assets": [{"inventory_id": "...", "params": {...}}, ...]}
    2. Legacy format: {"inventory_ids": ["id1", "id2", ...]}

    Returns:
        Tuple of (parsed_body, error_message)
    """
    try:
        body = json.loads(body_str or "{}")
    except json.JSONDecodeError:
        return None, "Invalid JSON in request body"

    return body, None


def _normalize_assets(body: dict) -> tuple[list[dict] | None, str | None]:
    """
    Normalize the request body to the new assets format.

    Supports:
    1. New format: {"assets": [{"inventory_id": "...", "params": {...}}, ...]}
    2. Legacy format: {"inventory_ids": ["id1", "id2", ...]}

    Returns:
        Tuple of (normalized_assets_list, error_message)
    """
    # Check for new format first
    if "assets" in body:
        assets = body.get("assets", [])
        if not isinstance(assets, list):
            return None, "assets must be an array"

        # Validate each asset has inventory_id
        for i, asset in enumerate(assets):
            if not isinstance(asset, dict):
                return None, f"Asset at index {i} must be an object"
            if not asset.get("inventory_id"):
                return (
                    None,
                    f"Asset at index {i} is missing required field 'inventory_id'",
                )
            # Ensure params exists (default to empty dict)
            if "params" not in asset:
                asset["params"] = {}
            elif not isinstance(asset.get("params"), dict):
                return (
                    None,
                    f"Asset at index {i} has invalid 'params' - must be an object",
                )

        return assets, None

    # Fall back to legacy format
    if "inventory_ids" in body:
        inventory_ids = body.get("inventory_ids", [])
        if not inventory_ids or not isinstance(inventory_ids, list):
            return None, "Missing or invalid inventory_ids in request body"

        # Convert to new format
        assets = [{"inventory_id": inv_id, "params": {}} for inv_id in inventory_ids]
        return assets, None

    return None, "Request body must contain either 'assets' or 'inventory_ids'"


def _validate_batch_size(assets: list[dict], max_batch_size: int) -> str | None:
    """
    Validate that the batch size doesn't exceed the maximum.

    Returns:
        Error message if validation fails, None otherwise
    """
    if len(assets) > max_batch_size:
        return f"Batch size {len(assets)} exceeds maximum allowed ({max_batch_size})"
    if len(assets) == 0:
        return "At least one asset is required"
    return None


def _get_user_id(event: dict) -> str | None:
    """Extract the caller's user id from the Cognito authorizer context."""
    return (event.get("requestContext", {}).get("authorizer", {}) or {}).get("userId")


def _extract_group_config(body: dict) -> tuple[dict | None, str | None]:
    """
    Parse and validate the optional ``group`` object from the request body.

    Shape (all fields optional except presence of the object itself):
        {"group": {"package": true, "purposes": ["smartcrop"], "name": "..."}}

    When present, all executions started by this request share a group key.
    When the group completes, the output artifacts its executions created are
    packaged into a downloadable zip via the bulk-download workflow (unless
    ``package`` is false).

    ``purposes`` is an optional filter. Omitted (the default), every derived
    representation the group's executions added to their assets is packaged —
    so this works the same for reframe, proxies, transcodes, or any other
    pipeline that records its outputs on the asset. Supplying purposes
    restricts packaging to those representation purposes.

    Returns:
        Tuple of (normalized_group_config, error_message). Both are None when
        the request has no group object (single/ungrouped behavior).
    """
    if "group" not in body:
        return None, None

    group = body.get("group")
    if not isinstance(group, dict):
        return None, "group must be an object"

    package = group.get("package", True)
    if not isinstance(package, bool):
        return None, "group.package must be a boolean"

    purposes = group.get("purposes", DEFAULT_GROUP_PURPOSES)
    if not isinstance(purposes, list) or not all(
        isinstance(p, str) and p.strip() for p in purposes
    ):
        return None, "group.purposes must be an array of non-empty strings"

    name = group.get("name", "")
    if not isinstance(name, str):
        return None, "group.name must be a string"

    return {"package": package, "purposes": purposes, "name": name.strip()}, None


def _packaging_mode(pipeline: dict) -> str:
    """
    Decide how the group's output artifacts will be resolved.

    A pipeline that contains a Download Collector node declares its own
    deliverables: the node registers the artifacts on the branch it sits on,
    and the finalizer packages exactly those. Pipelines without one keep the
    legacy behavior, where outputs are inferred by diffing each asset's
    derived representations against a submit-time baseline.

    Unparseable definitions fall back to AUTO_DISCOVER so a malformed record
    cannot block packaging outright.
    """
    try:
        nodes = (
            pipeline.get("definition", {}).get("configuration", {}).get("nodes", [])
            or []
        )
        for node in nodes:
            data = node.get("data", {}) if isinstance(node, dict) else {}
            node_template_id = data.get("nodeId") or data.get("id")
            if node_template_id == DOWNLOAD_COLLECTOR_NODE_ID:
                return PACKAGING_MODE_COLLECTOR
    except Exception as e:  # noqa: BLE001 - definition shape is user data
        print(f"Warning: could not inspect pipeline definition for collector: {e}")
    return PACKAGING_MODE_AUTO_DISCOVER


def _snapshot_baseline_reps(
    asset_table: Any, inventory_ids: list[str]
) -> dict[str, list[str]]:
    """
    Snapshot the derived-representation IDs each asset already has.

    The group finalizer packages only representations created AFTER the group
    was submitted, computed as (final reps) minus (this baseline). A partial
    or failed snapshot degrades gracefully: missing assets get an empty
    baseline, which at worst includes pre-existing artifacts in the zip.
    """
    baselines: dict[str, list[str]] = {inv_id: [] for inv_id in inventory_ids}
    unique_ids = list(dict.fromkeys(inventory_ids))

    try:
        for i in range(0, len(unique_ids), 100):
            batch = unique_ids[i : i + 100]
            request = {
                asset_table.name: {
                    "Keys": [{"InventoryID": inv_id} for inv_id in batch],
                    "ProjectionExpression": "InventoryID, DerivedRepresentations",
                }
            }
            while request:
                response = asset_table.meta.client.batch_get_item(RequestItems=request)
                for item in response.get("Responses", {}).get(asset_table.name, []):
                    inv_id = item.get("InventoryID")
                    reps = item.get("DerivedRepresentations", []) or []
                    if inv_id:
                        baselines[inv_id] = [
                            rep.get("ID") for rep in reps if rep.get("ID")
                        ]
                unprocessed = response.get("UnprocessedKeys") or {}
                request = unprocessed if unprocessed.get(asset_table.name) else None
    except Exception as e:
        print(f"Warning: baseline representation snapshot failed: {str(e)}")

    return baselines


def _create_group_record(
    groups_table: Any,
    group_id: str,
    user_id: str,
    pipeline_id: str,
    pipeline_name: str,
    group_config: dict,
    expected_count: int,
    packaging_mode: str = PACKAGING_MODE_AUTO_DISCOVER,
) -> None:
    """Create the group META item with counters at zero and status OPEN."""
    now = datetime.now(timezone.utc).isoformat()
    ttl_days = int(os.environ.get("GROUP_RECORD_TTL_DAYS", DEFAULT_GROUP_TTL_DAYS))
    groups_table.put_item(
        Item={
            "PK": f"GROUP#{group_id}",
            "SK": "META",
            "groupId": group_id,
            "userId": user_id,
            "pipelineId": pipeline_id,
            "pipelineName": pipeline_name,
            "groupName": group_config.get("name", ""),
            "status": GROUP_STATUS_OPEN,
            "expectedCount": expected_count,
            "completedCount": 0,
            "failedCount": 0,
            "resolvedCount": 0,
            "package": {
                "enabled": group_config.get("package", True),
                "purposes": group_config.get("purposes", DEFAULT_GROUP_PURPOSES),
                # COLLECTOR when the pipeline graph declares its deliverables
                # with a Download Collector node; AUTO_DISCOVER otherwise.
                "mode": packaging_mode,
            },
            "createdAt": now,
            "updatedAt": now,
            "ttl": int(datetime.now(timezone.utc).timestamp()) + ttl_days * 24 * 3600,
        },
        ConditionExpression="attribute_not_exists(PK)",
    )


def _record_group_member(
    groups_table: Any,
    group_id: str,
    execution_id: str,
    inventory_id: str,
    params: dict,
    baseline_rep_ids: list[str],
) -> None:
    """
    Record a member execution on the group.

    The executions event processor later claims this item (sets countedAt)
    when the execution reaches a terminal state; the finalizer reads
    baselineRepIds to compute which representations the execution created.
    """
    groups_table.put_item(
        Item={
            "PK": f"GROUP#{group_id}",
            "SK": f"EXEC#{execution_id}",
            "groupId": group_id,
            "executionId": execution_id,
            "inventoryId": inventory_id,
            "params": {k: v for k, v in params.items() if k != "group_id"},
            "baselineRepIds": baseline_rep_ids,
            "status": "STARTED",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    )


def _group_terminal_status(completed_count: int, failed_count: int) -> str:
    if failed_count == 0:
        return GROUP_STATUS_COMPLETED
    if completed_count == 0:
        return GROUP_STATUS_FAILED
    return GROUP_STATUS_COMPLETED_WITH_FAILURES


def _attempt_group_terminal_transition(groups_table: Any, group_id: str) -> None:
    """
    Transition the group META item OPEN → terminal once every member has
    resolved. Safe to call concurrently: the conditional update guarantees
    exactly one writer wins, and the groups-table stream fires the finalizer
    off that single transition.
    """
    try:
        meta = groups_table.get_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            ConsistentRead=True,
        ).get("Item")
        if not meta or meta.get("status") != GROUP_STATUS_OPEN:
            return
        if int(meta.get("resolvedCount", 0)) < int(meta.get("expectedCount", 0)):
            return

        terminal = _group_terminal_status(
            int(meta.get("completedCount", 0)), int(meta.get("failedCount", 0))
        )
        groups_table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            UpdateExpression="SET #st = :terminal, updatedAt = :now",
            ConditionExpression="#st = :open AND resolvedCount >= expectedCount",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":terminal": terminal,
                ":open": GROUP_STATUS_OPEN,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )
    except groups_table.meta.client.exceptions.ConditionalCheckFailedException:
        pass  # another writer already transitioned the group
    except Exception as e:
        print(f"Warning: group terminal transition attempt failed: {str(e)}")


def _count_failed_starts(groups_table: Any, group_id: str, failed_count: int) -> None:
    """
    Fold executions that never started into the group counters as failures.

    They will never emit a Step Functions terminal event, so without this the
    group could stay OPEN until the sweeper times it out.
    """
    if failed_count <= 0:
        return
    try:
        groups_table.update_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "META"},
            UpdateExpression=(
                "ADD failedCount :n, resolvedCount :n SET updatedAt = :now"
            ),
            ConditionExpression="#st = :open",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":n": failed_count,
                ":open": GROUP_STATUS_OPEN,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        print(f"Warning: failed-start count update failed: {str(e)}")


def _setup_group(
    event: dict,
    dynamodb: Any,
    assets: list[dict],
    pipeline_id: str,
    pipeline: dict,
    group_config: dict,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Create the execution group and stamp its key onto every asset's params.

    Returns:
        Tuple of (group_context, error_response). ``group_context`` carries
        ``group_id``, ``groups_table`` and the per-asset ``baselines`` when
        setup succeeded; ``error_response`` is a ready-to-return API Gateway
        response when it failed (and the caller must not start executions).
    """
    groups_table_name = os.environ.get("PIPELINE_GROUPS_TABLE_NAME")
    if not groups_table_name:
        return {}, _error_response(
            400, "Grouped execution is not available in this deployment"
        )

    user_id = _get_user_id(event)
    if not user_id:
        return {}, _error_response(
            401, "User identity is required for grouped execution"
        )

    groups_table = dynamodb.Table(groups_table_name)
    group_id = str(uuid.uuid4())
    packaging_mode = _packaging_mode(pipeline)

    # Snapshot existing derived reps. In AUTO_DISCOVER mode this is what the
    # finalizer diffs against; in COLLECTOR mode the collector node uses it as
    # the fallback selection basis when no purposes are configured on it.
    baselines: dict[str, list[str]] = {}
    asset_table_name = os.environ.get("MEDIALAKE_ASSET_TABLE", "")
    if asset_table_name:
        baselines = _snapshot_baseline_reps(
            dynamodb.Table(asset_table_name),
            [a["inventory_id"] for a in assets],
        )

    try:
        _create_group_record(
            groups_table,
            group_id,
            user_id,
            pipeline_id,
            pipeline.get("name", pipeline_id),
            group_config,
            len(assets),
            packaging_mode,
        )
    except Exception as e:
        print(f"Error creating group record: {str(e)}")
        return {}, _error_response(500, f"Failed to create execution group: {str(e)}")

    # Ride the group key on each asset's params. The lambda middleware
    # forwards params untouched and existing nodes ignore unknown keys, so
    # this is invisible to pipeline behavior.
    for asset in assets:
        asset["params"]["group_id"] = group_id

    print(
        f"Created execution group {group_id} for pipeline {pipeline_id} "
        f"({len(assets)} assets, packaging mode {packaging_mode})"
    )

    return (
        {
            "group_id": group_id,
            "groups_table": groups_table,
            "baselines": baselines,
            "packaging_mode": packaging_mode,
        },
        None,
    )


def _build_step_function_input(
    asset: dict[str, Any],
    pipeline_id: str,
) -> dict[str, Any]:
    """
    Build the Step Function execution input for a single asset.

    The input format is designed to work with the lambda_middleware's
    _standardize_input method, which expects:
    {
        "item": {
            "inventory_id": "...",
            "params": {...}
        }
    }

    The middleware will:
    1. Detect the item.inventory_id pattern
    2. Fetch the full asset record from DynamoDB
    3. Put the item object into payload.data
    4. Put the DynamoDB record into payload.assets

    Args:
        asset: Asset object with inventory_id and params
        pipeline_id: The pipeline being triggered

    Returns:
        Step Function input dictionary
    """
    return {
        "item": {
            "inventory_id": asset["inventory_id"],
            "params": asset.get("params", {}),
        },
        # Include pipeline context for tracking
        "pipeline_id": pipeline_id,
        "trigger_type": "manual",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda function to manually trigger a pipeline for specific assets.

    Expected path parameters:
    - pipeline_id: The ID of the pipeline to trigger

    Expected body (new format - preferred):
    {
        "assets": [
            {"inventory_id": "uuid-1", "params": {"correlation_id": "ABC123"}},
            {"inventory_id": "uuid-2", "params": {}}
        ]
    }

    Expected body (legacy format - still supported):
    {
        "inventory_ids": ["uuid-1", "uuid-2"]
    }

    The params object is flexible and can contain any pipeline-specific arguments.
    For external metadata enrichment pipelines, params may include:
    - correlation_id: Override for the external system asset ID

    Returns:
    - pipeline_id: The triggered pipeline ID
    - total_assets: Total number of assets to process
    - successful_executions: Number of successful executions started
    - failed_executions: Number of failed executions
    - executions: List of execution details with inventory_id, execution_arn, status
    - message: Success/error message
    """
    try:
        # Get max batch size from environment or use default
        max_batch_size = int(os.environ.get("MAX_BATCH_SIZE", DEFAULT_MAX_BATCH_SIZE))

        # Parse the request
        pipeline_id = event.get("pathParameters", {}).get("pipelineId")
        if not pipeline_id:
            return _error_response(400, "Missing pipelineId in path parameters")

        # Parse request body
        body, parse_error = _parse_request_body(event.get("body", "{}"))
        if parse_error or body is None:
            return _error_response(400, parse_error or "Invalid request body")

        # Normalize to assets format (supports both new and legacy formats)
        assets, normalize_error = _normalize_assets(body)
        if normalize_error or assets is None:
            return _error_response(400, normalize_error or "Invalid assets format")

        # Validate batch size
        batch_error = _validate_batch_size(assets, max_batch_size)
        if batch_error:
            return _error_response(400, batch_error)

        # Optional group config (backwards compatible: absent = ungrouped)
        group_config, group_error = _extract_group_config(body)
        if group_error:
            return _error_response(400, group_error)

        print(f"Triggering pipeline {pipeline_id} for {len(assets)} assets")

        # Initialize AWS clients
        dynamodb = boto3.resource("dynamodb")
        stepfunctions = boto3.client("stepfunctions")

        # Get pipeline information from DynamoDB
        pipelines_table = dynamodb.Table(
            os.environ.get("PIPELINES_TABLE", "MediaLakePipelines")
        )

        try:
            pipeline_response = pipelines_table.get_item(Key={"id": pipeline_id})
            if "Item" not in pipeline_response:
                return _error_response(404, f"Pipeline {pipeline_id} not found")

            pipeline = pipeline_response["Item"]

            # Check if pipeline has manual trigger capability by checking the type field
            pipeline_type = pipeline.get("type", "")
            if "Manual Trigger" not in pipeline_type:
                return _error_response(
                    400, f"Pipeline {pipeline_id} does not support manual triggering"
                )

        except Exception as e:
            print(f"Error fetching pipeline: {str(e)}")
            return _error_response(
                500, f"Error fetching pipeline information: {str(e)}"
            )

        # Get the Step Function ARN from the pipeline
        state_machine_arn = pipeline.get("stateMachineArn")
        if not state_machine_arn:
            return _error_response(
                500, f"Pipeline {pipeline_id} does not have a valid Step Function ARN"
            )

        # ── Group setup (only when the request carries a group object) ──
        group_ctx: dict[str, Any] = {}
        if group_config is not None:
            group_ctx, group_setup_error = _setup_group(
                event=event,
                dynamodb=dynamodb,
                assets=assets,
                pipeline_id=pipeline_id,
                pipeline=pipeline,
                group_config=group_config,
            )
            if group_setup_error:
                return group_setup_error

        group_id = group_ctx.get("group_id")
        groups_table = group_ctx.get("groups_table")
        baselines: dict[str, list[str]] = group_ctx.get("baselines", {})

        # Trigger pipeline executions for each asset
        executions = []
        successful_executions = 0
        failed_executions = 0

        for asset in assets:
            inventory_id = asset["inventory_id"]
            try:
                # Build input for Step Function execution
                # Format: {"item": {"inventory_id": "...", "params": {...}}}
                # This format is expected by the lambda_middleware
                step_function_input = _build_step_function_input(asset, pipeline_id)

                # Start Step Function execution
                sf_response = stepfunctions.start_execution(
                    stateMachineArn=state_machine_arn,
                    input=json.dumps(step_function_input),
                )

                # Extract execution ARN and name from response
                execution_arn = sf_response.get("executionArn", "")
                # Extract execution name from ARN (last part after the last colon)
                execution_name = (
                    execution_arn.split(":")[-1]
                    if execution_arn
                    else f"auto-{uuid.uuid4().hex[:8]}"
                )

                executions.append(
                    {
                        "inventory_id": inventory_id,
                        "execution_id": execution_name,
                        "execution_arn": execution_arn,
                        "status": "started",
                        "params": asset.get("params", {}),
                    }
                )
                successful_executions += 1

                # Track this execution as a group member so the executions
                # event processor can count its terminal state.
                if group_id and groups_table is not None:
                    try:
                        _record_group_member(
                            groups_table,
                            group_id,
                            execution_name,
                            inventory_id,
                            asset.get("params", {}),
                            baselines.get(inventory_id, []),
                        )
                    except Exception as member_error:
                        print(
                            f"Warning: failed to record group member for "
                            f"{inventory_id}: {str(member_error)}"
                        )

                print(
                    f"Successfully started Step Function execution for asset {inventory_id}: {execution_arn}"
                )

            except Exception as e:
                print(
                    f"Error starting Step Function execution for asset {inventory_id}: {str(e)}"
                )
                executions.append(
                    {
                        "inventory_id": inventory_id,
                        "execution_id": "",
                        "execution_arn": "",
                        "status": "failed",
                        "error": str(e),
                        "params": asset.get("params", {}),
                    }
                )
                failed_executions += 1

        # Fold never-started executions into the group as failures and close
        # the group immediately if nothing is left to wait for.
        if group_id and groups_table is not None:
            _count_failed_starts(groups_table, group_id, failed_executions)
            _attempt_group_terminal_transition(groups_table, group_id)

        # Prepare response
        total_assets = len(assets)

        if successful_executions > 0:
            message = f"Successfully triggered pipeline for {successful_executions} out of {total_assets} assets"
            if failed_executions > 0:
                message += f" ({failed_executions} failed)"
        else:
            message = f"Failed to trigger pipeline for all {total_assets} assets"

        response_body = {
            "pipeline_id": pipeline_id,
            "total_assets": total_assets,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "executions": executions,
            "message": message,
        }
        if group_id:
            response_body["group_id"] = group_id
            response_body["packaging_mode"] = group_ctx.get(
                "packaging_mode", PACKAGING_MODE_AUTO_DISCOVER
            )

        return {
            "statusCode": 200,
            "headers": _get_cors_headers(),
            "body": json.dumps(response_body),
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return _error_response(500, f"Internal server error: {str(e)}")
