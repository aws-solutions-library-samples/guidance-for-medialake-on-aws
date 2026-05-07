"""
Service for managing DynamoDB operations for auto-upgrade system.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBService:
    """Service for DynamoDB operations related to upgrades."""

    def __init__(self):
        """Initialize the DynamoDB service."""
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME", "")

        if not self.table_name:
            logger.warning("SYSTEM_SETTINGS_TABLE_NAME environment variable not set")

        self.table = self.dynamodb.Table(self.table_name) if self.table_name else None

    def get_current_version(self) -> Optional[Dict[str, Any]]:
        """
        Get the current deployed version from DynamoDB.

        Returns:
            Current version information or None if not found
        """
        try:
            if not self.table:
                raise ValueError("DynamoDB table not configured")

            response = self.table.get_item(
                Key={"PK": "SYSTEM_UPGRADE", "SK": "VERSION_CURRENT"}
            )

            if "Item" in response:
                return response["Item"].get("setting_value", {})

            return None

        except ClientError as e:
            logger.error(f"Failed to get current version: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting current version: {e}")
            raise

    def get_active_upgrade(self) -> Optional[Dict[str, Any]]:
        """
        Check if there's an active upgrade in progress.

        Returns:
            Active upgrade information or None if no upgrade in progress
        """
        try:
            if not self.table:
                raise ValueError("DynamoDB table not configured")

            response = self.table.get_item(
                Key={"PK": "SYSTEM_UPGRADE", "SK": "UPGRADE_ACTIVE"}
            )

            if "Item" in response:
                upgrade_info = response["Item"].get("setting_value", {})
                # Check if upgrade is actually in progress
                if upgrade_info.get("status") == "in_progress":
                    return upgrade_info

            return None

        except ClientError as e:
            logger.error(f"Failed to check active upgrade: {e}")
            raise
        except Exception as e:
            logger.error(f"Error checking active upgrade: {e}")
            raise

    def create_upgrade_record(
        self,
        upgrade_id: str,
        target_version: str,
        version_type: str,
        pipeline_execution_id: str,
        user_email: str,
    ) -> Dict[str, Any]:
        """
        Create a new upgrade record in DynamoDB.

        Args:
            upgrade_id: Unique upgrade identifier
            target_version: Target version
            version_type: Type of version ('branch' or 'tag')
            pipeline_execution_id: CodePipeline execution ID
            user_email: Email of user triggering upgrade

        Returns:
            Created upgrade record
        """
        try:
            if not self.table:
                raise ValueError("DynamoDB table not configured")

            current_time = datetime.now(timezone.utc).isoformat()

            # Get current version
            current_version_info = self.get_current_version()
            current_version = (
                current_version_info.get("version", "unknown")
                if current_version_info
                else "unknown"
            )

            upgrade_record = {
                "upgrade_id": upgrade_id,
                "from_version": current_version,
                "to_version": target_version,
                "version_type": version_type,
                "status": "in_progress",
                "pipeline_execution_id": pipeline_execution_id,
                "triggered_by": user_email,
                "start_time": current_time,
                "progress": {
                    "stage": "Initializing",
                    "percentage": 0,
                    "current_action": "Starting upgrade",
                },
            }

            # Store as active upgrade
            self.table.put_item(
                Item={
                    "PK": "SYSTEM_UPGRADE",
                    "SK": "UPGRADE_ACTIVE",
                    "setting_value": upgrade_record,
                    "description": "Currently active upgrade",
                    "created_by": user_email,
                    "last_updated": current_time,
                }
            )

            logger.info(f"Created upgrade record: {upgrade_id}")
            return upgrade_record

        except ClientError as e:
            logger.error(f"Failed to create upgrade record: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating upgrade record: {e}")
            raise

    def update_upgrade_status(
        self,
        upgrade_id: str,
        status: str,
        progress: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update the status of an active upgrade.

        Args:
            upgrade_id: Upgrade identifier
            status: New status
            progress: Progress information
            error_message: Error message if failed
        """
        try:
            if not self.table:
                raise ValueError("DynamoDB table not configured")

            current_time = datetime.now(timezone.utc).isoformat()

            # Get current upgrade record
            response = self.table.get_item(
                Key={"PK": "SYSTEM_UPGRADE", "SK": "UPGRADE_ACTIVE"}
            )

            if "Item" not in response:
                logger.warning(f"No active upgrade found for ID: {upgrade_id}")
                return

            upgrade_record = response["Item"]["setting_value"]

            # Update fields
            upgrade_record["status"] = status
            upgrade_record["last_updated"] = current_time

            if progress:
                upgrade_record["progress"] = progress

            if error_message:
                upgrade_record["error_message"] = error_message

            if status in ["completed", "failed"]:
                upgrade_record["end_time"] = current_time

            # Update the record
            self.table.put_item(
                Item={
                    "PK": "SYSTEM_UPGRADE",
                    "SK": "UPGRADE_ACTIVE",
                    "setting_value": upgrade_record,
                    "description": "Currently active upgrade",
                    "created_by": upgrade_record.get("triggered_by", "system"),
                    "last_updated": current_time,
                }
            )

            logger.info(f"Updated upgrade status to: {status}")

        except ClientError as e:
            logger.error(f"Failed to update upgrade status: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating upgrade status: {e}")
            raise

    def complete_upgrade(
        self,
        upgrade_id: str,
        new_version: str,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Complete an upgrade and update version history.

        Args:
            upgrade_id: Upgrade identifier
            new_version: New version that was deployed
            success: Whether upgrade was successful
            error_message: Error message if failed
        """
        try:
            if not self.table:
                raise ValueError("DynamoDB table not configured")

            current_time = datetime.now(timezone.utc).isoformat()

            # Get active upgrade
            response = self.table.get_item(
                Key={"PK": "SYSTEM_UPGRADE", "SK": "UPGRADE_ACTIVE"}
            )

            if "Item" not in response:
                logger.warning(f"No active upgrade found for ID: {upgrade_id}")
                return

            upgrade_record = response["Item"]["setting_value"]
            upgrade_record["status"] = "completed" if success else "failed"
            upgrade_record["end_time"] = current_time

            if error_message:
                upgrade_record["error_message"] = error_message

            # Calculate duration
            start_time = datetime.fromisoformat(
                upgrade_record["start_time"].replace("Z", "+00:00")
            )
            end_time = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
            duration = int((end_time - start_time).total_seconds())
            upgrade_record["duration"] = duration

            # Store in history
            timestamp = int(datetime.now(timezone.utc).timestamp())
            self.table.put_item(
                Item={
                    "PK": "SYSTEM_UPGRADE",
                    "SK": f"VERSION_UPGRADE#{timestamp}#{upgrade_id}",
                    "setting_value": upgrade_record,
                    "description": f'Upgrade from {upgrade_record["from_version"]} to {upgrade_record["to_version"]}',
                    "created_by": upgrade_record.get("triggered_by", "system"),
                    "last_updated": current_time,
                }
            )

            # Update current version if successful
            if success:
                self.table.put_item(
                    Item={
                        "PK": "SYSTEM_UPGRADE",
                        "SK": "VERSION_CURRENT",
                        "setting_value": {
                            "version": new_version,
                            "updated_at": current_time,
                            "updated_by": upgrade_record.get("triggered_by", "system"),
                        },
                        "description": "Current deployed version",
                        "created_by": upgrade_record.get("triggered_by", "system"),
                        "last_updated": current_time,
                    }
                )

            # Clear active upgrade
            self.table.delete_item(Key={"PK": "SYSTEM_UPGRADE", "SK": "UPGRADE_ACTIVE"})

            logger.info(f"Completed upgrade: {upgrade_id} - Success: {success}")

        except ClientError as e:
            logger.error(f"Failed to complete upgrade: {e}")
            raise
        except Exception as e:
            logger.error(f"Error completing upgrade: {e}")
            raise

    def get_upgrade_history(
        self, limit: int = 10, last_evaluated_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get upgrade history with pagination.

        Args:
            limit: Maximum number of records to return
            last_evaluated_key: Pagination token

        Returns:
            Dictionary with history items and pagination info
        """
        try:
            if not self.table:
                raise ValueError("DynamoDB table not configured")

            query_params = {
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "ExpressionAttributeValues": {
                    ":pk": "SYSTEM_UPGRADE",
                    ":sk_prefix": "VERSION_UPGRADE#",
                },
                "Limit": limit,
                "ScanIndexForward": False,  # Most recent first
            }

            if last_evaluated_key:
                query_params["ExclusiveStartKey"] = last_evaluated_key

            response = self.table.query(**query_params)

            items = [item["setting_value"] for item in response.get("Items", [])]

            return {
                "items": items,
                "last_evaluated_key": response.get("LastEvaluatedKey"),
                "count": len(items),
            }

        except ClientError as e:
            logger.error(f"Failed to get upgrade history: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting upgrade history: {e}")
            raise
