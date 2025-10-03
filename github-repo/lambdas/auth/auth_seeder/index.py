"""
Authorization Table Seeder Lambda for MediaLake.

This Lambda function is triggered by a CloudFormation Custom Resource
and seeds the default system groups and permission sets (
                                                             Super Administrator,
                                                             Editor,
                                                             Viewer
                                                         )
into the DynamoDB authorization table.
"""

import datetime
import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger
from crhelper import CfnResource

# Initialize powertools
logger = Logger()

# Initialize resources
helper = CfnResource(json_logging=True, log_level="DEBUG", boto_level="CRITICAL")
dynamodb = boto3.resource("dynamodb")

# Get environment variables
AUTH_TABLE_NAME = os.environ.get("AUTH_TABLE_NAME")

# Constants for DynamoDB keys
PREFIX_PERMISSION_SET = "PS#"
PREFIX_GROUP = "GROUP#"
PREFIX_METADATA = "METADATA"

# Default groups definitions
DEFAULT_GROUPS = [
    {
        "id": "superAdministrators",
        "name": "Super Administrator",
        "description": "System administrators with full access to all features and settings",
        "department": "Administration",
        "assignedPermissionSets": ["superAdministrator"],
    },
    {
        "id": "editors",
        "name": "Editor",
        "description": "Content editors who can create, modify, and manage media assets",
        "department": "Content Management",
        "assignedPermissionSets": ["editor"],
    },
    {
        "id": "read-only",
        "name": "Read Only",
        "description": "Users with read-only access to view media assets and reports",
        "department": "General",
        "assignedPermissionSets": ["viewer"],
    },
]

