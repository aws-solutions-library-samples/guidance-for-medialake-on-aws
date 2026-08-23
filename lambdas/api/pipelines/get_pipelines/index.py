import concurrent.futures
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig, content_types
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import Metrics
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.types import TypeDeserializer
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

# Import centralized file extension constants from common_libraries layer
from file_extensions import get_extensions_as_uppercase_string

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="Pipelines")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

PIPELINES_TABLE_NAME = os.environ["PIPELINES_TABLE_NAME"]

# Parallel scan tuning. Segments run concurrently, so the connection pool has to
# be at least as large as the worker count or threads serialize on sockets.
SCAN_TOTAL_SEGMENTS = max(1, int(os.environ.get("PIPELINES_SCAN_SEGMENTS", "4")))

# Safety valve: stop draining well before the 6 MB Lambda response limit can be
# reached. Applied per segment, so the effective ceiling is approximate.
MAX_PIPELINES = max(1, int(os.environ.get("PIPELINES_MAX_ITEMS", "5000")))

# The boto3 resource/Table API is NOT thread safe, so the parallel scan uses the
# low-level client (which is) and deserializes items by hand.
dynamodb_client = boto3.client(
    "dynamodb",
    config=BotoConfig(
        max_pool_connections=max(10, SCAN_TOTAL_SEGMENTS * 2),
        retries={"max_attempts": 5, "mode": "adaptive"},
    ),
)

# TypeDeserializer holds no mutable state, so one shared instance is safe.
_deserializer = TypeDeserializer()


class PipelineError(Exception):
    """Custom exception for pipeline errors"""


def _error_body(message: str) -> Dict[str, Any]:
    """Build the error body, keeping the response shape the UI expects."""
    return {
        "status": "500",
        "message": message,
        "data": {
            "searchMetadata": {"totalResults": 0, "pageSize": 0, "nextToken": None},
            "s": [],
        },
    }


def _error_response(message: str) -> Response:
    """Return a genuine HTTP 500 rather than a 200 with an error in the body."""
    return Response(
        status_code=500,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps(_error_body(message)),
    )


def extract_event_rule_info(pipeline: dict) -> dict:
    """
    Extract and format event rule information from a pipeline.

    Args:
        pipeline: The pipeline object from DynamoDB

    Returns:
        A dictionary containing event rule information
    """
    event_rule_info = {"triggerTypes": [], "eventRules": []}

    # Check if this is a manual trigger pipeline by examining the pipeline definition
    is_manual_trigger = False
    if "definition" in pipeline and isinstance(pipeline["definition"], dict):
        configuration = pipeline["definition"].get("configuration", {})
        nodes = configuration.get("nodes", [])

        # Look for trigger_manual node in the pipeline definition
        for node in nodes:
            if (
                isinstance(node, dict)
                and node.get("data", {}).get("id") == "trigger_manual"
            ):
                is_manual_trigger = True
                break

    if is_manual_trigger:
        event_rule_info["triggerTypes"].append("Manual Trigger")

        # Extract supported content types from the manual trigger node if available
        supported_content_types = []
        if "definition" in pipeline and isinstance(pipeline["definition"], dict):
            configuration = pipeline["definition"].get("configuration", {})
            nodes = configuration.get("nodes", [])

            for node in nodes:
                if (
                    isinstance(node, dict)
                    and node.get("data", {}).get("id") == "trigger_manual"
                ):
                    # Look for supported content types in the node configuration
                    node_config = node.get("data", {}).get("configuration", {})
                    parameters = node_config.get("parameters", {})

                    # Check for "Supported Content Types" parameter
                    content_types_param = parameters.get("Supported Content Types", "")
                    if content_types_param:
                        # Handle both list format (from multiselect) and comma-separated string
                        if isinstance(content_types_param, list):
                            supported_content_types = [
                                ct.strip().lower() for ct in content_types_param
                            ]
                        else:
                            supported_content_types = [
                                ct.strip().lower()
                                for ct in content_types_param.split(",")
                            ]
                    break

        # Set supported content types for frontend
        pipeline["supported_content_types"] = (
            supported_content_types
            if supported_content_types
            else ["video", "audio", "image"]
        )

    # Check for Event Triggered (EventBridge rules) - this can coexist with manual triggers
    if "dependentResources" in pipeline:
        for resource_type, resource_value in pipeline.get("dependentResources", []):
            if resource_type == "eventbridge_rule":
                # Add Event Trigger to trigger types if not already there
                if "Event Trigger" not in event_rule_info["triggerTypes"]:
                    event_rule_info["triggerTypes"].append("Event Trigger")

                # Extract rule name and eventbus name if available
                rule_info = {}
                if isinstance(resource_value, dict) and "rule_name" in resource_value:
                    rule_info["ruleName"] = resource_value.get("rule_name", "")
                    rule_info["eventBusName"] = resource_value.get("eventbus_name", "")
                else:
                    # If it's just a string ARN, extract the rule name from the ARN
                    rule_info["ruleArn"] = resource_value
                    if isinstance(resource_value, str) and "/" in resource_value:
                        rule_info["ruleName"] = resource_value.split("/")[-1]

                # Try to extract human-friendly information from the rule name
                if "ruleName" in rule_info:
                    rule_name = rule_info["ruleName"]

                    # Check for manual trigger patterns
                    if "manual_trigger" in rule_name:
                        rule_info["description"] = "Manual trigger event rule"
                        rule_info["eventType"] = "Manual Trigger"
                    # Check for default pipeline patterns - use centralized file extension lists
                    elif "default-image-pipeline" in rule_name:
                        image_exts_str = get_extensions_as_uppercase_string("Image")
                        rule_info["description"] = (
                            f"Triggers on image files ({image_exts_str})"
                        )
                        rule_info["fileTypes"] = image_exts_str.split(", ")
                        rule_info["eventType"] = "AssetCreated"
                    elif "default-video-pipeline" in rule_name:
                        video_exts_str = get_extensions_as_uppercase_string("Video")
                        rule_info["description"] = (
                            f"Triggers on video files ({video_exts_str})"
                        )
                        rule_info["fileTypes"] = video_exts_str.split(", ")
                        rule_info["eventType"] = "AssetCreated"
                    elif "default-audio-pipeline" in rule_name:
                        audio_exts_str = get_extensions_as_uppercase_string("Audio")
                        rule_info["description"] = (
                            f"Triggers on audio files ({audio_exts_str})"
                        )
                        rule_info["fileTypes"] = audio_exts_str.split(", ")
                        rule_info["eventType"] = "AssetCreated"
                    elif "pipeline_execution_completed" in rule_name:
                        rule_info["description"] = (
                            "Triggers when another pipeline completes execution"
                        )
                        rule_info["eventType"] = "Pipeline Execution Completed"
                    else:
                        rule_info["description"] = f"Custom event rule: {rule_name}"

                event_rule_info["eventRules"].append(rule_info)

    # Ensure we have at least one trigger type
    if not event_rule_info["triggerTypes"]:
        event_rule_info["triggerTypes"].append("Event Triggered")

    return event_rule_info


