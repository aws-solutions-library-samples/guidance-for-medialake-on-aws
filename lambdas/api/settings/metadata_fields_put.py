"""Handler for PUT /settings/system/metadata-fields endpoint."""

import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

logger = Logger(child=True)
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")

VALID_TYPES = {"string", "number", "date"}


def register_route(app):
    """Register PUT /settings/system/metadata-fields route"""

    @app.put("/settings/system/metadata-fields")
    @tracer.capture_method
    def settings_system_metadata_fields_put():
        """Update custom metadata field definitions"""
        try:
            body = app.current_event.json_body
        except Exception:
            raise BadRequestError("Request body must contain a 'fields' array")

        if not body or "fields" not in body:
            raise BadRequestError("Request body must contain a 'fields' array")

        fields = body["fields"]
        if not isinstance(fields, list):
            raise BadRequestError("'fields' must be an array")

        sanitized_fields = []
        for i, field in enumerate(fields):
            if not isinstance(field.get("name"), str) or not field["name"].strip():
                raise BadRequestError(
                    f"Field at index {i}: 'name' is required and must be a non-empty string"
                )
            if (
                not isinstance(field.get("displayName"), str)
                or not field["displayName"].strip()
            ):
                raise BadRequestError(
                    f"Field at index {i}: 'displayName' is required and must be a non-empty string"
                )
            if field.get("type") not in VALID_TYPES:
                raise BadRequestError(
                    f"Field at index {i}: 'type' must be one of 'string', 'number', 'date'"
                )
            if not isinstance(field.get("isDisplayable"), bool):
                raise BadRequestError(
                    f"Field at index {i}: 'isDisplayable' must be a boolean"
                )
            if not isinstance(field.get("isFilterable"), bool):
                raise BadRequestError(
                    f"Field at index {i}: 'isFilterable' must be a boolean"
                )

            sanitized_fields.append(
                {
                    "name": field["name"],
                    "displayName": field["displayName"],
                    "type": field["type"],
                    "isDisplayable": field["isDisplayable"],
                    "isFilterable": field["isFilterable"],
                }
            )

        try:
            updated_at = datetime.utcnow().isoformat() + "Z"
            table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE_NAME"))

            table.put_item(
                Item={
                    "PK": "SYSTEM_SETTINGS",
                    "SK": "METADATA_FIELDS",
                    "fields": sanitized_fields,
                    "updatedAt": updated_at,
                }
            )

            return {
                "status": "success",
                "data": {
                    "fields": sanitized_fields,
                    "updatedAt": updated_at,
                },
            }
        except Exception as e:
            logger.exception("Error saving metadata fields")
            return {
                "status": "error",
                "message": f"Error saving metadata fields: {str(e)}",
                "data": {},
            }
