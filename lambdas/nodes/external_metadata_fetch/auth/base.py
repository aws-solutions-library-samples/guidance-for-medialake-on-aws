"""Base authentication strategy interface for external metadata fetch.

This module defines the abstract base class for pluggable authentication strategies.
Each strategy implementation handles a specific authentication method (OAuth2, API Key,
Basic Auth, etc.) independently of the metadata adapter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthConfig:
    """Configuration for authentication strategy.

    Attributes:
        auth_endpoint_url: Authentication endpoint URL (e.g., OAuth token endpoint)
        additional_config: Strategy-specific configuration options
    """

    auth_endpoint_url: str = ""
    additional_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthResult:
    """Result from authentication operation.

    Attributes:
        success: Whether authentication succeeded
        access_token: Token/key for API calls (None if failed)
        token_type: How to use the token in requests (e.g., "Bearer", "Basic", "APIKey")
        expires_in: Token lifetime in seconds (None if doesn't expire)
        error_message: Error description if authentication failed
    """

    success: bool
    access_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None
    error_message: str | None = None


class AuthStrategy(ABC):
    """Abstract base class for authentication strategies.

    Each strategy implementation handles a specific authentication method
    (OAuth2, API Key, Basic Auth, etc.) independently of the metadata adapter.
    This allows mixing and matching auth strategies with different adapters.

    Example:
        >>> config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
        >>> strategy = OAuth2ClientCredentialsStrategy(config)
        >>> result = strategy.authenticate({"client_id": "...", "client_secret": "..."})
        >>> if result.success:
        ...     headers = strategy.get_auth_header(result)
    """

    def __init__(self, config: AuthConfig):
        """Initialize the auth strategy with configuration.

        Args:
            config: Authentication configuration including endpoint and options
        """
        self.config: AuthConfig = config

    @abstractmethod
    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Authenticate with the external system.

        Args:
            credentials: Dictionary containing authentication credentials.
                        Structure depends on strategy type:
                        - OAuth2: {"client_id": "...", "client_secret": "..."}
                        - API Key: {"api_key": "..."}
                        - Basic Auth: {"username": "...", "password": "..."}

        Returns:
            AuthResult containing token/key or error information
        """

    @abstractmethod
    def get_auth_header(self, auth_result: AuthResult) -> dict[str, Any]:
        """Build the authorization header for API requests.

        Args:
            auth_result: Successful authentication result

        Returns:
            Dictionary with authorization header(s) to include in requests.
            Example: {"Authorization": "Bearer <token>"}
        """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the unique name of this auth strategy.

        Returns:
            String identifier (e.g., "oauth2_client_credentials", "api_key", "basic_auth")
        """

    def is_token_expired_error(
        self, status_code: int, response_body: dict[str, Any] | None = None
    ) -> bool:
        """Check if an HTTP response indicates an expired/invalid token.

        Override in subclasses for strategy-specific expiry detection.
        Default implementation checks for 401 status code.

        Args:
            status_code: HTTP response status code
            response_body: Optional parsed response body for additional checks

        Returns:
            True if the response indicates token expiry/invalidity
        """
        return status_code == 401

    def supports_refresh(self) -> bool:
        """Whether this strategy supports token refresh.

        Returns:
            True if tokens can be refreshed, False if re-authentication is needed
        """
        return False
