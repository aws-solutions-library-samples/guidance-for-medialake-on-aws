"""API Key authentication strategy.

This module implements API Key authentication for external metadata APIs.
API keys can be passed via HTTP header or query parameter, with no separate
authentication call needed - the key is used directly in requests.
"""

from typing import Any, Final, override

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.auth.base import (
        AuthConfig,
        AuthResult,
        AuthStrategy,
    )
except ImportError:
    from auth.base import AuthConfig, AuthResult, AuthStrategy


class APIKeyStrategy(AuthStrategy):
    """API Key authentication strategy.

    Supports API keys passed via header or query parameter.
    No separate authentication call needed - key is used directly.

    Example:
        >>> config = AuthConfig(
        ...     auth_endpoint_url="",  # Not needed for API key auth
        ...     additional_config={
        ...         "header_name": "X-API-Key",
        ...         "key_location": "header"
        ...     }
        ... )
        >>> strategy = APIKeyStrategy(config)
        >>> result = strategy.authenticate({"api_key": "my_secret_key"})
        >>> if result.success:
        ...     headers = strategy.get_auth_header(result)
        ...     # headers = {"X-API-Key": "my_secret_key"}
    """

    # Default header name for API key
    DEFAULT_HEADER_NAME: Final[str] = "X-API-Key"
    # Default query parameter name for API key
    DEFAULT_QUERY_PARAM_NAME: Final[str] = "api_key"
    # Valid key locations
    KEY_LOCATION_HEADER: Final[str] = "header"
    KEY_LOCATION_QUERY: Final[str] = "query"

    def __init__(self, config: AuthConfig):
        """Initialize the API Key strategy.

        Args:
            config: Authentication configuration. The additional_config dict
                   may contain:
                   - header_name (str): HTTP header name for API key (default: "X-API-Key")
                   - key_location (str): Where to place the key - "header" or "query" (default: "header")
                   - query_param_name (str): Query parameter name if key_location is "query" (default: "api_key")
        """
        super().__init__(config)
        additional: dict[str, Any] = config.additional_config or {}
        self.header_name: str = additional.get("header_name", self.DEFAULT_HEADER_NAME)
        self.key_location: str = additional.get(
            "key_location", self.KEY_LOCATION_HEADER
        )
        self.query_param_name: str = additional.get(
            "query_param_name", self.DEFAULT_QUERY_PARAM_NAME
        )

        # Validate key_location
        if self.key_location not in (self.KEY_LOCATION_HEADER, self.KEY_LOCATION_QUERY):
            # Default to header if invalid location specified
            self.key_location = self.KEY_LOCATION_HEADER

    @override
    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Validate API key is present in credentials.

        No actual authentication call is made; the key is validated
        and stored for use directly in API requests.

        Args:
            credentials: Dictionary containing:
                - api_key (str): The API key to use for authentication

        Returns:
            AuthResult with api_key as access_token on success,
            or error_message if api_key is missing
        """
        api_key: Any = credentials.get("api_key")

        if not api_key:
            return AuthResult(
                success=False,
                error_message="API key authentication requires 'api_key' in credentials",
            )

        # Validate api_key is a non-empty string
        if not isinstance(api_key, str):
            return AuthResult(
                success=False,
                error_message="API key must be a string",
            )

        if not api_key.strip():
            return AuthResult(
                success=False,
                error_message="API key must be a non-empty string",
            )

        return AuthResult(
            success=True,
            access_token=api_key,
            token_type="APIKey",
            # API keys typically don't expire
            expires_in=None,
        )

    @override
    def get_auth_header(self, auth_result: AuthResult) -> dict[str, Any]:
        """Build the API key authorization header.

        If key_location is "header", returns a dict with the configured
        header name and API key value. If key_location is "query",
        returns an empty dict (use get_query_params instead).

        Args:
            auth_result: Successful authentication result containing the API key

        Returns:
            Dictionary with API key header if key_location is "header",
            empty dict if key_location is "query"
        """
        if self.key_location == self.KEY_LOCATION_HEADER:
            return {self.header_name: auth_result.access_token}
        # For query param location, return empty - adapter uses get_query_params
        return {}

    def get_query_params(self, auth_result: AuthResult) -> dict[str, Any]:
        """Get query parameters for API key authentication.

        If key_location is "query", returns a dict with the configured
        query parameter name and API key value. If key_location is "header",
        returns an empty dict.

        Args:
            auth_result: Successful authentication result containing the API key

        Returns:
            Dictionary with API key query parameter if key_location is "query",
            empty dict if key_location is "header"
        """
        if self.key_location == self.KEY_LOCATION_QUERY:
            return {self.query_param_name: auth_result.access_token}
        return {}

    @override
    def get_strategy_name(self) -> str:
        """Return the unique name of this auth strategy.

        Returns:
            "api_key"
        """
        return "api_key"

    @override
    def supports_refresh(self) -> bool:
        """Whether this strategy supports token refresh.

        API keys don't expire in the traditional sense and don't need
        refresh - the same key is used for all requests.

        Returns:
            False - API keys don't support refresh
        """
        return False

    @override
    def is_token_expired_error(
        self, status_code: int, response_body: dict[str, Any] | None = None
    ) -> bool:
        """Check if an HTTP response indicates an invalid API key.

        API keys don't expire in the traditional sense, but can be
        revoked or invalid. Checks for 401 Unauthorized or 403 Forbidden.

        Args:
            status_code: HTTP response status code
            response_body: Optional parsed response body (not used for API key)

        Returns:
            True if the response indicates an invalid/revoked API key
        """
        return status_code in (401, 403)
