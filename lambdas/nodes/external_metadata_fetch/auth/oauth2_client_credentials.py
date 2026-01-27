"""OAuth2 Client Credentials authentication strategy.

This module implements the OAuth2 Client Credentials flow for server-to-server
authentication where the client authenticates with client_id and client_secret.
"""

from typing import Any, Final, override

import requests

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.auth.base import (
        AuthConfig,
        AuthResult,
        AuthStrategy,
    )
except ImportError:
    from auth.base import AuthConfig, AuthResult, AuthStrategy


class OAuth2ClientCredentialsStrategy(AuthStrategy):
    """OAuth2 Client Credentials flow authentication.

    Used for server-to-server authentication where the client
    authenticates with client_id and client_secret to obtain
    an access token.

    Example:
        >>> config = AuthConfig(
        ...     auth_endpoint_url="https://auth.example.com/oauth/token",
        ...     additional_config={"scope": "read:metadata", "timeout_seconds": 30}
        ... )
        >>> strategy = OAuth2ClientCredentialsStrategy(config)
        >>> result = strategy.authenticate({
        ...     "client_id": "my_client_id",
        ...     "client_secret": "my_client_secret"  # pragma: allowlist secret
        ... })
        >>> if result.success:
        ...     headers = strategy.get_auth_header(result)
        ...     # headers = {"Authorization": "Bearer <access_token>"}
    """

    # Default timeout for HTTP requests in seconds
    DEFAULT_TIMEOUT_SECONDS: Final[int] = 30

    def __init__(self, config: AuthConfig):
        """Initialize the OAuth2 Client Credentials strategy.

        Args:
            config: Authentication configuration. The additional_config dict
                   may contain:
                   - timeout_seconds (int): HTTP request timeout (default: 30)
                   - scope (str): OAuth2 scope to request (optional)
                   - additional_headers (dict): Extra headers to include in token request (optional)
        """
        super().__init__(config)
        additional: dict[str, Any] = config.additional_config or {}
        self.timeout: int = additional.get(
            "timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS
        )
        self.scope: str | None = additional.get("scope")
        self.additional_headers: dict[str, str] = additional.get(
            "additional_headers", {}
        )

    @override
    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Authenticate using OAuth2 client credentials flow.

        Makes a POST request to the token endpoint with grant_type=client_credentials
        and the provided client_id/client_secret.

        Args:
            credentials: Dictionary containing:
                - client_id (str): OAuth2 client identifier
                - client_secret (str): OAuth2 client secret

        Returns:
            AuthResult with access_token on success, or error_message on failure
        """
        # Validate required credentials
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")

        if not client_id or not client_secret:
            return AuthResult(
                success=False,
                error_message="OAuth2 authentication requires 'client_id' and 'client_secret' in credentials",
            )

        # Validate auth endpoint is configured
        if not self.config.auth_endpoint_url:
            return AuthResult(
                success=False,
                error_message="OAuth2 authentication requires 'auth_endpoint_url' to be configured",
            )

        # Build token request payload
        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        # Add scope if configured
        if self.scope:
            data["scope"] = self.scope

        try:
            # Build headers - start with Content-Type, then add any additional headers
            # Headers can come from two sources:
            # 1. auth_config.additional_config.additional_headers (from node config)
            # 2. credentials.additional_headers (from Secrets Manager - for sensitive headers)
            headers: dict[str, str] = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            if self.additional_headers:
                headers.update(self.additional_headers)

            # Merge headers from credentials (these take precedence as they're more specific)
            credential_headers: dict[str, str] | None = credentials.get(
                "additional_headers"
            )
            if credential_headers and isinstance(credential_headers, dict):
                headers.update(credential_headers)

            response = requests.post(
                self.config.auth_endpoint_url,
                data=data,
                timeout=self.timeout,
                headers=headers,
            )

            # Handle non-success status codes
            if not response.ok:
                error_detail: str = self._extract_error_detail(response)
                return AuthResult(
                    success=False,
                    error_message=f"OAuth2 authentication failed with status {response.status_code}: {error_detail}",
                )

            # Parse successful token response
            return self._parse_token_response(response)

        except requests.exceptions.Timeout:
            return AuthResult(
                success=False,
                error_message=f"OAuth2 authentication timed out after {self.timeout} seconds",
            )
        except requests.exceptions.ConnectionError as e:
            return AuthResult(
                success=False,
                error_message=f"OAuth2 authentication failed: connection error - {str(e)}",
            )
        except requests.exceptions.RequestException as e:
            return AuthResult(
                success=False,
                error_message=f"OAuth2 authentication failed: {str(e)}",
            )

    def _parse_token_response(self, response: requests.Response) -> AuthResult:
        """Parse the OAuth2 token response.

        Args:
            response: Successful HTTP response from token endpoint

        Returns:
            AuthResult with parsed token data or error if parsing fails
        """
        try:
            token_data: dict[str, Any] = response.json()
        except ValueError:
            return AuthResult(
                success=False,
                error_message="OAuth2 authentication failed: invalid JSON response from token endpoint",
            )

        # Validate required access_token field
        access_token: str | None = token_data.get("access_token")
        if not access_token:
            return AuthResult(
                success=False,
                error_message="OAuth2 authentication failed: response missing 'access_token' field",
            )

        # Extract optional fields with defaults
        token_type: str = token_data.get("token_type", "Bearer")
        expires_in: int | None = token_data.get("expires_in")

        # Validate expires_in is an integer if present
        if expires_in is not None:
            try:
                expires_in = int(expires_in)
            except (ValueError, TypeError):
                # If expires_in is invalid, treat as no expiry
                expires_in = None

        return AuthResult(
            success=True,
            access_token=access_token,
            token_type=token_type,
            expires_in=expires_in,
        )

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract error details from a failed OAuth2 response.

        OAuth2 error responses typically include 'error' and 'error_description'
        fields in the JSON body.

        Args:
            response: Failed HTTP response

        Returns:
            Human-readable error description
        """
        try:
            error_data: dict[str, Any] = response.json()
            error: str = error_data.get("error", "unknown_error")
            error_description: str = error_data.get("error_description", "")
            if error_description:
                return f"{error}: {error_description}"
            return error
        except ValueError:
            # Response is not JSON, return raw text (truncated)
            text = response.text[:200] if response.text else "no response body"
            return text

    @override
    def get_auth_header(self, auth_result: AuthResult) -> dict[str, Any]:
        """Build the Bearer token authorization header.

        Args:
            auth_result: Successful authentication result containing access_token

        Returns:
            Dictionary with Authorization header in format:
            {"Authorization": "<token_type> <access_token>"}
        """
        token_type: str = auth_result.token_type or "Bearer"
        return {"Authorization": f"{token_type} {auth_result.access_token}"}

    @override
    def get_strategy_name(self) -> str:
        """Return the unique name of this auth strategy.

        Returns:
            "oauth2_client_credentials"
        """
        return "oauth2_client_credentials"

    @override
    def supports_refresh(self) -> bool:
        """Whether this strategy supports token refresh.

        OAuth2 client credentials can be re-authenticated with the same
        credentials to obtain a new token.

        Returns:
            True - can re-authenticate with same credentials
        """
        return True

    @override
    def is_token_expired_error(
        self, status_code: int, response_body: dict[str, Any] | None = None
    ) -> bool:
        """Check if an HTTP response indicates an expired/invalid token.

        For OAuth2, checks for 401 Unauthorized status code, or specific
        OAuth2 error codes in the response body.

        Args:
            status_code: HTTP response status code
            response_body: Optional parsed response body

        Returns:
            True if the response indicates token expiry/invalidity
        """
        if status_code == 401:
            return True

        # Check for OAuth2-specific error codes in response body
        if response_body:
            error: str = response_body.get("error", "")
            if error in ("invalid_token", "expired_token"):
                return True

        return False
