import os
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent

# (Adjust these imports if your project structure differs)
from lambda_utils import lambda_handler_decorator, logger, metrics, tracer, handle_error

# ─────────────────────────────────────────────────────────────────────────────
# Initialize DynamoDB table (with X-Ray tracing)
# ─────────────────────────────────────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"])

logger = Logger(service="pipelines_executions_event_processor")
tracer = Tracer(service="pipelines_executions_event_processor")
metrics = Metrics(service="pipelines_executions_event_processor", namespace="MyApp/Pipelines")


def convert_to_decimal(obj: Any) -> Any:
    """
    Recursively walk a structure (dict, list, primitive) and convert
    any float/int into a Decimal. Strings and other types pass through unchanged.
    """
    if isinstance(obj, dict):
        return {k: convert_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_to_decimal(v) for v in obj]
    if isinstance(obj, float):
        # Convert float → Decimal via string to preserve precision
        return Decimal(str(obj))
    if isinstance(obj, int):
        return Decimal(obj)
    # leave strings, booleans, None, etc. as‐is
    return obj


def calculate_execution_duration(
    start_time: Any, end_time: Optional[str] = None
) -> Optional[Decimal]:
    """
    Calculate the duration of the execution in seconds.

    Returns None if start_time or end_time is missing or unparseable.
    """
    if not end_time or not start_time:
        return None

    if isinstance(start_time, datetime):
        start_time = start_time.isoformat()
    elif not isinstance(start_time, str):
        logger.warning(f"Invalid start_time format: {type(start_time)}")
        return None

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        return Decimal(str((end_dt - start_dt).total_seconds()))
    except (ValueError, TypeError) as e:
        logger.warning(f"Error calculating duration: {e}")
        return None


@tracer.capture_method
def store_execution_details(item: Dict[str, Any]) -> None:
    """
    Write one item into DynamoDB (with X-Ray tracing).
    """
    logger.info(f"store_execution_details: about to write item to DynamoDB:\n{json.dumps(item, default=str)}")
    table.put_item(Item=item)
    logger.info("store_execution_details: write complete")


@tracer.capture_method
def extract_pipeline_name(execution_arn: str) -> str:
    """
    Given an SFN execution ARN, return the pipeline name portion.
    ARN format: arn:aws:states:region:acct:execution:pipeline_name:execution_id
    """
    try:
        pipeline_name = execution_arn.split(":")[-2]
        logger.debug(f"extract_pipeline_name: pipeline_name = {pipeline_name}")
        return pipeline_name
    except (IndexError, AttributeError):
        logger.error(f"Failed to extract pipeline name from ARN: {execution_arn}")
        raise ValueError(f"Invalid execution ARN format: {execution_arn}")


def convert_to_unix_timestamp(time_ms: float) -> int:
    """
    Convert a millisecond timestamp into a Unix timestamp (seconds).
    """
    return int(time_ms / 1000.0)


