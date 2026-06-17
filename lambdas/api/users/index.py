"""
Unified Users Lambda Handler

This Lambda consolidates all user-related endpoints into a single function
using AWS Powertools APIGatewayRestResolver for routing.
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from collections_migration import (
    ASYNC_MIGRATE_EVENT_KEY,
    migrate_user_collections,
)

# Import route handlers
from favorites_delete import handle_delete_favorite
from favorites_get import handle_get_favorites
from favorites_post import handle_post_favorite
from profile_change_password_post import handle_change_password
from profile_get import handle_get_profile
from profile_put import handle_put_profile
from settings_get import handle_get_settings
from settings_put import handle_put_setting
from users_delete import handle_delete_user
from users_disable_post import handle_disable_user
from users_enable_post import handle_enable_user
from users_get import handle_get_user
from users_post import handle_create_user
from users_put import handle_put_user
from users_reset_password_post import handle_reset_password

# Initialize PowerTools
logger = Logger(
    service="users",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="users")
metrics = Metrics(namespace="medialake", service="users")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize shared clients
cognito = boto3.client("cognito-idp")
dynamodb = boto3.resource("dynamodb")

# Get environment variables
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
USER_TABLE_NAME = os.environ["USER_TABLE_NAME"]
# Optional — when configured, collections owned by a deleted user are migrated
# to the deleting administrator instead of being orphaned.
COLLECTIONS_TABLE_NAME = os.environ.get("COLLECTIONS_TABLE_NAME")


def _get_requesting_user_id(event: Dict[str, Any]) -> Any:
    """Extract the Cognito sub of the caller from API Gateway JWT claims."""
    try:
        claims = event["requestContext"]["authorizer"]["claims"]
        if isinstance(claims, str):
            claims = json.loads(claims)
        return claims.get("sub")
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError):
        return None


# Register routes


# User CRUD routes
@app.post("/users")
@tracer.capture_method
def create_user():
    """POST /users - Create a new user"""
    return handle_create_user(app, cognito, USER_POOL_ID, logger, metrics, tracer)


@app.get("/users/<user_id>")
@tracer.capture_method
def get_user(user_id: str):
    """GET /users/{user_id} - Get user details"""
    return handle_get_user(user_id, cognito, USER_POOL_ID, logger, metrics, tracer)


@app.put("/users/<user_id>")
@tracer.capture_method
def put_user(user_id: str):
    """PUT /users/{user_id} - Update user details"""
    return handle_put_user(user_id, app, cognito, USER_POOL_ID, logger, metrics, tracer)


@app.delete("/users/<user_id>")
@tracer.capture_method
def delete_user(user_id: str):
    """DELETE /users/{user_id} - Delete a user"""
    requesting_user_id = _get_requesting_user_id(app.current_event.raw_event)
    return handle_delete_user(
        user_id,
        cognito,
        USER_POOL_ID,
        logger,
        metrics,
        tracer,
        dynamodb=dynamodb,
        user_table_name=USER_TABLE_NAME,
        collections_table_name=COLLECTIONS_TABLE_NAME,
        new_collection_owner_id=requesting_user_id,
    )


@app.post("/users/<user_id>/disable")
@tracer.capture_method
def disable_user(user_id: str):
    """POST /users/{user_id}/disable - Disable a user"""
    return handle_disable_user(user_id, cognito, USER_POOL_ID, logger, metrics, tracer)


@app.post("/users/<user_id>/enable")
@tracer.capture_method
def enable_user(user_id: str):
    """POST /users/{user_id}/enable - Enable a user"""
    return handle_enable_user(user_id, cognito, USER_POOL_ID, logger, metrics, tracer)


@app.post("/users/<user_id>/reset-password")
@tracer.capture_method
def reset_password(user_id: str):
    """POST /users/{user_id}/reset-password - Reset a user's password"""
    return handle_reset_password(
        user_id, cognito, USER_POOL_ID, logger, metrics, tracer
    )


# Profile routes
@app.get("/users/profile")
@tracer.capture_method
def get_profile():
    """GET /users/profile - Get user profile"""
    return handle_get_profile(app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer)


@app.put("/users/profile")
@tracer.capture_method
def put_profile():
    """PUT /users/profile - Update user profile"""
    return handle_put_profile(app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer)


@app.post("/users/profile/change-password")
@tracer.capture_method
def change_password():
    """POST /users/profile/change-password - Change own password"""
    return handle_change_password(app, cognito, USER_POOL_ID, logger, metrics, tracer)


# Settings routes
@app.get("/users/settings")
@tracer.capture_method
def get_settings():
    """GET /users/settings - Get user settings"""
    return handle_get_settings(app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer)


@app.put("/users/settings/<namespace>/<key>")
@tracer.capture_method
def put_setting(namespace: str, key: str):
    """PUT /users/settings/{namespace}/{key} - Update user setting"""
    return handle_put_setting(
        namespace, key, app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer
    )


# Favorites routes
@app.get("/users/favorites")
@tracer.capture_method
def get_favorites():
    """GET /users/favorites - Get user favorites"""
    return handle_get_favorites(app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer)


@app.post("/users/favorites")
@tracer.capture_method
def post_favorite():
    """POST /users/favorites - Add a favorite"""
    return handle_post_favorite(app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer)


@app.delete("/users/favorites/<item_type>/<item_id>")
@tracer.capture_method
def delete_favorite(item_type: str, item_id: str):
    """DELETE /users/favorites/{itemType}/{itemId} - Remove a favorite"""
    return handle_delete_favorite(
        item_type, item_id, app, dynamodb, USER_TABLE_NAME, logger, metrics, tracer
    )


SENSITIVE_BODY_KEYS = {"current_password", "new_password", "password"}


def _sanitize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy of the event with sensitive body fields redacted."""
    if not event.get("body"):
        return event

    sanitized = {**event}
    try:
        body = (
            json.loads(sanitized["body"])
            if isinstance(sanitized["body"], str)
            else sanitized["body"]
        )
        if any(k in body for k in SENSITIVE_BODY_KEYS):
            redacted = {
                k: "***REDACTED***" if k in SENSITIVE_BODY_KEYS else v
                for k, v in body.items()
            }
            sanitized["body"] = json.dumps(redacted)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass  # non-JSON body, leave as-is

    return sanitized


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    # Async self-invocation: migrate collections owned by a deleted user.
    # This path is reached only via the fire-and-forget invoke triggered from
    # the DELETE /users handler, never from API Gateway.
    if isinstance(event, dict) and event.get(ASYNC_MIGRATE_EVENT_KEY):
        deleted_user_id = event.get("deleted_user_id")
        new_owner_id = event.get("new_owner_id")
        if not COLLECTIONS_TABLE_NAME:
            logger.warning(
                {
                    "message": "COLLECTIONS_TABLE_NAME unset — cannot migrate",
                    "operation": "async_migrate_collections",
                }
            )
            return {"statusCode": 200, "body": "Collections table not configured"}
        migrated = migrate_user_collections(
            dynamodb,
            COLLECTIONS_TABLE_NAME,
            deleted_user_id,
            new_owner_id,
            logger,
            metrics,
        )
        return {
            "statusCode": 200,
            "body": json.dumps({"collectionsMigrated": migrated}),
        }

    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": _sanitize_event(event),
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
