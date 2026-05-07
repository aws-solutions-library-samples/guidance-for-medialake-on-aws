"""EventBridge event publishing utilities."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="dashboard-events")

EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")
EVENT_SOURCE = "medialake.dashboard"

_eventbridge_client = None


def _get_eventbridge_client():
    """Get or create EventBridge client."""
    global _eventbridge_client
    if _eventbridge_client is None:
        _eventbridge_client = boto3.client("events")
    return _eventbridge_client


def _publish_event(detail_type: str, detail: Dict[str, Any], user_id: str) -> bool:
    """Publish event to EventBridge."""
    try:
        client = _get_eventbridge_client()

        detail["userId"] = user_id
        detail["timestamp"] = datetime.now(timezone.utc).isoformat()

        client.put_events(
            Entries=[
                {
                    "Source": EVENT_SOURCE,
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "EventBusName": EVENT_BUS_NAME,
                }
            ]
        )
        logger.info(f"Published event: {detail_type}", extra={"user_id": user_id})
        return True
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")
        return False


def publish_layout_updated(
    user_id: str, layout_version: int, widget_count: int, action: str = "save"
) -> bool:
    """Publish DashboardLayoutUpdated event."""
    return _publish_event(
        detail_type="DashboardLayoutUpdated",
        detail={
            "layoutVersion": layout_version,
            "widgetCount": widget_count,
            "action": action,
        },
        user_id=user_id,
    )


def publish_widget_added(user_id: str, widget_id: str, widget_type: str) -> bool:
    """Publish WidgetAdded event."""
    return _publish_event(
        detail_type="WidgetAdded",
        detail={"widgetId": widget_id, "widgetType": widget_type},
        user_id=user_id,
    )


def publish_widget_removed(user_id: str, widget_id: str, widget_type: str) -> bool:
    """Publish WidgetRemoved event."""
    return _publish_event(
        detail_type="WidgetRemoved",
        detail={"widgetId": widget_id, "widgetType": widget_type},
        user_id=user_id,
    )


def publish_preset_created(
    user_id: str, preset_id: str, preset_name: str, widget_count: int
) -> bool:
    """Publish PresetCreated event."""
    return _publish_event(
        detail_type="PresetCreated",
        detail={
            "presetId": preset_id,
            "presetName": preset_name,
            "widgetCount": widget_count,
        },
        user_id=user_id,
    )
