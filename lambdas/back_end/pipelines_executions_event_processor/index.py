import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

# ─────────────────────────────────────────────────────────────────────────────
# Initialize
# ─────────────────────────────────────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"])

logger = Logger(service="pipelines_executions_event_processor")
tracer = Tracer(service="pipelines_executions_event_processor")
metrics = Metrics(
    service="pipelines_executions_event_processor", namespace="MyApp/Pipelines"
)


def convert_to_decimal(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: convert_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_to_decimal(v) for v in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, int):
        return Decimal(obj)
    return obj


def calculate_execution_duration(
    start_time: Any, end_time: Optional[str] = None
) -> Optional[Decimal]:
    if not end_time or not start_time:
        return None
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        return Decimal(str((end_dt - start_dt).total_seconds()))
    except Exception as e:
        logger.warning(f"Error calculating duration: {e}")
        return None


def convert_to_unix_timestamp(time_ms: float) -> int:
    return int(time_ms / 1000.0)


@tracer.capture_method
def is_map_child_execution(execution_arn: str) -> bool:
    """
    Detect if an execution is a child execution from a Map state (especially distributed maps).

    Map child executions have a slash in the state machine name part:
    Parent: arn:aws:states:region:account:execution:stateMachine:executionId
    Child:  arn:aws:states:region:account:execution:stateMachine/parentId:childId

    The slash separates the state machine name from the parent execution ID.
    """
    try:
        parts = execution_arn.split(":")
        if len(parts) < 7:
            return False

        # Check if the state machine name part (index 6) contains a slash
        state_machine_part = parts[6]
        return "/" in state_machine_part
    except Exception:
        return False


@tracer.capture_method
def extract_pipeline_name(execution_arn: str) -> str:
    """
    Extract the pipeline (state machine) name from the execution ARN.
    For parent executions: arn:aws:states:region:account:execution:PIPELINE_NAME:executionId
    For map children: arn:aws:states:region:account:execution:PIPELINE_NAME/PARENT_ID:childId...

    Step Functions uses a slash to separate state machine name from parent execution ID in distributed maps.
    Example map child: ...execution:my-pipeline/parent-exec-id:child-exec-id
    We need to extract just "my-pipeline", not "my-pipeline/parent-exec-id"
    """
    try:
        parts = execution_arn.split(":")
        if len(parts) < 8:
            raise ValueError(f"Invalid execution ARN format: {execution_arn}")

        # Pipeline name is at index 6, but may include "/parent-exec-id" for map children
        pipeline_part = parts[6]

        # Strip everything after the first slash to get just the state machine name
        pipeline_name = pipeline_part.split("/")[0]

        return pipeline_name
    except Exception:
        raise ValueError(f"Invalid execution ARN format: {execution_arn}")


@tracer.capture_method
def store_execution_details(item: Dict[str, Any]) -> None:
    logger.info(f"Writing item to DynamoDB: {json.dumps(item, default=str)}")
    table.put_item(Item=item)


def parse_nested_metadata(detail_input_str: str) -> Dict[str, Any]:
    nested_fields: Dict[str, Any] = {}
    try:
        nested = json.loads(detail_input_str)
    except Exception as e:
        logger.debug(
            f"parse_nested_metadata: could not parse detail.input as JSON: {e}"
        )
        return nested_fields

    detail1 = nested.get("detail", {})

    inv_top = detail1.get("InventoryID")
    if inv_top:
        nested_fields["inventory_id"] = inv_top
    else:
        detail2 = detail1.get("detail", {})
        inv_second = detail2.get("InventoryID")
        if inv_second:
            nested_fields["inventory_id"] = inv_second

    meta = detail1.get("metadata", {})
    pipeline_trace_id = meta.get("pipelineTraceId")
    if pipeline_trace_id:
        nested_fields["pipeline_trace_id"] = pipeline_trace_id

    dsa = detail1.get("DigitalSourceAsset", {})
    dsa_type = dsa.get("Type")
    if dsa_type:
        nested_fields["dsa_type"] = dsa_type

    try:
        obj_name = dsa["MainRepresentation"]["StorageInfo"]["PrimaryLocation"][
            "ObjectKey"
        ]["Name"]
        nested_fields["object_key_name"] = obj_name
    except KeyError:
        pass

    if meta:
        for k in ["stepName", "stepStatus", "stepResult"]:
            if k in meta:
                nested_fields[k.lower()] = meta[k]
        nested_fields["metadata"] = convert_to_decimal(meta)

    return nested_fields


