"""
Unit tests for SecretsRetriever class.

These tests verify:
- Credential retrieval from Secrets Manager (mocked)
- Auth caching behavior
- Cache invalidation

**Validates: Requirements 6.1, 6.4**
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from nodes.external_metadata_fetch.auth.base import AuthResult

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.secrets_retriever import (
    AuthenticationError,
    CredentialRetrievalError,
    SecretsRetriever,
)


@pytest.fixture
def mock_secrets_client():
    """Create a mock Secrets Manager client."""
    return MagicMock()


@pytest.fixture
def mock_auth_strategy():
    """Create a mock auth strategy."""
    strategy = MagicMock()
    strategy.get_strategy_name.return_value = "mock_strategy"
    return strategy


@pytest.fixture
def secrets_retriever(mock_secrets_client):
    """Create a SecretsRetriever with mocked client."""
    return SecretsRetriever(secrets_client=mock_secrets_client)


@pytest.mark.unit
class TestGetCredentials:
    """Tests for credential retrieval from Secrets Manager."""

    def test_retrieves_credentials_successfully(
        self, secrets_retriever, mock_secrets_client
    ):
        """Test successful credential retrieval from Secrets Manager."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        expected_credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # pragma: allowlist secret
        }
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps(expected_credentials)
        }

        # Act
        credentials = secrets_retriever.get_credentials(secret_arn)

        # Assert
        assert credentials == expected_credentials
        mock_secrets_client.get_secret_value.assert_called_once_with(
            SecretId=secret_arn
        )

    def test_caches_credentials_after_retrieval(
        self, secrets_retriever, mock_secrets_client
    ):
        """Test that credentials are cached after first retrieval."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        expected_credentials = {"api_key": "test-api-key"}  # pragma: allowlist secret
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps(expected_credentials)
        }

        # Act - call twice
        credentials1 = secrets_retriever.get_credentials(secret_arn)
        credentials2 = secrets_retriever.get_credentials(secret_arn)

        # Assert - should only call Secrets Manager once
        assert credentials1 == expected_credentials
        assert credentials2 == expected_credentials
        assert mock_secrets_client.get_secret_value.call_count == 1

    def test_raises_error_for_missing_secret_string(
        self, secrets_retriever, mock_secrets_client
    ):
        """Test error when secret doesn't contain SecretString."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        mock_secrets_client.get_secret_value.return_value = {}

        # Act & Assert
        with pytest.raises(CredentialRetrievalError) as exc_info:
            secrets_retriever.get_credentials(secret_arn)

        assert "does not contain a string value" in str(exc_info.value)

    def test_raises_error_for_invalid_json(
        self, secrets_retriever, mock_secrets_client
    ):
        """Test error when secret contains invalid JSON."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": "not valid json"
        }

        # Act & Assert
        with pytest.raises(CredentialRetrievalError) as exc_info:
            secrets_retriever.get_credentials(secret_arn)

        assert "invalid JSON" in str(exc_info.value)

    def test_raises_error_for_client_error(
        self, secrets_retriever, mock_secrets_client
    ):
        """Test error handling for Secrets Manager client errors."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        from botocore.exceptions import ClientError

        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Secret not found",
                }
            },
            "GetSecretValue",
        )

        # Act & Assert
        with pytest.raises(CredentialRetrievalError) as exc_info:
            secrets_retriever.get_credentials(secret_arn)

        assert "ResourceNotFoundException" in str(exc_info.value)


@pytest.mark.unit
class TestGetAuth:
    """Tests for authentication with caching."""

    def test_authenticates_successfully(self, secrets_retriever, mock_auth_strategy):
        """Test successful authentication using auth strategy."""
        # Arrange
        credentials = {
            "client_id": "test",
            "client_secret": "secret",  # pragma: allowlist secret
        }
        cache_key = "test-cache-key"
        expected_result = AuthResult(
            success=True,
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
        )
        mock_auth_strategy.authenticate.return_value = expected_result

        # Act
        result = secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        # Assert
        assert result == expected_result
        mock_auth_strategy.authenticate.assert_called_once_with(credentials)

    def test_caches_auth_result(self, secrets_retriever, mock_auth_strategy):
        """Test that auth results are cached."""
        # Arrange
        credentials = {
            "client_id": "test",
            "client_secret": "secret",  # pragma: allowlist secret
        }
        cache_key = "test-cache-key"
        expected_result = AuthResult(
            success=True,
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
        )
        mock_auth_strategy.authenticate.return_value = expected_result

        # Act - call twice
        result1 = secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)
        result2 = secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        # Assert - should only authenticate once
        assert result1 == expected_result
        assert result2 == expected_result
        assert mock_auth_strategy.authenticate.call_count == 1

    def test_raises_error_for_failed_auth(self, secrets_retriever, mock_auth_strategy):
        """Test error handling for failed authentication."""
        # Arrange
        credentials = {
            "client_id": "test",
            "client_secret": "wrong",  # pragma: allowlist secret
        }
        cache_key = "test-cache-key"
        mock_auth_strategy.authenticate.return_value = AuthResult(
            success=False,
            error_message="Invalid credentials",
        )

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        assert "Invalid credentials" in str(exc_info.value)
        assert "mock_strategy" in str(exc_info.value)

    def test_refreshes_expired_auth(self, secrets_retriever, mock_auth_strategy):
        """Test that expired auth is refreshed."""
        # Arrange
        credentials = {"client_id": "test", "client_secret": "secret"}
        cache_key = "test-cache-key"

        # First auth result with very short expiry
        first_result = AuthResult(
            success=True,
            access_token="first-token",
            token_type="Bearer",
            expires_in=1,  # 1 second expiry
        )
        second_result = AuthResult(
            success=True,
            access_token="second-token",
            token_type="Bearer",
            expires_in=3600,
        )
        mock_auth_strategy.authenticate.side_effect = [first_result, second_result]

        # Act
        result1 = secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        # Wait for expiry (considering the 60s buffer, we need to mock time)
        with patch("nodes.external_metadata_fetch.secrets_retriever.time") as mock_time:
            # Simulate time passing beyond expiry
            mock_time.time.return_value = time.time() + 100
            result2 = secrets_retriever.get_auth(
                mock_auth_strategy, credentials, cache_key
            )

        # Assert
        assert result1.access_token == "first-token"
        assert result2.access_token == "second-token"
        assert mock_auth_strategy.authenticate.call_count == 2


