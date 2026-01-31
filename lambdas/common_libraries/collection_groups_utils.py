"""
Collection Groups utilities for MediaLake Lambda functions.

This module provides standardized collection group-related utility functions
including CRUD operations, membership management, and common operations that can
be used across all collections Lambda functions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger(service="collection-groups-utils")
tracer = Tracer(service="collection-groups-utils")
metrics = Metrics(namespace="medialake", service="collection-groups-utils")

# Collection group constants
GROUP_PK_PREFIX = "GROUP#"
GROUP_METADATA_SK = "METADATA"
USER_PK_PREFIX = "USER#"
GROUPS_GSI2_PK = "GROUPS"
AUDIT_SK_PREFIX = "AUDIT#"

# Valid group statuses
ACTIVE_STATUS = "ACTIVE"


@tracer.capture_method
def get_collection_group_metadata(table, group_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve collection group metadata from DynamoDB.

    Args:
        table: DynamoDB table resource
        group_id: Collection group ID to retrieve

    Returns:
        Collection group metadata dictionary or None if not found
    """
    try:
        response = table.get_item(
            Key={"PK": f"{GROUP_PK_PREFIX}{group_id}", "SK": GROUP_METADATA_SK}
        )

        item = response.get("Item")
        if item:
            logger.debug(
                {
                    "message": "Collection group metadata retrieved",
                    "group_id": group_id,
                    "operation": "get_collection_group_metadata",
                }
            )
        else:
            logger.debug(
                {
                    "message": "Collection group not found",
                    "group_id": group_id,
                    "operation": "get_collection_group_metadata",
                }
            )

        return item

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to retrieve collection group metadata",
                "group_id": group_id,
                "error": str(e),
                "operation": "get_collection_group_metadata",
            }
        )
        return None


@tracer.capture_method
def create_collection_group(table, group_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new collection group in DynamoDB.

    Args:
        table: DynamoDB table resource
        group_data: Dictionary containing group attributes

    Returns:
        Created collection group dictionary

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        current_timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        group_id = group_data["id"]
        owner_id = group_data["ownerId"]

        item = {
            "PK": f"{GROUP_PK_PREFIX}{group_id}",
            "SK": GROUP_METADATA_SK,
            "name": group_data["name"],
            "ownerId": owner_id,
            "isPublic": group_data.get("isPublic", True),
            "sharedWith": group_data.get("sharedWith", []),
            "collectionIds": group_data.get("collectionIds", []),
            "createdAt": current_timestamp,
            "updatedAt": current_timestamp,
            # GSI1 for owner queries
            "GSI1_PK": f"{USER_PK_PREFIX}{owner_id}",
            "GSI1_SK": f"{GROUP_PK_PREFIX}{group_id}",
            # GSI2 for all groups queries
            "GSI2_PK": GROUPS_GSI2_PK,
            "GSI2_SK": current_timestamp,
        }

        if group_data.get("description"):
            item["description"] = group_data["description"]

        table.put_item(Item=item)

        logger.info(
            {
                "message": "Collection group created",
                "group_id": group_id,
                "owner_id": owner_id,
                "operation": "create_collection_group",
            }
        )
        metrics.add_metric(
            name="CollectionGroupsCreated", unit=MetricUnit.Count, value=1
        )

        return item

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to create collection group",
                "error": str(e),
                "operation": "create_collection_group",
            }
        )
        metrics.add_metric(
            name="CollectionGroupCreationFailures", unit=MetricUnit.Count, value=1
        )
        raise


