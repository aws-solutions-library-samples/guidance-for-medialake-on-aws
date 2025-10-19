"""Handler for DELETE /settings/system/search endpoint."""

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
    """Register DELETE /settings/system/search route"""

    @app.delete("/settings/system/search")
    @tracer.capture_method
    def settings_system_search_delete():
        """Delete search provider configuration and reset to default state"""
        try:
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
            )

            # Check if search provider exists
            existing_provider = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            ).get("Item")

            if not existing_provider:
                return {
                    "status": "error",
                    "message": "Search provider not found.",
                    "data": {},
                }

            # Delete the secret if it exists
            secret_arn = existing_provider.get("secretArn")
            if secret_arn:
                try:
                    secretsmanager.delete_secret(
                        SecretId=secret_arn, ForceDeleteWithoutRecovery=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete secret {secret_arn}: {str(e)}")
                    # Continue with provider deletion even if secret deletion fails

            # Delete the search provider record
            system_settings_table.delete_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            )

            # Reset embedding store to default
            embedding_store_item = {
                "PK": "SYSTEM_SETTINGS",
                "SK": "EMBEDDING_STORE",
                "type": "opensearch",
                "isEnabled": False,
                "updatedAt": datetime.utcnow().isoformat(),
            }

            # Check if embedding store exists to preserve createdAt
            existing_embedding_store = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
            ).get("Item")

            if existing_embedding_store:
                embedding_store_item["createdAt"] = existing_embedding_store.get(
                    "createdAt", embedding_store_item["updatedAt"]
                )
            else:
                embedding_store_item["createdAt"] = embedding_store_item["updatedAt"]

            # Update embedding store
            system_settings_table.put_item(Item=embedding_store_item)

            # Prepare response with default state
            return {
                "status": "success",
                "message": "Search provider deleted successfully",
                "data": {
                    "searchProvider": {
                        "name": "TwelveLabs API",
                        "type": "twelvelabs-api",
                        "isConfigured": False,
                        "isEnabled": False,
                    },
                    "embeddingStore": {
                        "type": "opensearch",
                        "isEnabled": False,
                    },
                },
            }
        except Exception as e:
            logger.exception("Error deleting search provider")
            return {
                "status": "error",
                "message": f"Error deleting search provider: {str(e)}",
                "data": {},
            }
