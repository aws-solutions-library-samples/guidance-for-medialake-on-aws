"""Handler for GET /settings/system/search endpoint."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")

# Provider metadata with all configuration details
PROVIDER_METADATA = {
    "twelvelabs-api": {
        "id": "twelvelabs-api",
        "name": "TwelveLabs Marengo Embed 2.7 API",
        "type": "twelvelabs",
        "defaultEndpoint": "https://api.twelvelabs.io/v1",
        "requiresApiKey": True,
        "isExternal": False,
        "supportedMediaTypes": ["image", "video", "audio"],
        "dimensions": [1024],
        "inference_provider": "twelvelabs_api",
    },
    "twelvelabs-bedrock": {
        "id": "twelvelabs-bedrock",
        "name": "TwelveLabs Marengo Embed 2.7 on Bedrock",
        "type": "twelvelabs-bedrock",
        "requiresApiKey": False,
        "isExternal": False,
        "supportedMediaTypes": ["image", "video", "audio"],
        "dimensions": [1024],
        "inference_provider": "aws_bedrock",
    },
    "twelvelabs-bedrock-3-0": {
        "id": "twelvelabs-bedrock-3-0",
        "name": "TwelveLabs Marengo Embed 3.0 on Bedrock",
        "type": "twelvelabs-bedrock-3-0",
        "requiresApiKey": False,
        "isExternal": False,
        "supportedMediaTypes": ["image", "video", "audio"],
        "dimensions": [512],
        "inference_provider": "aws_bedrock",
    },
    "coactive": {
        "id": "coactive",
        "name": "Coactive AI",
        "type": "coactive",
        "defaultEndpoint": "https://app.coactive.ai/api/v1/search",
        "requiresApiKey": True,
        "isExternal": True,
        "supportedMediaTypes": ["image", "video"],
        "inference_provider": "coactive_api",
    },
}

# Embedding store metadata
EMBEDDING_STORE_METADATA = {
    "opensearch": {
        "id": "opensearch",
        "name": "OpenSearch",
    },
    "s3-vector": {
        "id": "s3-vector",
        "name": "S3 Vectors",
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
                is_bedrock = original_item.get("type") in [
                    "twelvelabs-bedrock",
                    "twelvelabs-bedrock-3-0",
                ]

                search_provider["isConfigured"] = has_secret or is_bedrock

                # Add provider metadata
                provider_type = search_provider.get("type", "")
                if provider_type in PROVIDER_METADATA:
                    metadata = PROVIDER_METADATA[provider_type]
                    search_provider["isExternal"] = metadata.get("isExternal", False)
                    search_provider["supportedMediaTypes"] = metadata.get(
                        "supportedMediaTypes", []
                    )
                    # Add dimensions if available in metadata
                    if "dimensions" in metadata:
                        search_provider.setdefault(
                            "dimensions", metadata["dimensions"][0]
                        )

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

            # Prepare response with all available providers
            return {
                "status": "success",
                "message": "Search settings retrieved successfully",
                "data": {
                    "searchProvider": (
                        search_provider
                        if search_provider
                        else {
                            "name": "TwelveLabs Marengo Embed 2.7 API",
                            "type": "twelvelabs-api",
                            "isConfigured": False,
                            "isEnabled": False,
                        }
                    ),
                    "embeddingStore": embedding_store,
                    "availableProviders": PROVIDER_METADATA,
                    "availableEmbeddingStores": EMBEDDING_STORE_METADATA,
                },
            }
        except Exception as e:
            logger.exception("Error retrieving search provider")
            return {
                "status": "error",
                "message": f"Error retrieving search provider: {str(e)}",
                "data": {},
            }
