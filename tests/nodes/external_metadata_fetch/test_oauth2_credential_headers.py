"""
Unit tests for OAuth2 credential headers support during token request.

Tests that additional headers stored in Secrets Manager credentials
are correctly passed through to the OAuth2 token request.

This is important for scenarios like Azure APIM where subscription keys
need to be included in the token request headers.

**Feature: external-metadata-enrichment**
"""

from unittest.mock import MagicMock, patch

import pytest
from nodes.external_metadata_fetch.auth.base import AuthConfig

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.auth.oauth2_client_credentials import (
    OAuth2ClientCredentialsStrategy,
)


@pytest.mark.unit
class TestOAuth2CredentialHeaders:
    """Tests for credential-based additional headers in OAuth2 token requests."""

    def test_credential_headers_included_in_token_request(self):
        """
        Test that additional_headers from credentials are included in token request.

        This validates the scenario where Azure APIM subscription keys or other
        sensitive headers need to be included in the OAuth2 token request.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/oauth/token",
            additional_config={},
        )
        strategy = OAuth2ClientCredentialsStrategy(config)

        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # pragma: allowlist secret
            "additional_headers": {
                "x-subscription-key": "my-subscription-key-value",
                "x-custom-header": "custom-value",
            },
        }

        with patch(
            "nodes.external_metadata_fetch.auth.oauth2_client_credentials.requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
            mock_post.return_value = mock_response

            # Act
            result = strategy.authenticate(credentials)

            # Assert
            assert result.success is True
            mock_post.assert_called_once()

            # Verify headers include credential headers
            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            assert headers["x-subscription-key"] == "my-subscription-key-value"
            assert headers["x-custom-header"] == "custom-value"

    def test_credential_headers_override_config_headers(self):
        """
        Test that credential headers take precedence over config headers.

        If the same header is defined in both auth config and credentials,
        the credential value should win (more secure source takes precedence).
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/oauth/token",
            additional_config={
                "additional_headers": {
                    "x-api-key": "config-key-value",  # This should be overridden
                    "x-config-only": "config-value",  # This should remain
                }
            },
        )
        strategy = OAuth2ClientCredentialsStrategy(config)

        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "additional_headers": {
                "x-api-key": "secret-key-value",  # Should override config value
                "x-secret-only": "secret-value",  # Additional header from secret
            },
        }

        with patch(
            "nodes.external_metadata_fetch.auth.oauth2_client_credentials.requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "access_token": "test-token",
                "token_type": "Bearer",
            }
            mock_post.return_value = mock_response

            # Act
            result = strategy.authenticate(credentials)

            # Assert
            assert result.success is True

            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            # Credential header should override config header
            assert headers["x-api-key"] == "secret-key-value"
            # Config-only header should still be present
            assert headers["x-config-only"] == "config-value"
            # Secret-only header should be present
            assert headers["x-secret-only"] == "secret-value"

    def test_no_credential_headers_works(self):
        """
        Test that authentication works when no additional_headers in credentials.

        This is the default case for most OAuth2 configurations.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/oauth/token",
            additional_config={},
        )
        strategy = OAuth2ClientCredentialsStrategy(config)

        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            # No additional_headers
        }

        with patch(
            "nodes.external_metadata_fetch.auth.oauth2_client_credentials.requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "access_token": "test-token",
                "token_type": "Bearer",
            }
            mock_post.return_value = mock_response

            # Act
            result = strategy.authenticate(credentials)

            # Assert
            assert result.success is True
            mock_post.assert_called_once()

            # Verify only Content-Type header is present
            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            assert headers == {"Content-Type": "application/x-www-form-urlencoded"}

    def test_empty_credential_headers_works(self):
        """
        Test that authentication works with empty additional_headers dict.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/oauth/token",
            additional_config={},
        )
        strategy = OAuth2ClientCredentialsStrategy(config)

        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "additional_headers": {},  # Empty dict
        }

        with patch(
            "nodes.external_metadata_fetch.auth.oauth2_client_credentials.requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "access_token": "test-token",
                "token_type": "Bearer",
            }
            mock_post.return_value = mock_response

            # Act
            result = strategy.authenticate(credentials)

            # Assert
            assert result.success is True

    def test_non_dict_credential_headers_ignored(self):
        """
        Test that non-dict additional_headers in credentials is safely ignored.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/oauth/token",
            additional_config={},
        )
        strategy = OAuth2ClientCredentialsStrategy(config)

        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "additional_headers": "not-a-dict",  # Invalid type
        }

        with patch(
            "nodes.external_metadata_fetch.auth.oauth2_client_credentials.requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "access_token": "test-token",
                "token_type": "Bearer",
            }
            mock_post.return_value = mock_response

            # Act
            result = strategy.authenticate(credentials)

            # Assert - should succeed, ignoring invalid headers
            assert result.success is True

            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            # Should only have Content-Type, invalid headers ignored
            assert headers == {"Content-Type": "application/x-www-form-urlencoded"}

    def test_config_headers_used_when_no_credential_headers(self):
        """
        Test that config-based additional_headers are used when credentials don't have any.
        """
        # Arrange
        config = AuthConfig(
            auth_endpoint_url="https://auth.example.com/oauth/token",
            additional_config={
                "additional_headers": {
                    "x-config-header": "config-value",
                }
            },
        )
        strategy = OAuth2ClientCredentialsStrategy(config)

        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            # No additional_headers in credentials
        }

        with patch(
            "nodes.external_metadata_fetch.auth.oauth2_client_credentials.requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "access_token": "test-token",
                "token_type": "Bearer",
            }
            mock_post.return_value = mock_response

            # Act
            result = strategy.authenticate(credentials)

            # Assert
            assert result.success is True

            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            assert headers["x-config-header"] == "config-value"