@tracer.capture_method
def update_collection_group(
    table, group_id: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update collection group metadata in DynamoDB.

    Args:
        table: DynamoDB table resource
        group_id: Collection group ID to update
        updates: Dictionary of fields to update

    Returns:
        Updated collection group dictionary

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        current_timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Build update expression
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_values = {}

        # Always update updatedAt
        update_expr_parts.append("#updatedAt = :updatedAt")
        expr_attr_names["#updatedAt"] = "updatedAt"
        expr_attr_values[":updatedAt"] = current_timestamp

        # Add other fields
        if "name" in updates:
            update_expr_parts.append("#name = :name")
            expr_attr_names["#name"] = "name"
            expr_attr_values[":name"] = updates["name"]

        if "description" in updates:
            update_expr_parts.append("description = :description")
            expr_attr_values[":description"] = updates["description"]

        if "isPublic" in updates:
            update_expr_parts.append("isPublic = :isPublic")
            expr_attr_values[":isPublic"] = updates["isPublic"]

        if "sharedWith" in updates:
            update_expr_parts.append("sharedWith = :sharedWith")
            expr_attr_values[":sharedWith"] = updates["sharedWith"]

        update_expression = "SET " + ", ".join(update_expr_parts)

        response = table.update_item(
            Key={"PK": f"{GROUP_PK_PREFIX}{group_id}", "SK": GROUP_METADATA_SK},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW",
        )

        logger.info(
            {
                "message": "Collection group updated",
                "group_id": group_id,
                "operation": "update_collection_group",
            }
        )
        metrics.add_metric(
            name="CollectionGroupsUpdated", unit=MetricUnit.Count, value=1
        )

        return response["Attributes"]

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to update collection group",
                "group_id": group_id,
                "error": str(e),
                "operation": "update_collection_group",
            }
        )
        metrics.add_metric(
            name="CollectionGroupUpdateFailures", unit=MetricUnit.Count, value=1
        )
        raise


@tracer.capture_method
def delete_collection_group(table, group_id: str) -> None:
    """
    Delete a collection group from DynamoDB.

    Args:
        table: DynamoDB table resource
        group_id: Collection group ID to delete

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        table.delete_item(
            Key={"PK": f"{GROUP_PK_PREFIX}{group_id}", "SK": GROUP_METADATA_SK}
        )

        logger.info(
            {
                "message": "Collection group deleted",
                "group_id": group_id,
                "operation": "delete_collection_group",
            }
        )
        metrics.add_metric(
            name="CollectionGroupsDeleted", unit=MetricUnit.Count, value=1
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to delete collection group",
                "group_id": group_id,
                "error": str(e),
                "operation": "delete_collection_group",
            }
        )
        metrics.add_metric(
            name="CollectionGroupDeletionFailures", unit=MetricUnit.Count, value=1
        )
        raise


@tracer.capture_method
def add_collection_ids(table, group_id: str, collection_ids: List[str]) -> None:
    """
    Add collection IDs to a group's collectionIds list with uniqueness enforcement.

    Args:
        table: DynamoDB table resource
        group_id: Collection group ID
        collection_ids: List of collection IDs to add

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        current_timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Get current group to check existing collection IDs
        group = get_collection_group_metadata(table, group_id)
        if not group:
            raise ValueError(f"Collection group {group_id} not found")

        existing_ids = set(group.get("collectionIds", []))
        # Deduplicate input and filter out existing IDs
        unique_new_ids = list(set(collection_ids) - existing_ids)

        if not unique_new_ids:
            logger.debug(
                {
                    "message": "No new collection IDs to add (all already exist)",
                    "group_id": group_id,
                    "operation": "add_collection_ids",
                }
            )
            return

        # Add new IDs to the list
        updated_ids = list(existing_ids) + unique_new_ids

        table.update_item(
            Key={"PK": f"{GROUP_PK_PREFIX}{group_id}", "SK": GROUP_METADATA_SK},
            UpdateExpression="SET collectionIds = :ids, updatedAt = :timestamp",
            ExpressionAttributeValues={
                ":ids": updated_ids,
                ":timestamp": current_timestamp,
            },
        )

        logger.info(
            {
                "message": "Collection IDs added to group",
                "group_id": group_id,
                "added_count": len(unique_new_ids),
                "operation": "add_collection_ids",
            }
        )
        metrics.add_metric(
            name="CollectionsAddedToGroups",
            unit=MetricUnit.Count,
            value=len(unique_new_ids),
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to add collection IDs to group",
                "group_id": group_id,
                "error": str(e),
                "operation": "add_collection_ids",
            }
        )
        metrics.add_metric(
            name="AddCollectionToGroupFailures", unit=MetricUnit.Count, value=1
        )
        raise


