"""
Base Search Provider Classes
===========================
Base classes and interfaces for search providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from search_provider_models import (
    AssetDeletionResult,
    ExternalServicePlugin,
    ProviderLocation,
    SearchArchitectureType,
    SearchProviderConfig,
    SearchQuery,
)


class BaseSearchProvider(ABC):
    """Base class for all search providers"""

    def __init__(self, config: SearchProviderConfig, logger, metrics):
        self.config = config
        self.logger = logger
        self.metrics = metrics
        self.architecture = self._get_architecture_type()
        self.provider_location = self._get_provider_location()
        self.supported_media_types = self._get_supported_media_types()

    @abstractmethod
    def _get_architecture_type(self) -> SearchArchitectureType:
        """Return the architecture type for this provider"""

    @abstractmethod
    def _get_provider_location(self) -> ProviderLocation:
        """Return whether this is an internal or external provider"""

    @abstractmethod
    def _get_supported_media_types(self) -> List[str]:
        """Return list of supported media types"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and properly configured"""

    @abstractmethod
    def search(self, query: SearchQuery) -> Dict[str, Any]:
        """Execute search query"""

    def validate_query(self, query: SearchQuery) -> bool:
        """Validate if this provider can handle the query"""
        # Check media type support
        if query.media_types:
            for media_type in query.media_types:
                if media_type.lower() not in [
                    mt.lower() for mt in self.supported_media_types
                ]:
                    return False
        return True

    def supports_semantic_search(self) -> bool:
        """Check if provider supports semantic search"""
        return True  # Most providers support semantic search

    def delete_asset(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> AssetDeletionResult:
        """Delete asset from this provider's storage/index"""
        # Default implementation - providers should override if they support deletion
        return AssetDeletionResult(
            success=True,
            message=f"No deletion logic implemented for {self.config.provider}",
            deleted_count=0,
        )


class ProviderPlusStoreSearchProvider(BaseSearchProvider):
    """Base class for provider+store architecture (TwelveLabs + OpenSearch/S3Vector)"""

    def _get_architecture_type(self) -> SearchArchitectureType:
        return SearchArchitectureType.PROVIDER_PLUS_STORE

    @abstractmethod
    def generate_embeddings(self, query_text: str) -> List[float]:
        """Generate embeddings using the provider's embedding model"""


class ExternalSemanticServiceProvider(BaseSearchProvider):
    """Base class for external semantic service providers (Coactive)"""

    def _get_architecture_type(self) -> SearchArchitectureType:
        return SearchArchitectureType.EXTERNAL_SEMANTIC_SERVICE

    def supports_semantic_search(self) -> bool:
        return True


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


class ExternalServicePluginManager:
    """Manager for external service plugins that handle asset lifecycle events"""

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
        self._plugins = {}

    def register_plugin(self, service_name: str, plugin_class: type):
        """Register an external service plugin"""
        self._plugins[service_name] = plugin_class

    def create_plugin(
        self, service_name: str, config: Dict[str, Any]
    ) -> ExternalServicePlugin:
        """Create a plugin instance"""
        if service_name not in self._plugins:
            raise ValueError(f"Unknown external service: {service_name}")

        plugin_class = self._plugins[service_name]
        return plugin_class(config, self.logger, self.metrics)

    def get_available_plugins(
        self, asset_type: str = None
    ) -> List[ExternalServicePlugin]:
        """Get all available plugins, optionally filtered by asset type"""
        available_plugins = []

        for service_name, plugin_class in self._plugins.items():
            try:
                # Create a temporary instance to check availability
                plugin = plugin_class({}, self.logger, self.metrics)
                if plugin.is_available():
                    if asset_type is None or plugin.supports_asset_type(asset_type):
                        available_plugins.append(plugin)
            except Exception as e:
                self.logger.warning(
                    f"Failed to check availability for {service_name}: {e}"
                )

        return available_plugins
