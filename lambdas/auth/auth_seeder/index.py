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

# Permission set schema version - increment this to force update of system permission sets
PERMISSION_SCHEMA_VERSION = "2.5.0"

# ─────────────────────────────────────────────────────────────────────────────
# Auth behavior version
#
# Some corrections to token generation change observable behavior, so they must
# not be applied silently to a deployment that is already running. This marker
# records which set of behaviors a deployment uses:
#
#   1  legacy   - preserve the exact behavior shipped before the correction
#   2  current  - the corrected behavior
#
# It is written exactly once, and never changed automatically. A brand-new
# deployment gets version 2; an existing one gets version 1 and can be moved to
# 2 deliberately once the operator has reviewed the change.
#
# "Brand-new" is decided by whether the built-in groups already exist, which is
# checked *before* seeding creates them. A new CloudFormation custom resource
# cannot be used for this: adding one fires a Create event on existing
# deployments too, which would misclassify every current install as new.
# ─────────────────────────────────────────────────────────────────────────────
PK_AUTH_CONFIG = "CONFIG#AUTH"
AUTH_BEHAVIOR_VERSION_LEGACY = 1
AUTH_BEHAVIOR_VERSION_CURRENT = 2

# Presence of this group means the deployment has been seeded before.
EXISTING_DEPLOYMENT_MARKER_GROUP = "superAdministrators"