@tracer.capture_method
def remove_collection_ids(table, group_id: str, collection_ids: List[str]) -> None:
    """
    Remove collection IDs from a group's collectionIds list.

    Args:
        table: DynamoDB table resource
        group_id: Collection group ID
        collection_ids: List of collection IDs to remove

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        current_timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Get current group
        group = get_collection_group_metadata(table, group_id)
        if not group:
            raise ValueError(f"Collection group {group_id} not found")

        existing_ids = set(group.get("collectionIds", []))
        ids_to_remove = set(collection_ids)
        updated_ids = list(existing_ids - ids_to_remove)

        table.update_item(
            Key={"PK": f"{GROUP_PK_PREFIX}{group_id}", "SK": GROUP_METADATA_SK},
            UpdateExpression="SET collectionIds = :ids, updatedAt = :timestamp",
            ExpressionAttributeValues={
                ":ids": updated_ids,
                ":timestamp": current_timestamp,
            },
        )

        logger.info(
            {
                "message": "Collection IDs removed from group",
                "group_id": group_id,
                "removed_count": len(ids_to_remove),
                "operation": "remove_collection_ids",
            }
        )
        metrics.add_metric(
            name="CollectionsRemovedFromGroups",
            unit=MetricUnit.Count,
            value=len(ids_to_remove),
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to remove collection IDs from group",
                "group_id": group_id,
                "error": str(e),
                "operation": "remove_collection_ids",
            }
        )
        metrics.add_metric(
            name="RemoveCollectionFromGroupFailures", unit=MetricUnit.Count, value=1
        )
        raise


@tracer.capture_method
def remove_collection_from_all_groups(table, collection_id: str) -> None:
    """
    Remove a collection ID from all groups (cascade deletion).

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to remove from all groups

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        # Scan for all groups containing this collection ID
        response = table.scan(
            FilterExpression="contains(collectionIds, :collection_id) AND SK = :metadata_sk",
            ExpressionAttributeValues={
                ":collection_id": collection_id,
                ":metadata_sk": GROUP_METADATA_SK,
            },
        )

        groups_to_update = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression="contains(collectionIds, :collection_id) AND SK = :metadata_sk",
                ExpressionAttributeValues={
                    ":collection_id": collection_id,
                    ":metadata_sk": GROUP_METADATA_SK,
                },
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            groups_to_update.extend(response.get("Items", []))

        # Update each group
        for group in groups_to_update:
            group["PK"].replace(GROUP_PK_PREFIX, "")
            current_ids = group.get("collectionIds", [])
            updated_ids = [cid for cid in current_ids if cid != collection_id]

            table.update_item(
                Key={"PK": group["PK"], "SK": GROUP_METADATA_SK},
                UpdateExpression="SET collectionIds = :ids, updatedAt = :timestamp",
                ExpressionAttributeValues={
                    ":ids": updated_ids,
                    ":timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
            )

        logger.info(
            {
                "message": "Collection removed from all groups",
                "collection_id": collection_id,
                "groups_updated": len(groups_to_update),
                "operation": "remove_collection_from_all_groups",
            }
        )
        metrics.add_metric(
            name="CascadeCollectionRemovals", unit=MetricUnit.Count, value=1
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to remove collection from all groups",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "remove_collection_from_all_groups",
            }
        )
        metrics.add_metric(
            name="CascadeRemovalFailures", unit=MetricUnit.Count, value=1
        )
        raise


