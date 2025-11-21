"""Handler for GET /settings/api-keys/{id} endpoint."""

import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")


def register_route(app):
    """Register GET /settings/api-keys/{id} route"""

    @app.get("/settings/api-keys/<id>")
    @tracer.capture_method
    def settings_api_keys_ID_get(id: str):
        """Get a single API key by ID"""
        try:
            api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE_NAME"))

            # Get API key from DynamoDB
            response = api_keys_table.get_item(Key={"id": id})

            if "Item" not in response:
                return {
                    "status": "error",
                    "message": f"API key with ID {id} not found",
                    "data": {},
                }

            item = response["Item"]

            # Filter out sensitive data (secret ARN)
            api_key = {
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "isEnabled": item.get("isEnabled", True),
                "createdAt": item.get("createdAt"),
                "updatedAt": item.get("updatedAt"),
            }

            # Include permissions if present
            if "permissions" in item:
                try:
                    api_key["permissions"] = (
                        json.loads(item["permissions"])
                        if isinstance(item["permissions"], str)
                        else item["permissions"]
                    )
                except (json.JSONDecodeError, TypeError):
                    api_key["permissions"] = {}

            return {
                "status": "success",
                "message": "API key retrieved successfully",
                "data": api_key,
            }

        except Exception as e:
            logger.exception(f"Error getting API key {id}")
            return {
                "status": "error",
                "message": f"Error getting API key: {str(e)}",
                "data": {},
            }
