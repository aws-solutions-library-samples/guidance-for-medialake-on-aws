"""
Configuration management for search providers.
Handles storing and retrieving search provider configurations from DynamoDB.
"""

import json
import os
from typing import Any, Dict, List, Optional

import boto3
from unified_search_models import ProviderLocation, SearchArchitectureType


class SearchProviderConfigManager:
    """Manages search provider configurations in DynamoDB"""

    def __init__(self, logger):
        self.logger = logger
        self.dynamodb = boto3.resource("dynamodb")
        self.secretsmanager = boto3.client("secretsmanager")
        self.system_settings_table = self.dynamodb.Table(
            os.environ.get("SYSTEM_SETTINGS_TABLE")
        )

    def save_provider_config(self, provider_config: Dict[str, Any]) -> bool:
        """
        Save a search provider configuration to DynamoDB.

        Args:
            provider_config: Provider configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate required fields
            if not provider_config.get("provider"):
                raise ValueError("Provider name is required")

            # Get existing configurations
            existing_configs = self.get_all_provider_configs()

            # Update or add the new configuration
            provider_name = provider_config["provider"]
            updated = False

            for i, config in enumerate(existing_configs):
                if config.get("provider") == provider_name:
                    existing_configs[i] = provider_config
                    updated = True
                    break

            if not updated:
                existing_configs.append(provider_config)

            # Save back to DynamoDB
            response = self.system_settings_table.put_item(
                Item={
                    "PK": "SYSTEM_SETTINGS",
                    "SK": "SEARCH_PROVIDERS",
                    "providers": existing_configs,
                    "lastUpdated": boto3.dynamodb.conditions.Attr(
                        "lastUpdated"
                    ).exists(),
                }
            )

            self.logger.info(f"Saved search provider configuration: {provider_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save provider configuration: {str(e)}")
            return False

    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider configuration or None if not found
        """
        try:
            configs = self.get_all_provider_configs()

            for config in configs:
                if config.get("provider") == provider_name:
                    return config

            return None

        except Exception as e:
            self.logger.error(
                f"Failed to get provider configuration for {provider_name}: {str(e)}"
            )
            return None

    def get_all_provider_configs(self) -> List[Dict[str, Any]]:
        """
        Get all search provider configurations.

        Returns:
            List of provider configurations
        """
        try:
            response = self.system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDERS"}
            )

            if response.get("Item") and response["Item"].get("providers"):
                return response["Item"]["providers"]

            return []

        except Exception as e:
            self.logger.error(f"Failed to get provider configurations: {str(e)}")
            return []

    def delete_provider_config(self, provider_name: str) -> bool:
        """
        Delete a search provider configuration.

        Args:
            provider_name: Name of the provider to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            configs = self.get_all_provider_configs()

            # Filter out the provider to delete
            updated_configs = [
                config for config in configs if config.get("provider") != provider_name
            ]

            if len(updated_configs) == len(configs):
                self.logger.warning(f"Provider {provider_name} not found for deletion")
                return False

            # Save updated configurations
            self.system_settings_table.put_item(
                Item={
                    "PK": "SYSTEM_SETTINGS",
                    "SK": "SEARCH_PROVIDERS",
                    "providers": updated_configs,
                }
            )

            self.logger.info(f"Deleted search provider configuration: {provider_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete provider configuration: {str(e)}")
            return False

    def create_coactive_config(
        self,
        dataset_id: str,
        api_key: str,
        endpoint: Optional[str] = None,
        metadata_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Coactive provider configuration.

        Args:
            dataset_id: Coactive dataset ID
            api_key: Coactive API key
            endpoint: Optional custom endpoint
            metadata_mapping: Optional field mapping

        Returns:
            Coactive configuration dictionary
        """
        # Store API key in Secrets Manager
        secret_arn = self._store_api_key_in_secrets("coactive", api_key)

        config = {
            "provider": "coactive",
            "provider_location": "external",
            "architecture": "external_semantic_service",
            "capabilities": {"media": ["video", "audio", "image"], "semantic": True},
            "dataset_id": dataset_id,
            "endpoint": endpoint or "https://app.coactive.ai/api/v1/search",
            "auth": {"type": "bearer", "secret_arn": secret_arn},
            "metadata_mapping": metadata_mapping
            or {
                "asset_id": "medialake_uuid",
                "mediaType": "media_type",
                "duration": "duration_ms",
            },
        }

        return config

    def create_twelvelabs_config(
        self,
        api_key: str,
        store_type: str = "opensearch",
        endpoint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a TwelveLabs provider configuration.

        Args:
            api_key: TwelveLabs API key
            store_type: Embedding store type (opensearch or s3-vector)
            endpoint: Optional custom endpoint

        Returns:
            TwelveLabs configuration dictionary
        """
        # Store API key in Secrets Manager
        secret_arn = self._store_api_key_in_secrets("twelvelabs", api_key)

        config = {
            "provider": "twelvelabs",
            "provider_location": "external",
            "architecture": "provider_plus_store",
            "capabilities": {"media": ["video", "audio", "image"], "semantic": True},
            "endpoint": endpoint or "https://api.twelvelabs.io/v1",
            "store": store_type,
            "auth": {"type": "api_key", "secret_arn": secret_arn},
        }

        return config

    def _store_api_key_in_secrets(self, provider_name: str, api_key: str) -> str:
        """
        Store API key in AWS Secrets Manager.

        Args:
            provider_name: Name of the provider
            api_key: API key to store

        Returns:
            ARN of the created secret
        """
        try:
            secret_name = f"medialake-search-{provider_name}-api-key"

            # Check if secret already exists
            try:
                response = self.secretsmanager.describe_secret(SecretId=secret_name)
                secret_arn = response["ARN"]

                # Update existing secret
                self.secretsmanager.update_secret(
                    SecretId=secret_arn,
                    SecretString=json.dumps({"api_key": api_key, "token": api_key}),
                )

                self.logger.info(f"Updated existing secret for {provider_name}")

            except self.secretsmanager.exceptions.ResourceNotFoundException:
                # Create new secret
                response = self.secretsmanager.create_secret(
                    Name=secret_name,
                    Description=f"API key for {provider_name} search provider",
                    SecretString=json.dumps({"api_key": api_key, "token": api_key}),
                )

                secret_arn = response["ARN"]
                self.logger.info(f"Created new secret for {provider_name}")

            return secret_arn

        except Exception as e:
            self.logger.error(f"Failed to store API key in Secrets Manager: {str(e)}")
            raise

    def validate_provider_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate a provider configuration.

        Args:
            config: Provider configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Required fields
        required_fields = [
            "provider",
            "provider_location",
            "architecture",
            "capabilities",
        ]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate enums
        try:
            if "provider_location" in config:
                ProviderLocation(config["provider_location"])
        except ValueError:
            errors.append(
                f"Invalid provider_location: {config.get('provider_location')}"
            )

        try:
            if "architecture" in config:
                SearchArchitectureType(config["architecture"])
        except ValueError:
            errors.append(f"Invalid architecture: {config.get('architecture')}")

        # Architecture-specific validation
        if config.get("architecture") == "external_semantic_service":
            if not config.get("dataset_id") and config.get("provider") == "coactive":
                errors.append("dataset_id is required for Coactive provider")

        elif config.get("architecture") == "provider_plus_store":
            if not config.get("store"):
                errors.append("store is required for provider_plus_store architecture")

        # Validate capabilities
        capabilities = config.get("capabilities", {})
        if not isinstance(capabilities, dict):
            errors.append("capabilities must be a dictionary")
        else:
            media_types = capabilities.get("media", [])
            if not isinstance(media_types, list):
                errors.append("capabilities.media must be a list")
            else:
                valid_media_types = ["video", "audio", "image"]
                for media_type in media_types:
                    if media_type not in valid_media_types:
                        errors.append(f"Invalid media type: {media_type}")

        return errors

    def get_provider_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all provider configurations and their status.

        Returns:
            Status summary dictionary
        """
        try:
            configs = self.get_all_provider_configs()

            summary = {
                "total_providers": len(configs),
                "providers": {},
                "architectures": {
                    "provider_plus_store": 0,
                    "external_semantic_service": 0,
                },
                "locations": {"internal": 0, "external": 0},
            }

            for config in configs:
                provider_name = config.get("provider", "unknown")
                architecture = config.get("architecture", "unknown")
                location = config.get("provider_location", "unknown")

                summary["providers"][provider_name] = {
                    "architecture": architecture,
                    "location": location,
                    "capabilities": config.get("capabilities", {}),
                    "configured": True,
                }

                # Count architectures
                if architecture in summary["architectures"]:
                    summary["architectures"][architecture] += 1

                # Count locations
                if location in summary["locations"]:
                    summary["locations"][location] += 1

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get provider status summary: {str(e)}")
            return {
                "total_providers": 0,
                "providers": {},
                "architectures": {
                    "provider_plus_store": 0,
                    "external_semantic_service": 0,
                },
                "locations": {"internal": 0, "external": 0},
                "error": str(e),
            }
