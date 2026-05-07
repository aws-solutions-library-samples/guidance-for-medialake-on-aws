"""
DynamoDB operations for external metadata enrichment.

This module provides functions to update asset records in DynamoDB with:
- ExternalAssetId (correlation ID)
- ExternalMetadata (normalized metadata under Metadata field for search indexing)
- ExternalMetadataStatus (enrichment status tracking)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

# Maximum length for error messages stored in DynamoDB
MAX_ERROR_MESSAGE_LENGTH = 500

# DynamoDB resource and table (lazy initialization)
_dynamodb_resource: Any = None
_asset_table: Any = None


def _get_asset_table() -> Any:
    """Get the DynamoDB asset table.

    Returns:
        DynamoDB Table resource

    Raises:
        ValueError: If MEDIALAKE_ASSET_TABLE environment variable is not set
    """
    global _dynamodb_resource, _asset_table

    if _asset_table is None:
        table_name = os.environ.get("MEDIALAKE_ASSET_TABLE")
        if not table_name:
            raise ValueError("MEDIALAKE_ASSET_TABLE environment variable not set")

        _dynamodb_resource = boto3.resource("dynamodb")
        _asset_table = _dynamodb_resource.Table(table_name)

    return _asset_table


def _get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO 8601 format.

    Returns:
        ISO 8601 formatted timestamp string
    """
    return datetime.now(timezone.utc).isoformat()


