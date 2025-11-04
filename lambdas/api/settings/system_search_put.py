"""Handler for PUT /settings/system/search endpoint."""

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


def create_coactive_dataset(api_key: str, endpoint: str) -> dict:
    """
    Create or find existing MediaLake_Dataset_{ENVIRONMENT} in Coactive and return the dataset information

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

        logger.info(f"Checking for existing {dataset_name}")
        dataset_conn = http.client.HTTPSConnection("app.coactive.ai", timeout=30)

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

            for dataset in datasets:
                if dataset.get("name", "").lower() == dataset_name.lower():
                    dataset_id = dataset.get("datasetId")
                    logger.info(f"Found existing {dataset_name} with ID: {dataset_id}")
                    dataset_conn.close()
                    return dataset

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

    except http.client.HTTPException as e:
        logger.error(f"HTTP error during Coactive dataset operation: {str(e)}")
        raise Exception(f"HTTP error during Coactive dataset operation: {str(e)}")
    except Exception as e:
        logger.error(f"Error with Coactive dataset: {str(e)}")
        raise


def get_coactive_api_key(secret_arn: str) -> str:
    """
    Retrieve Coactive API key from AWS Secrets Manager

    Args:
        secret_arn: ARN of the secret containing the API key

    Returns:
        str: The API key
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_arn)
        secret_string = response["SecretString"]

        try:
            secret_data = json.loads(secret_string)
            return (
                secret_data.get("x-api-key")
                or secret_data.get("apiKey")
                or secret_data.get("personalToken")
            )
        except json.JSONDecodeError:
            return secret_string

    except Exception as e:
        logger.error(f"Error retrieving Coactive API key: {str(e)}")
        raise Exception(f"Failed to retrieve Coactive API key: {str(e)}")


