"""
Unified search orchestrator that routes queries to appropriate providers
and handles the unified search architecture.
"""

import os
import time
from typing import Any, Dict, List, Optional

import boto3
from bedrock_twelvelabs_search_provider import BedrockTwelveLabsSearchProvider
from coactive_search_provider import CoactiveSearchProvider
from twelvelabs_api_search_provider import TwelveLabsAPISearchProvider
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
        self._providers_initialized = False
        self._last_config_check = None
        self._config_cache_ttl = 60  # Reload config every 60 seconds if needed
        self._initialize_provider_classes()

    def _initialize_provider_classes(self):
        """Register all available search provider classes (without loading configs)"""
        self.provider_factory.register_provider("coactive", CoactiveSearchProvider)
        self.provider_factory.register_provider(
            "bedrock_twelvelabs", BedrockTwelveLabsSearchProvider
        )
        self.provider_factory.register_provider(
            "twelvelabs_api", TwelveLabsAPISearchProvider
        )
        self.logger.info("Registered search provider classes")

    def _should_reload_providers(self) -> bool:
        """Check if providers should be reloaded from configuration"""
        if not self._providers_initialized:
            self.logger.info("Providers not yet initialized, will load configurations")
            return True

        # If no providers are available, try reloading (handles config changes)
        if not self._providers:
            self.logger.info("No providers available, will attempt reload")
            return True

        # Reload periodically to pick up configuration changes
        if self._last_config_check:
            elapsed = time.time() - self._last_config_check
            if elapsed > self._config_cache_ttl:
                self.logger.info(
                    f"Config cache expired ({elapsed:.1f}s > {self._config_cache_ttl}s), will reload"
                )
                return True

        return False

    def _ensure_providers_initialized(self):
        """Lazy initialization of providers with cache invalidation"""
        if self._should_reload_providers():
            self.logger.info("Initializing/reloading search providers")
            self._load_provider_configurations()
            self._providers_initialized = True
            self._last_config_check = time.time()
        else:
            self.logger.debug(f"Using cached providers: {list(self._providers.keys())}")

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

            # Get the embedding store configuration
            embedding_store = self._get_embedding_store_type(system_settings_table)
            self.logger.info(f"Using embedding store type: {embedding_store}")

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
                provider_type = item.get("type", "coactive")

                # Map the DynamoDB record structure to expected config format
                if provider_type == "coactive":
                    provider_config = {
                        "provider": "coactive",
                        "provider_location": "external",
                        "architecture": "external_semantic_service",
                        "capabilities": {
                            "media": ["video", "audio", "image"],
                            "semantic": True,
                        },
                        "dataset_id": item.get("datasetId"),
                        "endpoint": item.get("endpoint"),
                        "auth": {
                            "type": "bearer",
                            "secret_arn": item.get("secretArn"),
                        },
                        "metadata_mapping": item.get("metadataMapping", {}),
                        "name": item.get("name", "Coactive AI"),
                        "id": item.get("id"),
                    }
                elif provider_type in ["bedrock twelvelabs", "twelvelabs-bedrock"]:
                    provider_config = {
                        "provider": "bedrock_twelvelabs",
                        "provider_location": "internal",
                        "architecture": "provider_plus_store",
                        "capabilities": {
                            "media": ["video", "audio", "image"],
                            "semantic": True,
                        },
                        "endpoint": item.get("endpoint"),
                        "auth": {
                            "type": "bedrock",
                            "secret_arn": item.get("secretArn"),
                        },
                        "store": embedding_store,
                        "metadata_mapping": item.get("metadataMapping", {}),
                        "name": item.get("name", "Bedrock TwelveLabs"),
                        "id": item.get("id"),
                    }
                elif provider_type in ["twelvelabs", "twelvelabs-api"]:
                    provider_config = {
                        "provider": "twelvelabs_api",
                        "provider_location": "internal",
                        "architecture": "provider_plus_store",
                        "capabilities": {
                            "media": ["video", "audio", "image"],
                            "semantic": True,
                        },
                        "endpoint": item.get(
                            "endpoint", "https://api.twelvelabs.io/v1"
                        ),
                        "auth": {
                            "type": "api_key",
                            "secret_arn": item.get("secretArn"),
                        },
                        "store": embedding_store,
                        "metadata_mapping": item.get("metadataMapping", {}),
                        "name": item.get("name", "TwelveLabs API"),
                        "id": item.get("id"),
                    }
                else:
                    # For unknown types, try to infer from the type string
                    self.logger.warning(
                        f"Unknown provider type: {provider_type}, attempting to infer configuration"
                    )
                    provider_config = {
                        "provider": provider_type,  # Use the type as-is for the provider name
                        "provider_location": "external",
                        "architecture": "external_semantic_service",
                        "capabilities": {
                            "media": ["video", "audio", "image"],
                            "semantic": True,
                        },
                        "dataset_id": item.get("datasetId"),
                        "endpoint": item.get("endpoint"),
                        "auth": {
                            "type": "bearer",
                            "secret_arn": item.get("secretArn"),
                        },
                        "metadata_mapping": item.get("metadataMapping", {}),
                        "name": item.get("name", f"Unknown Provider ({provider_type})"),
                        "id": item.get("id"),
                    }

                configs.append(provider_config)
                self.logger.info(
                    f"Found {provider_type} configuration: {provider_config.get('name')}"
                )

            return configs

        except Exception as e:
            self.logger.error(f"Error loading search provider configs: {str(e)}")
            return []

    def _get_embedding_store_type(self, system_settings_table) -> str:
        """Get the configured embedding store type from DynamoDB"""
        try:
            response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
            )

            if response.get("Item") and response["Item"].get("isEnabled"):
                store_type = response["Item"].get("type", "opensearch")
                # Map DynamoDB type to internal type
                if store_type == "s3-vector":
                    return "s3_vectors"
                elif store_type == "opensearch":
                    return "opensearch"
                else:
                    self.logger.warning(
                        f"Unknown embedding store type: {store_type}, defaulting to opensearch"
                    )
                    return "opensearch"
            else:
                self.logger.info(
                    "No embedding store configuration found, defaulting to opensearch"
                )
                return "opensearch"

        except Exception as e:
            self.logger.error(f"Error loading embedding store config: {str(e)}")
            return "opensearch"  # Safe default

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
            # Ensure providers are initialized (lazy initialization)
            self._ensure_providers_initialized()

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
                # No suitable provider found - handle based on search type
                if search_query.search_type.value == "keyword":
                    # Keyword search always works with OpenSearch directly
                    self.logger.info(
                        "Executing keyword search using OpenSearch directly"
                    )
                    result = self._execute_opensearch_search(query_params)

                    # Add presigned URLs to keyword search results (same as semantic search)
                    self._add_presigned_urls_to_search_results(result)

                    return result
                else:
                    # For semantic searches, we need a configured provider
                    available_providers = (
                        list(self._providers.keys()) if self._providers else []
                    )
                    error_msg = f"No suitable search provider found for semantic search. Available providers: {available_providers}"
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

        except Exception as e:
            self.logger.error(f"Unified search failed: {str(e)}")
            # Re-raise the error - no fallback needed since keyword search is handled directly
            raise RuntimeError(f"Search system failure: {str(e)}")

    def _select_provider(self, query: SearchQuery) -> Optional[BaseSearchProvider]:
        """
        Select the most appropriate provider for the given query.
        Note: Keyword search doesn't require a provider - it uses OpenSearch directly.

        Args:
            query: SearchQuery object

        Returns:
            Selected provider or None (None for keyword search means use OpenSearch directly)
        """
        # For semantic search, we need a configured provider
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

            # Use default provider if available for semantic search
            if self._default_provider and self._default_provider.validate_query(query):
                self.logger.info(
                    f"Using default provider for semantic search: {self._default_provider.config.provider}"
                )
                return self._default_provider

        # For keyword search, always use OpenSearch directly (no external providers)
        else:
            self.logger.info(
                "Keyword search requested - bypassing all providers to use OpenSearch directly"
            )
            return None

        # No provider found - this is fine for keyword search (uses OpenSearch directly)
        # but problematic for semantic search
        if query.search_type.value == "semantic":
            self.logger.warning("No suitable provider found for semantic search")
        else:
            self.logger.info(
                "No provider configured for keyword search - will use OpenSearch directly"
            )

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
            from index import get_indexed_thumbnail_url
            from url_utils import generate_cloudfront_url

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
                    presigned_url = generate_cloudfront_url(
                        bucket=rep_storage_info.get("Bucket", ""),
                        key=rep_storage_info.get("ObjectKey", {}).get("FullPath", ""),
                    )

                    if purpose == "thumbnail":
                        # Use shared function to convert to indexed thumbnail URL
                        thumbnail_url = get_indexed_thumbnail_url(presigned_url)
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

    def _add_presigned_urls_to_search_results(
        self, search_response: Dict[str, Any]
    ) -> None:
        """Add presigned URLs to all results in a search response"""
        try:
            # Navigate to the results array in the search response
            results = search_response.get("data", {}).get("results", [])

            if not results:
                self.logger.debug("No results found to add presigned URLs to")
                return

            # Process each result to add presigned URLs
            for result in results:
                self._add_presigned_urls(result)

            self.logger.info(
                f"Added presigned URLs to {len(results)} keyword search results"
            )

        except Exception as e:
            self.logger.warning(
                f"Failed to add presigned URLs to search results: {str(e)}"
            )
            # Continue without URLs rather than failing the entire request

    def _execute_opensearch_search(
        self, query_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute search using OpenSearch-based system for keyword search"""
        self.logger.info("Executing keyword search using OpenSearch directly")

        try:
            # Import here to avoid circular imports
            import os
            import sys

            # Add current directory to path for imports
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)

            # Import the legacy search components
            from index import SearchParams, perform_search

            # Convert query params to legacy SearchParams, handling missing optional fields
            search_params = {}

            # Required parameter
            search_params["q"] = query_params.get("q", "")

            # Optional parameters with defaults
            search_params["page"] = int(query_params.get("page", 1))
            search_params["pageSize"] = int(query_params.get("pageSize", 50))
            search_params["min_score"] = float(query_params.get("min_score", 0.01))
            search_params["semantic"] = (
                query_params.get("semantic", "false").lower() == "true"
            )

            # Handle optional filter parameters
            if "filters" in query_params:
                search_params["filters"] = query_params["filters"]
            if "search_fields" in query_params:
                search_params["search_fields"] = query_params["search_fields"]
            if "type" in query_params:
                search_params["type"] = query_params["type"]
            if "extension" in query_params:
                search_params["extension"] = query_params["extension"]
            if "LargerThan" in query_params:
                search_params["LargerThan"] = query_params["LargerThan"]
            if "asset_size_lte" in query_params:
                search_params["asset_size_lte"] = query_params["asset_size_lte"]
            if "asset_size_gte" in query_params:
                search_params["asset_size_gte"] = query_params["asset_size_gte"]
            if "ingested_date_lte" in query_params:
                search_params["ingested_date_lte"] = query_params["ingested_date_lte"]
            if "ingested_date_gte" in query_params:
                search_params["ingested_date_gte"] = query_params["ingested_date_gte"]
            if "filename" in query_params:
                search_params["filename"] = query_params["filename"]
            if "storageIdentifier" in query_params:
                search_params["storageIdentifier"] = query_params["storageIdentifier"]

            # Create SearchParams object
            params = SearchParams(**search_params)

            # Execute legacy search
            result = perform_search(params)

            self.logger.info("Legacy search completed successfully")
            return result

        except Exception as e:
            self.logger.error(f"Legacy search fallback failed: {str(e)}")
            self.logger.exception("Full traceback for legacy search failure")

            # Return empty result as last resort
            return {
                "status": "500",
                "message": "Search service temporarily unavailable",
                "data": {
                    "searchMetadata": {
                        "totalResults": 0,
                        "page": int(query_params.get("page", 1)),
                        "pageSize": int(query_params.get("pageSize", 50)),
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
