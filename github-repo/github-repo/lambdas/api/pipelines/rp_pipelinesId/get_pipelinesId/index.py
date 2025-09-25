import json
import os
from typing import List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel

# Initialize Power Tools
logger = Logger(service="get_pipline_service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="get_pipline_service")
metrics = Metrics(namespace="MediaLake", service="get_pipline_service")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_TABLE_NAME"])

# CORS Configuration
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

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict]


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


def determine_trigger_types(pipeline: dict) -> List[str]:
    """
    Determine the trigger types for a pipeline based on its configuration.

    Args:
        pipeline: The pipeline object from DynamoDB

    Returns:
        A list of trigger types (e.g., ["Event Triggered"])
    """
    event_rule_info = extract_event_rule_info(pipeline)
    return event_rule_info["triggerTypes"]


@app.get("/pipelines/<pipeline_id>")
@tracer.capture_method
def get_pipeline(pipeline_id: str):
    try:
        logger.debug(f"Retrieving pipeline details for ID: {pipeline_id}")
        metrics.add_metric(name="GetPipelineAttempt", unit="Count", value=1)

        # Validate pipeline_id is not empty
        if not pipeline_id:
            logger.error("Pipeline ID is required")
            return PipelineResponse(
                status="error", message="Pipeline ID is required", data=None
            ).dict()

        # Query DynamoDB
        response = table.get_item(Key={"id": pipeline_id})

        # Check if item exists
        if "Item" not in response:
            logger.warning(f"Pipeline not found for ID: {pipeline_id}")
            metrics.add_metric(name="PipelineNotFound", unit="Count", value=1)
            return PipelineResponse(
                status="error", message="Pipeline not found", data=None
            ).dict()

        # Get the pipeline item
        pipeline = response["Item"]

        # Extract event rule information
        event_rule_info = extract_event_rule_info(pipeline)

        # Update the pipeline type to use the determined trigger types
        pipeline["type"] = ",".join(event_rule_info["triggerTypes"])

        # Add event rule information to the pipeline
        pipeline["eventRuleInfo"] = event_rule_info

        logger.info(f"Successfully retrieved pipeline: {pipeline_id}")
        metrics.add_metric(name="SuccessfulPipeline", unit="Count", value=1)

        return PipelineResponse(
            status="success",
            message="Pipeline retrieved successfully",
            data={"pipeline": pipeline},
        ).dict()

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        metrics.add_metric(name="DynamoDBError", unit="Count", value=1)
        return PipelineResponse(
            status="error", message="Internal server error", data=None
        ).dict()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        metrics.add_metric(name="UnexpectedError", unit="Count", value=1)
        return PipelineResponse(
            status="error", message="Internal server error", data=None
        ).dict()


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext):
    return app.resolve(event, context)