def _truncate_error_message(error_message: str) -> str:
    """Truncate error message to maximum allowed length.

    Args:
        error_message: The error message to truncate

    Returns:
        Truncated error message (max 500 characters)
    """
    if len(error_message) <= MAX_ERROR_MESSAGE_LENGTH:
        return error_message
    return error_message[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."


def update_asset_external_asset_id(inventory_id: str, correlation_id: str) -> None:
    """Update asset record with ExternalAssetId.

    This stores the correlation ID used for external system lookup
    at the root level of the asset record.

    Args:
        inventory_id: The asset's inventory ID
        correlation_id: The correlation ID to store

    Raises:
        ClientError: If DynamoDB update fails
    """
    table = _get_asset_table()

    try:
        table.update_item(
            Key={"InventoryID": inventory_id},
            UpdateExpression="SET #eid = :cid",
            ExpressionAttributeNames={"#eid": "ExternalAssetId"},
            ExpressionAttributeValues={":cid": correlation_id},
        )
        logger.info(
            "Updated ExternalAssetId",
            extra={
                "inventory_id": inventory_id,
                "correlation_id": correlation_id,
            },
        )
    except ClientError as e:
        logger.error(
            "Failed to update ExternalAssetId",
            extra={
                "inventory_id": inventory_id,
                "correlation_id": correlation_id,
                "error": str(e),
            },
        )
        raise


def update_asset_status_pending(inventory_id: str) -> None:
    """Update asset record with pending enrichment status.

    Sets ExternalMetadataStatus to pending state with current timestamp.

    Args:
        inventory_id: The asset's inventory ID

    Raises:
        ClientError: If DynamoDB update fails
    """
    table = _get_asset_table()
    timestamp = _get_current_timestamp()

    status_value = {
        "status": "pending",
        "lastAttempt": timestamp,
        "attemptCount": 1,
        "errorMessage": None,
    }

    try:
        # Use ADD for attemptCount to increment if already exists
        table.update_item(
            Key={"InventoryID": inventory_id},
            UpdateExpression=(
                "SET #ems.#st = :status, "
                "#ems.#la = :timestamp, "
                "#ems.#em = :null "
                "ADD #ems.#ac :one"
            ),
            ExpressionAttributeNames={
                "#ems": "ExternalMetadataStatus",
                "#st": "status",
                "#la": "lastAttempt",
                "#ac": "attemptCount",
                "#em": "errorMessage",
            },
            ExpressionAttributeValues={
                ":status": "pending",
                ":timestamp": timestamp,
                ":one": 1,
                ":null": None,
            },
            ConditionExpression="attribute_exists(InventoryID)",
        )
        logger.info(
            "Updated status to pending",
            extra={"inventory_id": inventory_id},
        )
    except ClientError as e:
        # If ExternalMetadataStatus doesn't exist, create it
        if e.response.get("Error", {}).get("Code") == "ValidationException":
            try:
                table.update_item(
                    Key={"InventoryID": inventory_id},
                    UpdateExpression="SET #ems = :status_obj",
                    ExpressionAttributeNames={"#ems": "ExternalMetadataStatus"},
                    ExpressionAttributeValues={":status_obj": status_value},
                )
                logger.info(
                    "Created ExternalMetadataStatus with pending status",
                    extra={"inventory_id": inventory_id},
                )
                return
            except ClientError as inner_e:
                logger.error(
                    "Failed to create ExternalMetadataStatus",
                    extra={
                        "inventory_id": inventory_id,
                        "error": str(inner_e),
                    },
                )
                raise inner_e

        logger.error(
            "Failed to update status to pending",
            extra={
                "inventory_id": inventory_id,
                "error": str(e),
            },
        )
        raise


def update_asset_with_metadata(
    inventory_id: str,
    normalized_metadata: dict[str, Any],
) -> None:
    """Update asset record with normalized external metadata.

    Stores ExternalMetadata under the Metadata field for search indexing
    and updates ExternalMetadataStatus to success.

    Args:
        inventory_id: The asset's inventory ID
        normalized_metadata: The normalized metadata dictionary

    Raises:
        ClientError: If DynamoDB update fails
    """
    table = _get_asset_table()
    timestamp = _get_current_timestamp()

    try:
        table.update_item(
            Key={"InventoryID": inventory_id},
            UpdateExpression=(
                "SET #m.#em = :metadata, "
                "#ems.#st = :status, "
                "#ems.#la = :timestamp, "
                "#ems.#err = :null"
            ),
            ExpressionAttributeNames={
                "#m": "Metadata",
                "#em": "ExternalMetadata",
                "#ems": "ExternalMetadataStatus",
                "#st": "status",
                "#la": "lastAttempt",
                "#err": "errorMessage",
            },
            ExpressionAttributeValues={
                ":metadata": normalized_metadata,
                ":status": "success",
                ":timestamp": timestamp,
                ":null": None,
            },
        )
        logger.info(
            "Updated asset with external metadata",
            extra={
                "inventory_id": inventory_id,
                "metadata_keys": list(normalized_metadata.keys()),
            },
        )
    except ClientError as e:
        # If Metadata field doesn't exist, create it with ExternalMetadata
        if e.response.get("Error", {}).get("Code") == "ValidationException":
            try:
                table.update_item(
                    Key={"InventoryID": inventory_id},
                    UpdateExpression=(
                        "SET #m = :metadata_obj, "
                        "#ems.#st = :status, "
                        "#ems.#la = :timestamp, "
                        "#ems.#err = :null"
                    ),
                    ExpressionAttributeNames={
                        "#m": "Metadata",
                        "#ems": "ExternalMetadataStatus",
                        "#st": "status",
                        "#la": "lastAttempt",
                        "#err": "errorMessage",
                    },
                    ExpressionAttributeValues={
                        ":metadata_obj": {"ExternalMetadata": normalized_metadata},
                        ":status": "success",
                        ":timestamp": timestamp,
                        ":null": None,
                    },
                )
                logger.info(
                    "Created Metadata field with ExternalMetadata",
                    extra={"inventory_id": inventory_id},
                )
                return
            except ClientError as inner_e:
                logger.error(
                    "Failed to create Metadata field",
                    extra={
                        "inventory_id": inventory_id,
                        "error": str(inner_e),
                    },
                )
                raise inner_e

        logger.error(
            "Failed to update asset with metadata",
            extra={
                "inventory_id": inventory_id,
                "error": str(e),
            },
        )
        raise


def update_asset_status_failed(
    inventory_id: str,
    error_message: str,
    attempt_count: int = 0,
) -> None:
    """Update asset record with failed enrichment status.

    Records failure details including error message, attempt count,
    and timestamp.

    Args:
        inventory_id: The asset's inventory ID
        error_message: The error message (will be truncated to 500 chars)
        attempt_count: Number of attempts made

    Raises:
        ClientError: If DynamoDB update fails
    """
    table = _get_asset_table()
    timestamp = _get_current_timestamp()
    truncated_error = _truncate_error_message(error_message)

    status_value = {
        "status": "failed",
        "lastAttempt": timestamp,
        "attemptCount": max(attempt_count, 1),
        "errorMessage": truncated_error,
    }

    try:
        table.update_item(
            Key={"InventoryID": inventory_id},
            UpdateExpression="SET #ems = :status_obj",
            ExpressionAttributeNames={"#ems": "ExternalMetadataStatus"},
            ExpressionAttributeValues={":status_obj": status_value},
        )
        logger.info(
            "Updated status to failed",
            extra={
                "inventory_id": inventory_id,
                "attempt_count": attempt_count,
                "error_message_length": len(error_message),
            },
        )
    except ClientError as e:
        logger.error(
            "Failed to update status to failed",
            extra={
                "inventory_id": inventory_id,
                "error": str(e),
            },
        )
        raise


def get_asset_enrichment_status(inventory_id: str) -> dict[str, Any] | None:
    """Get the current enrichment status for an asset.

    Args:
        inventory_id: The asset's inventory ID

    Returns:
        ExternalMetadataStatus dict if exists, None otherwise

    Raises:
        ClientError: If DynamoDB query fails
    """
    table = _get_asset_table()

    try:
        response = table.get_item(
            Key={"InventoryID": inventory_id},
            ProjectionExpression="ExternalMetadataStatus",
        )
        item = response.get("Item", {})
        return item.get("ExternalMetadataStatus")
    except ClientError as e:
        logger.error(
            "Failed to get enrichment status",
            extra={
                "inventory_id": inventory_id,
                "error": str(e),
            },
        )
        raise
