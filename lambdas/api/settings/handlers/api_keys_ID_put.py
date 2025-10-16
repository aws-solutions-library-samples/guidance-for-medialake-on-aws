"""Handler for PUT /settings/api-keys/{id} endpoint."""

import json
import os
import secrets
import string
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")


def generate_api_key(length=32):
    """Generate a secure random API key"""
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def register_route(app):
    """Register PUT /settings/api-keys/{id} route"""

    @app.put("/settings/api-keys/<id>")
    @tracer.capture_method
    def settings_api_keys_ID_put(id: str):
        """Update an existing API key"""
        try:
            api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE_NAME"))

            # Get request body
            body = app.current_event.json_body

            # Get existing API key
            response = api_keys_table.get_item(Key={"keyId": id})

            if "Item" not in response:
                return {
                    "status": "error",
                    "message": f"API key with ID {id} not found",
                    "data": {},
                }

            existing_item = response["Item"]

            # Prepare update expression
            update_expression_parts = ["SET updatedAt = :updatedAt"]
            expression_attribute_values = {":updatedAt": datetime.utcnow().isoformat()}

            # Add fields to update
            if "name" in body:
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
                update_expression_parts.append("name = :name")
                expression_attribute_values[":name"] = body["name"].strip()

            if "description" in body:
                if not isinstance(body["description"], str):
                    return {
                        "status": "error",
                        "message": "Description must be a string",
                        "data": {},
                    }
                if len(body["description"]) > 500:
                    return {
                        "status": "error",
                        "message": "Description cannot exceed 500 characters",
                        "data": {},
                    }
                update_expression_parts.append("description = :description")
                expression_attribute_values[":description"] = body[
                    "description"
                ].strip()

            if "isEnabled" in body:
                if not isinstance(body["isEnabled"], bool):
                    return {
                        "status": "error",
                        "message": "isEnabled must be a boolean",
                        "data": {},
                    }
                update_expression_parts.append("isEnabled = :isEnabled")
                expression_attribute_values[":isEnabled"] = body["isEnabled"]

            if "permissions" in body:
                if not isinstance(body["permissions"], dict):
                    return {
                        "status": "error",
                        "message": "permissions must be an object",
                        "data": {},
                    }
                update_expression_parts.append("permissions = :permissions")
                expression_attribute_values[":permissions"] = json.dumps(
                    body["permissions"]
                )

            # Handle key rotation
            new_api_key = None
            if body.get("rotateKey"):
                # Generate new API key value
                api_key_value = generate_api_key(32)
                new_api_key = f"{id}_{api_key_value}"

                # Update secret in Secrets Manager
                secret_arn = existing_item.get("secretArn")
                if secret_arn:
                    secretsmanager.update_secret(
                        SecretId=secret_arn,
                        SecretString=api_key_value,
                    )
                else:
                    # Create new secret if it doesn't exist
                    secret_name = f"medialake/api-keys/{id}"
                    secret_response = secretsmanager.create_secret(
                        Name=secret_name,
                        Description=f"API key for {existing_item.get('name')}",
                        SecretString=api_key_value,
                    )
                    update_expression_parts.append("secretArn = :secretArn")
                    expression_attribute_values[":secretArn"] = secret_response["ARN"]

            # Update the API key
            update_expression = " , ".join(update_expression_parts)

            update_response = api_keys_table.update_item(
                Key={"keyId": id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW",
            )

            updated_item = update_response.get("Attributes", {})

            # Prepare response
            response_item = {
                "id": updated_item.get("keyId"),
                "name": updated_item.get("name"),
                "description": updated_item.get("description"),
                "isEnabled": updated_item.get("isEnabled", True),
                "createdAt": updated_item.get("createdAt"),
                "updatedAt": updated_item.get("updatedAt"),
            }

            # Include permissions if present
            if "permissions" in updated_item:
                try:
                    response_item["permissions"] = (
                        json.loads(updated_item["permissions"])
                        if isinstance(updated_item["permissions"], str)
                        else updated_item["permissions"]
                    )
                except (json.JSONDecodeError, TypeError):
                    response_item["permissions"] = {}

            # Include new API key only if it was rotated
            if new_api_key:
                response_item["apiKey"] = new_api_key

            return {
                "status": "success",
                "message": "API key updated successfully",
                "data": response_item,
            }

        except Exception as e:
            logger.exception(f"Error updating API key {id}")
            return {
                "status": "error",
                "message": f"Error updating API key: {str(e)}",
                "data": {},
            }