def register_route(app):
    """Register PUT /settings/system/search route"""

    @app.put("/settings/system/search")
    @tracer.capture_method
    def settings_system_search_put():
        """Update an existing search provider configuration"""
        try:
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
            )

            # Get request body
            body = app.current_event.json_body

            # Manual validation of request body
            allowed_fields = [
                "name",
                "type",
                "apiKey",
                "endpoint",
                "isEnabled",
                "embeddingStore",
            ]
            for field in body:
                if field not in allowed_fields:
                    return {
                        "status": "error",
                        "message": f"Invalid field: {field}. Allowed fields are: {', '.join(allowed_fields)}",
                        "data": {},
                    }

            # Validate embedding store if provided
            if "embeddingStore" in body:
                embedding_store = body["embeddingStore"]
                if not isinstance(embedding_store, dict):
                    return {
                        "status": "error",
                        "message": "embeddingStore must be an object",
                        "data": {},
                    }

                allowed_embedding_types = ["opensearch", "s3-vector"]
                if (
                    "type" in embedding_store
                    and embedding_store["type"] not in allowed_embedding_types
                ):
                    return {
                        "status": "error",
                        "message": f"Invalid embedding store type. Allowed types are: {', '.join(allowed_embedding_types)}",
                        "data": {},
                    }

            # Check if search provider exists
            existing_provider = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            ).get("Item")

            # If no provider exists, we'll create a new one (upsert behavior)
            is_creating_new = not existing_provider

            if is_creating_new:
                # Validate required fields for creation
                required_fields = ["name", "type", "apiKey"]
                for field in required_fields:
                    if field not in body:
                        return {
                            "status": "error",
                            "message": f"Missing required field for creation: {field}",
                            "data": {},
                        }

                provider_id = str(uuid.uuid4())
                logger.info(f"Creating new search provider with ID: {provider_id}")
            else:
                provider_id = existing_provider.get("id")
                logger.info(f"Updating existing search provider with ID: {provider_id}")

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

            # Handle secret creation/update if API key is provided
            secret_arn = None
            if "apiKey" in body:
                if is_creating_new:
                    secret_name = f"medialake/search/provider/{provider_id}"
                    secret_value = json.dumps({"x-api-key": body["apiKey"]})

                    secret_response = secretsmanager.create_secret(
                        Name=secret_name,
                        Description=f"API key for {body['name']} search provider",
                        SecretString=secret_value,
                    )
                    secret_arn = secret_response["ARN"]
                    logger.info(f"Created new secret with ARN: {secret_arn}")
                else:
                    existing_secret_arn = existing_provider.get("secretArn")

                    if existing_secret_arn:
                        secret_value = json.dumps({"x-api-key": body["apiKey"]})

                        secretsmanager.update_secret(
                            SecretId=existing_secret_arn,
                            Description=f"API key for {existing_provider['name']} search provider",
                            SecretString=secret_value,
                        )
                        secret_arn = existing_secret_arn
                        logger.info(f"Updated existing secret: {secret_arn}")
                    else:
                        secret_name = (
                            f"medialake/search/provider/{existing_provider['id']}"
                        )
                        secret_value = json.dumps({"x-api-key": body["apiKey"]})

                        secret_response = secretsmanager.create_secret(
                            Name=secret_name,
                            Description=f"API key for {existing_provider['name']} search provider",
                            SecretString=secret_value,
                        )
                        secret_arn = secret_response["ARN"]
                        logger.info(
                            f"Created new secret for existing provider: {secret_arn}"
                        )

            # Handle DynamoDB operation (create or update)
            now = datetime.utcnow().isoformat()

            if is_creating_new:
                search_provider_item = {
                    "PK": "SYSTEM_SETTINGS",
                    "SK": "SEARCH_PROVIDER",
                    "id": provider_id,
                    "name": body["name"],
                    "type": body["type"],
                    "endpoint": body.get("endpoint"),
                    "isEnabled": body.get("isEnabled", True),
                    "createdAt": now,
                    "updatedAt": now,
                }

                if secret_arn:
                    search_provider_item["secretArn"] = secret_arn

                if coactive_dataset_id:
                    search_provider_item["datasetId"] = coactive_dataset_id

                system_settings_table.put_item(Item=search_provider_item)
                updated_provider = search_provider_item
                logger.info(f"Created new search provider: {provider_id}")
            else:
                update_expression_parts = ["SET updatedAt = :updatedAt"]
                expression_attribute_values = {":updatedAt": now}
                expression_attribute_names = {}

                if "name" in body:
                    update_expression_parts.append("#name = :name")
                    expression_attribute_values[":name"] = body["name"]
                    expression_attribute_names["#name"] = "name"

                if "type" in body:
                    update_expression_parts.append("#type = :type")
                    expression_attribute_values[":type"] = body["type"]
                    expression_attribute_names["#type"] = "type"

                if "endpoint" in body:
                    update_expression_parts.append("endpoint = :endpoint")
                    expression_attribute_values[":endpoint"] = body["endpoint"]

                if "isEnabled" in body:
                    update_expression_parts.append("isEnabled = :isEnabled")
                    expression_attribute_values[":isEnabled"] = body["isEnabled"]

                if coactive_dataset_id:
                    update_expression_parts.append("datasetId = :datasetId")
                    expression_attribute_values[":datasetId"] = coactive_dataset_id

                if secret_arn:
                    update_expression_parts.append("secretArn = :secretArn")
                    expression_attribute_values[":secretArn"] = secret_arn

                update_expression = " , ".join(update_expression_parts)

                update_params = {
                    "Key": {"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"},
                    "UpdateExpression": update_expression,
                    "ExpressionAttributeValues": expression_attribute_values,
                    "ReturnValues": "ALL_NEW",
                }

                if expression_attribute_names:
                    update_params["ExpressionAttributeNames"] = (
                        expression_attribute_names
                    )

                response = system_settings_table.update_item(**update_params)
                updated_provider = response.get("Attributes", {})
                logger.info(f"Updated existing search provider: {provider_id}")

            # Remove DynamoDB specific attributes for response
            if updated_provider:
                updated_provider.pop("PK", None)
                updated_provider.pop("SK", None)
                # Don't expose the secret ARN in the response
                has_secret = updated_provider.pop("secretArn", None) is not None
                # Provider is configured if it has a secret ARN or if it's Bedrock (which doesn't need one)
                is_bedrock = updated_provider.get("type") == "twelvelabs-bedrock"
                updated_provider["isConfigured"] = has_secret or is_bedrock

            # Handle embedding store update if provided
            updated_embedding_store = None
            if "embeddingStore" in body:
                embedding_store_data = body["embeddingStore"]

                # Prepare embedding store record
                embedding_store_item = {
                    "PK": "SYSTEM_SETTINGS",
                    "SK": "EMBEDDING_STORE",
                    "type": embedding_store_data.get("type", "opensearch"),
                    "isEnabled": embedding_store_data.get("isEnabled", True),
                    "updatedAt": datetime.utcnow().isoformat(),
                }

                # Add config if provided
                if "config" in embedding_store_data:
                    embedding_store_item["config"] = embedding_store_data["config"]

                # Check if embedding store record exists
                existing_embedding_store = system_settings_table.get_item(
                    Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
                ).get("Item")

                if not existing_embedding_store:
                    # Create new embedding store record
                    embedding_store_item["createdAt"] = embedding_store_item[
                        "updatedAt"
                    ]

                # Update or create embedding store record
                system_settings_table.put_item(Item=embedding_store_item)

                # Prepare embedding store for response
                updated_embedding_store = {
                    "type": embedding_store_item["type"],
                    "isEnabled": embedding_store_item["isEnabled"],
                }
                if "config" in embedding_store_item:
                    updated_embedding_store["config"] = embedding_store_item["config"]

            # Get current embedding store if not updated
            if updated_embedding_store is None:
                embedding_response = system_settings_table.get_item(
                    Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
                )
                embedding_store = embedding_response.get("Item", {})

                if embedding_store:
                    embedding_store.pop("PK", None)
                    embedding_store.pop("SK", None)
                    embedding_store.pop("createdAt", None)
                    embedding_store.pop("updatedAt", None)
                    updated_embedding_store = embedding_store
                else:
                    updated_embedding_store = {"type": "opensearch", "isEnabled": True}

            # Prepare response
            action_message = "created" if is_creating_new else "updated"
            return {
                "status": "success",
                "message": f"Search settings {action_message} successfully",
                "data": {
                    "searchProvider": updated_provider,
                    "embeddingStore": updated_embedding_store,
                },
            }
        except Exception as e:
            logger.exception("Error updating search provider")
            return {
                "status": "error",
                "message": f"Error updating search provider: {str(e)}",
                "data": {},
            }
