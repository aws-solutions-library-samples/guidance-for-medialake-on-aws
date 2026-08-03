"""
Pipeline utility functions for the MediaLake application.

This file is deployed as part of the common_libraries Lambda layer and is
accessible to all Lambda functions.
"""

import copy
from typing import Any, Dict

from aws_lambda_powertools import Logger

logger = Logger()

# Node icons are a presentation-only concern: the editor renders whatever React
# element it finds here and no backend code inspects the value. Pipeline
# definitions authored outside the editor (library templates, scripts, curl)
# routinely omit it, so we supply this placeholder rather than rejecting an
# otherwise valid pipeline.
DEFAULT_NODE_ICON: Dict[str, Any] = {"props": {"size": 20}}


def normalize_pipeline_definition(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a raw pipeline definition into the shape ``PipelineDefinition`` expects.

    Pipeline definitions reach the API from three places that each serialize
    slightly differently: the editor UI, the ``pipeline_library`` templates
    (loaded from S3 at deploy time), and hand-written API calls. This function
    reconciles those differences so any of them validate:

    1. ``width``/``height`` are coerced from numbers to strings.
    2. ``data.id`` is derived from ``data.nodeId`` when absent — both hold the
       node *template* id (e.g. ``video_reframe``), not the instance id.
    3. ``data.icon`` is defaulted when absent, since it is required by the model
       but only ever used for display.

    The input is not mutated.

    Args:
        pipeline_data: Raw pipeline definition dictionary

    Returns:
        A normalized copy of the pipeline definition
    """
    if not isinstance(pipeline_data, dict):
        return pipeline_data

    normalized = copy.deepcopy(pipeline_data)

    configuration = normalized.get("configuration")
    if not isinstance(configuration, dict):
        return normalized

    nodes = configuration.get("nodes")
    if not isinstance(nodes, list):
        return normalized

    for node in nodes:
        if not isinstance(node, dict):
            continue

        # Step 1: numeric dimensions -> strings
        for dimension in ("width", "height"):
            value = node.get(dimension)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            node[dimension] = (
                str(int(value)) if float(value).is_integer() else str(value)
            )

        data = node.get("data")
        if not isinstance(data, dict):
            continue

        # Step 2: data.id <- data.nodeId
        if not data.get("id") and data.get("nodeId"):
            data["id"] = data["nodeId"]

        # Step 3: default the display-only icon
        if not isinstance(data.get("icon"), dict):
            data["icon"] = copy.deepcopy(DEFAULT_NODE_ICON)

    return normalized


def determine_pipeline_type(pipeline: Any) -> str:
    """
    Determine the pipeline type based on the pipeline definition.

    Analyzes the pipeline's trigger nodes to determine if it supports
    manual triggering, event triggering, or both.

    Args:
        pipeline: Pipeline definition object (Pydantic model or dict)

    Returns:
        Comma-separated string of trigger types (e.g., "Manual Trigger,Event Trigger")
    """
    trigger_types = []
    has_manual_trigger = False
    has_event_trigger = False

    logger.info("Analyzing pipeline nodes for trigger type determination")

    # Get nodes from pipeline - handle both object and dict structures
    if hasattr(pipeline, "configuration"):
        nodes = pipeline.configuration.nodes
    elif isinstance(pipeline, dict) and "configuration" in pipeline:
        nodes = pipeline["configuration"].get("nodes", [])
    else:
        logger.warning(
            "Unable to extract nodes from pipeline, defaulting to Event Trigger"
        )
        return "Event Trigger"

    # Check for trigger nodes
    for node in nodes:
        # Handle both object and dictionary node structures
        if hasattr(node, "data"):
            # Object structure (Pydantic model)
            node_data = node.data
            node_type = getattr(node_data, "type", "").lower()
            node_id = getattr(node_data, "id", "")
        elif isinstance(node, dict) and "data" in node:
            # Dictionary structure
            node_data = node["data"]
            node_type = node_data.get("type", "").lower()
            node_id = node_data.get("id", "")
        else:
            logger.warning(f"Unexpected node structure: {node}")
            continue

        if node_type == "trigger":
            if node_id == "trigger_manual":
                has_manual_trigger = True
                logger.info(f"Found manual trigger node: {node_id}")
            else:
                has_event_trigger = True
                logger.info(f"Found event trigger node: {node_id}")

    # Build trigger types array
    if has_manual_trigger:
        trigger_types.append("Manual Trigger")
    if has_event_trigger:
        trigger_types.append("Event Trigger")

    # If no trigger nodes found, default to Event Trigger
    if not trigger_types:
        trigger_types.append("Event Trigger")
        logger.info("No trigger nodes found, defaulting to Event Trigger")

    # Return comma-separated string of trigger types
    pipeline_type = ",".join(trigger_types)
    logger.info(f"Determined pipeline type: {pipeline_type}")
    return pipeline_type
