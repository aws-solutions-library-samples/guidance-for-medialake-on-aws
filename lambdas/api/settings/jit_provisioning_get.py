"""Handler for GET /settings/system/jit-provisioning endpoint.

Returns the just-in-time (JIT) provisioning policy for users arriving from an
external identity provider. The policy is stored as a single system-settings
record; when it is absent the deploy-time defaults supplied through environment
variables are returned so the UI always has something coherent to show.
"""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.exceptions import InternalServerError

logger = Logger(child=True)
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")

SETTINGS_PK = "SYSTEM_SETTINGS"
SETTINGS_SK = "JIT_PROVISIONING"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def build_response_payload(item: dict | None) -> dict:
    """Merge the stored record with the deploy-time defaults.

    ``capabilityEnabled`` reflects whether the deployment was synthesized with
    JIT provisioning turned on. When it is false the feature cannot run no
    matter what the stored record says, because the Cognito trigger has not been
    granted the permissions it needs. The UI uses this to explain that a
    redeploy is required.
    """
    capability_enabled = _env_flag("JIT_PROVISIONING_ENABLED", False)
    default_group_fallback = os.environ.get("JIT_DEFAULT_GROUP") or "read-only"

    if not item:
        return {
            "enabled": capability_enabled,
            "defaultGroupId": default_group_fallback,
            "capabilityEnabled": capability_enabled,
            "updatedAt": None,
            "updatedBy": None,
            "isDefault": True,
        }

    stored_enabled = item.get("enabled")
    return {
        # A stored record wins, but it can never enable the feature when the
        # deployment does not support it.
        "enabled": bool(
            stored_enabled if stored_enabled is not None else capability_enabled
        )
        and capability_enabled,
        "defaultGroupId": item.get("defaultGroupId") or default_group_fallback,
        "capabilityEnabled": capability_enabled,
        "updatedAt": item.get("updatedAt"),
        "updatedBy": item.get("updatedBy"),
        "isDefault": False,
    }


def register_route(app):
    """Register GET /settings/system/jit-provisioning route"""

    @app.get("/settings/system/jit-provisioning")
    @tracer.capture_method
    def settings_system_jit_provisioning_get():
        """Get the JIT provisioning policy for federated users"""
        table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
        if not table_name:
            logger.error("SYSTEM_SETTINGS_TABLE_NAME environment variable not set")
            raise InternalServerError(
                "SYSTEM_SETTINGS_TABLE_NAME environment variable is not configured"
            )

        try:
            table = dynamodb.Table(table_name)
            response = table.get_item(
                Key={"PK": SETTINGS_PK, "SK": SETTINGS_SK},
                ConsistentRead=True,
            )
            return {
                "status": "success",
                "data": build_response_payload(response.get("Item")),
            }
        except InternalServerError:
            raise
        except Exception:
            logger.exception("Error retrieving JIT provisioning settings")
            raise InternalServerError("Error retrieving JIT provisioning settings")
