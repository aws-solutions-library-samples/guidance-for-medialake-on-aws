"""
Base search provider interface for unified search architecture.
Supports both provider+store and external semantic service patterns.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from unified_search_models import (
    MediaType,
    ProviderLocation,
    SearchArchitectureType,
    SearchProviderConfig,
    SearchQuery,
    SearchResult,
)


class BaseSearchProvider(ABC):
    """Abstract base class for all search providers"""

    def __init__(self, config: SearchProviderConfig, logger, metrics):
        self.config = config
        self.logger = logger
        self.metrics = metrics
        self.architecture = self._get_architecture_type()
        self.provider_location = self._get_provider_location()
        self.supported_media_types = self._get_supported_media_types()

    @abstractmethod
    def _get_architecture_type(self) -> SearchArchitectureType:
        """Return architecture type for routing"""

    @abstractmethod
    def _get_provider_location(self) -> ProviderLocation:
        """Return whether this is an internal or external provider"""

    def _get_supported_media_types(self) -> List[MediaType]:
        """Get supported media types from configuration"""
        media_types = self.config.capabilities.get("media", ["video", "audio", "image"])
        return [MediaType(m) for m in media_types]

    def supports_semantic_search(self) -> bool:
        """Check if provider supports semantic search"""
        return self.config.capabilities.get("semantic", False)

    def supports_media_type(self, media_type: MediaType) -> bool:
        """Check if provider supports the given media type"""
        return (
            media_type in self.supported_media_types
            or MediaType.ALL in self.supported_media_types
        )

    def validate_query(self, query: SearchQuery) -> bool:
        """Validate if the query can be handled by this provider"""
        # Check if semantic search is supported
        if (
            query.search_type.value == "semantic"
            and not self.supports_semantic_search()
        ):
            return False

        # Check media type filters
        if query.filters:
            for filter_item in query.filters:
                if filter_item.get("key") == "mediaType":
                    requested_types = filter_item.get("value", [])
                    if isinstance(requested_types, str):
                        requested_types = [requested_types]

                    for media_type_str in requested_types:
                        try:
                            media_type = MediaType(media_type_str)
                            if not self.supports_media_type(media_type):
                                return False
                        except ValueError:
                            # Invalid media type
                            return False

        return True

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResult:
        """Execute the search and map to SearchResult"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and properly configured"""


class ProviderPlusStoreSearchProvider(BaseSearchProvider):
    """Base class for provider+store architecture (TwelveLabs + OpenSearch/S3Vector)"""

    def _get_architecture_type(self) -> SearchArchitectureType:
        return SearchArchitectureType.PROVIDER_PLUS_STORE

    @abstractmethod
    def generate_embeddings(self, query_text: str) -> List[float]:
        """Generate embeddings for the query text"""

    @abstractmethod
    def execute_store_search(
        self, embeddings: List[float], query: SearchQuery
    ) -> SearchResult:
        """Execute search against the embedding store"""

    @abstractmethod
    def get_allowed_clip_embedding_types(self) -> List[str]:
        """
        Get the list of embedding types that should be included in clips for timeline display.
        This is model-specific as different models return different embedding types.

        Returns:
            List of embedding type strings (e.g., ["visual-text"])
        """


class ExternalSemanticServiceProvider(BaseSearchProvider):
    """Base class for external semantic service architecture (Coactive)"""

    def _get_architecture_type(self) -> SearchArchitectureType:
        return SearchArchitectureType.EXTERNAL_SEMANTIC_SERVICE

    @abstractmethod
    def execute_external_search(self, query: SearchQuery) -> SearchResult:
        """Execute search against the external semantic service"""

    @abstractmethod
    def enrich_results_with_medialake_data(
        self, results: SearchResult, query: SearchQuery
    ) -> SearchResult:
        """Enrich external search results with MediaLake metadata"""

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute external search and enrich with MediaLake data"""
        # Step 1: Execute search against external service
        external_results = self.execute_external_search(query)

        # Step 2: Enrich results with MediaLake metadata
        enriched_results = self.enrich_results_with_medialake_data(
            external_results, query
        )

        return enriched_results


class SearchProviderFactory:
    """Factory for creating search provider instances"""

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
        self._providers = {}

    def register_provider(self, provider_name: str, provider_class: type):
        """Register a provider class"""
        self._providers[provider_name] = provider_class

    def create_provider(self, config: SearchProviderConfig) -> BaseSearchProvider:
        """Create a provider instance from configuration"""
        provider_name = config.provider

        if provider_name not in self._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = self._providers[provider_name]
        return provider_class(config, self.logger, self.metrics)

    def get_available_providers(self) -> List[str]:
        """Get list of registered provider names"""
        return list(self._providers.keys())


def create_search_provider_config(
    provider_data: Dict[str, Any],
) -> SearchProviderConfig:
    """Create SearchProviderConfig from dictionary data"""
    return SearchProviderConfig(
        provider=provider_data.get("provider", ""),
        provider_location=ProviderLocation(
            provider_data.get("provider_location", "external")
        ),
        architecture=SearchArchitectureType(
            provider_data.get("architecture", "provider_plus_store")
        ),
        capabilities=provider_data.get("capabilities", {}),
        endpoint=provider_data.get("endpoint"),
        store=provider_data.get("store"),
        auth=provider_data.get("auth"),
        metadata_mapping=provider_data.get("metadata_mapping"),
        callbacks=provider_data.get("callbacks"),
        dataset_id=provider_data.get("dataset_id"),
    )
