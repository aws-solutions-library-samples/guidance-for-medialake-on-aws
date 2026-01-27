"""Base metadata adapter interface for external source systems.

This module defines the abstract base class for pluggable metadata source adapters.
Each adapter implementation handles the specifics of communicating with a particular
external metadata source API. Authentication is delegated to the injected AuthStrategy,
allowing auth types to be mixed and matched with adapters without code duplication.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.auth.base import AuthResult, AuthStrategy
except ImportError:
    from auth.base import AuthResult, AuthStrategy


@dataclass
class AdapterConfig:
    """Configuration passed to adapter from node config.

    Attributes:
        metadata_endpoint: Base URL for the metadata API
        additional_config: Adapter-specific configuration options
    """

    metadata_endpoint: str
    additional_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    """Result from metadata fetch operation.

    Attributes:
        success: Whether the fetch operation succeeded
        raw_metadata: Raw metadata dictionary from the external system (None if failed)
        error_message: Error description if fetch failed
        http_status_code: HTTP status code from the API response (for error handling)
    """

    success: bool
    raw_metadata: dict[str, Any] | None = None
    error_message: str | None = None
    http_status_code: int | None = None


class MetadataAdapter(ABC):
    """Abstract base class for metadata source adapters.

    Each adapter implementation handles the specifics of communicating
    with a particular external metadata source API. Authentication is
    delegated to the injected AuthStrategy, allowing auth types to be
    mixed and matched with adapters without code duplication.

    The adapter receives an AuthStrategy via constructor (composition pattern),
    which separates API communication logic from authentication logic.

    Example:
        >>> auth_strategy = OAuth2ClientCredentialsStrategy(auth_config)
        >>> adapter_config = AdapterConfig(metadata_endpoint_url="https://api.example.com/assets")
        >>> adapter = GenericRestAdapter(adapter_config, auth_strategy)
        >>> auth_result = auth_strategy.authenticate(credentials)
        >>> fetch_result = adapter.fetch_metadata("ABC123", auth_result)
    """

    def __init__(self, config: AdapterConfig, auth_strategy: AuthStrategy):
        """Initialize the adapter with configuration and auth strategy.

        Args:
            config: Adapter configuration including endpoint and options
            auth_strategy: Authentication strategy to use for API calls
        """
        self.config: AdapterConfig = config
        self.auth_strategy: AuthStrategy = auth_strategy

    @abstractmethod
    def fetch_metadata(
        self,
        correlation_id: str,
        auth_result: AuthResult,
        credential_headers: dict[str, str] | None = None,
    ) -> FetchResult:
        """Fetch metadata for an asset from the external system.

        Args:
            correlation_id: The external system's identifier for the asset
            auth_result: Valid authentication result from auth_strategy.authenticate()
            credential_headers: Optional additional headers from credentials secret.
                               These are merged with config-based headers, with credential
                               headers taking precedence. Useful for API keys or subscription
                               keys that should be stored securely in Secrets Manager.

        Returns:
            FetchResult containing raw metadata or error information
        """

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the unique name of this adapter for source attribution.

        Returns:
            String identifier (e.g., "generic_rest_api", "custom_mam_v1")
        """

    def get_full_source_name(self) -> str:
        """Return combined adapter + auth strategy name for attribution.

        This is used in source attribution to identify both the adapter
        and authentication method used to fetch the metadata.

        Returns:
            String like "generic_rest_api:oauth2_client_credentials"
        """
        return f"{self.get_adapter_name()}:{self.auth_strategy.get_strategy_name()}"
