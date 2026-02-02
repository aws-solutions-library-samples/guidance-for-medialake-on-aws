import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

# Default maximum batch size for pipeline trigger requests
DEFAULT_MAX_BATCH_SIZE = 50


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

        return {
            "statusCode": 200,
            "headers": _get_cors_headers(),
            "body": json.dumps(response_body),
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return _error_response(500, f"Internal server error: {str(e)}")