def parse_nested_metadata(detail_input_str: str) -> Dict[str, Any]:
    """
    Parse the JSON string in detail.input and extract:

    • inventory_id:
        – top-level: nested["detail"]["InventoryID"]
        – or second-level: nested["detail"]["detail"]["InventoryID"]

    • pipeline_trace_id:
        – nested["detail"]["metadata"]["pipelineTraceId"]

    • dsa_type (DigitalSourceAsset Type):
        – nested["detail"]["DigitalSourceAsset"]["Type"]

    • object_key_name:
        – nested["detail"]["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"]
          ["PrimaryLocation"]["ObjectKey"]["Name"]

    • metadata fields (if present):
        – stepName     → top-level "step_name"
        – stepStatus   → top-level "step_status"
        – stepResult   → top-level "step_result"
        – the entire metadata object (with all numbers converted to Decimal)

    Returns a dict containing any of:
        {
          "inventory_id": "...",
          "pipeline_trace_id": "...",
          "dsa_type": "...",
          "object_key_name": "...",
          "step_name": "...",
          "step_status": "...",
          "step_result": "...",
          "metadata": { ... }    # full nested metadata, but nums as Decimal
        }
    """
    nested_fields: Dict[str, Any] = {}
    try:
        nested = json.loads(detail_input_str)
    except (TypeError, json.JSONDecodeError) as e:
        # Not valid JSON (or not a string) → nothing to extract
        logger.debug(f"parse_nested_metadata: could not parse detail.input as JSON: {e}")
        return nested_fields

    detail1 = nested.get("detail", {})

    # —————————
    # 1) InventoryID (top-level or second-level)
    # —————————
    inv_top = detail1.get("InventoryID")
    if inv_top:
        nested_fields["inventory_id"] = inv_top
        logger.info(f"parse_nested_metadata: found top-level inventory_id = {inv_top}")
    else:
        detail2 = detail1.get("detail", {})
        inv_second = detail2.get("InventoryID")
        if inv_second:
            nested_fields["inventory_id"] = inv_second
            logger.info(f"parse_nested_metadata: found nested inventory_id = {inv_second}")

    # —————————
    # 2) pipelineTraceId
    # —————————
    meta = detail1.get("metadata", {})
    pipeline_trace_id = meta.get("pipelineTraceId")
    if pipeline_trace_id:
        nested_fields["pipeline_trace_id"] = pipeline_trace_id
        logger.info(f"parse_nested_metadata: pipelineTraceId = {pipeline_trace_id}")

    # —————————
    # 3) DigitalSourceAsset Type ("dsa_type")
    # —————————
    dsa = detail1.get("DigitalSourceAsset", {})
    dsa_type = dsa.get("Type")
    if dsa_type:
        nested_fields["dsa_type"] = dsa_type
        logger.info(f"parse_nested_metadata: dsa_type = {dsa_type}")

    # —————————
    # 4) ObjectKey → Name ("object_key_name")
    # —————————
    main_repr = dsa.get("MainRepresentation", {})
    storage_info = main_repr.get("StorageInfo", {})
    primary_loc = storage_info.get("PrimaryLocation", {})
    object_key = primary_loc.get("ObjectKey", {})
    obj_name = object_key.get("Name")
    if obj_name:
        nested_fields["object_key_name"] = obj_name
        logger.info(f"parse_nested_metadata: object_key_name = {obj_name}")

    # —————————
    # 5) metadata: stepName, stepStatus, stepResult, plus the entire metadata map
    # —————————
    if meta:
        # If the payload’s metadata dict exists, pull out specific fields:
        step_name = meta.get("stepName")
        if step_name:
            nested_fields["step_name"] = step_name
            logger.info(f"parse_nested_metadata: stepName = {step_name}")

        step_status = meta.get("stepStatus")
        if step_status:
            nested_fields["step_status"] = step_status
            logger.info(f"parse_nested_metadata: stepStatus = {step_status}")

        step_result = meta.get("stepResult")
        if step_result:
            nested_fields["step_result"] = step_result
            logger.info(f"parse_nested_metadata: stepResult = {step_result}")

        # Convert the entire metadata dict so any floats/ints become Decimal
        # before saving into DynamoDB.
        decimal_metadata = convert_to_decimal(meta)
        nested_fields["metadata"] = decimal_metadata
        logger.info("parse_nested_metadata: stored full metadata map (nums→Decimal)")

    return nested_fields


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Processes Step Functions execution‐status events and writes (or updates) a row in DynamoDB.

    Includes:
      • inventory_id
      • pipeline_trace_id
      • dsa_type
      • object_key_name
      • step_name, step_status, step_result
      • full metadata map (with numbers as Decimal)
    """
    try:
        logger.info(f"lambda_handler: incoming event = {json.dumps(event)}")
        evt = EventBridgeEvent(event)
        detail = evt.detail

        # ────────────────────────────────────────────────────────────────
        # 1) Required top-level fields
        # ────────────────────────────────────────────────────────────────
        execution_arn = detail.get("executionArn")
        if not execution_arn:
            raise ValueError("executionArn is required but missing")

        execution_id = execution_arn.split(":")[-1]
        if not execution_id:
            raise ValueError("Could not extract execution_id from executionArn")

        state_machine_arn = detail.get("stateMachineArn")
        if not state_machine_arn:
            raise ValueError("stateMachineArn is required but missing")

        status = detail.get("status")
        if not status:
            raise ValueError("status is required but missing")

        start_date_ms = detail.get("startDate")
        if not start_date_ms:
            raise ValueError("startDate is required but missing")

        # Convert startDate → UNIX seconds + ISO string
        start_date_unix = convert_to_unix_timestamp(start_date_ms)
        start_date_iso = datetime.fromtimestamp(start_date_unix).isoformat()
        current_time_iso = datetime.utcnow().isoformat()

        logger.debug(
            "Processing execution event",
            extra={
                "execution_id": execution_id,
                "execution_arn": execution_arn,
                "state_machine_arn": state_machine_arn,
                "status": status,
                "start_date": start_date_iso,
            },
        )

        # ────────────────────────────────────────────────────────────────
        # 2) Extract pipeline name from execution ARN
        # ────────────────────────────────────────────────────────────────
        pipeline_name = extract_pipeline_name(execution_arn)

        # ────────────────────────────────────────────────────────────────
        # 3) Build the “base” DynamoDB item
        # ────────────────────────────────────────────────────────────────
        base_item: Dict[str, Any] = {
            "execution_id": execution_id,              # PK
            "start_time": start_date_unix,             # sort key
            "start_time_iso": start_date_iso,          # human-readable
            "pipeline_name": pipeline_name,
            "execution_arn": execution_arn,
            "state_machine_arn": state_machine_arn,
            "status": status,
            "last_updated": current_time_iso,
            # TTL = now + 90 days (in UNIX seconds)
            "ttl": int(datetime.utcnow().timestamp() + (90 * 24 * 60 * 60)),
        }

        logger.info(f"lambda_handler: base item = {json.dumps(base_item)}")

        # ────────────────────────────────────────────────────────────────
        # 4) Parse nested metadata (inventory_id, pipeline_trace_id, etc.)
        # ────────────────────────────────────────────────────────────────
        nested_meta_from_input: Dict[str, Any] = {}
        raw_input = detail.get("input")
        if isinstance(raw_input, str):
            logger.info("lambda_handler: detail.input is a JSON string—parsing for nested metadata")
            nested_meta_from_input = parse_nested_metadata(raw_input)
            logger.info(f"lambda_handler: nested_meta_from_input = {nested_meta_from_input}")

        # Merge any nested fields into base_item
        if nested_meta_from_input:
            base_item.update(nested_meta_from_input)

        # ────────────────────────────────────────────────────────────────
        # 5) If terminal status, capture stopDate / duration / error / cause
        # ────────────────────────────────────────────────────────────────
        if status in ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]:
            stop_date_ms = detail.get("stopDate")
            if stop_date_ms:
                stop_date_unix = convert_to_unix_timestamp(stop_date_ms)
                end_time_iso = datetime.fromtimestamp(stop_date_unix).isoformat()

                base_item["end_time"] = stop_date_unix
                base_item["end_time_iso"] = end_time_iso

                duration = calculate_execution_duration(start_date_iso, end_time_iso)
                if duration is not None:
                    base_item["duration_seconds"] = duration  # Already a Decimal

            if status in ["FAILED", "TIMED_OUT", "ABORTED"]:
                error_msg = detail.get("error")
                cause_msg = detail.get("cause")
                if error_msg:
                    base_item["error"] = error_msg
                if cause_msg:
                    base_item["cause"] = cause_msg

        # ────────────────────────────────────────────────────────────────
        # 6) Write final item to DynamoDB
        # ────────────────────────────────────────────────────────────────
        store_execution_details(base_item)

        # ────────────────────────────────────────────────────────────────
        # 7) Publish custom metrics
        # ────────────────────────────────────────────────────────────────
        metrics.add_metric(name="SuccessfulExecutionUpdates", unit="Count", value=1)
        if base_item.get("duration_seconds") is not None:
            metrics.add_metric(
                name="ExecutionDuration",
                unit="Seconds",
                value=float(base_item["duration_seconds"]),  # convert Decimal→float for metrics
            )

        logger.info(
            "Successfully processed Step Functions execution",
            extra={
                "execution_id": execution_id,
                "status": status,
                "duration_seconds": base_item.get("duration_seconds"),
            },
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Successfully processed execution event",
                    "execution_id": execution_id,
                    "status": status,
                }
            ),
        }

    except Exception as e:
        logger.exception("Error processing execution event")
        metrics.add_metric(name="FailedExecutionUpdates", unit="Count", value=1)
        raise


