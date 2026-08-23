"""
Pre-Token Generation Lambda for Media Lake.

This Lambda function is triggered during the Cognito token generation process
and inserts custom claims (e.g., group memberships, permissions) into the ID token.

It dynamically looks up user permissions from the DynamoDB authorization table
based on both direct user permission assignments and group memberships.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError
from lambda_middleware import is_lambda_warmer_event

logger = Logger()

# Initialize clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
AUTH_TABLE_NAME = os.environ.get("AUTH_TABLE_NAME")

auth_table = dynamodb.Table(AUTH_TABLE_NAME)


def get_user_groups(user_id: str, cognito_groups: List[str] = None) -> List[str]:
    """
    Get all groups the user belongs to.

    Cognito group membership is the single source of truth. It is written by the
    users API (POST/PUT /users) and, for first-time federated users, by the
    just-in-time provisioning below.

    This previously also queried the authorization table for
    ``PK=USER#{sub}, SK begins_with MEMBERSHIP#`` rows and merged them in. That
    query was removed because it could never contribute anything: the only writer
    stored the sort key as ``MEMBERSHIP#GROUP#{id}``, so stripping ``MEMBERSHIP#``
    yielded ``GROUP#{id}``, which was then looked up as ``PK=GROUP#GROUP#{id}``
    and never matched. Keeping it would also have invited divergence, since the
    users API maintains only Cognito membership -- a stale row would have gone on
    granting a group the user had been moved out of.

    Args:
        user_id: The user's ID (sub)
        cognito_groups: List of groups from the Cognito token

    Returns:
        List of group IDs the user belongs to
    """
    return list(dict.fromkeys(cognito_groups or []))


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
            # A node can mix boolean actions with nested resources
            # (e.g. {"settings": {"view": true, "users": {...}}}), so every
            # child is examined individually rather than classifying the whole
            # node as either an actions dict or a nested resource.
            for child_key, child_value in value.items():
                if isinstance(child_value, bool):
                    if child_value:
                        flattened.append(f"{current_key}:{child_key}")
                elif isinstance(child_value, dict):
                    flattened.extend(
                        _flatten_nested_permissions(
                            {child_key: child_value}, current_key
                        )
                    )

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


# ─────────────────────────────────────────────────────────────────────────────
# Just-in-time (JIT) provisioning for federated users
#
# The first time a user signs in through an external identity provider, Cognito
# creates their profile but puts them in no groups, so their very first token
# would carry no permissions and every API call would be denied until an
# administrator intervened.
#
# This section assigns a default group during that first sign-in. Two properties
# matter:
#
#   1. The group is added to the in-memory group list for *this* invocation, so
#      the first token already carries the right permissions.
#   2. It happens exactly once per user. A sentinel record records that the
#      default has been applied, so an administrator who later moves the user to
#      a different group -- or removes every group to revoke access -- is never
#      overridden by a subsequent sign-in.
# ─────────────────────────────────────────────────────────────────────────────

SENTINEL_SK = "JIT_PROVISIONED"

# ─────────────────────────────────────────────────────────────────────────────
# Auth behavior version
#
# Written once per deployment by the auth seeder. Version 1 preserves the exact
# token output this Lambda produced before the group-claim correction below;
# version 2 applies the correction. New deployments get version 2 automatically.
# See lambdas/auth/auth_seeder/index.py for how the value is decided.
# ─────────────────────────────────────────────────────────────────────────────
PK_AUTH_CONFIG = "CONFIG#AUTH"
AUTH_BEHAVIOR_VERSION_LEGACY = 1
AUTH_BEHAVIOR_VERSION_CURRENT = 2

_behavior_cache: Dict[str, Any] = {"expires_at": 0.0, "value": None}


def get_auth_behavior_version() -> int:
    """Read the deployment's auth behavior version, cached briefly.

    Defaults to legacy whenever the marker is missing or unreadable, so an
    unseeded or degraded deployment can never have its token output change
    unexpectedly.
    """
    now = time.monotonic()
    if _behavior_cache["value"] is not None and now < _behavior_cache["expires_at"]:
        return _behavior_cache["value"]

    version = AUTH_BEHAVIOR_VERSION_LEGACY
    try:
        item = auth_table.get_item(Key={"PK": PK_AUTH_CONFIG, "SK": "METADATA"}).get(
            "Item"
        )
        if item and item.get("authBehaviorVersion") is not None:
            version = int(item["authBehaviorVersion"])
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Could not read auth behavior version, assuming legacy: {str(e)}"
        )

    _behavior_cache["value"] = version
    _behavior_cache["expires_at"] = now + POLICY_CACHE_TTL_SECONDS
    return version


# Trigger sources where provisioning should not run. A refresh always follows an
# initial authentication that already provisioned the user, so doing the work
# again would only add latency.
SKIP_TRIGGER_SOURCES = frozenset({"TokenGeneration_RefreshTokens"})

# How long a resolved policy is reused within a warm execution environment.
POLICY_CACHE_TTL_SECONDS = 60

_policy_cache: Dict[str, Any] = {"expires_at": 0.0, "value": None}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_json_dict(name: str) -> Dict[str, str]:
    raw = os.environ.get(name)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning(f"{name} is not valid JSON; ignoring")
        return {}
    if not isinstance(parsed, dict):
        logger.warning(f"{name} is not a JSON object; ignoring")
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


JIT_ENABLED = _env_flag("JIT_PROVISIONING_ENABLED", False)
JIT_DEFAULT_GROUP_FALLBACK = os.environ.get("JIT_DEFAULT_GROUP") or "read-only"
JIT_ALLOW_IDP_GROUP_ASSERTIONS = _env_flag("JIT_ALLOW_IDP_GROUP_ASSERTIONS", False)
JIT_IDP_GROUP_MAPPING = _env_json_dict("JIT_IDP_GROUP_MAPPING")
SYSTEM_SETTINGS_TABLE_NAME = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")

# Created lazily so that deployments with the feature disabled never pay the
# client construction cost.
_cognito_idp_client = None


def _cognito_idp():
    global _cognito_idp_client
    if _cognito_idp_client is None:
        _cognito_idp_client = boto3.client("cognito-idp")
    return _cognito_idp_client


def is_federated_user(user_attributes: Dict[str, Any]) -> bool:
    """Whether this profile was created by signing in through an external IdP.

    Cognito records federated origins in the ``identities`` attribute and marks
    such profiles ``EXTERNAL_PROVIDER``. Locally created users (the initial
    administrator, anyone added through the users API) match neither, which is
    what keeps JIT provisioning away from them.
    """
    status = user_attributes.get("cognito:user_status")
    if isinstance(status, str) and status.upper() == "EXTERNAL_PROVIDER":
        return True

    identities = user_attributes.get("identities")
    if not identities:
        return False
    if isinstance(identities, list):
        return len(identities) > 0
    if isinstance(identities, str):
        try:
            parsed = json.loads(identities)
        except (TypeError, ValueError):
            # A non-empty, unparseable value still indicates a linked identity.
            return bool(identities.strip())
        if isinstance(parsed, list):
            return len(parsed) > 0
        return bool(parsed)
    return False


def get_jit_policy() -> Dict[str, Any]:
    """Resolve the runtime JIT policy, preferring the administrator's setting.

    Falls back to the deploy-time default when the settings record is missing so
    the feature behaves predictably before anyone visits the settings page.
    Cached briefly because this runs on the token path.
    """
    now = time.monotonic()
    if _policy_cache["value"] is not None and now < _policy_cache["expires_at"]:
        return _policy_cache["value"]

    policy = {"enabled": True, "default_group": JIT_DEFAULT_GROUP_FALLBACK}

    if SYSTEM_SETTINGS_TABLE_NAME:
        try:
            settings_table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
            response = settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "JIT_PROVISIONING"}
            )
            item = response.get("Item")
            if item:
                stored_enabled = item.get("enabled")
                if stored_enabled is not None:
                    policy["enabled"] = bool(stored_enabled)
                stored_group = item.get("defaultGroupId")
                if stored_group:
                    policy["default_group"] = str(stored_group)
        except Exception as e:  # noqa: BLE001
            # Fall back to the deploy-time default rather than denying the user
            # a usable token.
            logger.warning(f"Could not read JIT provisioning settings: {str(e)}")

    _policy_cache["value"] = policy
    _policy_cache["expires_at"] = now + POLICY_CACHE_TTL_SECONDS
    return policy


def has_been_jit_provisioned(user_id: str) -> bool:
    """Whether the default group has already been applied to this user."""
    try:
        response = auth_table.get_item(Key={"PK": f"USER#{user_id}", "SK": SENTINEL_SK})
        return "Item" in response
    except Exception as e:  # noqa: BLE001
        # Fail closed: if we cannot tell, assume already provisioned so that a
        # transient read error can never re-apply a default group over an
        # administrator's decision.
        logger.warning(
            f"Could not read JIT sentinel for {user_id}, skipping provisioning: {str(e)}"
        )
        return True


def mark_jit_provisioned(user_id: str, groups_applied: List[str]) -> None:
    """Record that provisioning has run so it never runs again for this user."""
    try:
        auth_table.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": SENTINEL_SK,
                "type": "JIT_PROVISIONING_RECORD",
                "userId": user_id,
                "groupsApplied": groups_applied,
                "provisionedAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # A concurrent sign-in won the race. Group assignment is idempotent,
            # so there is nothing to repair.
            logger.info(f"JIT sentinel already present for {user_id}")
            return
        logger.warning(f"Could not write JIT sentinel for {user_id}: {str(e)}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not write JIT sentinel for {user_id}: {str(e)}")


def group_exists(group_id: str) -> bool:
    """Whether a group record exists, so permissions can actually resolve."""
    try:
        response = auth_table.get_item(
            Key={"PK": f"GROUP#{group_id}", "SK": "METADATA"}
        )
        return "Item" in response
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not verify group {group_id}: {str(e)}")
        return False


def add_user_to_cognito_group(username: str, group_id: str) -> bool:
    """Add the user to a Cognito group. Idempotent; never raises."""
    if not COGNITO_USER_POOL_ID:
        logger.warning("COGNITO_USER_POOL_ID not configured; cannot assign group")
        return False
    try:
        _cognito_idp().admin_add_user_to_group(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            GroupName=group_id,
        )
        logger.info(f"Added {username} to Cognito group {group_id}")
        return True
    except Exception as e:  # noqa: BLE001
        # Never break sign-in over this. The group is still applied to the
        # current token in memory; only durability is lost.
        logger.error(f"Could not add {username} to Cognito group {group_id}: {str(e)}")
        return False


def resolve_idp_asserted_groups(user_attributes: Dict[str, Any]) -> List[str]:
    """Map groups asserted by the identity provider to MediaLake group ids.

    Assertions are only honoured through the explicit mapping, which acts as the
    allowlist. An IdP that can assert arbitrary group names must never be able
    to name a MediaLake group directly -- that would be a privilege-escalation
    path -- and every mapped id is additionally checked for existence.
    """
    if not JIT_ALLOW_IDP_GROUP_ASSERTIONS or not JIT_IDP_GROUP_MAPPING:
        return []

    raw = user_attributes.get("custom:groups")
    if not raw:
        return []

    asserted: List[str] = []
    if isinstance(raw, list):
        asserted = [str(v) for v in raw]
    elif isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    asserted = [str(v) for v in parsed]
            except (TypeError, ValueError):
                asserted = []
        if not asserted:
            # Comma-separated is the shape Cognito attribute mapping produces.
            asserted = [part.strip().strip("'\"") for part in text.split(",")]

    resolved: List[str] = []
    for name in asserted:
        if not name:
            continue
        group_id = JIT_IDP_GROUP_MAPPING.get(name)
        if not group_id:
            logger.info(f"Ignoring unmapped IdP group assertion: {name}")
            continue
        if group_id in resolved:
            continue
        if not group_exists(group_id):
            logger.warning(
                f"IdP group '{name}' maps to '{group_id}', which has no group record; ignoring"
            )
            continue
        resolved.append(group_id)

    return resolved


def apply_jit_provisioning(
    event: Dict[str, Any],
    user_id: str,
    existing_groups: List[str],
) -> List[str]:
    """Assign groups to a first-time federated user.

    Returns the group ids to add to this token. An empty list means nothing was
    applied, for any reason -- disabled, not federated, already provisioned, or
    the user already has groups.
    """
    if not JIT_ENABLED:
        return []

    trigger_source = event.get("triggerSource")
    if trigger_source in SKIP_TRIGGER_SOURCES:
        return []

    user_attributes = event.get("request", {}).get("userAttributes", {})
    if not is_federated_user(user_attributes):
        # Locally created users are provisioned by the admin flows.
        return []

    if existing_groups:
        # Already has group membership from any source; nothing to seed.
        return []

    if has_been_jit_provisioned(user_id):
        logger.info(
            f"User {user_id} was already provisioned; not re-applying a default group"
        )
        return []

    policy = get_jit_policy()
    if not policy.get("enabled", True):
        logger.info("JIT provisioning is disabled in system settings")
        return []

    groups_to_apply = resolve_idp_asserted_groups(user_attributes)
    source = "idp-assertion"

    if not groups_to_apply:
        default_group = policy.get("default_group") or JIT_DEFAULT_GROUP_FALLBACK
        if not group_exists(default_group):
            logger.error(
                f"JIT default group '{default_group}' has no group record; "
                "cannot provision. Check the default group in System Settings."
            )
            return []
        groups_to_apply = [default_group]
        source = "default-group"

    username = event.get("userName") or user_id

    applied: List[str] = []
    durable: List[str] = []
    for group_id in groups_to_apply:
        # Applied to this token either way: if the durable Cognito assignment
        # failed we still want the first session to work. Durability is tracked
        # separately so the sentinel below is only written after a successful
        # assignment and a failed one is retried on the next sign-in.
        if add_user_to_cognito_group(username, group_id):
            durable.append(group_id)
        applied.append(group_id)

    if durable:
        # Written last: if every group assignment failed we would rather retry
        # on the next sign-in than permanently mark the user as provisioned.
        mark_jit_provisioned(user_id, durable)
    else:
        logger.error(
            "No durable group assignment succeeded; leaving user unprovisioned "
            "so the next sign-in retries",
            extra={"user_id": user_id, "groups": groups_to_apply},
        )

    logger.info(
        "JIT provisioning applied",
        extra={
            "user_id": user_id,
            "groups": applied,
            "source": source,
            "trigger_source": trigger_source,
        },
    )
    return applied


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

        # Just-in-time provisioning for first-time federated users. Runs only
        # when the user resolved to no groups at all, and applies at most once
        # per user. Any failure inside is swallowed so sign-in cannot break.
        try:
            jit_groups = apply_jit_provisioning(event, user_id, groups)
            if jit_groups:
                # Added in-memory as well as in Cognito so that this very first
                # token already carries the resulting permissions.
                groups = list(dict.fromkeys(groups + jit_groups))
                logger.info(f"Groups after JIT provisioning: {groups}")
        except Exception as e:
            logger.error(f"JIT provisioning failed, continuing without it: {str(e)}")

        # Which set of claim-shaping behaviors this deployment uses.
        behavior_version = get_auth_behavior_version()

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

            if behavior_version >= AUTH_BEHAVIOR_VERSION_CURRENT:
                # cognito:groups is a reserved claim. Cognito only accepts it
                # through groupOverrideDetails; setting it in
                # claimsToAddOrOverride (as version 1 does) has no effect on the
                # issued token.
                event["response"]["claimsAndScopeOverrideDetails"][
                    "groupOverrideDetails"
                ] = {"groupsToOverride": groups}
            else:
                # Legacy: preserve the exact output produced before the
                # correction, even though Cognito ignores this claim.
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

            if behavior_version >= AUTH_BEHAVIOR_VERSION_CURRENT:
                # Same reserved-claim rule applies to version 1 events, where
                # groupOverrideDetails sits under claimsOverrideDetails.
                event["response"]["claimsOverrideDetails"]["groupOverrideDetails"] = {
                    "groupsToOverride": groups
                }
            else:
                # Legacy: preserve the exact output produced before the correction.
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