def fetch_parent_by_trace_id(
    trace_id: str, current_execution_id: str
) -> Optional[Dict[str, Any]]:
    try:
        response = table.scan(
            FilterExpression="pipeline_trace_id = :trace_id",
            ExpressionAttributeValues={":trace_id": trace_id},
        )
        for item in response.get("Items", []):
            if item.get("execution_id") != current_execution_id:
                return item
    except Exception as e:
        logger.warning(f"fetch_parent_by_trace_id: {e}")
    return None


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    try:
        evt = EventBridgeEvent(event)
        detail = evt.detail

        execution_arn = detail.get("executionArn")

        # DEBUG: Log ARN structure details
        arn_parts = execution_arn.split(":")
        colon_count = execution_arn.count(":")
        logger.info(
            "ARN Analysis",
            extra={
                "execution_arn": execution_arn,
                "arn_parts": arn_parts,
                "arn_parts_count": len(arn_parts),
                "colon_count": colon_count,
                "part_6_pipeline_name": arn_parts[6] if len(arn_parts) > 6 else "N/A",
                "part_7_execution_id": arn_parts[7] if len(arn_parts) > 7 else "N/A",
                "part_8_extra": arn_parts[8] if len(arn_parts) > 8 else "N/A",
            },
        )

        # Skip map state child executions - only track parent/main pipeline executions
        if is_map_child_execution(execution_arn):
            logger.info(
                f"Skipping map child execution: {execution_arn}",
                extra={
                    "execution_arn": execution_arn,
                    "colon_count": colon_count,
                    "reason": "Map child execution detected",
                },
            )
            metrics.add_metric(name="SkippedMapChildExecutions", unit="Count", value=1)
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Skipped map child execution",
                        "execution_arn": execution_arn,
                    }
                ),
            }
        execution_id = execution_arn.split(":")[-1]
        state_machine_arn = detail["stateMachineArn"]
        status = detail["status"]
        start_date_ms = detail["startDate"]
        start_date_unix = convert_to_unix_timestamp(start_date_ms)
        start_date_iso = datetime.fromtimestamp(start_date_unix).isoformat()
        current_time_iso = datetime.utcnow().isoformat()

        pipeline_name = extract_pipeline_name(execution_arn)

        # DEBUG: Log what we extracted
        logger.info(
            "Extracted pipeline info",
            extra={
                "execution_id": execution_id,
                "pipeline_name": pipeline_name,
                "execution_arn": execution_arn,
                "state_machine_arn": state_machine_arn,
            },
        )

        base_item: Dict[str, Any] = {
            "execution_id": execution_id,
            "start_time": start_date_unix,
            "start_time_iso": start_date_iso,
            "pipeline_name": pipeline_name,
            "execution_arn": execution_arn,
            "state_machine_arn": state_machine_arn,
            "status": status,
            "last_updated": current_time_iso,
            "ttl": int(datetime.utcnow().timestamp() + 90 * 24 * 3600),
        }

        nested_meta_from_input: Dict[str, Any] = {}
        raw_input = detail.get("input")
        if isinstance(raw_input, str):
            nested_meta_from_input = parse_nested_metadata(raw_input)

        if nested_meta_from_input:
            base_item.update(nested_meta_from_input)

        # ────────────────────────────────────────
        # Backfill from parent by pipeline_trace_id
        # ────────────────────────────────────────
        trace_id = base_item.get("pipeline_trace_id")
        if trace_id:
            missing_fields = [
                f
                for f in ["inventory_id", "dsa_type", "object_key_name"]
                if f not in base_item
            ]
            if missing_fields:
                parent_item = fetch_parent_by_trace_id(
                    trace_id, base_item["execution_id"]
                )
                if parent_item:
                    for field in missing_fields:
                        if field in parent_item:
                            base_item[field] = parent_item[field]
                            logger.info(f"Backfilled {field} from parent execution")

        if status in ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]:
            stop_date_ms = detail.get("stopDate")
            if stop_date_ms:
                stop_date_unix = convert_to_unix_timestamp(stop_date_ms)
                end_time_iso = datetime.fromtimestamp(stop_date_unix).isoformat()
                base_item["end_time"] = stop_date_unix
                base_item["end_time_iso"] = end_time_iso

                duration = calculate_execution_duration(start_date_iso, end_time_iso)
                if duration is not None:
                    base_item["duration_seconds"] = duration

            if status in ["FAILED", "TIMED_OUT", "ABORTED"]:
                if "error" in detail:
                    base_item["error"] = detail["error"]
                if "cause" in detail:
                    base_item["cause"] = detail["cause"]

        store_execution_details(base_item)

        metrics.add_metric(name="SuccessfulExecutionUpdates", unit="Count", value=1)
        if base_item.get("duration_seconds") is not None:
            metrics.add_metric(
                name="ExecutionDuration",
                unit="Seconds",
                value=float(base_item["duration_seconds"]),
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

    except Exception:
        logger.exception("Error processing execution event")
        metrics.add_metric(name="FailedExecutionUpdates", unit="Count", value=1)
        raise
