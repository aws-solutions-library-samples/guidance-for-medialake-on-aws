import json
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger

from config import INGEST_EVENT_BUS_NAME, NODE_TEMPLATES_BUCKET
from iam_operations import get_events_role_arn
from lambda_operations import read_yaml_from_s3

# Initialize logger
logger = Logger()


def get_event_pattern_for_rule(
    rule_name: str, node: Any, pipeline_name: str
) -> Dict[str, Any]:
    """
    Get the event pattern for a specific rule type.

    Args:
        rule_name: Name of the rule
        node: Node object containing configuration
        pipeline_name: Name of the pipeline

    Returns:
        Event pattern dictionary for the rule
    """
    # Base pattern
    pattern = {"source": ["custom.asset.processor"]}

    # Add specific pattern based on rule name
    if rule_name == "video_ingested":
        pattern.update(
            {
                "detail-type": ["AssetCreated"],
                "detail": {"DigitalSourceAsset": {"Type": ["Video"]}},
            }
        )
    elif rule_name == "video_processing_completed":
        pattern.update(
            {
                "detail-type": ["ProcessingCompleted"],
                "detail": {"DigitalSourceAsset": {"Type": ["Video"]}},
            }
        )
    elif rule_name == "pipeline_execution_completed":
        # Determine asset type and format based on node configuration
        asset_type = "Video"  # Default asset type
        asset_format = "MP4"  # Default format
        
        # Get parameters from node configuration
        parameters = node.data.configuration.get("parameters", {})
        logger.info(f"Node parameters: {parameters}")
        
        # Check for different asset type parameters in configuration
        if "Image Type" in parameters:
            asset_type = "Image"
            asset_format = parameters.get("Image Type", "PNG")
            logger.info(f"Using Image asset type with format: {asset_format}")
        elif "Video Type" in parameters:
            asset_type = "Video"
            asset_format = parameters.get("Video Type", "MP4")
            logger.info(f"Using Video asset type with format: {asset_format}")
        elif "Audio Type" in parameters:
            asset_type = "Audio"
            asset_format = parameters.get("Audio Type", "MP3")
            logger.info(f"Using Audio asset type with format: {asset_format}")
        else:
            logger.warning(f"No specific asset type found in parameters, defaulting to Video/MP4")
        
        # Create the base pattern with appropriate asset type and format
        digital_source_asset = {
            "Type": [asset_type],
            "MainRepresentation": {"Format": [asset_format.upper()]},
        }
        
        logger.info(f"Created digital source asset pattern: {digital_source_asset}")
        
        # Override the source for pipeline execution completed events
        pattern = {
            "source": ["medialake.pipeline"],
            "detail-type": ["Pipeline Execution Completed"],
            "detail": {
                "outputs": {"input": {"DigitalSourceAsset": digital_source_asset}},
            },
        }
        
        # Skip the rest of the function to avoid adding parameters at the top level
        return pattern
    elif rule_name == "workflow_completed":
        # Get pipeline name from node configuration if available
        target_pipeline = node.data.configuration.get("pipeline_name", "")
        pattern.update({"detail-type": ["WorkflowCompleted"]})

        # Add pipeline name filter if specified
        if target_pipeline:
            pattern["detail"] = {"pipeline_name": [target_pipeline]}

    # Add any additional filters from node configuration
    for param in node.data.configuration:
        # Skip pipeline_name, method, and Video Type parameters
        # Video Type is handled separately for pipeline_execution_completed
        if (
            param not in ["pipeline_name", "method", "Video Type"]
            and node.data.configuration[param]
        ):
            if "detail" not in pattern:
                pattern["detail"] = {}

            # Handle parameters differently - they need to be properly formatted for EventBridge
            if param == "parameters":
                # If parameters is a dictionary or list, process it properly
                if isinstance(node.data.configuration[param], dict):
                    # For dictionaries, add each key-value pair directly to detail
                    for key, value in node.data.configuration[param].items():
                        pattern["detail"][key] = [value]
                elif isinstance(node.data.configuration[param], list):
                    # For lists of dictionaries, extract and flatten
                    for item in node.data.configuration[param]:
                        if isinstance(item, dict):
                            for key, value in item.items():
                                pattern["detail"][key] = [value]
                else:
                    # For simple values, add as is
                    pattern["detail"][param] = [node.data.configuration[param]]
            else:
                # For all other parameters, add as is
                pattern["detail"][param] = [node.data.configuration[param]]

    return pattern