def _deserialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a low-level DynamoDB item into plain Python types."""
    return {key: _deserializer.deserialize(value) for key, value in item.items()}


def _build_scan_filter(
    status: Optional[str],
) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """
    Build the filter for the pipeline list.

    Returns a (FilterExpression, ExpressionAttributeNames, ExpressionAttributeValues)
    triple in low-level client form.
    """
    if status:
        return (
            "#status = :status",
            {"#status": "status"},
            {":status": {"S": status}},
        )

    # Default: hide soft-deleted pipelines.
    return (
        "attribute_not_exists(#ds) OR #ds <> :deleted",
        {"#ds": "deploymentStatus"},
        {":deleted": {"S": "DELETED"}},
    )


def _scan_segment(
    segment: int,
    total_segments: int,
    filter_expression: str,
    attribute_names: Dict[str, str],
    attribute_values: Dict[str, Any],
    max_items: int,
) -> List[Dict[str, Any]]:
    """
    Drain a single parallel-scan segment.

    DynamoDB applies Limit *before* FilterExpression, so a page can come back
    short (or empty) while LastEvaluatedKey is still set. This loops until the
    segment is genuinely exhausted and re-sends the filter on every page rather
    than dropping it after the first call.
    """
    items: List[Dict[str, Any]] = []
    start_key = None

    while True:
        scan_kwargs: Dict[str, Any] = {
            "TableName": PIPELINES_TABLE_NAME,
            "FilterExpression": filter_expression,
            "ExpressionAttributeNames": attribute_names,
            "ExpressionAttributeValues": attribute_values,
        }

        # Omit segment args entirely when not doing a parallel scan; DynamoDB
        # rejects TotalSegments=1 paired with Segment on some API versions.
        if total_segments > 1:
            scan_kwargs["Segment"] = segment
            scan_kwargs["TotalSegments"] = total_segments

        if start_key:
            scan_kwargs["ExclusiveStartKey"] = start_key

        response = dynamodb_client.scan(**scan_kwargs)
        items.extend(_deserialize_item(item) for item in response.get("Items", []))

        start_key = response.get("LastEvaluatedKey")
        if not start_key or len(items) >= max_items:
            break

    return items


@tracer.capture_method
def scan_all_pipelines(
    status: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Read every matching pipeline, fanning the scan out across segments.

    The table has no sort key and no GSIs (PK `id` only), so Scan is the only
    way to list. Segments run in parallel to keep wall-clock time flat as the
    table grows.

    Returns:
        (items, truncated). `truncated` is True when any segment hit its item
        cap, meaning the list may be incomplete. The per-segment cap splits
        MAX_PIPELINES evenly, so a hot segment can be cut short even when other
        segments are nearly empty -- the flag is deliberately conservative.
    """
    filter_expression, attribute_names, attribute_values = _build_scan_filter(status)
    segments = SCAN_TOTAL_SEGMENTS
    per_segment_cap = max(1, MAX_PIPELINES // segments)

    if segments == 1:
        items = _scan_segment(
            0, 1, filter_expression, attribute_names, attribute_values, MAX_PIPELINES
        )
        return items, len(items) >= MAX_PIPELINES

    items: List[Dict[str, Any]] = []
    truncated = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=segments) as pool:
        futures = [
            pool.submit(
                _scan_segment,
                segment,
                segments,
                filter_expression,
                attribute_names,
                attribute_values,
                per_segment_cap,
            )
            for segment in range(segments)
        ]
        # Surfaces the first segment failure instead of returning a partial list.
        for future in concurrent.futures.as_completed(futures):
            segment_items = future.result()
            if len(segment_items) >= per_segment_cap:
                truncated = True
            items.extend(segment_items)

    if truncated:
        logger.warning(
            "Pipeline scan truncated by cap; list may be incomplete",
            extra={"returned": len(items), "max_pipelines": MAX_PIPELINES},
        )
    return items, truncated


