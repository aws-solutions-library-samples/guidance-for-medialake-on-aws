"""Handler for PUT /settings/system/jit-provisioning endpoint.

Updates the just-in-time (JIT) provisioning policy applied to users arriving
from an external identity provider.

The chosen group is validated against the Cognito user pool rather than trusted
blindly: assigning a group that does not exist in the pool would make
``AdminAddUserToGroup`` fail *inside the sign-in path*, which is a far worse
failure mode than rejecting the save here.
"""

import os
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    ServiceError,
)
from boto3.dynamodb.conditions import Attr
from jit_provisioning_get import (
    SETTINGS_PK,
    SETTINGS_SK,
    _env_flag,
    build_response_payload,
)

logger = Logger(child=True)
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
cognito_idp = boto3.client("cognito-idp")

# Groups that grant full administrative access. Selecting one as the JIT default
# would silently make every federated user an administrator, so it requires the
# deployment to opt in explicitly.
PRIVILEGED_GROUP_IDS = frozenset({"superAdministrators"})


def _list_cognito_group_names(user_pool_id: str) -> list[str]:
    """Return every group name in the user pool, following pagination."""
    names: list[str] = []
    next_token = None
    while True:
        kwargs = {"UserPoolId": user_pool_id, "Limit": 60}
        if next_token:
            kwargs["NextToken"] = next_token
        response = cognito_idp.list_groups(**kwargs)
        names.extend(
            group["GroupName"]
            for group in response.get("Groups", [])
            if group.get("GroupName")
        )
        next_token = response.get("NextToken")
        if not next_token:
            return names


def _get_actor(app) -> str:
    """Best-effort identity of the caller, for the audit attribute."""
    try:
        authorizer = app.current_event.raw_event.get("requestContext", {}).get(
            "authorizer", {}
        )
        claims = authorizer.get("claims") or {}
        return (
            claims.get("email")
            or claims.get("cognito:username")
            or claims.get("sub")
            or authorizer.get("userId")
            or "unknown"
        )
    except Exception:  # noqa: BLE001 - never fail a save over audit metadata
        return "unknown"


def _get_actor_sub(app) -> str:
    """Caller's Cognito sub for log correlation (avoids emailing PII to logs)."""
    try:
        authorizer = app.current_event.raw_event.get("requestContext", {}).get(
            "authorizer", {}
        )
        claims = authorizer.get("claims") or {}
        return claims.get("sub") or authorizer.get("userId") or "unknown"
    except Exception:  # noqa: BLE001 - never fail a save over audit metadata
        return "unknown"


def register_route(app):
    """Register PUT /settings/system/jit-provisioning route"""

    @app.put("/settings/system/jit-provisioning")
    @tracer.capture_method
    def settings_system_jit_provisioning_put():
        """Update the JIT provisioning policy for federated users"""
        try:
            body = app.current_event.json_body
        except Exception:
            raise BadRequestError("Request body must be valid JSON")

        if not isinstance(body, dict):
            raise BadRequestError("Request body must be a JSON object")

        enabled = body.get("enabled", False)
        if not isinstance(enabled, bool):
            raise BadRequestError("'enabled' must be a boolean")

        default_group_id = body.get("defaultGroupId") or ""
        if not isinstance(default_group_id, str):
            raise BadRequestError("'defaultGroupId' must be a string")
        default_group_id = default_group_id.strip()

        # A group is only mandatory when provisioning is switched on; saving a
        # disabled policy with no group selected must be possible (it is the
        # initial state).
        if enabled and not default_group_id:
            raise BadRequestError(
                "'defaultGroupId' must be a non-empty string when provisioning is enabled"
            )

        expected_updated_at = body.get("expectedUpdatedAt")
        if expected_updated_at is not None and not isinstance(expected_updated_at, str):
            raise BadRequestError("'expectedUpdatedAt' must be a string when provided")

        if default_group_id in PRIVILEGED_GROUP_IDS and not _env_flag(
            "JIT_ALLOW_PRIVILEGED_DEFAULT_GROUP", False
        ):
            raise BadRequestError(
                f"'{default_group_id}' grants full administrative access and cannot be used "
                "as the default group for just-in-time provisioning. This deployment was not "
                "configured to allow it. Choose a lower-privilege group, or set "
                "authZ.jit_provisioning.allow_privileged_default_group in the deployment "
                "configuration if this is genuinely intended."
            )

        table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
        if not table_name:
            logger.error("SYSTEM_SETTINGS_TABLE_NAME environment variable not set")
            raise InternalServerError(
                "SYSTEM_SETTINGS_TABLE_NAME environment variable is not configured"
            )

        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
        if not user_pool_id:
            logger.error("COGNITO_USER_POOL_ID environment variable not set")
            raise InternalServerError(
                "COGNITO_USER_POOL_ID environment variable is not configured"
            )

        # Validate against the pool so a bad value can never reach the sign-in
        # path. Skipped when no group is set (only possible while disabled).
        if default_group_id:
            try:
                group_names = _list_cognito_group_names(user_pool_id)
            except Exception:
                logger.exception("Unable to list Cognito groups for validation")
                raise InternalServerError(
                    "Unable to verify the selected group against the user pool"
                )

            if default_group_id not in group_names:
                raise BadRequestError(
                    f"Group '{default_group_id}' does not exist in the Cognito user pool, so "
                    "users could not be assigned to it during sign-in. Available groups: "
                    f"{', '.join(sorted(group_names)) or 'none'}."
                )

        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        item = {
            "PK": SETTINGS_PK,
            "SK": SETTINGS_SK,
            "enabled": enabled,
            "defaultGroupId": default_group_id,
            "updatedAt": updated_at,
            "updatedBy": _get_actor(app),
        }

        put_kwargs = {"Item": item}
        if expected_updated_at is not None:
            # Only overwrite when the stored version matches what the caller read.
            put_kwargs["ConditionExpression"] = Attr("updatedAt").eq(
                expected_updated_at
            )

        try:
            table = dynamodb.Table(table_name)
            try:
                table.put_item(**put_kwargs)
            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                raise ServiceError(
                    status_code=409,
                    msg=(
                        "Conflict: the just-in-time provisioning settings were modified by "
                        "another user. Please refresh and try again."
                    ),
                )
        except ServiceError:
            raise
        except Exception:
            logger.exception("Error saving JIT provisioning settings")
            raise InternalServerError("Error saving JIT provisioning settings")

        logger.info(
            "JIT provisioning settings updated",
            extra={
                "enabled": enabled,
                "default_group_id": default_group_id,
                # Sub, not email: keep PII out of CloudWatch. The human-readable
                # identity is preserved in the DynamoDB item's updatedBy.
                "updated_by_sub": _get_actor_sub(app),
            },
        )

        return {"status": "success", "data": build_response_payload(item)}
