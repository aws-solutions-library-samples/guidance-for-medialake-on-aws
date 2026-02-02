"""Metadata adapters for external source systems.

This module provides pluggable metadata adapters for fetching metadata from
external APIs. Use the `create_adapter()` factory function to instantiate
the appropriate adapter based on the adapter_type configuration.

Supported adapter types:
- generic_rest: Generic REST API adapter for metadata sources

Example:
    >>> from lambdas.nodes.external_metadata_fetch.adapters import (
    ...     create_adapter,
    ...     AdapterConfig,
    ... )
    >>> from lambdas.nodes.external_metadata_fetch.auth import (
    ...     create_auth_strategy,
    ...     AuthConfig,
    ... )
    >>> auth_config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
    >>> auth_strategy = create_auth_strategy("oauth2_client_credentials", auth_config)
    >>> adapter_config = AdapterConfig(
    ...     metadata_endpoint="https://api.example.com/assets",
    ...     additional_config={"correlation_id_param": "externalId"}
    ... )
    >>> adapter = create_adapter("generic_rest", adapter_config, auth_strategy)
"""

from typing import Final

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.adapters.base import (
        AdapterConfig,
        FetchResult,
        MetadataAdapter,
    )
    from nodes.external_metadata_fetch.adapters.generic_rest import GenericRestAdapter
    from nodes.external_metadata_fetch.auth.base import AuthStrategy
except ImportError:
    from adapters.base import AdapterConfig, FetchResult, MetadataAdapter
    from adapters.generic_rest import GenericRestAdapter
    from auth.base import AuthStrategy


# Registry of available metadata adapters
# Maps adapter_type string to adapter class
ADAPTERS: Final[dict[str, type[MetadataAdapter]]] = {
    "generic_rest": GenericRestAdapter,
}


def create_adapter(
    adapter_type: str, config: AdapterConfig, auth_strategy: AuthStrategy
) -> MetadataAdapter:
    """Factory function to create adapter instances.

    Creates and returns the appropriate MetadataAdapter implementation
    based on the adapter_type parameter.

    Args:
        adapter_type: Adapter type identifier. Must be one of:
            - "generic_rest": Generic REST API adapter
        config: Adapter configuration including endpoint and options
        auth_strategy: Authentication strategy to use for API calls

    Returns:
        Configured MetadataAdapter instance

    Raises:
        ValueError: If adapter_type is not recognized

    Example:
        >>> auth_strategy = create_auth_strategy("api_key", auth_config)
        >>> adapter_config = AdapterConfig(
        ...     metadata_endpoint="https://api.example.com/assets"
        ... )
        >>> adapter = create_adapter("generic_rest", adapter_config, auth_strategy)
        >>> isinstance(adapter, GenericRestAdapter)
        True
    """
    if adapter_type not in ADAPTERS:
        available_types: str = ", ".join(sorted(ADAPTERS.keys()))
        raise ValueError(
            f"Unknown adapter type: '{adapter_type}'. Available types: {available_types}"
        )

    adapter_class: type[MetadataAdapter] = ADAPTERS[adapter_type]
    return adapter_class(config, auth_strategy)


def get_available_adapter_types() -> list[str]:
    """Get a list of all available adapter type identifiers.

    Returns:
        Sorted list of adapter type strings that can be passed to create_adapter()

    Example:
        >>> types = get_available_adapter_types()
        >>> "generic_rest" in types
        True
    """
    return sorted(ADAPTERS.keys())


__all__ = [
    # Base classes and types
    "MetadataAdapter",
    "AdapterConfig",
    "FetchResult",
    # Adapter implementations
    "GenericRestAdapter",
    # Factory functions
    "create_adapter",
    "get_available_adapter_types",
    # Registry
    "ADAPTERS",
]
