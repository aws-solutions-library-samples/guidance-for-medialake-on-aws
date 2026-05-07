"""
Pre-Token Generation Lambda for Media Lake.

This Lambda function is triggered during the Cognito token generation process
and inserts custom claims (e.g., group memberships, permissions) into the ID token.

It dynamically looks up user permissions from the DynamoDB authorization table
based on both direct user permission assignments and group memberships.
"""

import json
import os
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key
from lambda_middleware import is_lambda_warmer_event

logger = Logger()

# Initialize clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
AUTH_TABLE_NAME = os.environ.get("AUTH_TABLE_NAME")

auth_table = dynamodb.Table(AUTH_TABLE_NAME)


def get_user_groups(user_id: str, cognito_groups: List[str] = None) -> List[str]:
    """
    Get all groups the user belongs to, combining DynamoDB data and Cognito groups.

    Args:
        user_id: The user's ID (sub)
        cognito_groups: List of groups from Cognito token

    Returns:
        List of group IDs the user belongs to
    """
    groups = set(cognito_groups or [])

    try:
        # Query DynamoDB for user's group memberships
        # Format: PK=USER#{user_id}, SK begins_with(MEMBERSHIP#)
        response = auth_table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("MEMBERSHIP#")
        )

        # Extract group IDs from the query results
        for item in response.get("Items", []):
            # SK format is MEMBERSHIP#{group_id}
            sk = item.get("SK", "")
            if sk.startswith("MEMBERSHIP#"):
                group_id = sk[len("MEMBERSHIP#") :]
                groups.add(group_id)
                logger.info(f"Found group membership in DynamoDB: {group_id}")

    except Exception as e:
        logger.error(f"Error querying DynamoDB for user groups: {str(e)}")
        # Continue with existing groups rather than failing

    return list(groups)


def get_permission_set(permission_set_id: str) -> Dict[str, Any]:
    """
    Get a permission set by ID from the authorization table.

    Args:
        permission_set_id: The ID of the permission set

    Returns:
        Permission set object or None if not found
    """
    try:
        response = auth_table.get_item(
            Key={"PK": f"PS#{permission_set_id}", "SK": "METADATA"}
        )

        return response.get("Item")
    except Exception as e:
        logger.error(f"Error getting permission set {permission_set_id}: {str(e)}")
        return None


def get_group_permission_sets(group_id: str) -> List[str]:
    """
    Get permission sets assigned to a group.

    Args:
        group_id: The ID of the group

    Returns:
        List of permission set IDs assigned to the group
    """
    try:
        response = auth_table.get_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"}
        )

        group_item = response.get("Item", {})
        return group_item.get("assignedPermissionSets", [])
    except Exception as e:
        logger.error(f"Error getting permission sets for group {group_id}: {str(e)}")
        return []


def flatten_permissions(permissions) -> List[str]:
    """
    Flatten permissions into a list of permission strings.
    Handles both nested boolean format (system permission sets) and array format (API permission sets).

    Args:
        permissions: Either a nested dict with boolean values or a list of permission objects

    Returns:
        List of flattened permission strings (e.g., "users:edit", "pipelines:view")
    """
    flattened = []

    # Handle array format (API permission sets)
    if isinstance(permissions, list):
        for permission in permissions:
            if isinstance(permission, dict):
                action = permission.get("action")
                resource = permission.get("resource")
                effect = permission.get("effect", "Allow")

                # Only include permissions with Allow effect
                if action and resource and effect == "Allow":
                    flattened.append(f"{resource}:{action}")
        return flattened

    # Handle nested boolean format (system permission sets)
    if isinstance(permissions, dict):
        return _flatten_nested_permissions(permissions)

    return flattened


def _flatten_nested_permissions(
    permissions: Dict[str, Any], prefix: str = ""
) -> List[str]:
    """
    Helper function to flatten nested boolean permission structure.

    Args:
        permissions: Nested permissions object
        prefix: Current prefix for nested resources

    Returns:
        List of flattened permission strings
    """
    flattened = []

    for key, value in permissions.items():
        current_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            # Check if this dict contains boolean values (actions)
            has_boolean_values = any(isinstance(v, bool) for v in value.values())

            if has_boolean_values:
                # This is an actions dict, process the boolean permissions
                for action, allowed in value.items():
                    if isinstance(allowed, bool) and allowed:
                        flattened.append(f"{current_key}:{action}")
            else:
                # This is a nested resource, recurse deeper
                flattened.extend(_flatten_nested_permissions(value, current_key))

    return flattened


def get_user_permissions(user_id: str, groups: List[str]) -> List[str]:
    """
    Get all permissions for a user based on direct assignments and group memberships.

    Args:
        user_id: The user's ID (sub)
        groups: List of group IDs the user belongs to

    Returns:
        List of permission strings
    """
    all_permissions = set()
    permission_set_ids = set()

    # Get permission sets from groups
    for group_id in groups:
        group_permission_sets = get_group_permission_sets(group_id)
        permission_set_ids.update(group_permission_sets)
        logger.info(f"Group {group_id} has permission sets: {group_permission_sets}")

    # Get direct user permission sets (future enhancement)
    # This could query for user's directly assigned permission sets

    # Get and flatten all permission sets
    for ps_id in permission_set_ids:
        permission_set = get_permission_set(ps_id)
        if permission_set and "permissions" in permission_set:
            flattened = flatten_permissions(permission_set["permissions"])
            all_permissions.update(flattened)
            logger.info(f"Permission set {ps_id} adds permissions: {flattened}")

    return list(all_permissions)