def format_pipeline_for_list(pipeline: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive the list-view fields, then drop the heavy pipeline definition.

    `definition` carries the whole visual node graph and dwarfs every other
    attribute; shipping it for hundreds of pipelines is what puts the response
    near Lambda's 6 MB limit. The detail endpoint still returns it.
    """
    # Note: also sets `supported_content_types` on the pipeline as a side effect,
    # so it has to run before `definition` is removed.
    event_rule_info = extract_event_rule_info(pipeline)

    if not pipeline.get("type"):
        pipeline["type"] = ",".join(event_rule_info["triggerTypes"])

    pipeline["eventRuleInfo"] = event_rule_info

    definition = pipeline.pop("definition", None)
    if isinstance(definition, dict):
        # name/description are not reliably top-level, so hoist them out of the
        # definition before it goes away.
        if not pipeline.get("name"):
            pipeline["name"] = definition.get("name", "")
        if not pipeline.get("description"):
            pipeline["description"] = definition.get("description", "")

    return pipeline


@tracer.capture_method
def get_pipelines(status: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve every pipeline the caller is allowed to list.

    The full set is returned in one response so the UI can sort, filter and
    paginate across all pipelines rather than across an arbitrary first page.
    `searchMetadata` is kept for response-shape compatibility, but `nextToken`
    is now always None because there is never a further page to fetch.

    Args:
        status: Optional status filter

    Returns:
        Dict containing status, message, and the full pipeline list
    """
    try:
        scanned_pipelines, truncated = scan_all_pipelines(status)
        pipelines = [
            format_pipeline_for_list(pipeline) for pipeline in scanned_pipelines
        ]

        # Sort across the whole set. The previous implementation sorted a single
        # scan page, which is meaningless given Scan returns items in hash order.
        pipelines.sort(key=lambda item: str(item.get("start_time") or ""), reverse=True)

        metrics.add_metric(name="SuccessfulQueries", unit="Count", value=1)
        metrics.add_metric(name="PipelinesReturned", unit="Count", value=len(pipelines))

        return {
            "status": "200",
            "message": "ok",
            "data": {
                "searchMetadata": {
                    # Real total, not the post-filter count of one page.
                    "totalResults": len(pipelines),
                    "pageSize": len(pipelines),
                    "nextToken": None,
                    # True when the scan hit its cap and the list may be
                    # incomplete, so clients don't mistake a partial list for
                    # the full set.
                    "truncated": truncated,
                },
                "s": pipelines,
            },
        }

    except ClientError as e:
        logger.exception("Failed to retrieve pipelines")
        metrics.add_metric(name="FailedQueries", unit="Count", value=1)
        raise PipelineError(f"Failed to retrieve pipelines: {str(e)}")


@app.get("/pipelines")
@tracer.capture_method
def handle_get_pipelines() -> Any:
    """
    Handle GET request for the pipeline list.

    Returns the complete list; the client paginates. `pageSize`/`nextToken` are
    still accepted for backward compatibility but no longer affect the result.

    Returns:
        The pipeline list response, or a 500 Response on failure.
    """
    try:
        query_string = app.current_event.query_string_parameters or {}
        status = query_string.get("status")

        return get_pipelines(status)
    except PipelineError as e:
        logger.exception("Error processing pipelines request")
        # Report failure as a real 500. Returning 200 with a "500" in the body
        # made the UI render an empty table as if there were no pipelines.
        return _error_response(str(e))


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Main Lambda handler

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Error in lambda handler")
        # `body` has to be a JSON string for the proxy integration; the previous
        # version returned a dict, which API Gateway rejects.
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(_error_body("Internal server error")),
        }
