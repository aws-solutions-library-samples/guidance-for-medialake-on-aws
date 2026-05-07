"""Handler for GET /settings/system endpoint."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")


def register_route(app):
    """Register GET /settings/system route"""

    @app.get("/settings/system")
    @tracer.capture_method
    def settings_system_get():
        """Get all system settings"""
        try:
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
            )

            # Get search provider settings
            search_provider_response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            )

            search_provider = search_provider_response.get("Item", {})

            # Remove DynamoDB specific attributes
            if search_provider:
                search_provider.pop("PK", None)
                search_provider.pop("SK", None)

            # Prepare response
            response = {
                "status": "success",
                "message": "System settings retrieved successfully",
                "data": {
                    "searchProvider": search_provider if search_provider else None
                },
            }

            return response
        except Exception as e:
            logger.exception("Error retrieving system settings")
            return {
                "status": "error",
                "message": f"Error retrieving system settings: {str(e)}",
                "data": {},
            }
