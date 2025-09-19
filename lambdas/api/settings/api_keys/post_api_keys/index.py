import json
import os
import secrets
import string
import uuid
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
API_KEYS_TABLE = os.environ.get("API_KEYS_TABLE")
if not API_KEYS_TABLE:
    raise ValueError("API_KEYS_TABLE environment variable is required")
api_keys_table = dynamodb.Table(API_KEYS_TABLE)
secretsmanager = boto3.client("secretsmanager")

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


def generate_api_key(length=32):
    """Generate a secure random API key"""
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


@app.post("/settings/api-keys")
@tracer.capture_method
def create_api_key():
    """
    Create a new API key
    """
    try:
        # Get request body
        body = app.current_event.json_body

        # Validate required fields
        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in body:
                return {
                    "status": "error",
                    "message": f"Missing required field: {field}",
                    "data": {},
                }
            # Validate field content
            if not isinstance(body[field], str) or not body[field].strip():
                return {
                    "status": "error",
                    "message": f"Field {field} must be a non-empty string",
                    "data": {},
                }

        # Validate field lengths
        if len(body["name"]) > 100:
            return {
                "status": "error",
                "message": "Name cannot exceed 100 characters",
                "data": {},
            }
        if len(body["description"]) > 500:
            return {
                "status": "error",
                "message": "Description cannot exceed 500 characters",
                "data": {},
            }

        # Generate unique API key ID and value
        api_key_id = str(uuid.uuid4())
        api_key_value = generate_api_key(32)

        # Create the full API key with format: id_secretValue
        full_api_key = f"{api_key_id}_{api_key_value}"

        # Store API key value in Secrets Manager (just the secret part)
        secret_name = f"medialake/api-keys/{api_key_id}"

        # Create the secret in Secrets Manager
        secret_response = secretsmanager.create_secret(
            Name=secret_name,
            Description=f"API key for {body['name']}",
            SecretString=api_key_value,
        )

        secret_arn = secret_response["ARN"]

        # Create API key metadata in DynamoDB
        now = datetime.utcnow().isoformat()

        # Define default permissions for API keys
        default_permissions = {
            "api-key:view": True,
            "api-key:create": True,
            "api-key:edit": True,
            "api-key:delete": True,
        }

        # Allow custom permissions if provided, otherwise use defaults
        permissions = body.get("permissions", default_permissions)

        api_key_item = {
            "id": api_key_id,
            "name": body["name"],
            "description": body["description"],
            "secretArn": secret_arn,
            "isEnabled": body.get("isEnabled", True),
            "permissions": json.dumps(permissions),
            "createdAt": now,
            "updatedAt": now,
        }

        # Save to DynamoDB
        api_keys_table.put_item(Item=api_key_item)

        # Prepare response (exclude secret ARN)
        response_item = {
            "id": api_key_item["id"],
            "name": api_key_item["name"],
            "description": api_key_item["description"],
            "isEnabled": api_key_item["isEnabled"],
            "permissions": permissions,
            "createdAt": api_key_item["createdAt"],
            "updatedAt": api_key_item["updatedAt"],
            # Include the full API key value only on creation
            "apiKey": full_api_key,
        }

        return {
            "status": "success",
            "message": "API key created successfully",
            "data": response_item,
        }

    except Exception as e:
        logger.exception("Error creating API key")
        return {
            "status": "error",
            "message": f"Error creating API key: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for API key creation endpoint
    """
    return app.resolve(event, context)
