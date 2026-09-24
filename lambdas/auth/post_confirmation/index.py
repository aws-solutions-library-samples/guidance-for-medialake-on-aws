"""Post confirmation Lambda trigger for Media Lake.

Assigns a default Cognito group to a user the first time they sign in through
an external (SAML/OIDC) identity provider.

Why this trigger
----------------
For a federated user, Cognito invokes the post confirmation trigger with
``triggerSource == "PostConfirmation_ConfirmSignUp"`` exactly once: on the
first sign-in, right after it has created the user's profile. Subsequent
federated sign-ins invoke pre/post *authentication* instead. So "applied once
per user" is a property of the trigger itself, not something this function has
to enforce with a marker record, and an administrator who later moves the user
to a different group -- or removes every group to revoke access -- is never
overridden by a later sign-in.

The profile already exists when this runs, so ``AdminAddUserToGroup`` works.
(It would not from pre sign-up, which runs before the profile is created.)

Which group
-----------
1. When IdP group assertions are enabled, groups asserted by the identity
   provider are honoured -- but only through the configured mapping, which is
   the allowlist. An identity provider must never be able to name a Media Lake
   group directly.
2. Otherwise, or when no asserted group could be assigned, the default group.
   An administrator chooses it in System Settings (``PK=SYSTEM_SETTINGS``,
   ``SK=JIT_PROVISIONING``); the ``JIT_DEFAULT_GROUP`` environment variable is
   the deploy-time fallback used until that record exists.

Failure policy
--------------
This function never raises. An exception here fails the sign-in, and for a
federated first sign-in that can lock the user out entirely, which is far worse
than a missing default group. Because the trigger only fires once, a failed
assignment is *not* retried automatically: it is logged as an error and counted
in the ``DefaultGroupAssignmentFailed`` metric so an administrator can assign
the group by hand.
"""

import json
import os
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
metrics = Metrics(namespace="MediaLake/Auth", service="post_confirmation")

FIRST_SIGN_IN_TRIGGER = "PostConfirmation_ConfirmSignUp"

SETTINGS_PK = "SYSTEM_SETTINGS"
SETTINGS_SK = "JIT_PROVISIONING"


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


DEFAULT_GROUP_FALLBACK = os.environ.get("JIT_DEFAULT_GROUP") or "read-only"
SYSTEM_SETTINGS_TABLE_NAME = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
ALLOW_IDP_GROUP_ASSERTIONS = _env_flag("JIT_ALLOW_IDP_GROUP_ASSERTIONS", False)
# IdP-asserted group name -> Media Lake group id. Doubles as the allowlist.
IDP_GROUP_MAPPING = _env_json_dict("JIT_IDP_GROUP_MAPPING")
# True when the inbound federation trigger is attached. That trigger has already
# translated the assertion through IDP_GROUP_MAPPING, so custom:groups then
# carries Media Lake group ids rather than the provider's own names.
GROUPS_PRE_MAPPED = _env_flag("JIT_GROUPS_PRE_MAPPED", False)

dynamodb = boto3.resource("dynamodb")
cognito_idp = boto3.client("cognito-idp")


def is_federated_user(user_attributes: Dict[str, Any]) -> bool:
    """Whether this profile was created by signing in through an external IdP.

    Cognito marks such profiles ``EXTERNAL_PROVIDER`` and records the linked
    provider in ``identities``. Locally created users -- the initial
    administrator, anyone added through the users API -- match neither; they
    are placed in groups by the admin flows, so this trigger leaves them alone.
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


def get_policy() -> Dict[str, Any]:
    """Resolve the administrator's setting, falling back to the deploy default.

    A read failure falls back to the deploy-time default rather than skipping
    the assignment, because this trigger only gets one chance per user.
    """
    policy = {"enabled": True, "default_group": DEFAULT_GROUP_FALLBACK}
    if not SYSTEM_SETTINGS_TABLE_NAME:
        return policy

    try:
        item = (
            dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
            .get_item(Key={"PK": SETTINGS_PK, "SK": SETTINGS_SK})
            .get("Item")
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not read default group settings: {str(e)}")
        return policy

    if item:
        if item.get("enabled") is not None:
            policy["enabled"] = bool(item["enabled"])
        if item.get("defaultGroupId"):
            policy["default_group"] = str(item["defaultGroupId"])
    return policy


def _parse_group_list(raw: Any) -> List[str]:
    """Turn a custom:groups value into a list of names.

    Cognito attribute mapping produces a comma-separated string; some providers
    send a JSON array instead.
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if str(v).strip()]
    text = str(raw).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except (TypeError, ValueError):
            pass
    return [
        part.strip().strip("'\"")
        for part in text.split(",")
        if part.strip().strip("'\"")
    ]


