"""
Notification adapter for EventBridge and messaging operations.

This module handles all event publishing and notification operations
for asset processing events.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()


class NotificationAdapter:
    """
    Adapter for AWS EventBridge and messaging operations.

    This class encapsulates all event publishing and notification
    functionality needed for asset processing workflows.
    """

    def __init__(self):
        """Initialize AWS clients with connection reuse for Lambda optimization."""
        self.eventbridge_client = boto3.client("events")
        self.event_bus_name = os.environ.get("EVENT_BUS_NAME", "default")
        self.event_source = os.environ.get("EVENT_SOURCE", "medialake.asset.processor")

    def publish_asset_created_event(
        self, inventory_id: str, asset_record: Dict[str, Any]
    ) -> None:
        """Publish asset created event to EventBridge."""
        try:
            event_detail = {
                "inventory_id": inventory_id,
                "asset_type": asset_record.get("AssetType"),
                "bucket": asset_record.get("Bucket"),
                "object_key": asset_record.get("ObjectKey"),
                "file_hash": asset_record.get("FileHash"),
                "file_size": asset_record.get("FileSize"),
                "created_at": asset_record.get("CreatedAt"),
                "metadata": asset_record.get("Metadata", {}),
                "event_type": "asset_created",
            }

            self._publish_event(detail_type="Asset Created", detail=event_detail)

            logger.info(
                "Asset created event published",
                extra={"inventory_id": inventory_id, "event_type": "asset_created"},
            )

        except Exception as e:
            logger.exception(
                "Error publishing asset created event",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for event publishing errors

    def publish_asset_deleted_event(
        self, inventory_id: str, bucket: str, object_key: str
    ) -> None:
        """Publish asset deleted event to EventBridge."""
        try:
            event_detail = {
                "inventory_id": inventory_id,
                "bucket": bucket,
                "object_key": object_key,
                "deleted_at": datetime.utcnow().isoformat(),
                "event_type": "asset_deleted",
            }

            self._publish_event(detail_type="Asset Deleted", detail=event_detail)

            logger.info(
                "Asset deleted event published",
                extra={"inventory_id": inventory_id, "event_type": "asset_deleted"},
            )

        except Exception as e:
            logger.exception(
                "Error publishing asset deleted event",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for event publishing errors

    def publish_duplicate_detected_event(
        self,
        inventory_id: str,
        original_inventory_id: str,
        bucket: str,
        object_key: str,
        file_hash: str,
    ) -> None:
        """Publish duplicate asset detected event to EventBridge."""
        try:
            event_detail = {
                "inventory_id": inventory_id,
                "original_inventory_id": original_inventory_id,
                "bucket": bucket,
                "object_key": object_key,
                "file_hash": file_hash,
                "detected_at": datetime.utcnow().isoformat(),
                "event_type": "duplicate_detected",
            }

            self._publish_event(
                detail_type="Duplicate Asset Detected", detail=event_detail
            )

            logger.info(
                "Duplicate detected event published",
                extra={
                    "inventory_id": inventory_id,
                    "original_inventory_id": original_inventory_id,
                    "event_type": "duplicate_detected",
                },
            )

        except Exception as e:
            logger.exception(
                "Error publishing duplicate detected event",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for event publishing errors

    def publish_processing_error_event(
        self,
        bucket: str,
        object_key: str,
        error_message: str,
        error_type: str = "processing_error",
    ) -> None:
        """Publish processing error event to EventBridge."""
        try:
            event_detail = {
                "bucket": bucket,
                "object_key": object_key,
                "error_message": error_message,
                "error_type": error_type,
                "occurred_at": datetime.utcnow().isoformat(),
                "event_type": "processing_error",
            }

            self._publish_event(
                detail_type="Asset Processing Error", detail=event_detail
            )

            logger.info(
                "Processing error event published",
                extra={
                    "bucket": bucket,
                    "object_key": object_key,
                    "error_type": error_type,
                    "event_type": "processing_error",
                },
            )

        except Exception as e:
            logger.exception(
                "Error publishing processing error event",
                extra={"bucket": bucket, "object_key": object_key, "error": str(e)},
            )
            # Don't fail the main operation for event publishing errors

    def publish_asset_updated_event(
        self, inventory_id: str, asset_record: Dict[str, Any], changes: Dict[str, Any]
    ) -> None:
        """Publish asset updated event to EventBridge."""
        try:
            event_detail = {
                "inventory_id": inventory_id,
                "asset_type": asset_record.get("AssetType"),
                "bucket": asset_record.get("Bucket"),
                "object_key": asset_record.get("ObjectKey"),
                "changes": changes,
                "updated_at": datetime.utcnow().isoformat(),
                "event_type": "asset_updated",
            }

            self._publish_event(detail_type="Asset Updated", detail=event_detail)

            logger.info(
                "Asset updated event published",
                extra={"inventory_id": inventory_id, "event_type": "asset_updated"},
            )

        except Exception as e:
            logger.exception(
                "Error publishing asset updated event",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for event publishing errors

    def _publish_event(self, detail_type: str, detail: Dict[str, Any]) -> None:
        """Internal method to publish events to EventBridge."""
        try:
            # Ensure detail is JSON serializable
            serializable_detail = self._make_json_serializable(detail)

            response = self.eventbridge_client.put_events(
                Entries=[
                    {
                        "Source": self.event_source,
                        "DetailType": detail_type,
                        "Detail": json.dumps(serializable_detail),
                        "EventBusName": self.event_bus_name,
                        "Time": datetime.utcnow(),
                    }
                ]
            )

            # Check for failed entries
            failed_entries = response.get("FailedEntryCount", 0)
            if failed_entries > 0:
                logger.error(
                    "Failed to publish some events",
                    extra={
                        "failed_entries": failed_entries,
                        "entries": response.get("Entries", []),
                    },
                )

        except ClientError as e:
            logger.exception(
                "AWS EventBridge client error",
                extra={
                    "detail_type": detail_type,
                    "error_code": e.response.get("Error", {}).get("Code"),
                    "error_message": e.response.get("Error", {}).get("Message"),
                },
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error publishing event",
                extra={"detail_type": detail_type, "error": str(e)},
            )
            raise

    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            return self._make_json_serializable(obj.__dict__)
        else:
            # For any other type, try to convert to string as fallback
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

    def send_notification(
        self,
        notification_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a general notification (can be extended for SNS, SQS, etc.)."""
        try:
            event_detail = {
                "notification_type": notification_type,
                "message": message,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "notification",
            }

            self._publish_event(detail_type="General Notification", detail=event_detail)

            logger.info(
                "General notification sent",
                extra={
                    "notification_type": notification_type,
                    "event_type": "notification",
                },
            )

        except Exception as e:
            logger.exception(
                "Error sending notification",
                extra={"notification_type": notification_type, "error": str(e)},
            )
            # Don't fail the main operation for notification errors

    def publish_batch_processing_event(
        self, batch_id: str, total_items: int, processed_items: int, failed_items: int
    ) -> None:
        """Publish batch processing status event to EventBridge."""
        try:
            event_detail = {
                "batch_id": batch_id,
                "total_items": total_items,
                "processed_items": processed_items,
                "failed_items": failed_items,
                "success_rate": (
                    (processed_items / total_items) * 100 if total_items > 0 else 0
                ),
                "completed_at": datetime.utcnow().isoformat(),
                "event_type": "batch_processing_completed",
            }

            self._publish_event(
                detail_type="Batch Processing Completed", detail=event_detail
            )

            logger.info(
                "Batch processing event published",
                extra={
                    "batch_id": batch_id,
                    "total_items": total_items,
                    "processed_items": processed_items,
                    "failed_items": failed_items,
                    "event_type": "batch_processing_completed",
                },
            )

        except Exception as e:
            logger.exception(
                "Error publishing batch processing event",
                extra={"batch_id": batch_id, "error": str(e)},
            )
            # Don't fail the main operation for event publishing errors
