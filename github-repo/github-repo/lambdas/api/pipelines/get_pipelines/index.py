import base64
import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import Metrics
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

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

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_TABLE_NAME"])

# Default pagination values
DEFAULT_PAGE_SIZE = 20


class PipelineError(Exception):
    """Custom exception for pipeline errors"""


def extract_event_rule_info(pipeline: dict) -> dict:
    """
    Extract and format event rule information from a pipeline.

    Args:
        pipeline: The pipeline object from DynamoDB

    Returns:
        A dictionary containing event rule information
    """
    event_rule_info = {"triggerTypes": ["Event Triggered"], "eventRules": []}

    # Check for Event Triggered (EventBridge rules)
    if "dependentResources" in pipeline:
        for resource_type, resource_value in pipeline.get("dependentResources", []):
            if resource_type == "eventbridge_rule":
                # Add Event Triggered to trigger types if not already there
                if "Event Triggered" not in event_rule_info["triggerTypes"]:
                    event_rule_info["triggerTypes"].append("Event Triggered")

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

                    # Check for default pipeline patterns
                    if "default-image-pipeline" in rule_name:
                        rule_info["description"] = (
                            "Triggers on image files (TIF, JPG, JPEG, PNG, WEBP, GIF, SVG)"
                        )
                        rule_info["fileTypes"] = [
                            "TIF",
                            "JPG",
                            "JPEG",
                            "PNG",
                            "WEBP",
                            "GIF",
                            "SVG",
                        ]
                        rule_info["eventType"] = "AssetCreated"
                    elif "default-video-pipeline" in rule_name:
                        rule_info["description"] = (
                            "Triggers on video files (MP4, MOV, AVI, MKV, WEBM)"
                        )
                        rule_info["fileTypes"] = ["MP4", "MOV", "AVI", "MKV", "WEBM"]
                        rule_info["eventType"] = "AssetCreated"
                    elif "default-audio-pipeline" in rule_name:
                        rule_info["description"] = (
                            "Triggers on audio files (WAV, AIFF, AIF, MP3, PCM, M4A)"
                        )
                        rule_info["fileTypes"] = [
                            "WAV",
                            "AIFF",
                            "AIF",
                            "MP3",
                            "PCM",
                            "M4A",
                        ]
                        rule_info["eventType"] = "AssetCreated"
                    elif "pipeline_execution_completed" in rule_name:
                        rule_info["description"] = (
                            "Triggers when another pipeline completes execution"
                        )
                        rule_info["eventType"] = "Pipeline Execution Completed"
                    else:
                        rule_info["description"] = f"Custom event rule: {rule_name}"

                event_rule_info["eventRules"].append(rule_info)

    # For now, we're only supporting Event Triggered
    # In the future, we can add logic for API Triggered and Manually Triggered

    return event_rule_info


def encode_last_evaluated_key(last_evaluated_key: Dict) -> str:
    """Encode the LastEvaluatedKey to a base64 string"""
    if not last_evaluated_key:
        return ""
    return base64.b64encode(json.dumps(last_evaluated_key).encode()).decode()


def decode_last_evaluated_key(encoded_key: str) -> Dict:
    """Decode the base64 string back to LastEvaluatedKey"""
    if not encoded_key:
        return None
    try:
        return json.loads(base64.b64decode(encoded_key.encode()).decode())
    except:
        return None
        return None


@tracer.capture_method
def get_pipelines(
    page_size: int, next_token: str = None, status: str = None
) -> Dict[str, Any]:
    """
    Retrieve paginated pipelines from DynamoDB using Scan operation with filtering

    Args:
        page_size: Number of items per page
        next_token: Base64 encoded LastEvaluatedKey for pagination
        status: Optional status filter

    Returns:
        Dict containing status, message, and paginated pipeline s data
    """
    try:
        # Base scan parameters
        scan_params = {"Limit": page_size}

        # Add status filter if provided
        if status:
            scan_params.update(
                {
                    "FilterExpression": "#status = :status",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {":status": status},
                }
            )

        # Add LastEvaluatedKey if next_token is provided
        if next_token:
            last_evaluated_key = decode_last_evaluated_key(next_token)
            if last_evaluated_key:
                scan_params["ExclusiveStartKey"] = last_evaluated_key

        # Execute scan
        response = table.scan(**scan_params)
        s = response.get("Items", [])

        # Process each pipeline to add event rule information and update type
        for pipeline in s:
            # Extract event rule information
            event_rule_info = extract_event_rule_info(pipeline)

            # Update the pipeline type to use the determined trigger types
            pipeline["type"] = ",".join(event_rule_info["triggerTypes"])

            # Add event rule information to the pipeline
            pipeline["eventRuleInfo"] = event_rule_info

        # Sort s by start_time in descending order
        s.sort(key=lambda x: x.get("start_time", ""), reverse=True)

        # Get the next token for pagination
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_last_evaluated_key(response["LastEvaluatedKey"])

        # Add metrics for monitoring
        metrics.add_metric(name="SuccessfulQueries", unit="Count", value=1)

        return {
            "status": "200",
            "message": "ok",
            "data": {
                "searchMetadata": {
                    "totalResults": response.get("Count", 0),
                    "pageSize": page_size,
                    "nextToken": next_token,
                },
                "s": s,
            },
        }

    except ClientError as e:
        logger.exception("Failed to retrieve pipeline s")
        metrics.add_metric(name="FailedQueries", unit="Count", value=1)
        raise PipelineError(f"Failed to retrieve pipelines: {str(e)}")


@app.get("/pipelines")
@tracer.capture_method
def handle_get_pipelines() -> Dict[str, Any]:
    """
    Handle GET request for pipelines with pagination

    Returns:
        Dict containing response with paginated pipelines
    """
    try:
        # Get query parameters
        query_string = app.current_event.query_string_parameters or {}

        # Parse pagination parameters
        try:
            page_size = int(query_string.get("pageSize", DEFAULT_PAGE_SIZE))
            page_size = max(1, min(100, page_size))  # Limit page size between 1 and 100
        except (ValueError, TypeError):
            page_size = DEFAULT_PAGE_SIZE

        # Get the next token for pagination
        next_token = query_string.get("nextToken")

        # Get status filter if provided
        status = query_string.get("status")

        return get_pipelines(page_size, next_token, status)
    except PipelineError as e:
        logger.exception("Error processing pipelines request")
        return {
            "status": "500",
            "message": str(e),
            "data": {
                "searchMetadata": {
                    "totalResults": 0,
                    "pageSize": DEFAULT_PAGE_SIZE,
                    "nextToken": None,
                },
                "s": [],
            },
        }


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
        return {
            "statusCode": 500,
            "body": {
                "status": "500",
                "message": "Internal server error",
                "data": {
                    "searchMetadata": {
                        "totalResults": 0,
                        "pageSize": DEFAULT_PAGE_SIZE,
                        "nextToken": None,
                    },
                    "s": [],
                },
            },
        }