@logger.inject_lambda_context
def handler(event, context):
    """
    Cognito Pre-Token Generation trigger to enrich JWT tokens with dynamic permissions
    """
    # Lambda warmer short-circuit
    if is_lambda_warmer_event(event):
        return {"warmed": True}
    try:
        logger.info("Cognito Pre-Token Generation Lambda invoked")

        # Check if this is a V2_0 event
        version = event.get("version", "1")
        logger.info(f"Pre Token Generation version: {version}")

        # Log the event structure for debugging
        logger.info(f"Event keys: {list(event.keys())}")
        logger.info(f"Request keys: {list(event.get('request', {}).keys())}")

        # Extract user information
        user_attributes = event.get("request", {}).get("userAttributes", {})
        # Use sub as the primary user identifier
        user_id = user_attributes.get("sub")

        if not user_id:
            logger.warning("No user ID found in the event")
            return event

        logger.info(f"Processing token for user: {user_id}")

        # Get groups from Cognito token
        cognito_groups = []
        group_config = event.get("request", {}).get("groupConfiguration", {})
        if group_config:
            cognito_groups = group_config.get("groupsToOverride", [])
            logger.info(
                f"Found {len(cognito_groups)} groups in Cognito token: {cognito_groups}"
            )

        # Get all user groups (combining DynamoDB and Cognito)
        groups = get_user_groups(user_id, cognito_groups)
        logger.info(f"Combined user groups: {groups}")

        # Get user permissions based on groups
        try:
            permissions = get_user_permissions(user_id, groups)
            logger.info(f"Retrieved {len(permissions)} permissions for user")
        except Exception as e:
            logger.error(f"Error getting user permissions: {str(e)}")
            # Use empty permissions list if lookup fails
            permissions = []

        # Add custom claims to the token based on version
        if version in ["2", "3"]:
            # V2_0/V3 format
            # Initialize claimsAndScopeOverrideDetails if it's null or doesn't exist
            if event["response"].get("claimsAndScopeOverrideDetails") is None:
                event["response"]["claimsAndScopeOverrideDetails"] = {}

            if (
                "idTokenGeneration"
                not in event["response"]["claimsAndScopeOverrideDetails"]
            ):
                event["response"]["claimsAndScopeOverrideDetails"][
                    "idTokenGeneration"
                ] = {}

            if (
                "claimsToAddOrOverride"
                not in event["response"]["claimsAndScopeOverrideDetails"][
                    "idTokenGeneration"
                ]
            ):
                event["response"]["claimsAndScopeOverrideDetails"]["idTokenGeneration"][
                    "claimsToAddOrOverride"
                ] = {}

            claims = event["response"]["claimsAndScopeOverrideDetails"][
                "idTokenGeneration"
            ]["claimsToAddOrOverride"]

            # Add groups claim with the list of group IDs
            if groups:
                claims["cognito:groups"] = groups

            # Add custom permissions claim with dynamically retrieved permissions
            # Custom claims should use string values in V2
            claims["custom:permissions"] = json.dumps(permissions)

            # Also add to access token if needed
            if (
                "accessTokenGeneration"
                not in event["response"]["claimsAndScopeOverrideDetails"]
            ):
                event["response"]["claimsAndScopeOverrideDetails"][
                    "accessTokenGeneration"
                ] = {}

            if (
                "claimsToAddOrOverride"
                not in event["response"]["claimsAndScopeOverrideDetails"][
                    "accessTokenGeneration"
                ]
            ):
                event["response"]["claimsAndScopeOverrideDetails"][
                    "accessTokenGeneration"
                ]["claimsToAddOrOverride"] = {}

            access_claims = event["response"]["claimsAndScopeOverrideDetails"][
                "accessTokenGeneration"
            ]["claimsToAddOrOverride"]
            access_claims["custom:permissions"] = json.dumps(permissions)

        else:
            # V1 format (legacy)
            if "claimsOverrideDetails" not in event["response"]:
                event["response"]["claimsOverrideDetails"] = {}

            if (
                "claimsToAddOrOverride"
                not in event["response"]["claimsOverrideDetails"]
            ):
                event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] = {}

            # Add groups claim with the list of group IDs
            if groups:
                event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"][
                    "cognito:groups"
                ] = groups

            # Add custom permissions claim with dynamically retrieved permissions
            event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"][
                "custom:permissions"
            ] = json.dumps(permissions)

        logger.info(f"Added groups claim with {len(groups)} groups")
        logger.info(
            f"Added custom:permissions claim with {len(permissions)} permissions"
        )

        # Log the response structure for debugging
        logger.info(
            f"Final response structure: {json.dumps(event.get('response', {}))}"
        )

        # For V2/V3, we should only have claimsAndScopeOverrideDetails
        if version in ["2", "3"] and "claimsOverrideDetails" in event["response"]:
            logger.warning("Removing claimsOverrideDetails from V2/V3 response")
            del event["response"]["claimsOverrideDetails"]

    except Exception as e:
        # Catch all exceptions to ensure token generation doesn't fail
        logger.error(f"Unexpected error in pre-token generation Lambda: {str(e)}")
        # Don't modify the event if we encounter an error

    return event
