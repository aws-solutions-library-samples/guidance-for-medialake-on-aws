"""
Unified Groups Lambda Handler

This Lambda consolidates all group-related endpoints into a single function
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
from groups_get import handle_get_groups
from groups_groupId_delete import handle_delete_group
from groups_groupId_get import handle_get_group
from groups_groupId_members_post import handle_post_group_members
from groups_groupId_members_userId_delete import handle_delete_group_member
from groups_groupId_put import handle_put_group
from groups_post import handle_post_groups

# Initialize PowerTools
logger = Logger(
    service="groups",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="groups")
metrics = Metrics(namespace="medialake", service="groups")

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
AUTH_TABLE_NAME = os.environ["AUTH_TABLE_NAME"]
COGNITO_USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]


# Register routes


# Group CRUD routes
@app.post("/groups")
@tracer.capture_method
def create_group():
    """POST /groups - Create a new group"""
    return handle_post_groups(
        app,
        cognito,
        dynamodb,
        AUTH_TABLE_NAME,
        COGNITO_USER_POOL_ID,
        logger,
        metrics,
        tracer,
    )


@app.get("/groups")
@tracer.capture_method
def list_groups():
    """GET /groups - List all groups"""
    return handle_get_groups(app, dynamodb, AUTH_TABLE_NAME, logger, metrics, tracer)


@app.get("/groups/<group_id>")
@tracer.capture_method
def get_group(group_id: str):
    """GET /groups/{groupId} - Get group details"""
    return handle_get_group(
        group_id, dynamodb, AUTH_TABLE_NAME, logger, metrics, tracer
    )


@app.put("/groups/<group_id>")
@tracer.capture_method
def put_group(group_id: str):
    """PUT /groups/{groupId} - Update group details"""
    return handle_put_group(
        group_id, app, dynamodb, AUTH_TABLE_NAME, logger, metrics, tracer
    )


@app.delete("/groups/<group_id>")
@tracer.capture_method
def delete_group(group_id: str):
    """DELETE /groups/{groupId} - Delete a group"""
    return handle_delete_group(
        group_id,
        dynamodb,
        COGNITO_USER_POOL_ID,
        AUTH_TABLE_NAME,
        logger,
        metrics,
        tracer,
    )


# Group members routes
@app.post("/groups/<group_id>/members")
@tracer.capture_method
def post_group_members(group_id: str):
    """POST /groups/{groupId}/members - Add members to group"""
    return handle_post_group_members(
        group_id, app, dynamodb, AUTH_TABLE_NAME, logger, metrics, tracer
    )


@app.delete("/groups/<group_id>/members/<user_id>")
@tracer.capture_method
def delete_group_member(group_id: str, user_id: str):
    """DELETE /groups/{groupId}/members/{userId} - Remove member from group"""
    return handle_delete_group_member(
        group_id, user_id, dynamodb, AUTH_TABLE_NAME, logger, metrics, tracer
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
