import json
import os
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger

logger = Logger()

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")


def get_search_provider_config() -> Dict[str, Any]:
    """
    Get the search provider configuration from DynamoDB
    """
    try:
        system_settings_table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE"))

        # Get search provider settings
        response = system_settings_table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
        )

        search_provider = response.get("Item", {})

        if not search_provider:
            logger.warning("No search provider configuration found")
            return {"isConfigured": False, "isEnabled": False}

        return search_provider
    except Exception:
        logger.exception("Error retrieving search provider configuration")
        return {"isConfigured": False, "isEnabled": False}


def get_api_key() -> Optional[str]:
    """
    Get the API key from Secrets Manager
    """
    try:
        # Get the search provider configuration
        search_provider = get_search_provider_config()

        # Check if the provider is configured and enabled
        if not search_provider.get("isEnabled", False):
            logger.warning("Search provider is not enabled")
            return None

        # Get the secret ARN
        secret_arn = search_provider.get("secretArn")

        if not secret_arn:
            logger.warning("No secret ARN found in search provider configuration")
            return None

        # Get the secret value
        secret_response = secretsmanager.get_secret_value(SecretId=secret_arn)

        if not secret_response or "SecretString" not in secret_response:
            logger.warning("No secret value found")
            return None

        # Parse the secret value
        secret_data = json.loads(secret_response["SecretString"])

        # Get the API key
        api_key = secret_data.get("x-api-key")

        if not api_key:
            logger.warning("No API key found in secret")
            return None

        return api_key
    except Exception:
        logger.exception("Error retrieving API key")
        return None


def get_endpoint() -> str:
    """
    Get the endpoint URL from the search provider configuration
    """
    try:
        # Get the search provider configuration
        search_provider = get_search_provider_config()

        # Get the endpoint
        endpoint = search_provider.get("endpoint")

        if not endpoint:
            # Return default endpoint
            return "https://api.twelvelabs.io/v1"

        return endpoint
    except Exception:
        logger.exception("Error retrieving endpoint")
        return "https://api.twelvelabs.io/v1"
