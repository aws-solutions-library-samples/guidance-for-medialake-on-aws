"""Secrets retrieval and authentication caching for external metadata fetch.

This module provides the SecretsRetriever class which handles:
- Credential retrieval from AWS Secrets Manager with caching
- Authentication result caching with expiry tracking
- Cache invalidation for token refresh scenarios

The SecretsRetriever coordinates with AuthStrategy implementations to manage
the full authentication lifecycle for external API access.
"""

import json
import time
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.auth.base import AuthResult, AuthStrategy
except ImportError:
    from auth.base import AuthResult, AuthStrategy


@dataclass
class CachedAuth:
    """Cached authentication result with expiry tracking.

    Attributes:
        auth_result: The authentication result from the auth strategy
        cached_at: Unix timestamp when the auth was cached
        expires_at: Unix timestamp when the token expires (None if no expiry)
    """

    auth_result: AuthResult
    cached_at: float
    expires_at: float | None


class SecretsRetrieverError(Exception):
    """Base exception for SecretsRetriever errors."""


class CredentialRetrievalError(SecretsRetrieverError):
    """Raised when credential retrieval from Secrets Manager fails."""


class AuthenticationError(SecretsRetrieverError):
    """Raised when authentication with external system fails."""


class SecretsRetriever:
    """Manages credential retrieval and authentication caching.

    This class handles:
    1. Retrieving credentials from AWS Secrets Manager
    2. Caching credentials to avoid repeated Secrets Manager calls
    3. Caching authentication results (tokens) with expiry tracking
    4. Invalidating cached auth when tokens expire or are rejected

    Example:
        >>> retriever = SecretsRetriever()
        >>> credentials = retriever.get_credentials("arn:aws:secretsmanager:...")
        >>> auth_result = retriever.get_auth(strategy, credentials, "cache-key")
        >>> # Later, if token is rejected:
        >>> retriever.invalidate_auth("cache-key")
    """

    # Buffer time (seconds) before token expiry to trigger refresh
    EXPIRY_BUFFER_SECONDS: int = 60

    def __init__(self, secrets_client: Any | None = None):
        """Initialize the SecretsRetriever.

        Args:
            secrets_client: Optional boto3 Secrets Manager client.
                           If not provided, a new client will be created.
        """
        self._secrets_client = secrets_client or boto3.client("secretsmanager")
        self._credentials_cache: dict[str, dict[str, Any]] = {}
        self._auth_cache: dict[str, CachedAuth] = {}

    def get_credentials(self, secret_arn: str) -> dict[str, Any]:
        """Retrieve credentials from AWS Secrets Manager.

        Credentials are cached after first retrieval to avoid repeated
        Secrets Manager API calls within the same Lambda invocation.

        Args:
            secret_arn: ARN of the secret containing credentials

        Returns:
            Dictionary with credential fields (structure depends on auth type):
            - OAuth2: {"client_id": "...", "client_secret": "..."}
            - API Key: {"api_key": "..."}
            - Basic Auth: {"username": "...", "password": "..."}

        Raises:
            CredentialRetrievalError: If secret retrieval fails
        """
        # Check cache first
        if secret_arn in self._credentials_cache:
            return self._credentials_cache[secret_arn]

        try:
            response = self._secrets_client.get_secret_value(SecretId=secret_arn)
            secret_string = response.get("SecretString")

            if not secret_string:
                raise CredentialRetrievalError(
                    f"Secret '{secret_arn}' does not contain a string value"
                )

            credentials = json.loads(secret_string)

            # Cache the credentials
            self._credentials_cache[secret_arn] = credentials

            return credentials

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise CredentialRetrievalError(
                f"Failed to retrieve secret '{secret_arn}': {error_code} - {error_message}"
            ) from e
        except json.JSONDecodeError as e:
            raise CredentialRetrievalError(
                f"Secret '{secret_arn}' contains invalid JSON: {e}"
            ) from e

    def get_auth(
        self,
        auth_strategy: AuthStrategy,
        credentials: dict[str, Any],
        cache_key: str,
    ) -> AuthResult:
        """Get authentication result, using cache if available and valid.

        This method checks for a cached authentication result first. If the
        cached result is still valid (not expired), it returns the cached
        result. Otherwise, it authenticates using the provided strategy
        and caches the new result.

        Args:
            auth_strategy: The auth strategy to use for authentication
            credentials: Credentials dictionary from get_credentials()
            cache_key: Key for auth caching (typically the secret_arn)

        Returns:
            Valid AuthResult with access token

        Raises:
            AuthenticationError: If authentication fails
        """
        # Check cache first
        cached = self._auth_cache.get(cache_key)
        if cached and not self._is_auth_expired(cached):
            return cached.auth_result

        # Authenticate using the strategy
        auth_result = auth_strategy.authenticate(credentials)

        if not auth_result.success:
            raise AuthenticationError(
                f"Authentication failed using {auth_strategy.get_strategy_name()}: "
                f"{auth_result.error_message}"
            )

        # Calculate expiry time
        expires_at: float | None = None
        if auth_result.expires_in is not None:
            expires_at = time.time() + auth_result.expires_in

        # Cache the result
        self._auth_cache[cache_key] = CachedAuth(
            auth_result=auth_result,
            cached_at=time.time(),
            expires_at=expires_at,
        )

        return auth_result

    def invalidate_auth(self, cache_key: str) -> None:
        """Invalidate cached authentication for a given key.

        Call this method when a token is rejected (e.g., 401 response)
        to force re-authentication on the next get_auth() call.

        Args:
            cache_key: The cache key to invalidate
        """
        _ = self._auth_cache.pop(cache_key, None)

    def invalidate_credentials(self, secret_arn: str) -> None:
        """Invalidate cached credentials for a given secret ARN.

        Call this method if credentials need to be refreshed from
        Secrets Manager (e.g., after secret rotation).

        Args:
            secret_arn: The secret ARN to invalidate
        """
        _ = self._credentials_cache.pop(secret_arn, None)

    def clear_all_caches(self) -> None:
        """Clear all cached credentials and authentication results.

        Useful for testing or when a full cache reset is needed.
        """
        self._credentials_cache.clear()
        self._auth_cache.clear()

    def _is_auth_expired(self, cached: CachedAuth) -> bool:
        """Check if cached authentication has expired.

        Uses a buffer time before actual expiry to ensure tokens
        are refreshed before they become invalid.

        Args:
            cached: The cached authentication to check

        Returns:
            True if the auth has expired or is about to expire
        """
        if cached.expires_at is None:
            # No expiry info, assume valid
            return False

        # Check if current time is past (expiry - buffer)
        return time.time() >= (cached.expires_at - self.EXPIRY_BUFFER_SECONDS)

    def is_auth_cached(self, cache_key: str) -> bool:
        """Check if valid authentication is cached for a key.

        Args:
            cache_key: The cache key to check

        Returns:
            True if valid (non-expired) auth is cached
        """
        cached = self._auth_cache.get(cache_key)
        if cached is None:
            return False
        return not self._is_auth_expired(cached)

    def is_credentials_cached(self, secret_arn: str) -> bool:
        """Check if credentials are cached for a secret ARN.

        Args:
            secret_arn: The secret ARN to check

        Returns:
            True if credentials are cached
        """
        return secret_arn in self._credentials_cache
