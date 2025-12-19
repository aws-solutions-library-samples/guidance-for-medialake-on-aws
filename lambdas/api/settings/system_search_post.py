"""Handler for POST /settings/system/search endpoint."""

import http.client
import json
import os
import uuid
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger(child=True)
tracer = Tracer()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")


def create_coactive_dataset(api_key: str, endpoint: str = None) -> dict:
    """
    Create or find existing MediaLake_Dataset_{ENVIRONMENT} in Coactive.

    Args:
        api_key: Coactive personal token
        endpoint: Coactive API endpoint (not used, we use correct hosts)

    Returns:
        dict: Dataset information including datasetId

    Raises:
        Exception: If dataset creation/lookup fails
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    dataset_name = f"MediaLake_Dataset_{environment}"
    try:
        # Step 1: Authenticate to get access token (following working script pattern)
        auth_conn = http.client.HTTPSConnection("api.coactive.ai", timeout=30)

        login_payload = {"grant_type": "refresh_token"}
        login_data = json.dumps(login_payload)

        logger.info("Authenticating with Coactive API using personal token")
        auth_conn.request(
            "POST",
            "/api/v0/login",
            body=login_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "MediaLake/1.0",
            },
        )

        login_response = auth_conn.getresponse()
        login_response_data = login_response.read().decode("utf-8")
        auth_conn.close()

        if login_response.status != 200:
            raise Exception(
                f"Coactive authentication failed: {login_response.status} - {login_response_data}"
            )

        login_json = json.loads(login_response_data)
        access_token = login_json.get("access_token")
        if not access_token:
            raise Exception("No access token received from Coactive authentication")

        logger.info("Successfully obtained Coactive access token")

        # Step 2: Check if MediaLake_Dataset_{ENVIRONMENT} already exists (following working script pattern)
        logger.info(f"Checking for existing {dataset_name}")
        dataset_conn = http.client.HTTPSConnection("app.coactive.ai", timeout=30)

        # List datasets to find existing dataset
        dataset_conn.request(
            "GET",
            "/api/v1/datasets?limit=100",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "MediaLake/1.0",
            },
        )

        list_response = dataset_conn.getresponse()
        list_response_data = list_response.read().decode("utf-8")

        if list_response.status == 200:
            list_json = json.loads(list_response_data)
            datasets = list_json.get("data", [])

            # Look for existing dataset (case insensitive)
            for dataset in datasets:
                if dataset.get("name", "").lower() == dataset_name.lower():
                    dataset_id = dataset.get("datasetId")
                    logger.info(f"Found existing {dataset_name} with ID: {dataset_id}")
                    dataset_conn.close()
                    return dataset

        # Step 3: Create dataset if it doesn't exist
        dataset_payload = {
            "name": dataset_name,
            "description": f"MediaLake unified search dataset for semantic search operations ({environment} environment)",
            "encoder": "multimodal-tx-large3",
        }
        dataset_data = json.dumps(dataset_payload)

        logger.info(f"Creating new {dataset_name} in Coactive")
        dataset_conn.request(
            "POST",
            "/api/v1/datasets",
            body=dataset_data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "MediaLake/1.0",
            },
        )

        create_response = dataset_conn.getresponse()
        create_response_data = create_response.read().decode("utf-8")
        dataset_conn.close()

        if create_response.status != 200:
            raise Exception(
                f"Coactive dataset creation failed: {create_response.status} - {create_response_data}"
            )

        dataset_info = json.loads(create_response_data)
        logger.info(
            f"Successfully created Coactive dataset: {dataset_info.get('datasetId')}"
        )

        return dataset_info

    except Exception as e:
        logger.error(f"Error in create_coactive_dataset: {str(e)}")
        raise


def register_route(app):
    """Register POST /settings/system/search route"""

    @app.post("/settings/system/search")
    @tracer.capture_method
    def settings_system_search_post():
        """Create a new search provider configuration"""
        try:
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
            )

            # Get request body
            body = app.current_event.json_body

            # Manual validation of required fields
            required_fields = ["name", "type"]
            for field in required_fields:
                if field not in body:
                    return {
                        "status": "error",
                        "message": f"Missing required field: {field}",
                        "data": {},
                    }

            # API key is required for certain providers
            if body.get("type") == "twelvelabs-api" and "apiKey" not in body:
                return {
                    "status": "error",
                    "message": "API key is required for Twelve Labs API provider",
                    "data": {},
                }

            if body.get("type") == "coactive" and "apiKey" not in body:
                return {
                    "status": "error",
                    "message": "API key is required for Coactive provider",
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

            # Only create secret for providers that need API keys
            secret_arn = None
            if body.get("apiKey"):
                # Store API key in Secrets Manager
                secret_name = f"medialake/search/provider/{provider_id}"
                secret_value = json.dumps({"x-api-key": body["apiKey"]})

                logger.info(f"Creating secret with name: {secret_name}")

                # Create the secret in Secrets Manager
                secret_response = secretsmanager.create_secret(
                    Name=secret_name,
                    Description=f"API key for {body['name']} search provider",
                    SecretString=secret_value,
                )

                secret_arn = secret_response["ARN"]
                logger.info(f"Secret created successfully with ARN: {secret_arn}")

            # Create new search provider
            now = datetime.utcnow().isoformat()
            search_provider = {
                "PK": "SYSTEM_SETTINGS",
                "SK": "SEARCH_PROVIDER",
                "id": provider_id,
                "name": body["name"],
                "type": body["type"],
                "endpoint": body.get("endpoint"),
                "isEnabled": True,  # Always default to True for new providers
                "createdAt": now,
                "updatedAt": now,
            }

            # Only override isEnabled if explicitly provided in request
            if "isEnabled" in body:
                search_provider["isEnabled"] = body["isEnabled"]

            # Handle Coactive dataset creation
            coactive_dataset_id = None
            if body.get("type") == "coactive" and "apiKey" in body:
                try:
                    environment = os.environ.get("ENVIRONMENT", "dev")
                    dataset_name = f"MediaLake_Dataset_{environment}"
                    logger.info(f"Coactive provider detected - creating {dataset_name}")
                    dataset_info = create_coactive_dataset(
                        api_key=body["apiKey"],
                        endpoint=body.get(
                            "endpoint", "https://app.coactive.ai/api/v1/search"
                        ),
                    )
                    coactive_dataset_id = dataset_info.get("datasetId")
                    logger.info(
                        f"Successfully created Coactive dataset with ID: {coactive_dataset_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create Coactive dataset: {str(e)}")
                    return {
                        "status": "error",
                        "message": f"Failed to create Coactive dataset: {str(e)}",
                        "data": {},
                    }

            # Only add secretArn if we created a secret
            if secret_arn:
                search_provider["secretArn"] = secret_arn
                logger.info(f"Adding secretArn to provider: {secret_arn}")

            # Add datasetId if Coactive dataset was created
            if coactive_dataset_id:
                search_provider["datasetId"] = coactive_dataset_id
                logger.info(f"Adding datasetId to provider: {coactive_dataset_id}")

            logger.info(f"Saving provider to DynamoDB: {search_provider}")

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
            # Don't expose the secret ARN in the response (if it exists)
            response_provider.pop("secretArn", None)
            # Provider is configured if it has a secret ARN or if it's Bedrock (which doesn't need one)
            response_provider["isConfigured"] = (
                bool(secret_arn) or body.get("type") == "twelvelabs-bedrock"
            )

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
