"""Handler for GET /settings/system/metadata-fields endpoint."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.exceptions import InternalServerError

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
            table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
            if not table_name:
                raise ValueError(
                    "SYSTEM_SETTINGS_TABLE_NAME environment variable not set"
                )
            table = dynamodb.Table(table_name)

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
                    "fields": item.get("fields", []),
                    "updatedAt": item.get("updatedAt"),
                },
            }
        except Exception:
            logger.exception("Error retrieving metadata fields")
            raise InternalServerError("Error retrieving metadata fields")