# Default permission sets definitions
DEFAULT_PERMISSION_SETS = [
    {
        "id": "superAdministrator",
        "name": "Super Administrator",
        "description": "Full access to all system features and resources",
        "isSystem": True,
        "permissions": {
            "assets": {
                "upload": True,
                "download": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "pipelines": {"create": True, "view": True, "edit": True, "delete": True},
            "pipelinesExecutions": {"view": True, "retry": True, "cancel": True},
            "collections": {"create": True, "view": True, "edit": True, "delete": True},
            "settings": {
                "users": {"edit": True, "view": True, "delete": True, "create": True},
                "system": {"edit": True},
                "integrations": {"edit": True, "view": True, "delete": True},
                "regions": {"edit": True},
                "connectors": {"edit": True, "delete": True, "create": True},
                "permissions": {"edit": True, "delete": True, "create": True},
            },
        },
    },
    {
        "id": "editor",
        "name": "Editor",
        "description": "Can view, edit, and manage assets and pipelines, but cannot perform administrative actions",
        "isSystem": True,
        "effectiveRole": "Editor",
        "permissions": {
            "assets": {
                "upload": True,
                "download": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "pipelines": {"create": True, "view": True, "edit": True, "delete": True},
            "pipelinesExecutions": {"view": True, "retry": True, "cancel": True},
            "collections": {"create": True, "view": True, "edit": True, "delete": True},
        },
    },
    {
        "id": "viewer",
        "name": "Viewer",
        "description": "Read-only access to assets, pipelines, and collections",
        "isSystem": True,
        "effectiveRole": "Viewer",
        "permissions": {
            "assets": {
                "upload": False,
                "download": True,
                "view": True,
                "edit": False,
                "delete": False,
            },
            "pipelines": {
                "create": False,
                "view": True,
                "edit": False,
                "delete": False,
            },
            "pipelinesExecutions": {"view": True, "retry": False, "cancel": False},
            "collections": {
                "create": False,
                "view": True,
                "edit": False,
                "delete": False,
            },
        },
    },
]


def seed_group(group: Dict[str, Any]) -> bool:
    """
    Seed a group into the DynamoDB authorization table.

    Args:
        group: Group definition

    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize DynamoDB table
        table = dynamodb.Table(AUTH_TABLE_NAME)

        # Generate timestamps
        current_time = datetime.datetime.now().isoformat()

        # Prepare DynamoDB item following the group data model
        item = {
            "PK": f"{PREFIX_GROUP}{group['id']}",
            "SK": PREFIX_METADATA,
            "name": group["name"],
            "description": group["description"],
            "department": group["department"],
            "assignedPermissionSets": group.get("assignedPermissionSets", []),
            "createdAt": current_time,
            "updatedAt": current_time,
            "entity": "group",
            "id": group["id"],
        }

        # Check if the group already exists
        response = table.get_item(Key={"PK": item["PK"], "SK": item["SK"]})

        if "Item" in response:
            logger.info(
                f"Group {group['id']} already exists, skipping to preserve existing data"
            )
            # Skip updating existing groups to preserve any customizations
            return True
        else:
            logger.info(f"Creating group {group['id']}")
            # Create a new item
            table.put_item(Item=item)

        return True
    except Exception as e:
        logger.error(f"Error seeding group {group['id']}: {str(e)}")
        return False


def seed_permission_set(permission_set: Dict[str, Any]) -> bool:
    """
    Seed a permission set into the DynamoDB authorization table.

    Args:
        permission_set: Permission set definition

    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize DynamoDB table
        table = dynamodb.Table(AUTH_TABLE_NAME)

        # Generate timestamps
        current_time = datetime.datetime.now().isoformat()

        # Prepare DynamoDB item
        item = {
            "PK": f"{PREFIX_PERMISSION_SET}{permission_set['id']}",
            "SK": PREFIX_METADATA,
            "name": permission_set["name"],
            "description": permission_set["description"],
            "isSystem": permission_set["isSystem"],
            "permissions": permission_set["permissions"],
            "createdAt": current_time,
            "updatedAt": current_time,
        }

        # Add effectiveRole if present
        if "effectiveRole" in permission_set:
            item["effectiveRole"] = permission_set["effectiveRole"]

        # Check if the permission set already exists
        response = table.get_item(Key={"PK": item["PK"], "SK": item["SK"]})

        if "Item" in response:
            logger.info(
                f"Permission set {permission_set['id']} already exists, skipping to preserve existing data"
            )
            # Skip updating existing permission sets to preserve any customizations
            return True
        else:
            logger.info(f"Creating permission set {permission_set['id']}")
            # Create a new item
            table.put_item(Item=item)

        return True
    except Exception as e:
        logger.error(f"Error seeding permission set {permission_set['id']}: {str(e)}")
        return False


@helper.create
def create_handler(event: Dict[str, Any], context: Any) -> None:
    """
    Handle the creation of the default groups and permission sets.

    Args:
        event: CloudFormation Custom Resource event
        context: Lambda context
    """
    logger.info("Creating default groups and permission sets")

    # Seed groups first
    group_success_count = 0
    group_failure_count = 0

    for group in DEFAULT_GROUPS:
        if seed_group(group):
            group_success_count += 1
        else:
            group_failure_count += 1

    logger.info(
        f"Group seeding completed: {group_success_count} succeeded, {group_failure_count} failed"
    )

    # Then seed permission sets
    ps_success_count = 0
    ps_failure_count = 0

    for permission_set in DEFAULT_PERMISSION_SETS:
        if seed_permission_set(permission_set):
            ps_success_count += 1
        else:
            ps_failure_count += 1

    logger.info(
        f"Permission set seeding completed: {ps_success_count} succeeded, {ps_failure_count} failed"
    )

    total_success = group_success_count + ps_success_count
    total_failure = group_failure_count + ps_failure_count
    logger.info(
        f"Total seeding completed: {total_success} succeeded, {total_failure} failed"
    )


@helper.update
def update_handler(event: Dict[str, Any], context: Any) -> None:
    """
    Handle updates to the custom resource.

    Args:
        event: CloudFormation Custom Resource event
        context: Lambda context
    """
    logger.info("Update operation - skipping seeding to preserve existing data")
    # For updates, we skip seeding to avoid overwriting existing custom groups,
    # permission sets, and user assignments that may have been created after initial deployment
    logger.info("No action taken on UPDATE event to preserve user customizations")


@helper.delete
def delete_handler(event: Dict[str, Any], context: Any) -> None:
    """
    Handle the deletion of the custom resource.

    Args:
        event: CloudFormation Custom Resource event
        context: Lambda context
    """
    # We don't delete the default groups and permission sets when the stack is deleted
    logger.info("Delete operation - not removing default groups and permission sets")


@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """
    Lambda handler to process CloudFormation Custom Resource events.

    Args:
        event: CloudFormation Custom Resource event
        context: Lambda context
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        helper(event, context)
    except Exception as e:
        logger.exception(f"Error in lambda_handler: {str(e)}")
        helper.init_failure(e)
