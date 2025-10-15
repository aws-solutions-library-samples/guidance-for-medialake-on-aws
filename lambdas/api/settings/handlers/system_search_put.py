"""Handler for PUT /settings/system/search endpoint."""

import json
import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")


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

            # Check if search provider exists
            existing_provider = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            ).get("Item")

            if not existing_provider:
                return {
                    "status": "error",
                    "message": "Search provider not found. Use POST to create a new one.",
                    "data": {},
                }

            # Update the secret if API key is provided
            if "apiKey" in body:
                # Get the existing secret ARN
                secret_arn = existing_provider.get("secretArn")

                if secret_arn:
                    # Update the secret
                    secret_value = json.dumps({"x-api-key": body["apiKey"]})

                    secretsmanager.update_secret(
                        SecretId=secret_arn,
                        Description=f"API key for {existing_provider['name']} search provider",
                        SecretString=secret_value,
                    )
                else:
                    # Create a new secret if one doesn't exist
                    secret_name = f"medialake/search/provider/{existing_provider['id']}"
                    secret_value = json.dumps({"x-api-key": body["apiKey"]})

                    secret_response = secretsmanager.create_secret(
                        Name=secret_name,
                        Description=f"API key for {existing_provider['name']} search provider",
                        SecretString=secret_value,
                    )

                    # Add the secret ARN to the update expression
                    existing_provider["secretArn"] = secret_response["ARN"]

            # Prepare update expression
            update_expression_parts = ["SET updatedAt = :updatedAt"]
            expression_attribute_values = {":updatedAt": datetime.utcnow().isoformat()}
            expression_attribute_names = {}

            # Add fields to update
            if "name" in body:
                update_expression_parts.append("name = :name")
                expression_attribute_values[":name"] = body["name"]

            if "endpoint" in body:
                update_expression_parts.append("endpoint = :endpoint")
                expression_attribute_values[":endpoint"] = body["endpoint"]

            if "isEnabled" in body:
                update_expression_parts.append("isEnabled = :isEnabled")
                expression_attribute_values[":isEnabled"] = body["isEnabled"]

            if "type" in body:
                update_expression_parts.append("#type = :type")
                expression_attribute_values[":type"] = body["type"]
                expression_attribute_names["#type"] = "type"

            # Add secretArn to update expression if it was created for API key update
            if "apiKey" in body and "secretArn" in existing_provider:
                update_expression_parts.append("secretArn = :secretArn")
                expression_attribute_values[":secretArn"] = existing_provider[
                    "secretArn"
                ]

            # Update search provider
            update_expression = " , ".join(update_expression_parts)

            # Prepare update_item parameters
            update_params = {
                "Key": {"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"},
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }

            # Add ExpressionAttributeNames if type field is being updated
            if expression_attribute_names:
                update_params["ExpressionAttributeNames"] = expression_attribute_names

            response = system_settings_table.update_item(**update_params)

            # Get updated item
            updated_provider = response.get("Attributes", {})

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
            return {
                "status": "success",
                "message": "Search settings updated successfully",
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
