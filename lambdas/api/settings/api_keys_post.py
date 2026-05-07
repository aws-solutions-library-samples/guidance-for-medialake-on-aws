"""Handler for POST /settings/api-keys endpoint."""

import json
import os
import secrets
import string
import uuid
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")

# ============================================================================
# Scope-based permission presets
# ============================================================================
# These map to predefined permission sets using the flat resource:action format
# that matches the authorizer's permission mapping and JWT custom claims.

SCOPE_PRESETS = {
    "read-only": {
        "assets:view": True,
        "assets:download": True,
        "collections:view": True,
        "connectors:view": True,
        "environments:view": True,
        "groups:view": True,
        "integrations:view": True,
        "nodes:view": True,
        "permissions:view": True,
        "pipelines:view": True,
        "pipelinesExecutions:view": True,
        "reviews:view": True,
        "search:view": True,
        "api-keys:view": True,
        "collection-types:view": True,
        "system:view": True,
        "users:view": True,
        "storage:view": True,
        "regions:view": True,
    },
    "read-write": {
        # All read-only permissions
        "assets:view": True,
        "assets:upload": True,
        "assets:edit": True,
        "assets:delete": True,
        "assets:download": True,
        "collections:view": True,
        "collections:create": True,
        "collections:edit": True,
        "collections:delete": True,
        "connectors:view": True,
        "connectors:create": True,
        "connectors:edit": True,
        "connectors:delete": True,
        "environments:view": True,
        "environments:create": True,
        "environments:edit": True,
        "environments:delete": True,
        "groups:view": True,
        "integrations:view": True,
        "integrations:create": True,
        "integrations:edit": True,
        "integrations:delete": True,
        "nodes:view": True,
        "pipelines:view": True,
        "pipelines:create": True,
        "pipelines:edit": True,
        "pipelines:delete": True,
        "pipelinesExecutions:view": True,
        "pipelinesExecutions:retry": True,
        "reviews:view": True,
        "reviews:edit": True,
        "reviews:delete": True,
        "search:view": True,
        "api-keys:view": True,
        "collection-types:view": True,
        "system:view": True,
        "users:view": True,
        "storage:view": True,
        "regions:view": True,
    },
    "admin": {
        "assets:view": True,
        "assets:upload": True,
        "assets:edit": True,
        "assets:delete": True,
        "assets:download": True,
        "collections:view": True,
        "collections:create": True,
        "collections:edit": True,
        "collections:delete": True,
        "connectors:view": True,
        "connectors:create": True,
        "connectors:edit": True,
        "connectors:delete": True,
        "environments:view": True,
        "environments:create": True,
        "environments:edit": True,
        "environments:delete": True,
        "groups:view": True,
        "groups:create": True,
        "groups:edit": True,
        "groups:delete": True,
        "integrations:view": True,
        "integrations:create": True,
        "integrations:edit": True,
        "integrations:delete": True,
        "nodes:view": True,
        "permissions:view": True,
        "permissions:create": True,
        "permissions:edit": True,
        "permissions:delete": True,
        "pipelines:view": True,
        "pipelines:create": True,
        "pipelines:edit": True,
        "pipelines:delete": True,
        "pipelinesExecutions:view": True,
        "pipelinesExecutions:retry": True,
        "reviews:view": True,
        "reviews:edit": True,
        "reviews:delete": True,
        "search:view": True,
        "api-keys:view": True,
        "api-keys:create": True,
        "api-keys:edit": True,
        "api-keys:delete": True,
        "collection-types:view": True,
        "collection-types:create": True,
        "collection-types:edit": True,
        "collection-types:delete": True,
        "system:view": True,
        "system:edit": True,
        "users:view": True,
        "users:edit": True,
        "users:delete": True,
        "storage:view": True,
        "regions:view": True,
    },
}

VALID_SCOPES = set(SCOPE_PRESETS.keys())


def generate_api_key(length=32):
    """Generate a secure random API key"""
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def register_route(app):
    """Register POST /settings/api-keys route"""

    @app.post("/settings/api-keys")
    @tracer.capture_method
    def settings_api_keys_post():
        """Create a new API key"""
        try:
            api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE_NAME"))

            # Get request body
            body = app.current_event.json_body

            # Validate required fields
            if "name" not in body:
                return {
                    "status": "error",
                    "message": "Missing required field: name",
                    "data": {},
                }

            # Validate name
            if not isinstance(body["name"], str) or not body["name"].strip():
                return {
                    "status": "error",
                    "message": "Name must be a non-empty string",
                    "data": {},
                }

            if len(body["name"]) > 100:
                return {
                    "status": "error",
                    "message": "Name cannot exceed 100 characters",
                    "data": {},
                }

            # Validate description (optional field)
            description = body.get("description", "")
            if not isinstance(description, str):
                return {
                    "status": "error",
                    "message": "Description must be a string",
                    "data": {},
                }

            if len(description) > 500:
                return {
                    "status": "error",
                    "message": "Description cannot exceed 500 characters",
                    "data": {},
                }

            # Generate unique API key ID and value
            api_key_id = str(uuid.uuid4())
            api_key_value = generate_api_key(32)

            # Create the full API key with format: id_secretValue
            full_api_key = f"{api_key_id}_{api_key_value}"

            # Store API key value in Secrets Manager (just the secret part)
            secret_name = f"medialake/api-keys/{api_key_id}"

            # Create the secret in Secrets Manager
            secret_response = secretsmanager.create_secret(
                Name=secret_name,
                Description=f"API key for {body['name']}",
                SecretString=api_key_value,
            )

            secret_arn = secret_response["ARN"]

            # Create API key metadata in DynamoDB
            now = datetime.utcnow().isoformat()

            # Define default permissions for API keys using the flat resource:action
            # format that matches the authorizer's permission mapping.
            default_permissions = SCOPE_PRESETS["read-write"]

            # Resolve permissions: scope preset > custom permissions > default
            scope = body.get("scope")
            if scope:
                if scope not in VALID_SCOPES:
                    return {
                        "status": "error",
                        "message": f"Invalid scope '{scope}'. Valid scopes: {', '.join(sorted(VALID_SCOPES))}",
                        "data": {"validScopes": sorted(VALID_SCOPES)},
                    }
                permissions = SCOPE_PRESETS[scope].copy()
            elif "permissions" in body:
                permissions = body["permissions"]
            else:
                permissions = default_permissions

            api_key_item = {
                "id": api_key_id,
                "name": body["name"],
                "description": description,
                "secretArn": secret_arn,
                "isEnabled": body.get("isEnabled", True),
                "permissions": json.dumps(permissions),
                "scope": scope or "custom",
                "createdAt": now,
                "updatedAt": now,
            }

            # Save to DynamoDB
            api_keys_table.put_item(Item=api_key_item)

            # Prepare response (exclude secret ARN)
            response_item = {
                "id": api_key_item["id"],
                "name": api_key_item["name"],
                "description": api_key_item["description"],
                "isEnabled": api_key_item["isEnabled"],
                "permissions": permissions,
                "scope": api_key_item["scope"],
                "createdAt": api_key_item["createdAt"],
                "updatedAt": api_key_item["updatedAt"],
                # Include the full API key value only on creation
                "apiKey": full_api_key,
            }

            return {
                "status": "success",
                "message": "API key created successfully",
                "data": response_item,
            }

        except Exception as e:
            logger.exception("Error creating API key")
            return {
                "status": "error",
                "message": f"Error creating API key: {str(e)}",
                "data": {},
            }
