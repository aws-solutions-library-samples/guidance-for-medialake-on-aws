"""
Unified search orchestrator that routes queries to appropriate providers
and handles the unified search architecture.

Index Routing Logic (Phase 3):
- twelvelabs / twelvelabs-bedrock → Query 'media' index (Marengo 2.7)
- twelvelabs-bedrock-3-0 → Query 'asset-embeddings' index (Marengo 3.0)
- s3-vector → Uses S3 Vector Store (no OpenSearch index)
- coactive → Query 'media' index
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import boto3
from bedrock_twelvelabs_search_provider import BedrockTwelveLabsSearchProvider
from coactive_search_provider import CoactiveSearchProvider
from search_provider_models import DEFAULT_PAGE_SIZE
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

# Global DynamoDB resource — reused across all orchestrator methods
_dynamodb_resource = boto3.resource("dynamodb")

# Global Secrets Manager client — reused across all orchestrator methods
_secretsmanager_client = boto3.client("secretsmanager")

# Provider type to index mapping constants
PROVIDER_INDEX_MAPPING = {
    # Marengo 2.7 providers use the 'media' index
    "twelvelabs": "OPENSEARCH_INDEX",
    "twelvelabs-api": "OPENSEARCH_INDEX",
    "twelvelabs-bedrock": "OPENSEARCH_INDEX",
    "bedrock twelvelabs": "OPENSEARCH_INDEX",
    # Marengo 3.0 providers use the 'asset-embeddings' index
    "twelvelabs-bedrock-3-0": "ASSET_EMBEDDINGS_INDEX",
    # Coactive uses the 'media' index
    "coactive": "OPENSEARCH_INDEX",
}


PERSONAL_PREFIX = "personal/"

PERSONAL_ASSETS_BUCKET = os.environ.get("PERSONAL_ASSETS_BUCKET", "")


def _get_full_path_from_result(result: Dict[str, Any]) -> str:
    """Extract the S3 FullPath from a search result dict."""
    return (
        result.get("DigitalSourceAsset", {})
        .get("MainRepresentation", {})
        .get("StorageInfo", {})
        .get("PrimaryLocation", {})
        .get("ObjectKey", {})
        .get("FullPath", "")
    )


def _get_bucket_from_result(result: Dict[str, Any]) -> str:
    """Extract the S3 Bucket from a search result dict."""
    return (
        result.get("DigitalSourceAsset", {})
        .get("MainRepresentation", {})
        .get("StorageInfo", {})
        .get("PrimaryLocation", {})
        .get("Bucket", "")
    )


def is_owned_or_nonpersonal(
    bucket: str, full_path: str, user_sub: Optional[str]
) -> bool:
    """Authoritative personal-asset ownership check.

    Personal "My Assets" objects live under the reserved ``personal/{sub}/``
    key prefix. A result is visible to ``user_sub`` when it is NOT a personal
    asset, or when it is that user's OWN personal asset.

    ``Bucket`` and ``ObjectKey.FullPath`` are analyzed ``text`` fields in
    OpenSearch and cannot be matched/prefixed server-side, so this guard is the
    authoritative enforcement point (the search Lambda over-fetches and applies
    it in Python).

    Fail closed: if ``PERSONAL_ASSETS_BUCKET`` is not configured, or a result
    under ``personal/`` is missing its ``Bucket`` value, we cannot positively
    rule it out as a personal asset, so we treat it as personal and require
    ownership rather than leaking it. Only a result whose ``Bucket`` is a known,
    *different* bucket is exempted from the ownership check.
    """
    if not full_path.startswith(PERSONAL_PREFIX):
        # Not a personal asset — always visible.
        return True
    if PERSONAL_ASSETS_BUCKET and bucket and bucket != PERSONAL_ASSETS_BUCKET:
        # Lives in a known, non-personal bucket — not a My Assets object.
        return True
    # Personal asset (or, fail-closed, possibly one): require ownership.
    return bool(user_sub) and full_path.startswith(f"{PERSONAL_PREFIX}{user_sub}/")


class UnifiedSearchOrchestrator:
    """
    Main orchestrator for unified search that routes queries to appropriate providers
    based on configuration and query requirements.
    """

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
        if not PERSONAL_ASSETS_BUCKET:
            self.logger.warning(
                "PERSONAL_ASSETS_BUCKET is not configured; personal-asset "
                "isolation will fail closed (objects under 'personal/' are "
                "treated as private and hidden from non-owners)."
            )
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

    def _apply_owner_guard_hits(
        self, hits: List[SearchHit], user_sub: Optional[str]
    ) -> List[SearchHit]:
        """Filter SearchHit list to enforce personal-asset ownership."""
        return [
            h
            for h in hits
            if is_owned_or_nonpersonal(
                _get_bucket_from_result(h.source or {}),
                _get_full_path_from_result(h.source or {}),
                user_sub,
            )
        ]

    def _apply_owner_guard_dicts(
        self, results: List[Dict[str, Any]], user_sub: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Filter plain-dict result list to enforce personal-asset ownership."""
        return [
            r
            for r in results
            if is_owned_or_nonpersonal(
                _get_bucket_from_result(r),
                _get_full_path_from_result(r),
                user_sub,
            )
        ]

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
                    # Inject target_index based on provider type if not already set
                    if (
                        "target_index" not in config_data
                        or config_data["target_index"] is None
                    ):
                        provider_type = config_data.get("type", "")
                        target_index = self._get_target_index_for_provider(
                            provider_type
                        )
                        config_data["target_index"] = target_index
                        self.logger.info(
                            f"[INDEX ROUTING] Set target_index='{target_index}' for provider type '{provider_type}'"
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
            system_settings_table = _dynamodb_resource.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")
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
                        # Configurable Coactive endpoints
                        "search_endpoint": item.get("searchEndpoint"),
                        "dataset_endpoint": item.get("datasetEndpoint"),
                        "auth_endpoint": item.get("authEndpoint"),
                        "response_format": item.get("responseFormat"),
                    }
                elif provider_type in [
                    "bedrock twelvelabs",
                    "twelvelabs-bedrock",
                    "twelvelabs-bedrock-3-0",
                ]:
                    # Determine target index based on provider type
                    target_index = self._get_target_index_for_provider(provider_type)
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
                        "type": provider_type,
                        "dimensions": item.get("dimensions"),
                        # Target index for OpenSearch queries (Phase 3)
                        "target_index": target_index,
                    }
                    self.logger.info(
                        f"[INDEX ROUTING] Bedrock TwelveLabs provider '{provider_type}' "
                        f"configured to query index: '{target_index}'"
                    )
                elif provider_type in ["twelvelabs", "twelvelabs-api"]:
                    # Determine target index based on provider type
                    target_index = self._get_target_index_for_provider(provider_type)
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
                        "type": provider_type,
                        "dimensions": item.get("dimensions"),
                        # Target index for OpenSearch queries (Phase 3)
                        "target_index": target_index,
                    }
                    self.logger.info(
                        f"[INDEX ROUTING] TwelveLabs API provider '{provider_type}' "
                        f"configured to query index: '{target_index}'"
                    )
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
            response = _secretsmanager_client.get_secret_value(SecretId=secret_arn)

            if response and "SecretString" in response:
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

    def _get_target_index_for_provider(self, provider_type: str) -> str:
        """
        Determine the target OpenSearch index based on the search provider type.

        Index Routing:
        - twelvelabs / twelvelabs-bedrock → 'media' index (Marengo 2.7)
        - twelvelabs-bedrock-3-0 → 'asset-embeddings' index (Marengo 3.0)
        - coactive → 'media' index

        Args:
            provider_type: The search provider type from configuration

        Returns:
            The target index name to query
        """
        # Normalize provider type for lookup
        normalized_type = provider_type.lower().strip()

        # Look up the environment variable name from the mapping
        env_var_name = PROVIDER_INDEX_MAPPING.get(normalized_type)

        if env_var_name:
            index_name = os.environ.get(env_var_name)
            if index_name:
                self.logger.info(
                    f"[INDEX ROUTING] Provider '{provider_type}' → index '{index_name}' "
                    f"(from {env_var_name})"
                )
                return index_name
            else:
                self.logger.warning(
                    f"[INDEX ROUTING] Environment variable {env_var_name} not set, "
                    f"falling back to OPENSEARCH_INDEX"
                )
        else:
            self.logger.warning(
                f"[INDEX ROUTING] Unknown provider type '{provider_type}', "
                f"defaulting to OPENSEARCH_INDEX (media)"
            )

        # Default fallback to OPENSEARCH_INDEX (media) for backward compatibility
        default_index = os.environ.get("OPENSEARCH_INDEX", "media")
        self.logger.info(
            f"[INDEX ROUTING] Using default index '{default_index}' for provider '{provider_type}'"
        )
        return default_index

    def search(
        self, query_params: Dict[str, Any], user_sub: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main search method that routes queries to appropriate providers.

        Args:
            query_params: HTTP query parameters
            user_sub: Authenticated user's sub claim (for personal-asset ownership guard)

        Returns:
            Search response in MediaLake format
        """
        start_time = time.time()

        try:
            # Parse query parameters into unified SearchQuery first
            # so we can skip provider initialization for keyword searches
            search_query = create_search_query_from_params(query_params)

            self.logger.info(f"Processing search query: {search_query.query_text}")
            self.logger.info(f"Search type: {search_query.search_type.value}")

            # Keyword searches go straight to OpenSearch — no provider needed
            if search_query.search_type.value == "keyword":
                result = self._execute_opensearch_search(query_params, user_sub)
                self._add_presigned_urls_to_search_results(result)

                # Apply owner guard to keyword search results
                data = result.get("data", {})
                if "results" in data:
                    data["results"] = self._apply_owner_guard_dicts(
                        data["results"], user_sub
                    )

                total_time = time.time() - start_time
                self.logger.info(f"Keyword search completed in {total_time:.3f}s")
                return result

            # Semantic search — ensure providers are loaded
            self._ensure_providers_initialized()

            # Route to appropriate provider
            provider = self._select_provider(search_query)

            if provider:
                # Execute search using selected provider
                search_result = provider.search(search_query)

                # Apply owner guard: filter out personal assets not owned by the user
                search_result.hits = self._apply_owner_guard_hits(
                    search_result.hits, user_sub
                )

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

        # Batch-add CloudFront URLs to all results at once
        self._add_presigned_urls_batch(results)

        # Create search metadata in expected MediaLake format
        search_metadata = {
            "totalResults": search_result.total_results,
            "page": (query.page_offset // query.page_size) + 1,
            "pageSize": query.page_size,
            "facets": search_result.facets if search_result.facets else None,
        }

        return {
            "status": "200",
            "message": "ok",
            "data": {"searchMetadata": search_metadata, "results": results},
        }

    def _convert_search_hit_to_medialake_format(self, hit: SearchHit) -> Dict[str, Any]:
        """Convert SearchHit to MediaLake result format (without URLs — added in batch later)"""
        if hit.source:
            return hit.source.copy()
        else:
            return {"InventoryID": hit.asset_id}

    def _add_presigned_urls_batch(self, results: List[Dict[str, Any]]) -> None:
        """Add CloudFront URLs to a list of results using batch generation.

        Skips results that already have thumbnailUrl/proxyUrl set (e.g. from
        provider-level processing like Marengo 3.0's _process_marengo_30_results).
        """
        try:
            from index import get_indexed_thumbnail_url
            from url_utils import generate_cloudfront_urls_batch

            # Step 1: Collect URL requests only for results missing URLs
            url_requests = []
            result_url_map: List[Dict[str, Optional[str]]] = [
                {"thumbnail_request_id": None, "proxy_request_id": None}
                for _ in results
            ]

            for idx, result in enumerate(results):
                has_thumbnail = result.get("thumbnailUrl")
                has_proxy = result.get("proxyUrl")
                if has_thumbnail and has_proxy:
                    continue  # Already has both URLs — skip

                derived_representations = result.get("DerivedRepresentations", [])
                for representation in derived_representations:
                    purpose = representation.get("Purpose")
                    # Skip purposes we already have
                    if purpose == "thumbnail" and has_thumbnail:
                        continue
                    if purpose == "proxy" and has_proxy:
                        continue

                    rep_storage_info = representation.get("StorageInfo", {}).get(
                        "PrimaryLocation", {}
                    )

                    if rep_storage_info.get("StorageType") == "s3":
                        bucket = rep_storage_info.get("Bucket", "")
                        key = rep_storage_info.get("ObjectKey", {}).get("FullPath", "")
                        if bucket and key:
                            request_id = f"batch_{idx}_{purpose}_{len(url_requests)}"
                            url_requests.append(
                                {
                                    "request_id": request_id,
                                    "bucket": bucket,
                                    "key": key,
                                }
                            )
                            if purpose == "thumbnail":
                                result_url_map[idx]["thumbnail_request_id"] = request_id
                            elif purpose == "proxy":
                                result_url_map[idx]["proxy_request_id"] = request_id

            if not url_requests:
                return

            # Step 2: Generate all URLs in one batch call
            cloudfront_urls = generate_cloudfront_urls_batch(url_requests)

            # Step 3: Assign URLs back to results
            for idx, result in enumerate(results):
                mapping = result_url_map[idx]
                if mapping["thumbnail_request_id"]:
                    url = cloudfront_urls.get(mapping["thumbnail_request_id"])
                    if url:
                        result["thumbnailUrl"] = get_indexed_thumbnail_url(url)
                if mapping["proxy_request_id"]:
                    url = cloudfront_urls.get(mapping["proxy_request_id"])
                    if url:
                        result["proxyUrl"] = url

        except Exception as e:
            self.logger.warning(f"Failed to batch generate presigned URLs: {str(e)}")

    def _add_presigned_urls_to_search_results(
        self, search_response: Dict[str, Any]
    ) -> None:
        """Add presigned URLs to all results in a search response using batch generation"""
        try:
            results = search_response.get("data", {}).get("results", [])
            if not results:
                return
            self._add_presigned_urls_batch(results)
        except Exception as e:
            self.logger.warning(
                f"Failed to add presigned URLs to search results: {str(e)}"
            )

    def _execute_opensearch_search(
        self, query_params: Dict[str, Any], user_sub: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute search using OpenSearch-based system for keyword search"""
        self.logger.info("Executing keyword search using OpenSearch directly")

        try:
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
            search_params["pageSize"] = int(
                query_params.get("pageSize", DEFAULT_PAGE_SIZE)
            )
            search_params["min_score"] = float(query_params.get("min_score", 0.01))
            search_params["semantic"] = (
                query_params.get("semantic", "false").lower() == "true"
            )

            # Handle optional filter parameters
            if "filters" in query_params:
                search_params["filters"] = query_params["filters"]
            if "search_fields" in query_params:
                search_params["search_fields"] = query_params["search_fields"]
            if "fields" in query_params and "search_fields" not in search_params:
                fields_val = query_params["fields"]
                if isinstance(fields_val, list):
                    parsed_fields = [
                        token.strip()
                        for entry in fields_val
                        if isinstance(entry, str)
                        for token in entry.split(",")
                        if token.strip()
                    ]
                elif isinstance(fields_val, str):
                    parsed_fields = [
                        f.strip() for f in fields_val.split(",") if f.strip()
                    ]
                else:
                    parsed_fields = []
                if parsed_fields:
                    search_params["search_fields"] = parsed_fields
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
            if "objectPrefix" in query_params:
                search_params["objectPrefix"] = query_params["objectPrefix"]
            if "sort" in query_params:
                search_params["sort"] = query_params["sort"]
            if "searchModality" in query_params:
                search_params["searchModality"] = query_params["searchModality"]

            # Create SearchParams object
            params = SearchParams(**search_params)

            # Execute legacy search
            result = perform_search(params, user_sub)

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
                        "pageSize": int(
                            query_params.get("pageSize", DEFAULT_PAGE_SIZE)
                        ),
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
