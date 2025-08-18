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
            self.logger.info(f"Found {len(provider_configs)} provider configurations")

            for config_data in provider_configs:
                try:
                    self.logger.info(
                        f"Processing provider config: {config_data.get('provider', 'unknown')}"
                    )
                    config = create_search_provider_config(config_data)
                    provider = self.provider_factory.create_provider(config)

                    self.logger.info(
                        f"Created provider instance for: {config.provider}"
                    )

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

            self.logger.info(f"Total providers loaded: {len(self._providers)}")

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

            # Check for Coactive configuration with correct DynamoDB key
            coactive_response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
            )

            self.logger.info(
                f"DynamoDB response for SEARCH_PROVIDER: {coactive_response}"
            )

            if coactive_response.get("Item") and coactive_response["Item"].get(
                "isEnabled"
            ):
                item = coactive_response["Item"]
                # Map the DynamoDB record structure to expected config format
                coactive_config = {
                    "provider": item.get(
                        "type", "coactive"
                    ),  # Use 'type' field from DB
                    "provider_location": "external",
                    "architecture": "external_semantic_service",
                    "capabilities": {
                        "media": ["video", "audio", "image"],
                        "semantic": True,
                    },
                    "dataset_id": item.get(
                        "datasetId"
                    ),  # Now populated by PUT endpoint when Coactive dataset is created
                    "endpoint": item.get("endpoint"),
                    "auth": {
                        "type": "bearer",
                        "secret_arn": item.get("secretArn"),
                    },
                    "metadata_mapping": item.get("metadataMapping", {}),
                    "name": item.get("name", "Coactive AI"),
                    "id": item.get("id"),
                }
                configs.append(coactive_config)
                self.logger.info(
                    f"Found Coactive configuration: {item.get('name', 'Coactive AI')}"
                )

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
                # No suitable provider found - raise error instead of fallback
                available_providers = (
                    list(self._providers.keys()) if self._providers else []
                )
                error_msg = f"No suitable search provider found for query. Available providers: {available_providers}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

        except Exception as e:
            self.logger.error(f"Unified search failed: {str(e)}")
            # Re-raise the error instead of falling back to legacy system
            raise RuntimeError(f"Search system failure: {str(e)}")

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

        # Create search metadata in expected MediaLake format
        search_metadata = {
            "totalResults": search_result.total_results,
            "page": (query.page_offset // query.page_size) + 1,
            "pageSize": query.page_size,
            "searchTerm": query.query_text,
            "facets": search_result.facets if search_result.facets else None,
            "suggestions": None,
        }

        return {
            "status": "200",
            "message": "ok",
            "data": {"searchMetadata": search_metadata, "results": results},
        }

    def _convert_search_hit_to_medialake_format(self, hit: SearchHit) -> Dict[str, Any]:
        """Convert SearchHit to MediaLake result format"""
        # Return the OpenSearch record exactly as it is
        if hit.source:
            result = hit.source.copy()

            # Add presigned URLs for thumbnails and proxies
            self._add_presigned_urls(result)

            return result
        else:
            # Fallback if no source data
            return {"InventoryID": hit.asset_id}

    def _add_presigned_urls(self, result: Dict[str, Any]) -> None:
        """Add presigned URLs for thumbnail and proxy representations"""
        try:
            # Import here to avoid circular imports
            from search_utils import generate_presigned_url

            derived_representations = result.get("DerivedRepresentations", [])
            thumbnail_url = None
            proxy_url = None

            # Process derived representations for thumbnails and proxies
            for representation in derived_representations:
                purpose = representation.get("Purpose")
                rep_storage_info = representation.get("StorageInfo", {}).get(
                    "PrimaryLocation", {}
                )

                if rep_storage_info.get("StorageType") == "s3":
                    presigned_url = generate_presigned_url(
                        bucket=rep_storage_info.get("Bucket", ""),
                        key=rep_storage_info.get("ObjectKey", {}).get("FullPath", ""),
                    )

                    if purpose == "thumbnail":
                        thumbnail_url = presigned_url
                    elif purpose == "proxy":
                        proxy_url = presigned_url

                if thumbnail_url and proxy_url:
                    break

            # Add URLs to result
            if thumbnail_url:
                result["thumbnailUrl"] = thumbnail_url
            if proxy_url:
                result["proxyUrl"] = proxy_url

        except Exception as e:
            self.logger.warning(f"Failed to generate presigned URLs: {str(e)}")
            # Continue without URLs rather than failing the entire request

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