@pytest.mark.unit
class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_auth_clears_cache(self, secrets_retriever, mock_auth_strategy):
        """Test that invalidate_auth clears the auth cache."""
        # Arrange
        credentials = {"client_id": "test", "client_secret": "secret"}
        cache_key = "test-cache-key"
        auth_result = AuthResult(
            success=True,
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
        )
        mock_auth_strategy.authenticate.return_value = auth_result

        # First call to populate cache
        secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)
        assert secrets_retriever.is_auth_cached(cache_key)

        # Act
        secrets_retriever.invalidate_auth(cache_key)

        # Assert
        assert not secrets_retriever.is_auth_cached(cache_key)

    def test_invalidate_credentials_clears_cache(
        self, secrets_retriever, mock_secrets_client
    ):
        """Test that invalidate_credentials clears the credentials cache."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test"})
        }

        # First call to populate cache
        secrets_retriever.get_credentials(secret_arn)
        assert secrets_retriever.is_credentials_cached(secret_arn)

        # Act
        secrets_retriever.invalidate_credentials(secret_arn)

        # Assert
        assert not secrets_retriever.is_credentials_cached(secret_arn)

    def test_clear_all_caches(
        self, secrets_retriever, mock_secrets_client, mock_auth_strategy
    ):
        """Test that clear_all_caches clears both caches."""
        # Arrange
        secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
        cache_key = "test-cache-key"
        credentials = {"client_id": "test", "client_secret": "secret"}

        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps(credentials)
        }
        mock_auth_strategy.authenticate.return_value = AuthResult(
            success=True,
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
        )

        # Populate both caches
        secrets_retriever.get_credentials(secret_arn)
        secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        assert secrets_retriever.is_credentials_cached(secret_arn)
        assert secrets_retriever.is_auth_cached(cache_key)

        # Act
        secrets_retriever.clear_all_caches()

        # Assert
        assert not secrets_retriever.is_credentials_cached(secret_arn)
        assert not secrets_retriever.is_auth_cached(cache_key)

    def test_invalidate_nonexistent_auth_is_safe(self, secrets_retriever):
        """Test that invalidating non-existent auth doesn't raise error."""
        # Act & Assert - should not raise
        secrets_retriever.invalidate_auth("nonexistent-key")

    def test_invalidate_nonexistent_credentials_is_safe(self, secrets_retriever):
        """Test that invalidating non-existent credentials doesn't raise error."""
        # Act & Assert - should not raise
        secrets_retriever.invalidate_credentials("nonexistent-arn")


@pytest.mark.unit
class TestAuthExpiry:
    """Tests for auth expiry tracking."""

    def test_auth_without_expiry_never_expires(
        self, secrets_retriever, mock_auth_strategy
    ):
        """Test that auth without expires_in is considered valid indefinitely."""
        # Arrange
        credentials = {"api_key": "test-key"}  # pragma: allowlist secret
        cache_key = "test-cache-key"
        auth_result = AuthResult(
            success=True,
            access_token="test-token",
            token_type="APIKey",
            expires_in=None,  # No expiry
        )
        mock_auth_strategy.authenticate.return_value = auth_result

        # Act
        secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        # Simulate time passing
        with patch("nodes.external_metadata_fetch.secrets_retriever.time") as mock_time:
            mock_time.time.return_value = time.time() + 86400  # 24 hours later
            # Should still be cached
            assert secrets_retriever.is_auth_cached(cache_key)

    def test_expiry_buffer_triggers_refresh(
        self, secrets_retriever, mock_auth_strategy
    ):
        """Test that auth is refreshed within the expiry buffer window."""
        # Arrange
        credentials = {"client_id": "test", "client_secret": "secret"}
        cache_key = "test-cache-key"
        current_time = time.time()

        # Auth with 90 second expiry (buffer is 60 seconds)
        auth_result = AuthResult(
            success=True,
            access_token="test-token",
            token_type="Bearer",
            expires_in=90,
        )
        mock_auth_strategy.authenticate.return_value = auth_result

        # Act - first call
        with patch("nodes.external_metadata_fetch.secrets_retriever.time") as mock_time:
            mock_time.time.return_value = current_time
            secrets_retriever.get_auth(mock_auth_strategy, credentials, cache_key)

        # Check at 25 seconds - should still be cached (90 - 60 = 30 second window)
        with patch("nodes.external_metadata_fetch.secrets_retriever.time") as mock_time:
            mock_time.time.return_value = current_time + 25
            assert secrets_retriever.is_auth_cached(cache_key)

        # Check at 35 seconds - should be expired (past the 30 second window)
        with patch("nodes.external_metadata_fetch.secrets_retriever.time") as mock_time:
            mock_time.time.return_value = current_time + 35
            assert not secrets_retriever.is_auth_cached(cache_key)
