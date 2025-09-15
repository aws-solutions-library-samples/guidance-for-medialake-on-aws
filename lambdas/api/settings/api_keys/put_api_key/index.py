import json
import os
import secrets
import string
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE"))
secretsmanager = boto3.client("secretsmanager")

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


def generate_api_key(length=32):
    """Generate a secure random API key"""
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def validate_input(body):
    """
    Validate input fields for API key update.
    Only allows 'name', 'description', 'isEnabled', 'permissions' and 'rotateKey' fields.
    """
    allowed_fields = {"name", "description", "isEnabled", "permissions", "rotateKey"}

    # Check for unexpected fields
    unexpected_fields = set(body.keys()) - allowed_fields
    if unexpected_fields:
        raise ValueError(
            f"Unexpected fields: {', '.join(unexpected_fields)}. Only 'name', 'description', 'isEnabled', 'permissions', and 'rotateKey' are allowed."
        )

    # Validate 'name' field
    if "name" in body:
        name = body["name"]
        if not isinstance(name, str):
            raise ValueError("Field 'name' must be a string")
        name = name.strip()
        if not name:
            raise ValueError("Field 'name' cannot be empty or contain only whitespace")
        if len(name) > 100:
            raise ValueError("Field 'name' cannot exceed 100 characters")
        body["name"] = name  # Update with trimmed value

    # Validate 'description' field
    if "description" in body:
        description = body["description"]
        if not isinstance(description, str):
            raise ValueError("Field 'description' must be a string")
        description = description.strip()
        if len(description) > 500:
            raise ValueError("Field 'description' cannot exceed 500 characters")
        body["description"] = description  # Update with trimmed value

    # Validate 'isEnabled' field
    if "isEnabled" in body:
        is_enabled = body["isEnabled"]
        if not isinstance(is_enabled, bool):
            raise ValueError("Field 'isEnabled' must be a boolean")

    # Validate 'rotateKey' field
    if "rotateKey" in body:
        rotate_key = body["rotateKey"]
        if not isinstance(rotate_key, bool):
            raise ValueError("Field 'rotateKey' must be a boolean")

    # Validate 'permissions' field
    if "permissions" in body:
        permissions = body["permissions"]
        if not isinstance(permissions, dict):
            raise ValueError("Field 'permissions' must be an object")
        # Validate permission values are booleans
        for key, value in permissions.items():
            if not isinstance(value, bool):
                raise ValueError(f"Permission value for '{key}' must be a boolean")

    return body


@app.put("/settings/api-keys/{id}")
@tracer.capture_method
def update_api_key(id: str):
    """
    Update an existing API key
    """
    try:
        # Get request body
        body = app.current_event.json_body

        # Validate input
        body = validate_input(body)

        # Check if there are any fields to update (excluding rotateKey for this check)
        updateable_fields = {k: v for k, v in body.items() if k != "rotateKey"}
        if not updateable_fields and not body.get("rotateKey", False):
            return {
                "status": "error",
                "message": "No valid fields provided for update",
                "data": {},
            }

        # Check if API key exists
        response = api_keys_table.get_item(Key={"id": id})

        if "Item" not in response:
            return {
                "status": "error",
                "message": f"API key with ID {id} not found",
                "data": {},
            }

        existing_item = response["Item"]

        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        # Update allowed fields
        allowed_fields = ["name", "description", "isEnabled", "permissions"]

        for field in allowed_fields:
            if field in body:
                update_expression_parts.append(f"#{field} = :{field}")
                if field == "permissions":
                    # Store permissions as JSON string in DynamoDB
                    expression_attribute_values[f":{field}"] = json.dumps(body[field])
                else:
                    expression_attribute_values[f":{field}"] = body[field]
                expression_attribute_names[f"#{field}"] = field

        # Check if key rotation is requested
        if body.get("rotateKey", False):
            # Generate new API key value
            new_api_key_value = generate_api_key(32)

            # Update the secret in Secrets Manager
            secret_arn = existing_item["secretArn"]

            secretsmanager.update_secret(
                SecretId=secret_arn,
                SecretString=new_api_key_value,
            )

            # Create the full API key with format: id_secretValue
            full_api_key = f"{id}_{new_api_key_value}"

            logger.info(f"Rotated API key for {id}")

        # Always update the updatedAt timestamp
        now = datetime.utcnow().isoformat()
        update_expression_parts.append("#updatedAt = :updatedAt")
        expression_attribute_values[":updatedAt"] = now
        expression_attribute_names["#updatedAt"] = "updatedAt"

        # Perform the update
        if update_expression_parts:
            update_expression = "SET " + ", ".join(update_expression_parts)

            api_keys_table.update_item(
                Key={"id": id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ExpressionAttributeNames=expression_attribute_names,
            )

        # Get the updated item
        updated_response = api_keys_table.get_item(Key={"id": id})
        updated_item = updated_response["Item"]

        # Prepare response (exclude secret ARN)
        response_item = {
            "id": updated_item.get("id"),
            "name": updated_item.get("name"),
            "description": updated_item.get("description"),
            "isEnabled": updated_item.get("isEnabled", True),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt"),
        }

        # Include permissions in response if present
        if "permissions" in updated_item:
            response_item["permissions"] = json.loads(updated_item["permissions"])

        # If key was rotated, include the new key in response
        if body.get("rotateKey", False):
            response_item["apiKey"] = full_api_key
            response_item["keyRotated"] = True

        return {
            "status": "success",
            "message": "API key updated successfully",
            "data": response_item,
        }

    except ValueError as e:
        logger.warning(f"Validation error for API key {id}: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "data": {},
        }

    except Exception as e:
        logger.exception(f"Error updating API key {id}")
        return {
            "status": "error",
            "message": f"Error updating API key: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for API key update endpoint
    """
    return app.resolve(event, context)
