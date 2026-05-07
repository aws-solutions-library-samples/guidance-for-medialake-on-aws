"""Authentication strategies for external metadata fetch.

This module provides pluggable authentication strategies for external metadata APIs.
Use the `create_auth_strategy()` factory function to instantiate the appropriate
strategy based on the auth_type configuration.

Supported auth types:
- oauth2_client_credentials: OAuth2 Client Credentials flow
- api_key: API Key authentication (header or query parameter)
- basic_auth: HTTP Basic Authentication

Example:
    >>> from lambdas.nodes.external_metadata_fetch.auth import (
    ...     create_auth_strategy,
    ...     AuthConfig,
    ... )
    >>> config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
    >>> strategy = create_auth_strategy("oauth2_client_credentials", config)
    >>> result = strategy.authenticate({"client_id": "...", "client_secret": "..."})
"""

from typing import Final

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.auth.api_key import APIKeyStrategy
    from nodes.external_metadata_fetch.auth.base import (
        AuthConfig,
        AuthResult,
        AuthStrategy,
    )
    from nodes.external_metadata_fetch.auth.basic_auth import BasicAuthStrategy
    from nodes.external_metadata_fetch.auth.oauth2_client_credentials import (
        OAuth2ClientCredentialsStrategy,
    )
except ImportError:
    from auth.api_key import APIKeyStrategy
    from auth.base import AuthConfig, AuthResult, AuthStrategy
    from auth.basic_auth import BasicAuthStrategy
    from auth.oauth2_client_credentials import OAuth2ClientCredentialsStrategy


# Registry of available auth strategies
# Maps auth_type string to strategy class
AUTH_STRATEGIES: Final[dict[str, type[AuthStrategy]]] = {
    "oauth2_client_credentials": OAuth2ClientCredentialsStrategy,
    "api_key": APIKeyStrategy,
    "basic_auth": BasicAuthStrategy,
}


def create_auth_strategy(auth_type: str, config: AuthConfig) -> AuthStrategy:
    """Factory function to create auth strategy instances.

    Creates and returns the appropriate AuthStrategy implementation
    based on the auth_type parameter.

    Args:
        auth_type: Strategy type identifier. Must be one of:
            - "oauth2_client_credentials": OAuth2 Client Credentials flow
            - "api_key": API Key authentication
            - "basic_auth": HTTP Basic Authentication
        config: Authentication configuration including endpoint and options

    Returns:
        Configured AuthStrategy instance

    Raises:
        ValueError: If auth_type is not recognized

    Example:
        >>> config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
        >>> strategy = create_auth_strategy("oauth2_client_credentials", config)
        >>> isinstance(strategy, OAuth2ClientCredentialsStrategy)
        True
    """
    if auth_type not in AUTH_STRATEGIES:
        available_types: str = ", ".join(sorted(AUTH_STRATEGIES.keys()))
        raise ValueError(
            f"Unknown auth type: '{auth_type}'. Available types: {available_types}"
        )

    strategy_class: type[AuthStrategy] = AUTH_STRATEGIES[auth_type]
    return strategy_class(config)


def get_available_auth_types() -> list[str]:
    """Get a list of all available auth type identifiers.

    Returns:
        Sorted list of auth type strings that can be passed to create_auth_strategy()

    Example:
        >>> types = get_available_auth_types()
        >>> "oauth2_client_credentials" in types
        True
    """
    return sorted(AUTH_STRATEGIES.keys())


__all__ = [
    # Base classes and types
    "AuthStrategy",
    "AuthConfig",
    "AuthResult",
    # Strategy implementations
    "OAuth2ClientCredentialsStrategy",
    "APIKeyStrategy",
    "BasicAuthStrategy",
    # Factory functions
    "create_auth_strategy",
    "get_available_auth_types",
    # Registry
    "AUTH_STRATEGIES",
]