@tracer.capture_method
def get_groups_by_collection_id(table, collection_id: str) -> List[Dict[str, Any]]:
    """
    Get all groups that contain a specific collection.

    Args:
        table: DynamoDB table resource
        collection_id: Collection ID to search for

    Returns:
        List of collection group dictionaries
    """
    try:
        response = table.scan(
            FilterExpression="contains(collectionIds, :collection_id) AND SK = :metadata_sk",
            ExpressionAttributeValues={
                ":collection_id": collection_id,
                ":metadata_sk": GROUP_METADATA_SK,
            },
        )

        groups = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression="contains(collectionIds, :collection_id) AND SK = :metadata_sk",
                ExpressionAttributeValues={
                    ":collection_id": collection_id,
                    ":metadata_sk": GROUP_METADATA_SK,
                },
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            groups.extend(response.get("Items", []))

        logger.debug(
            {
                "message": "Groups retrieved by collection ID",
                "collection_id": collection_id,
                "group_count": len(groups),
                "operation": "get_groups_by_collection_id",
            }
        )

        return groups

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get groups by collection ID",
                "collection_id": collection_id,
                "error": str(e),
                "operation": "get_groups_by_collection_id",
            }
        )
        return []


@tracer.capture_method
def get_collection_ids_by_group_ids(table, group_ids: List[str]) -> List[str]:
    """
    Get all collection IDs from specified groups (OR logic).

    Args:
        table: DynamoDB table resource
        group_ids: List of group IDs to query

    Returns:
        List of unique collection IDs
    """
    try:
        all_collection_ids = set()

        for group_id in group_ids:
            group = get_collection_group_metadata(table, group_id)
            if group:
                collection_ids = group.get("collectionIds", [])
                all_collection_ids.update(collection_ids)

        logger.debug(
            {
                "message": "Collection IDs retrieved by group IDs",
                "group_count": len(group_ids),
                "collection_count": len(all_collection_ids),
                "operation": "get_collection_ids_by_group_ids",
            }
        )

        return list(all_collection_ids)

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to get collection IDs by group IDs",
                "error": str(e),
                "operation": "get_collection_ids_by_group_ids",
            }
        )
        return []


@tracer.capture_method
def format_collection_group_item(
    item: Dict[str, Any], user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format DynamoDB collection group item to standardized API response format.

    Args:
        item: Raw DynamoDB item
        user_context: User context information

    Returns:
        Formatted collection group object
    """
    # Extract group ID from PK
    group_id = item["PK"].replace(GROUP_PK_PREFIX, "")
    user_id = user_context.get("user_id") if user_context else None
    owner_id = item.get("ownerId", "")

    formatted_item = {
        "id": group_id,
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "ownerId": owner_id,
        "isPublic": item.get("isPublic", True),
        "sharedWith": item.get("sharedWith", []),
        "collectionIds": item.get("collectionIds", []),
        "collectionCount": len(item.get("collectionIds", [])),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }

    # Add user-specific fields if user context available
    if user_id:
        if owner_id == user_id:
            formatted_item["isOwner"] = True
            formatted_item["userRole"] = "owner"
        else:
            formatted_item["isOwner"] = False
            formatted_item["userRole"] = "viewer"

    logger.debug(
        {
            "message": "Collection group item formatted",
            "group_id": group_id,
            "operation": "format_collection_group_item",
        }
    )

    return formatted_item


@tracer.capture_method
def validate_collection_ids(table, collection_ids: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that all collection IDs reference existing collections.

    Args:
        table: DynamoDB table resource
        collection_ids: List of collection IDs to validate

    Returns:
        Tuple of (all_valid: bool, invalid_ids: List[str])
    """
    from lambdas.common_libraries.collections_utils import (
        COLLECTION_PK_PREFIX,
        METADATA_SK,
    )

    invalid_ids = []

    try:
        for collection_id in collection_ids:
            response = table.get_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": METADATA_SK,
                }
            )
            if "Item" not in response:
                invalid_ids.append(collection_id)

        all_valid = len(invalid_ids) == 0

        logger.debug(
            {
                "message": "Collection IDs validated",
                "total_ids": len(collection_ids),
                "invalid_count": len(invalid_ids),
                "operation": "validate_collection_ids",
            }
        )

        return all_valid, invalid_ids

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate collection IDs",
                "error": str(e),
                "operation": "validate_collection_ids",
            }
        )
        # On error, assume all are invalid for safety
        return False, collection_ids