def create_eventbridge_rule(
    pipeline_name: str, node: Any, state_machine_arn: str
) -> Optional[str]:
    """
    Create an EventBridge rule for a trigger node.

    Args:
        pipeline_name: Name of the pipeline
        node: Node object containing configuration
        state_machine_arn: ARN of the state machine to target

    Returns:
        ARN of the created rule, or None if creation was skipped
    """
    logger.info(f"Creating EventBridge rule for trigger node: {node.id}")

    try:
        # Read YAML file from S3
        yaml_file_path = f"node_templates/{node.data.type.lower()}/{node.data.id}.yaml"
        yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)

        # Get EventBridge rule configuration
        # Note: Some YAML files use aws_event_bridge and others use aws_eventbridge
        rule_config = yaml_data["node"]["integration"]["config"].get(
            "aws_eventbridge",
            yaml_data["node"]["integration"]["config"].get("aws_event_bridge", {}),
        )

        if not rule_config:
            logger.warning(
                f"No EventBridge rule configuration found for node {node.id}"
            )
            return None

        rule_name = rule_config.get("aws_eventbridge_rule")
        if not rule_name:
            logger.warning(f"No rule name specified for node {node.id}")
            return None

        # Create a unique rule name for this pipeline and node
        # Sanitize the pipeline name to replace spaces with hyphens and remove any other invalid characters
        sanitized_pipeline_name = pipeline_name.replace(" ", "-")
        # Replace any characters that aren't alphanumeric, periods, hyphens, or underscores
        sanitized_pipeline_name = "".join(
            c for c in sanitized_pipeline_name if c.isalnum() or c in ".-_"
        )

        unique_rule_name = f"{sanitized_pipeline_name}-{rule_name}-{node.data.id}"[
            :64
        ]  # Ensure name is not too long

        # Get event pattern based on rule name and node configuration
        event_pattern = get_event_pattern_for_rule(rule_name, node, pipeline_name)

        # Create the EventBridge rule
        events_client = boto3.client("events")

        # Get the event bus name from environment variable
        event_bus_name = INGEST_EVENT_BUS_NAME

        # Create the rule
        response = events_client.put_rule(
            Name=unique_rule_name,
            EventPattern=json.dumps(event_pattern),
            State="ENABLED",
            EventBusName=event_bus_name,
            Description=f"Rule for pipeline {pipeline_name}, node {node.data.label}",
        )

        # Create or get IAM role for EventBridge to invoke Step Functions
        role_arn = get_events_role_arn(sanitized_pipeline_name)

        # Set the Step Function as the target
        events_client.put_targets(
            Rule=unique_rule_name,
            EventBusName=event_bus_name,
            Targets=[
                {
                    "Id": f"{sanitized_pipeline_name}-target",
                    "Arn": state_machine_arn,
                    "RoleArn": role_arn,
                    # Add input transformer to include metadata about the trigger
                    "InputTransformer": {
                        "InputPathsMap": {
                            "detail": "$.detail",
                            "source": "$.source",
                            "detailType": "$.detail-type",
                            "time": "$.time",
                        },
                        "InputTemplate": json.dumps(
                            {
                                "detail": "<detail>",
                                "source": "<source>",
                                "detailType": "<detailType>",
                                "time": "<time>",
                                "triggerNode": node.data.id,
                                "pipelineName": pipeline_name,
                            }
                        )
                        .replace('"<detail>"', "<detail>")
                        .replace('"<source>"', "<source>")
                        .replace('"<detailType>"', "<detailType>")
                        .replace('"<time>"', "<time>"),
                    },
                }
            ],
        )

        logger.info(f"Created EventBridge rule {unique_rule_name} for node {node.id}")
        return response["RuleArn"]

    except Exception as e:
        logger.exception(f"Failed to create EventBridge rule for node {node.id}: {e}")
        return None


def delete_eventbridge_rule(rule_name: str) -> None:
    """
    Delete an EventBridge rule and its targets.

    Args:
        rule_name: Name of the rule
    """
    events_client = boto3.client("events")
    event_bus_name = INGEST_EVENT_BUS_NAME

    try:
        # First remove targets
        # Extract a sanitized target ID from the rule name
        target_id = f"{rule_name}-target"

        events_client.remove_targets(
            Rule=rule_name, EventBusName=event_bus_name, Ids=[target_id]
        )

        # Then delete the rule
        events_client.delete_rule(Name=rule_name, EventBusName=event_bus_name)

        logger.info(f"Deleted EventBridge rule: {rule_name}")
    except Exception as e:
        logger.error(f"Error deleting EventBridge rule {rule_name}: {e}")