def ensure_auth_behavior_version() -> int:
    """Record the deployment's auth behavior version if it is not already set.

    Returns the effective version. Never overwrites an existing value, so an
    operator who moves a deployment to version 2 is not reverted by the next
    deploy.
    """
    try:
        table = dynamodb.Table(AUTH_TABLE_NAME)

        existing = table.get_item(
            Key={"PK": PK_AUTH_CONFIG, "SK": PREFIX_METADATA}, ConsistentRead=True
        ).get("Item")
        if existing and existing.get("authBehaviorVersion") is not None:
            version = int(existing["authBehaviorVersion"])
            logger.info(f"Auth behavior version already set to {version}")
            return version

        # Checked before seeding runs, so this genuinely distinguishes a fresh
        # deployment from one that has been seeded before.
        marker = table.get_item(
            Key={
                "PK": f"{PREFIX_GROUP}{EXISTING_DEPLOYMENT_MARKER_GROUP}",
                "SK": PREFIX_METADATA,
            },
            ConsistentRead=True,
        ).get("Item")

        is_existing_deployment = marker is not None
        version = (
            AUTH_BEHAVIOR_VERSION_LEGACY
            if is_existing_deployment
            else AUTH_BEHAVIOR_VERSION_CURRENT
        )

        current_time = datetime.datetime.now().isoformat()
        try:
            table.put_item(
                Item={
                    "PK": PK_AUTH_CONFIG,
                    "SK": PREFIX_METADATA,
                    "entity": "authConfig",
                    "authBehaviorVersion": version,
                    "reason": (
                        "existing deployment detected at first marker write"
                        if is_existing_deployment
                        else "new deployment"
                    ),
                    "createdAt": current_time,
                    "updatedAt": current_time,
                },
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )
            logger.info(
                f"Auth behavior version set to {version} "
                f"({'existing' if is_existing_deployment else 'new'} deployment)"
            )
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            # A concurrent run won; whatever it wrote is authoritative.
            logger.info("Auth behavior version was written concurrently")

        return version
    except Exception as e:
        logger.error(f"Error setting auth behavior version: {str(e)}")
        # Legacy is the safe answer: it preserves existing behavior.
        return AUTH_BEHAVIOR_VERSION_LEGACY


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
            # Asset permissions
            "assets": {
                "create": True,
                "upload": True,
                "download": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            # Search permissions
            "search": {"view": True},
            # Pipeline permissions
            "pipelines": {"create": True, "view": True, "edit": True, "delete": True},
            "pipelinesExecutions": {"view": True, "retry": True},
            # Collection permissions
            "collections": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
                "add_assets": True,
                "remove_assets": True,
            },
            # Dashboard permissions
            "dashboard": {"view": True, "create": True, "edit": True, "delete": True},
            "defaultDashboard": {
                "view": True,
                "create": True,
                "edit": True,
                "delete": True,
            },
            # System permissions (top-level for app initialization)
            "system": {
                "view": True,
                "edit": True,
            },
            # Top-level resource permissions (required by custom authorizer)
            # These are flattened to "resource:action" format (e.g., "connectors:view")
            "connectors": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
                # Upload assets into shared (non-personal) connectors.
                "upload": True,
            },
            "users": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "groups": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "integrations": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "permissions": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "regions": {
                "view": True,
                "edit": True,
            },
            "nodes": {
                "view": True,
            },
            "environments": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "reviews": {
                "view": True,
                "edit": True,
                "delete": True,
            },
            "storage": {
                "view": True,
            },
            "api-keys": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            "collection-types": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
                "manage": True,
            },
            # Settings menu visibility (only admins see the Settings menu in sidebar)
            "settings-menu": {
                "view": True,
            },
            # Nested settings permissions (for frontend UI compatibility)
            "settings": {
                "users": {"edit": True, "view": True, "delete": True, "create": True},
                "groups": {"edit": True, "view": True, "delete": True, "create": True},
                "system": {"edit": True, "view": True},
                "integrations": {
                    "edit": True,
                    "view": True,
                    "delete": True,
                    "create": True,
                },
                "regions": {"edit": True, "view": True},
                "connectors": {
                    "edit": True,
                    "view": True,
                    "delete": True,
                    "create": True,
                },
                "permissions": {
                    "edit": True,
                    "view": True,
                    "delete": True,
                    "create": True,
                },
                "api-keys": {
                    "create": True,
                    "view": True,
                    "edit": True,
                    "delete": True,
                },
                "collection-types": {
                    "create": True,
                    "view": True,
                    "edit": True,
                    "delete": True,
                    "manage": True,
                },
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
            # Asset permissions
            "assets": {
                "create": True,
                "upload": True,
                "download": True,
                "view": True,
                "edit": True,
                "delete": True,
            },
            # Search permissions
            "search": {"view": True},
            # Pipeline permissions
            "pipelines": {"create": True, "view": True, "edit": True, "delete": True},
            "pipelinesExecutions": {"view": True, "retry": True},
            # Collection permissions
            "collections": {
                "create": True,
                "view": True,
                "edit": True,
                "delete": True,
                "add_assets": True,
                "remove_assets": True,
            },
            # Dashboard permissions
            "dashboard": {"view": True, "create": True, "edit": True, "delete": True},
            # Collection types (view only - needed to work with collections)
            "collection-types": {"view": True},
            # System permissions (read-only for app initialization)
            "system": {
                "view": True,
                "edit": False,
            },
            # Top-level resource permissions (required by custom authorizer)
            # Connectors: view to browse the Assets page; upload to send assets
            # into shared (non-personal) connectors.
            "connectors": {
                "view": True,
                "upload": True,
            },
            "nodes": {
                "view": True,
            },
            "regions": {
                "view": True,
            },
            "storage": {
                "view": True,
            },
        },
    },
    {
        "id": "viewer",
        "name": "Viewer",
        "description": "Read-only access to assets, pipelines, and collections",
        "isSystem": True,
        "effectiveRole": "Viewer",
        "permissions": {
            # Asset permissions (read-only + download)
            "assets": {
                "upload": False,
                "download": True,
                "view": True,
                "edit": False,
                "delete": False,
            },
            # Search permissions
            "search": {"view": True},
            # Pipeline permissions (view only)
            "pipelines": {
                "create": False,
                "view": True,
                "edit": False,
                "delete": False,
            },
            "pipelinesExecutions": {"view": True, "retry": False},
            # Collection permissions (view only)
            "collections": {
                "create": False,
                "view": True,
                "edit": False,
                "delete": False,
            },
            # Dashboard permissions (view only)
            "dashboard": {"view": True},
            # Collection types (view only - needed to view collections)
            "collection-types": {"view": True},
            # System permissions (read-only for app initialization)
            "system": {
                "view": True,
                "edit": False,
            },
            # Top-level resource permissions (required by custom authorizer)
            # Connectors (view only - needed to browse assets on the assets page)
            "connectors": {
                "view": True,
            },
            "nodes": {
                "view": True,
            },
            "regions": {
                "view": True,
            },
            "storage": {
                "view": True,
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


def seed_permission_set(
    permission_set: Dict[str, Any], force_update: bool = False
) -> bool:
    """
    Seed a permission set into the DynamoDB authorization table.

    Args:
        permission_set: Permission set definition
        force_update: If True, update existing system permission sets

    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize DynamoDB table
        table = dynamodb.Table(AUTH_TABLE_NAME)

        # Generate timestamps
        current_time = datetime.datetime.now().isoformat()

        # Check if the permission set already exists
        pk = f"{PREFIX_PERMISSION_SET}{permission_set['id']}"
        response = table.get_item(Key={"PK": pk, "SK": PREFIX_METADATA})

        if "Item" in response:
            existing_item = response["Item"]

            # Only update if it's a system permission set and force_update is True
            if force_update and permission_set.get("isSystem", False):
                logger.info(
                    f"Force updating system permission set {permission_set['id']}"
                )

                # Preserve original creation time
                created_at = existing_item.get("createdAt", current_time)

                # Prepare updated DynamoDB item
                item = {
                    "PK": pk,
                    "SK": PREFIX_METADATA,
                    "name": permission_set["name"],
                    "description": permission_set["description"],
                    "isSystem": permission_set["isSystem"],
                    "permissions": permission_set["permissions"],
                    "createdAt": created_at,
                    "updatedAt": current_time,
                }

                # Add effectiveRole if present
                if "effectiveRole" in permission_set:
                    item["effectiveRole"] = permission_set["effectiveRole"]

                # Update the item
                table.put_item(Item=item)
                logger.info(
                    f"Successfully updated system permission set {permission_set['id']}"
                )
            else:
                logger.info(
                    f"Permission set {permission_set['id']} already exists, skipping to preserve existing data"
                )
            return True
        else:
            logger.info(f"Creating permission set {permission_set['id']}")

            # Prepare DynamoDB item
            item = {
                "PK": pk,
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

    # Must run before seeding, which creates the groups used to tell a fresh
    # deployment from an existing one.
    ensure_auth_behavior_version()

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
        if seed_permission_set(permission_set, force_update=False):
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
    logger.info("Creating default groups and permission sets")

    # Also run on update, so deployments that predate this marker get one. They
    # already have the built-in groups, so they are correctly recorded as legacy.
    ensure_auth_behavior_version()

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

    # Then seed permission sets with force update for system permission sets
    ps_success_count = 0
    ps_failure_count = 0

    for permission_set in DEFAULT_PERMISSION_SETS:
        # Force update system permission sets on updates to ensure they have latest permissions
        if seed_permission_set(permission_set, force_update=True):
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

    # logger.info("Update operation - skipping seeding to preserve existing data")
    # # For updates, we skip seeding to avoid overwriting existing custom groups,
    # # permission sets, and user assignments that may have been created after initial deployment
    # logger.info("No action taken on UPDATE event to preserve user customizations")


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
