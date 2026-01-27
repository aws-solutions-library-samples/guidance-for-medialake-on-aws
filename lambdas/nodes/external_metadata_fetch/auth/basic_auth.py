"""Basic HTTP Authentication strategy.

This module implements HTTP Basic Authentication for external metadata APIs.
Credentials (username:password) are Base64 encoded and sent in the Authorization header.
"""

import base64
from typing import Any, override

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.auth.base import (
        AuthConfig,
        AuthResult,
        AuthStrategy,
    )
except ImportError:
    from auth.base import AuthConfig, AuthResult, AuthStrategy


class BasicAuthStrategy(AuthStrategy):
    """HTTP Basic Authentication strategy.

    Encodes username:password as Base64 for the Authorization header.
    No separate authentication call is made - credentials are encoded
    and used directly in API requests.

    Example:
        >>> config = AuthConfig(
        ...     auth_endpoint_url="",  # Not needed for Basic auth
        ... )
        >>> strategy = BasicAuthStrategy(config)
        >>> result = strategy.authenticate({
        ...     "username": "my_user",
        ...     "password": "my_password"  # pragma: allowlist secret
        ... })
        >>> if result.success:
        ...     headers = strategy.get_auth_header(result)
        ...     # headers = {"Authorization": "Basic <base64_encoded_credentials>"}
    """

    def __init__(self, config: AuthConfig):
        """Initialize the Basic Auth strategy.

        Args:
            config: Authentication configuration. For Basic Auth,
                   auth_endpoint_url is not required as credentials
                   are encoded and used directly.
        """
        super().__init__(config)

    @override
    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Encode credentials for Basic Authentication.

        No actual authentication call is made; credentials are validated
        and Base64 encoded for use in the Authorization header.

        Args:
            credentials: Dictionary containing:
                - username (str): The username for authentication
                - password (str): The password for authentication

        Returns:
            AuthResult with Base64-encoded credentials as access_token on success,
            or error_message if username or password is missing
        """
        username: Any = credentials.get("username")
        password: Any = credentials.get("password")

        # Validate username is present and non-empty
        if not username:
            return AuthResult(
                success=False,
                error_message="Basic authentication requires 'username' in credentials",
            )

        if not isinstance(username, str):
            return AuthResult(
                success=False,
                error_message="Username must be a string",
            )

        # Validate password is present (can be empty string but must exist)
        if password is None:
            return AuthResult(
                success=False,
                error_message="Basic authentication requires 'password' in credentials",
            )

        if not isinstance(password, str):
            return AuthResult(
                success=False,
                error_message="Password must be a string",
            )

        # Encode credentials as Base64
        # Format: base64(username:password)
        credentials_string: str = f"{username}:{password}"
        encoded_credentials: str = base64.b64encode(
            credentials_string.encode("utf-8")
        ).decode("utf-8")

        return AuthResult(
            success=True,
            access_token=encoded_credentials,
            token_type="Basic",
            # Basic auth credentials don't expire
            expires_in=None,
        )

    @override
    def get_auth_header(self, auth_result: AuthResult) -> dict[str, Any]:
        """Build the Basic authorization header.

        Args:
            auth_result: Successful authentication result containing
                        Base64-encoded credentials

        Returns:
            Dictionary with Authorization header in format:
            {"Authorization": "Basic <base64_encoded_credentials>"}
        """
        return {"Authorization": f"Basic {auth_result.access_token}"}

    @override
    def get_strategy_name(self) -> str:
        """Return the unique name of this auth strategy.

        Returns:
            "basic_auth"
        """
        return "basic_auth"

    @override
    def supports_refresh(self) -> bool:
        """Whether this strategy supports token refresh.

        Basic auth credentials don't expire and don't need refresh -
        the same encoded credentials are used for all requests.

        Returns:
            False - Basic auth doesn't support refresh
        """
        return False

    @override
    def is_token_expired_error(
        self, status_code: int, response_body: dict[str, Any] | None = None
    ) -> bool:
        """Check if an HTTP response indicates invalid credentials.

        Basic auth credentials don't expire, but can be invalid or
        revoked. Checks for 401 Unauthorized status code.

        Args:
            status_code: HTTP response status code
            response_body: Optional parsed response body (not used for Basic auth)

        Returns:
            True if the response indicates invalid credentials
        """
        return status_code == 401
