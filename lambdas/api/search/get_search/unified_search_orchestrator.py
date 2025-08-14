"""
Unified search orchestrator that routes queries to appropriate providers
and handles the unified search architecture.
"""

import os
import time
from typing import Any, Dict, List, Optional

import boto3
from coactive_search_provider import CoactiveSearchProvider
from unified_search_models import (
    SearchArchitectureType,
    SearchHit,
    SearchQuery,
    SearchResult,
    create_search_query_from_params,
)
from unified_search_provider import (
    BaseSearchProvider,
    SearchProviderFactory,
    create_search_provider_config,
)


class UnifiedSearchOrchestrator:
    """
    Main orchestrator for unified search that routes queries to appropriate providers
    based on configuration and query requirements.
    """

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
        self.provider_factory = SearchProviderFactory(logger, metrics)
        self._providers = {}
        self._default_provider = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize and register all available search providers"""
        # Register provider classes
        self.provider_factory.register_provider("coactive", CoactiveSearchProvider)

        # Load provider configurations and create instances
        self._load_provider_configurations()

    def _load_provider_configurations(self):
        """Load search provider configurations from system settings"""
        try:
            # Get search provider configurations from DynamoDB
            provider_configs = self._get_search_provider_configs()

            for config_data in provider_configs:
                try:
                    config = create_search_provider_config(config_data)
                    provider = self.provider_factory.create_provider(config)

                    if provider.is_available():
                        self._providers[config.provider] = provider
                        self.logger.info(
                            f"Initialized search provider: {config.provider}"
                        )

                        # Set first available provider as default
                        if self._default_provider is None:
                            self._default_provider = provider
                            self.logger.info(
                                f"Set default search provider: {config.provider}"
                            )
                    else:
                        self.logger.warning(
                            f"Search provider not available: {config.provider}"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Failed to initialize provider {config_data.get('provider', 'unknown')}: {str(e)}"
                    )

        except Exception as e:
            self.logger.error(
                f"Failed to load search provider configurations: {str(e)}"
            )
            # Fall back to legacy embedding store if no providers configured
            self._setup_legacy_fallback()

    def _get_search_provider_configs(self) -> List[Dict[str, Any]]:
        """Get search provider configurations from DynamoDB system settings"""
        try:
            dynamodb = boto3.resource("dynamodb")
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE")
            )

            # Try to get unified search provider configurations
            response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDERS"}
            )

            if response.get("Item") and response["Item"].get("providers"):
                return response["Item"]["providers"]

            # Fall back to checking for individual provider configurations
            configs = []

            # Check for Coactive configuration
            coactive_response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "COACTIVE_SEARCH"}
            )

            if coactive_response.get("Item") and coactive_response["Item"].get(
                "isEnabled"
            ):
                coactive_config = {
                    "provider": "coactive",
                    "provider_location": "external",
                    "architecture": "external_semantic_service",
                    "capabilities": {
                        "media": ["video", "audio", "image"],
                        "semantic": True,
                    },
                    "dataset_id": coactive_response["Item"].get("datasetId"),
                    "endpoint": coactive_response["Item"].get("endpoint"),
                    "auth": {
                        "type": "bearer",
                        "token": self._get_coactive_api_key(
                            coactive_response["Item"].get("secretArn")
                        ),
                    },
                    "metadata_mapping": coactive_response["Item"].get(
                        "metadataMapping", {}
                    ),
                }
                configs.append(coactive_config)

            return configs

        except Exception as e:
            self.logger.error(f"Error loading search provider configs: {str(e)}")
            return []

    def _get_coactive_api_key(self, secret_arn: str) -> Optional[str]:
        """Get Coactive API key from AWS Secrets Manager"""
        if not secret_arn:
            return None

        try:
            secretsmanager = boto3.client("secretsmanager")
            response = secretsmanager.get_secret_value(SecretId=secret_arn)

            if response and "SecretString" in response:
                import json

                secret_data = json.loads(response["SecretString"])
                return secret_data.get("api_key") or secret_data.get("token")

        except Exception as e:
            self.logger.error(f"Failed to get Coactive API key: {str(e)}")

        return None

    def _setup_legacy_fallback(self):
        """Setup fallback to legacy embedding store system"""
        self.logger.info("Setting up legacy embedding store fallback")
        # This will use the existing embedding store factory as fallback
        self._legacy_fallback = True

    def search(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main search method that routes queries to appropriate providers.

        Args:
            query_params: HTTP query parameters

        Returns:
            Search response in MediaLake format
        """
        start_time = time.time()

        try:
            # Parse query parameters into unified SearchQuery
            search_query = create_search_query_from_params(query_params)

            self.logger.info(f"Processing search query: {search_query.query_text}")
            self.logger.info(f"Search type: {search_query.search_type.value}")
            self.logger.info(f"Filters: {search_query.filters}")

            # Route to appropriate provider
            provider = self._select_provider(search_query)

            if provider:
                # Execute search using selected provider
                search_result = provider.search(search_query)

                # Convert to MediaLake response format
                response = self._convert_to_medialake_response(
                    search_result, search_query
                )

                total_time = time.time() - start_time
                self.logger.info(
                    f"Unified search completed in {total_time:.3f}s using provider: {provider.config.provider}"
                )

                return response
            else:
                # Fall back to legacy system
                return self._execute_legacy_search(query_params)

        except Exception as e:
            self.logger.error(f"Unified search failed: {str(e)}")
            # Fall back to legacy system on error
            return self._execute_legacy_search(query_params)

    def _select_provider(self, query: SearchQuery) -> Optional[BaseSearchProvider]:
        """
        Select the most appropriate provider for the given query.

        Args:
            query: SearchQuery object

        Returns:
            Selected provider or None if no suitable provider found
        """
        # For semantic search, prefer external semantic services
        if query.search_type.value == "semantic":
            # Look for external semantic service providers first
            for provider in self._providers.values():
                if (
                    provider.architecture
                    == SearchArchitectureType.EXTERNAL_SEMANTIC_SERVICE
                    and provider.validate_query(query)
                ):
                    self.logger.info(
                        f"Selected external semantic provider: {provider.config.provider}"
                    )
                    return provider

            # Fall back to provider+store for semantic search
            for provider in self._providers.values():
                if (
                    provider.architecture == SearchArchitectureType.PROVIDER_PLUS_STORE
                    and provider.supports_semantic_search()
                    and provider.validate_query(query)
                ):
                    self.logger.info(
                        f"Selected provider+store for semantic: {provider.config.provider}"
                    )
                    return provider

        # For keyword search, prefer provider+store
        else:
            for provider in self._providers.values():
                if (
                    provider.architecture == SearchArchitectureType.PROVIDER_PLUS_STORE
                    and provider.validate_query(query)
                ):
                    self.logger.info(
                        f"Selected provider+store for keyword: {provider.config.provider}"
                    )
                    return provider

        # Use default provider if available
        if self._default_provider and self._default_provider.validate_query(query):
            self.logger.info(
                f"Using default provider: {self._default_provider.config.provider}"
            )
            return self._default_provider

        self.logger.warning("No suitable provider found for query")
        return None

    def _convert_to_medialake_response(
        self, search_result: SearchResult, query: SearchQuery
    ) -> Dict[str, Any]:
        """Convert SearchResult to MediaLake API response format"""
        # Convert SearchHit objects to MediaLake format
        results = []
        for hit in search_result.hits:
            result = self._convert_search_hit_to_medialake_format(hit)
            results.append(result)

        # Create search metadata
        search_metadata = {
            "totalResults": search_result.total_results,
            "page": (query.page_offset // query.page_size) + 1,
            "pageSize": query.page_size,
            "searchTerm": query.query_text,
            "provider": search_result.provider,
            "architecture": search_result.architecture_type.value,
            "providerLocation": search_result.provider_location.value,
            "tookMs": search_result.took_ms,
        }

        if search_result.facets:
            search_metadata["facets"] = search_result.facets

        return {
            "status": "200",
            "message": "ok",
            "data": {"searchMetadata": search_metadata, "results": results},
        }

    def _convert_search_hit_to_medialake_format(self, hit: SearchHit) -> Dict[str, Any]:
        """Convert SearchHit to MediaLake result format"""
        result = {
            "score": hit.score,
            "InventoryID": hit.asset_id,
            "mediaType": hit.media_type.value,
        }

        # Add source data
        if hit.source:
            result.update(hit.source)

        # Add highlights if present
        if hit.highlights:
            result["highlights"] = hit.highlights

        # Add clips if present
        if hit.clips:
            result["clips"] = hit.clips

        # Add provider metadata
        if hit.provider_metadata:
            result["providerMetadata"] = hit.provider_metadata

        return result

    def _execute_legacy_search(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search using legacy embedding store system"""
        self.logger.info("Falling back to legacy search system")

        try:
            # Import and use existing search logic
            from index import SearchParams, perform_search

            # Convert query params to legacy SearchParams
            params = SearchParams(**query_params)

            # Execute legacy search
            return perform_search(params)

        except Exception as e:
            self.logger.error(f"Legacy search fallback failed: {str(e)}")

            # Return empty result as last resort
            return {
                "status": "500",
                "message": "Search service temporarily unavailable",
                "data": {
                    "searchMetadata": {
                        "totalResults": 0,
                        "page": 1,
                        "pageSize": 50,
                        "searchTerm": query_params.get("q", ""),
                    },
                    "results": [],
                },
            }

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all configured providers"""
        status = {
            "providers": {},
            "defaultProvider": (
                self._default_provider.config.provider
                if self._default_provider
                else None
            ),
            "totalProviders": len(self._providers),
        }

        for name, provider in self._providers.items():
            status["providers"][name] = {
                "available": provider.is_available(),
                "architecture": provider.architecture.value,
                "location": provider.provider_location.value,
                "supportedMediaTypes": [
                    mt.value for mt in provider.supported_media_types
                ],
                "supportsSemanticSearch": provider.supports_semantic_search(),
            }

        return status
