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

# Import route handlers
from favorites_delete import handle_delete_favorite
from favorites_get import handle_get_favorites
from favorites_post import handle_post_favorite
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
    return handle_delete_user(user_id, cognito, USER_POOL_ID, logger, metrics, tracer)


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


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
