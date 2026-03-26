"""Handler for GET /settings/system/metadata-fields endpoint."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")


def register_route(app):
    """Register GET /settings/system/metadata-fields route"""

    @app.get("/settings/system/metadata-fields")
    @tracer.capture_method
    def settings_system_metadata_fields_get():
        """Get custom metadata field definitions"""
        try:
            table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE_NAME"))

            response = table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "METADATA_FIELDS"},
                ConsistentRead=True,
            )

            item = response.get("Item")
            if not item:
                return {
                    "status": "success",
                    "data": {"fields": [], "updatedAt": None},
                }

            return {
                "status": "success",
                "data": {
                    "fields": item["fields"],
                    "updatedAt": item["updatedAt"],
                },
            }
        except Exception as e:
            logger.exception("Error retrieving metadata fields")
            return {
                "status": "error",
                "message": f"Error retrieving metadata fields: {str(e)}",
                "data": {},
            }
