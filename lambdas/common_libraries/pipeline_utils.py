"""
Pipeline utility functions for the MediaLake application.

This file is deployed as part of the common_libraries Lambda layer and is
accessible to all Lambda functions.
"""

from typing import Any

from aws_lambda_powertools import Logger

logger = Logger()


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
