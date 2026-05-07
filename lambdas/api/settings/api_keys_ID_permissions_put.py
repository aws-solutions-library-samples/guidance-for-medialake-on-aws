"""Handler for PUT /settings/api-keys/{id}/permissions endpoint.

Allows granular update of API key permissions using the flat resource:action
format that matches JWT custom claims (e.g., {"assets:view": True}).
"""

import json
import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")

# All valid permission keys matching the authorizer's permission mapping.
# This is the single source of truth for what permissions can be assigned.
VALID_PERMISSION_KEYS = {
    # Assets
    "assets:view",
    "assets:upload",
    "assets:edit",
    "assets:delete",
    "assets:download",
    # Collections
    "collections:view",
    "collections:create",
    "collections:edit",
    "collections:delete",
    # Connectors
    "connectors:view",
    "connectors:create",
    "connectors:edit",
    "connectors:delete",
    # Environments
    "environments:view",
    "environments:create",
    "environments:edit",
    "environments:delete",
    # Groups
    "groups:view",
    "groups:create",
    "groups:edit",
    "groups:delete",
    # Integrations
    "integrations:view",
    "integrations:create",
    "integrations:edit",
    "integrations:delete",
    # Nodes
    "nodes:view",
    # Permissions / Roles
    "permissions:view",
    "permissions:create",
    "permissions:edit",
    "permissions:delete",
    # Pipelines
    "pipelines:view",
    "pipelines:create",
    "pipelines:edit",
    "pipelines:delete",
    "pipelinesExecutions:view",
    "pipelinesExecutions:retry",
    # Reviews
    "reviews:view",
    "reviews:edit",
    "reviews:delete",
    # Search
    "search:view",
    # Settings - API keys
    "api-keys:view",
    "api-keys:create",
    "api-keys:edit",
    "api-keys:delete",
    # Settings - Collection types
    "collection-types:view",
    "collection-types:create",
    "collection-types:edit",
    "collection-types:delete",
    # Settings - System
    "system:view",
    "system:edit",
    # Settings - Users
    "users:view",
    "users:edit",
    "users:delete",
    # Storage
    "storage:view",
    # Regions
    "regions:view",
}


def register_route(app):
    """Register PUT /settings/api-keys/{id}/permissions route"""

    @app.put("/settings/api-keys/<id>/permissions")
    @tracer.capture_method
    def settings_api_keys_ID_permissions_put(id: str):
        """
        Granularly update permissions for an API key.

        Accepts a flat resource:action permission map:
            {"assets:view": true, "assets:upload": true, "search:view": false}

        Supports two modes via the "mode" field:
        - "merge" (default): Merges provided permissions with existing ones.
        - "replace": Replaces all permissions with the provided set.
        """
        try:
            api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE_NAME"))

            body = app.current_event.json_body

            # Guard against missing or non-dict body
            if not isinstance(body, dict):
                return {
                    "status": "error",
                    "message": "Request body must be a JSON object with a 'permissions' field",
                    "data": {},
                }

            # Validate body has permissions
            permissions = body.get("permissions")
            if permissions is None or not isinstance(permissions, dict):
                return {
                    "status": "error",
                    "message": "Request body must include a 'permissions' object with resource:action keys and boolean values",
                    "data": {},
                }

            # Validate all permission keys and values
            invalid_keys = []
            invalid_values = []
            for key, value in permissions.items():
                if key not in VALID_PERMISSION_KEYS:
                    invalid_keys.append(key)
                if not isinstance(value, bool):
                    invalid_values.append(key)

            if invalid_keys:
                return {
                    "status": "error",
                    "message": f"Invalid permission keys: {', '.join(sorted(invalid_keys))}. "
                    f"Valid keys use the resource:action format (e.g., 'assets:view', 'collections:edit').",
                    "data": {"validKeys": sorted(VALID_PERMISSION_KEYS)},
                }

            if invalid_values:
                return {
                    "status": "error",
                    "message": f"Permission values must be booleans. Non-boolean values for: {', '.join(sorted(invalid_values))}",
                    "data": {},
                }

            # Get existing API key
            response = api_keys_table.get_item(Key={"id": id})

            if "Item" not in response:
                return {
                    "status": "error",
                    "message": f"API key with ID {id} not found",
                    "data": {},
                }

            existing_item = response["Item"]

            # Parse existing permissions
            existing_permissions = {}
            if "permissions" in existing_item:
                try:
                    existing_permissions = (
                        json.loads(existing_item["permissions"])
                        if isinstance(existing_item["permissions"], str)
                        else existing_item["permissions"]
                    )
                except (json.JSONDecodeError, TypeError) as parse_err:
                    logger.warning(
                        f"Failed to parse permissions for API key {id}: {parse_err}, "
                        f"raw value: {existing_item.get('permissions')}"
                    )
                    existing_permissions = {}

            # Normalize legacy nested permissions to flat format before merging
            if existing_permissions and any(
                isinstance(v, dict) for v in existing_permissions.values()
            ):
                logger.info(f"Normalizing legacy nested permissions for API key {id}")
                normalized = {}
                for k, v in existing_permissions.items():
                    if isinstance(v, bool) and v and ":" in k:
                        normalized[k] = True
                    elif isinstance(v, dict):
                        # Flatten nested structure (e.g., {"api-keys": {"view": True}})
                        for action, enabled in v.items():
                            if isinstance(enabled, bool) and enabled:
                                normalized[f"{k}:{action}"] = True
                            elif isinstance(enabled, dict):
                                # Deeper nesting (e.g., {"settings": {"api-keys": {"view": True}}})
                                for sub_action, sub_enabled in enabled.items():
                                    if isinstance(sub_enabled, bool) and sub_enabled:
                                        normalized[f"{k}.{action}:{sub_action}"] = True
                existing_permissions = normalized

            # Determine update mode
            mode = body.get("mode", "merge")
            if mode not in ("merge", "replace"):
                return {
                    "status": "error",
                    "message": "mode must be 'merge' or 'replace'",
                    "data": {},
                }

            if mode == "merge":
                # Merge: update existing permissions with new values
                updated_permissions = {**existing_permissions, **permissions}
                # Remove any keys explicitly set to False to keep the dict clean
                updated_permissions = {
                    k: v for k, v in updated_permissions.items() if v is True
                }
            else:
                # Replace: use only the provided permissions (keep True values)
                updated_permissions = {
                    k: v for k, v in permissions.items() if v is True
                }

            # Update DynamoDB
            now = datetime.utcnow().isoformat()
            api_keys_table.update_item(
                Key={"id": id},
                UpdateExpression="SET permissions = :permissions, updatedAt = :updatedAt",
                ExpressionAttributeValues={
                    ":permissions": json.dumps(updated_permissions),
                    ":updatedAt": now,
                },
            )

            return {
                "status": "success",
                "message": "API key permissions updated successfully",
                "data": {
                    "id": id,
                    "permissions": updated_permissions,
                    "mode": mode,
                    "updatedAt": now,
                },
            }

        except Exception:
            logger.exception(f"Error updating permissions for API key {id}")
            return {
                "status": "error",
                "message": "Error updating API key permissions",
                "data": {},
            }
