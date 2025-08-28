import json
import os
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
system_settings_table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE"))
secretsmanager = boto3.client("secretsmanager")

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


@app.post("/settings/system/search")
@tracer.capture_method
def create_search_provider():
    """
    Create a new search provider configuration
    """
    try:
        # Get request body
        body = app.current_event.json_body

        # Manual validation of required fields
        required_fields = ["name", "type", "apiKey"]
        for field in required_fields:
            if field not in body:
                return {
                    "status": "error",
                    "message": f"Missing required field: {field}",
                    "data": {},
                }

        # Check if search provider already exists
        existing_provider = system_settings_table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
        ).get("Item")

        if existing_provider:
            return {
                "status": "error",
                "message": "Search provider already exists. Use PUT to update.",
                "data": {},
            }

        # Create a unique identifier for the provider
        provider_id = str(uuid.uuid4())

        # Store API key in Secrets Manager
        secret_name = f"medialake/search/provider/{provider_id}"
        secret_value = json.dumps({"x-api-key": body["apiKey"]})

        # Create the secret in Secrets Manager
        secret_response = secretsmanager.create_secret(
            Name=secret_name,
            Description=f"API key for {body['name']} search provider",
            SecretString=secret_value,
        )

        secret_arn = secret_response["ARN"]

        # Create new search provider without the API key
        now = datetime.utcnow().isoformat()
        search_provider = {
            "PK": "SYSTEM_SETTINGS",
            "SK": "SEARCH_PROVIDER",
            "id": provider_id,
            "name": body["name"],
            "type": body["type"],
            "secretArn": secret_arn,  # Store the ARN of the secret instead of the API key
            "endpoint": body.get("endpoint"),
            "isEnabled": body.get("isEnabled", True),
            "createdAt": now,
            "updatedAt": now,
        }

        # Save to DynamoDB
        system_settings_table.put_item(Item=search_provider)

        # Handle embedding store creation if provided
        embedding_store_response = None
        if "embeddingStore" in body:
            embedding_store_data = body["embeddingStore"]

            # Validate embedding store type
            allowed_embedding_types = ["opensearch", "s3-vector"]
            embedding_type = embedding_store_data.get("type", "opensearch")
            if embedding_type not in allowed_embedding_types:
                embedding_type = "opensearch"  # Default to opensearch if invalid

            # Create embedding store record
            embedding_store_item = {
                "PK": "SYSTEM_SETTINGS",
                "SK": "EMBEDDING_STORE",
                "type": embedding_type,
                "isEnabled": embedding_store_data.get("isEnabled", True),
                "createdAt": now,
                "updatedAt": now,
            }

            # Add config if provided
            if "config" in embedding_store_data:
                embedding_store_item["config"] = embedding_store_data["config"]

            # Save embedding store to DynamoDB
            system_settings_table.put_item(Item=embedding_store_item)

            # Prepare embedding store for response
            embedding_store_response = {
                "type": embedding_store_item["type"],
                "isEnabled": embedding_store_item["isEnabled"],
            }
            if "config" in embedding_store_item:
                embedding_store_response["config"] = embedding_store_item["config"]
        else:
            # Default embedding store
            embedding_store_response = {"type": "opensearch", "isEnabled": True}

        # Remove DynamoDB specific attributes for response
        response_provider = search_provider.copy()
        response_provider.pop("PK")
        response_provider.pop("SK")
        response_provider.pop(
            "secretArn"
        )  # Don't expose the secret ARN in the response
        response_provider["isConfigured"] = True

        # Prepare response
        return {
            "status": "success",
            "message": "Search settings created successfully",
            "data": {
                "searchProvider": response_provider,
                "embeddingStore": embedding_store_response,
            },
        }
    except Exception as e:
        logger.exception("Error creating search provider")
        return {
            "status": "error",
            "message": f"Error creating search provider: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for search provider API
    """
    # Verify origin if needed
    # secret_value = get_secret(os.environ.get("X_ORIGIN_VERIFY_SECRET_ARN"))

    return app.resolve(event, context)
