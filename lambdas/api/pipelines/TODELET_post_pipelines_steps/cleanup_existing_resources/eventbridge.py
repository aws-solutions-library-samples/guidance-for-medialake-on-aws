"""
EventBridge utility functions for cleaning up existing resources.
"""

import boto3
from aws_lambda_powertools import Logger
import os

# Initialize logger
logger = Logger()

# Get the event bus name from environment variables
INGEST_EVENT_BUS_NAME = os.environ.get("INGEST_EVENT_BUS_NAME")

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
        raise