def resolve_asserted_groups(user_attributes: Dict[str, Any]) -> List[str]:
    """Media Lake group ids the identity provider asserted, via the allowlist."""
    if not ALLOW_IDP_GROUP_ASSERTIONS or not IDP_GROUP_MAPPING:
        return []

    allowed_ids = set(IDP_GROUP_MAPPING.values())
    resolved: List[str] = []
    for name in _parse_group_list(user_attributes.get("custom:groups")):
        group_id = IDP_GROUP_MAPPING.get(name)
        if not group_id and GROUPS_PRE_MAPPED and name in allowed_ids:
            # Already translated by the inbound federation trigger.
            group_id = name
        if not group_id:
            logger.info(f"Ignoring unmapped IdP group assertion: {name}")
            continue
        if group_id not in resolved:
            resolved.append(group_id)
    return resolved


def add_to_group(user_pool_id: str, username: str, group_id: str) -> bool:
    """Add the user to a Cognito group. Idempotent; never raises."""
    try:
        cognito_idp.admin_add_user_to_group(
            UserPoolId=user_pool_id, Username=username, GroupName=group_id
        )
        logger.info(f"Added {username} to group {group_id}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Could not add {username} to group {group_id}: {str(e)}")
        return False


def assign_default_group(event: Dict[str, Any]) -> List[str]:
    """Assign groups to a first-time federated user. Returns the groups added."""
    if event.get("triggerSource") != FIRST_SIGN_IN_TRIGGER:
        # PostConfirmation_ConfirmForgotPassword fires for local users resetting
        # a password; it must never change group membership.
        return []

    user_attributes = (event.get("request") or {}).get("userAttributes") or {}
    if not is_federated_user(user_attributes):
        return []

    user_pool_id = event.get("userPoolId")
    username = event.get("userName")
    if not user_pool_id or not username:
        logger.error("Event is missing userPoolId or userName; cannot assign")
        return []

    policy = get_policy()
    if not policy["enabled"]:
        logger.info("Default group assignment is disabled in System Settings")
        return []

    assigned: List[str] = []
    source = "idp-assertion"
    for group_id in resolve_asserted_groups(user_attributes):
        if add_to_group(user_pool_id, username, group_id):
            assigned.append(group_id)

    if not assigned:
        # Either nothing was asserted or none of it could be assigned (for
        # example a mapping that names a group missing from the pool). Fall back
        # rather than leave the user with no access at all.
        source = "default-group"
        default_group = policy["default_group"]
        if add_to_group(user_pool_id, username, default_group):
            assigned.append(default_group)

    if assigned:
        metrics.add_metric(name="DefaultGroupAssigned", unit=MetricUnit.Count, value=1)
        logger.info(
            "Assigned groups to first-time federated user",
            extra={
                "sub": user_attributes.get("sub"),
                "groups": assigned,
                "source": source,
            },
        )
    else:
        metrics.add_metric(
            name="DefaultGroupAssignmentFailed", unit=MetricUnit.Count, value=1
        )
        logger.error(
            "No group could be assigned to a first-time federated user. This "
            "trigger does not fire again for them, so assign a group manually.",
            extra={"sub": user_attributes.get("sub"), "username": username},
        )
    return assigned


@metrics.log_metrics
@logger.inject_lambda_context
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Cognito post confirmation trigger. Always returns the event unchanged."""
    try:
        assign_default_group(event)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Post confirmation trigger failed: {str(e)}")
    return event
