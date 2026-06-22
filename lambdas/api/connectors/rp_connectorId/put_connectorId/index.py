import json
import os
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from cors_utils import create_error_response, create_response

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MEDIALAKE_CONNECTOR_TABLE"])

# Only these fields may be changed after a connector is created. Everything
# else (bucket, integration method, filters, IAM, etc.) is provisioned at
# creation time and cannot be edited in place.
UPDATABLE_FIELDS = ("name", "description")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    try:
        connector_id = (event.get("pathParameters") or {}).get("connector_id")
        if not connector_id:
            logger.error("No connector_id provided in path parameters")
            return create_error_response(400, "Connector ID is required")

        try:
            body = json.loads(event.get("body") or "{}")
        except (TypeError, ValueError):
            return create_error_response(400, "Invalid JSON body")

        if not isinstance(body, dict):
            return create_error_response(400, "Request body must be a JSON object")

        # Collect only the allowed, present, non-null fields.
        updates: dict = {}
        for field in UPDATABLE_FIELDS:
            if field in body and body[field] is not None:
                value = body[field]
                if not isinstance(value, str):
                    return create_error_response(400, f"'{field}' must be a string")
                updates[field] = value.strip()

        if "name" in updates and not updates["name"]:
            return create_error_response(400, "Connector name cannot be empty")

        if not updates:
            return create_error_response(
                400, "No updatable fields provided (name, description)"
            )

        # Ensure the connector exists before attempting an update.
        try:
            existing = table.get_item(Key={"id": connector_id})
        except ClientError as e:
            logger.error(f"DynamoDB get_item failed: {str(e)}")
            return create_error_response(500, "Failed to retrieve connector details")

        if "Item" not in existing:
            logger.warning(f"Connector not found with ID: {connector_id}")
            return create_error_response(404, "Connector not found")

        updates["updatedAt"] = datetime.now(timezone.utc).isoformat()

        # Build a safe UpdateExpression. "name" is a DynamoDB reserved word, so
        # every attribute goes through an expression-name placeholder.
        set_parts = []
        expr_names = {}
        expr_values = {}
        for i, (key, val) in enumerate(updates.items()):
            set_parts.append(f"#f{i} = :v{i}")
            expr_names[f"#f{i}"] = key
            expr_values[f":v{i}"] = val

        try:
            table.update_item(
                Key={"id": connector_id},
                UpdateExpression="SET " + ", ".join(set_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            logger.error(f"DynamoDB update_item failed: {str(e)}")
            return create_error_response(500, "Failed to update connector")

        logger.info(
            f"Updated connector {connector_id}: fields={sorted(updates.keys())}"
        )
        # Return a small, JSON-safe payload (avoids Decimal serialization issues
        # from returning the full DynamoDB item).
        return create_response(200, {"id": connector_id, **updates})

    except Exception as e:
        logger.exception("Unexpected error occurred")
        return create_error_response(500, f"Internal server error: {str(e)}")
