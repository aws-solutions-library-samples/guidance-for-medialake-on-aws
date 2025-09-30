"""
External Service Manager
=======================
Centralized manager for external service plugins that handle asset lifecycle events.
This provides a unified interface for managing external service integrations.
"""

import json
import os
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics
from coactive_plugin import CoactivePlugin
from search_provider_base import ExternalServicePluginManager
from search_provider_models import (
    AssetDeletionResult,
    SearchProviderConfig,
    create_search_provider_config,
)
from twelvelabs_plugin import TwelveLabsPlugin


class MediaLakeExternalServiceManager:
    """
    Centralized manager for external service plugins.
    Handles discovery, configuration, and orchestration of external service operations.
    """

    def __init__(
        self, logger: Optional[Logger] = None, metrics: Optional[Metrics] = None
    ):
        self.logger = logger or Logger()
        self.metrics = metrics or Metrics()

        # Initialize plugin manager
        self.plugin_manager = ExternalServicePluginManager(self.logger, self.metrics)

        # Register built-in plugins
        self._register_builtin_plugins()

        # AWS clients
        self.dynamodb = boto3.resource("dynamodb")
        self.system_settings_table_name = os.environ.get("SYSTEM_SETTINGS_TABLE", "")

    def _register_builtin_plugins(self):
        """Register built-in external service plugins"""
        self.plugin_manager.register_plugin("coactive", CoactivePlugin)
        self.plugin_manager.register_plugin("twelvelabs", TwelveLabsPlugin)
        self.logger.info(
            "Registered built-in external service plugins: coactive, twelvelabs"
        )

    def get_search_provider_config(self) -> Dict[str, Any]:
        """
        Get the search provider configuration from DynamoDB (same as search lambda)
        """
        try:
            if not self.system_settings_table_name:
                self.logger.warning("SYSTEM_SETTINGS_TABLE not configured")
                return {"isConfigured": False, "isEnabled": False}

            table = self.dynamodb.Table(self.system_settings_table_name)

            # Get search provider settings (same key as search lambda)
            response = table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            )

            search_provider = response.get("Item", {})

            if not search_provider:
                self.logger.warning("No search provider configuration found")
                return {"isConfigured": False, "isEnabled": False}

            return search_provider
        except Exception:
            self.logger.exception("Error retrieving search provider configuration")
            return {"isConfigured": False, "isEnabled": False}

    def get_api_key_from_secret(self, secret_arn: str) -> Optional[str]:
        """
        Get API key from Secrets Manager (same pattern as search lambda)
        """
        try:
            if not secret_arn:
                self.logger.warning("No secret ARN provided")
                return None

            secretsmanager = boto3.client("secretsmanager")

            # Get the secret value
            secret_response = secretsmanager.get_secret_value(SecretId=secret_arn)

            if not secret_response or "SecretString" not in secret_response:
                self.logger.warning("No secret value found")
                return None

            # Parse the secret value
            secret_data = json.loads(secret_response["SecretString"])

            # Get the API key (try both x-api-key and token formats)
            api_key = secret_data.get("x-api-key") or secret_data.get("token")

            if not api_key:
                self.logger.warning("No API key found in secret")
                return None

            return api_key
        except Exception:
            self.logger.exception("Error retrieving API key from secret")
            return None

    def get_configured_search_providers(self) -> List[SearchProviderConfig]:
        """Get configured search provider as a list (for compatibility with existing code)"""
        search_provider_config = self.get_search_provider_config()

        if not search_provider_config.get("isEnabled", False):
            self.logger.info("Search provider not enabled")
            return []

        provider_type = search_provider_config.get("type", "").lower()
        if not provider_type:
            self.logger.warning("No provider type specified in configuration")
            return []

        try:
            # Convert single DynamoDB item to SearchProviderConfig
            provider_data = {
                "provider": provider_type,
                "provider_location": (
                    "internal" if provider_type == "bedrock twelvelabs" else "external"
                ),
                "architecture": (
                    "external_semantic_service"
                    if provider_type == "coactive"
                    else "provider_plus_store"
                ),
                "auth": (
                    {"secret_arn": search_provider_config.get("secretArn")}
                    if search_provider_config.get("secretArn")
                    else None
                ),
                "endpoint": search_provider_config.get("endpoint"),
                "dataset_id": search_provider_config.get("datasetId"),
                "capabilities": {
                    "media": ["image", "video", "audio"],
                    "semantic": True,
                },
            }

            config = create_search_provider_config(provider_data)
            self.logger.info(f"Found configured search provider: {provider_type}")
            return [config]

        except Exception as e:
            self.logger.error(f"Failed to parse search provider config: {e}")
            return []

    def delete_asset_from_external_services(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> Dict[str, AssetDeletionResult]:
        """
        Delete asset from all configured external services.

        Args:
            asset_record: The complete asset record from DynamoDB
            inventory_id: The inventory ID of the asset

        Returns:
            Dictionary mapping service names to deletion results
        """
        results = {}

        try:
            # Get configured search providers
            search_providers = self.get_configured_search_providers()

            if not search_providers:
                self.logger.info(
                    "No search providers configured - skipping external service deletion"
                )
                return results

            asset_type = asset_record.get("DigitalSourceAsset", {}).get("Type", "")
            self.logger.info(
                f"Deleting asset {inventory_id} (type: {asset_type}) from external services"
            )

            # Process each configured provider
            for provider_config in search_providers:
                service_name = provider_config.provider

                try:
                    # Create plugin instance
                    plugin_config = {
                        "dataset_id": provider_config.dataset_id,
                        "auth": provider_config.auth,
                        "endpoint": provider_config.endpoint,
                        "capabilities": provider_config.capabilities,
                    }

                    plugin = self.plugin_manager.create_plugin(
                        service_name, plugin_config
                    )

                    # Check if plugin is available and supports this asset type
                    if not plugin.is_available():
                        self.logger.info(
                            f"Service {service_name} not available - skipping"
                        )
                        results[service_name] = AssetDeletionResult(
                            success=True,
                            message=f"Service {service_name} not available",
                            deleted_count=0,
                        )
                        continue

                    if not plugin.supports_asset_type(asset_type):
                        self.logger.info(
                            f"Service {service_name} does not support asset type {asset_type} - skipping"
                        )
                        results[service_name] = AssetDeletionResult(
                            success=True,
                            message=f"Asset type {asset_type} not supported",
                            deleted_count=0,
                        )
                        continue

                    # Perform deletion
                    result = plugin.delete_asset(asset_record, inventory_id)
                    results[service_name] = result

                    if result.success:
                        self.logger.info(
                            f"Successfully processed deletion for {service_name}: {result.message}"
                        )
                    else:
                        self.logger.warning(
                            f"Deletion failed for {service_name}: {result.message}"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error processing deletion for {service_name}: {str(e)}"
                    )
                    results[service_name] = AssetDeletionResult(
                        success=False,
                        message=f"Exception occurred: {str(e)}",
                        errors=[str(e)],
                    )

            # Log summary
            total_deleted = sum(result.deleted_count for result in results.values())
            successful_services = [
                name for name, result in results.items() if result.success
            ]
            failed_services = [
                name for name, result in results.items() if not result.success
            ]

            self.logger.info(
                f"External service deletion summary for {inventory_id}: "
                f"{total_deleted} items deleted, "
                f"{len(successful_services)} services succeeded, "
                f"{len(failed_services)} services failed"
            )

            # Record metrics
            if total_deleted > 0:
                self.metrics.add_metric(
                    name="ExternalServiceDeletions", unit="Count", value=total_deleted
                )

            if failed_services:
                self.metrics.add_metric(
                    name="ExternalServiceDeletionFailures",
                    unit="Count",
                    value=len(failed_services),
                )

        except Exception as e:
            self.logger.error(
                f"Failed to delete asset from external services: {str(e)}"
            )
            results["error"] = AssetDeletionResult(
                success=False,
                message=f"External service manager error: {str(e)}",
                errors=[str(e)],
            )

        return results

    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all configured external services"""
        status = {}

        try:
            search_providers = self.get_configured_search_providers()

            for provider_config in search_providers:
                service_name = provider_config.provider

                try:
                    plugin_config = {
                        "dataset_id": provider_config.dataset_id,
                        "auth": provider_config.auth,
                        "endpoint": provider_config.endpoint,
                        "capabilities": provider_config.capabilities,
                    }

                    plugin = self.plugin_manager.create_plugin(
                        service_name, plugin_config
                    )

                    status[service_name] = {
                        "available": plugin.is_available(),
                        "supported_media_types": plugin.config.get(
                            "capabilities", {}
                        ).get("media", []),
                        "endpoint": provider_config.endpoint,
                        "has_dataset_id": bool(provider_config.dataset_id),
                        "has_auth": bool(provider_config.auth),
                    }

                except Exception as e:
                    status[service_name] = {"available": False, "error": str(e)}

        except Exception as e:
            self.logger.error(f"Failed to get service status: {str(e)}")
            status["error"] = str(e)

        return status


# Convenience function for easy import
def create_external_service_manager(
    logger: Optional[Logger] = None, metrics: Optional[Metrics] = None
) -> MediaLakeExternalServiceManager:
    """Create and return a configured external service manager"""
    return MediaLakeExternalServiceManager(logger, metrics)
