"""Handler for GET /settings/system/search endpoint."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")

# Provider metadata with capabilities and location info
PROVIDER_METADATA = {
    "twelvelabs-api": {
        "name": "TwelveLabs API",
        "isExternal": True,
        "supportedMediaTypes": ["image", "video", "audio"],
    },
    "twelvelabs-bedrock": {
        "name": "TwelveLabs Bedrock",
        "isExternal": False,
        "supportedMediaTypes": ["image", "video", "audio"],
    },
    "coactive": {
        "name": "Coactive AI",
        "isExternal": True,
        "supportedMediaTypes": ["image", "video"],
    },
}


def register_route(app):
    """Register GET /settings/system/search route"""

    @app.get("/settings/system/search")
    @tracer.capture_method
    def settings_system_search_get():
        """Get search provider and embedding store configuration"""
        try:
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
            )

            # Get search provider settings
            provider_response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            )

            search_provider = provider_response.get("Item", {})
            logger.info(f"Retrieved search_provider: {search_provider}")

            # Remove DynamoDB specific attributes
            if search_provider:
                # Create a proper copy of the original item BEFORE modifying search_provider
                original_item = provider_response.get("Item", {}).copy()

                search_provider.pop("PK", None)
                search_provider.pop("SK", None)

                # Don't expose the secret ARN in the response
                search_provider.pop("secretArn", None)

                # Add isConfigured flag - true if secretArn exists OR if it's Bedrock (which doesn't need one)
                has_secret = "secretArn" in original_item  # pragma: allowlist secret
                is_bedrock = original_item.get("type") == "twelvelabs-bedrock"

                search_provider["isConfigured"] = has_secret or is_bedrock

                # Add provider metadata (location and supported media types)
                provider_type = search_provider.get("type", "")
                if provider_type in PROVIDER_METADATA:
                    metadata = PROVIDER_METADATA[provider_type]
                    search_provider["isExternal"] = metadata["isExternal"]
                    search_provider["supportedMediaTypes"] = metadata[
                        "supportedMediaTypes"
                    ]

            # Get embedding store settings
            embedding_response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
            )

            embedding_store = embedding_response.get("Item", {})

            # Remove DynamoDB specific attributes and prepare embedding store data
            if embedding_store:
                embedding_store.pop("PK", None)
                embedding_store.pop("SK", None)
            else:
                # Default embedding store configuration
                embedding_store = {"type": "opensearch", "isEnabled": True}

            # Prepare response
            return {
                "status": "success",
                "message": "Search settings retrieved successfully",
                "data": {
                    "searchProvider": (
                        search_provider
                        if search_provider
                        else {
                            "name": "TwelveLabs API",
                            "type": "twelvelabs-api",
                            "isConfigured": False,
                            "isEnabled": False,
                        }
                    ),
                    "embeddingStore": embedding_store,
                },
            }
        except Exception as e:
            logger.exception("Error retrieving search provider")
            return {
                "status": "error",
                "message": f"Error retrieving search provider: {str(e)}",
                "data": {},
            }
