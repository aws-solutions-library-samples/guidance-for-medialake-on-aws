"""
Unit tests for credential-based additional headers support.

Tests that additional headers stored in Secrets Manager credentials
are correctly passed through to API requests.

**Feature: external-metadata-enrichment**
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock aws_lambda_powertools before any imports that might trigger it
mock_powertools = MagicMock()
mock_powertools.Logger = MagicMock(return_value=MagicMock())
mock_powertools.Tracer = MagicMock(return_value=MagicMock())
mock_powertools.utilities = MagicMock()
mock_powertools.utilities.typing = MagicMock()
mock_powertools.utilities.typing.LambdaContext = MagicMock()
sys.modules["aws_lambda_powertools"] = mock_powertools
sys.modules["aws_lambda_powertools.utilities"] = mock_powertools.utilities
sys.modules["aws_lambda_powertools.utilities.typing"] = mock_powertools.utilities.typing

# Also mock lambda_middleware
sys.modules["lambda_middleware"] = MagicMock()

from nodes.external_metadata_fetch.adapters.base import AdapterConfig

# Now we can import from the adapters submodule directly
from nodes.external_metadata_fetch.adapters.generic_rest import GenericRestAdapter
from nodes.external_metadata_fetch.auth.base import AuthResult


@pytest.mark.unit
class TestCredentialHeaders:
    """Tests for credential-based additional headers support."""

    def test_credential_headers_added_to_request(self):
        """
        Test that credential headers from secrets are added to API requests.

        This validates that headers stored in Secrets Manager (like Azure API keys)
        are correctly passed through to the metadata API request.
        """
        # Arrange
        mock_auth_strategy = MagicMock()
        mock_auth_strategy.get_auth_header.return_value = {
            "Authorization": "Bearer token123"
        }

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/metadata",
            additional_config={
                "correlation_id_param": "assetId",
            },
        )

        adapter = GenericRestAdapter(adapter_config, mock_auth_strategy)

        auth_result = AuthResult(
            success=True,
            access_token="token123",
            token_type="Bearer",
        )

        credential_headers = {
            "x-subscription-key": "my-subscription-key-value",
            "x-custom-header": "custom-value",
        }

        # Mock the requests.get call
        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"title": "Test Asset"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, credential_headers)

            # Assert
            assert result.success is True
            mock_get.assert_called_once()

            # Verify headers include both auth and credential headers
            call_kwargs = mock_get.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            assert headers["Authorization"] == "Bearer token123"
            assert headers["x-subscription-key"] == "my-subscription-key-value"
            assert headers["x-custom-header"] == "custom-value"

    def test_credential_headers_override_config_headers(self):
        """
        Test that credential headers take precedence over config headers.

        If the same header is defined in both adapter config and credentials,
        the credential value should win (more secure source takes precedence).
        """
        # Arrange
        mock_auth_strategy = MagicMock()
        mock_auth_strategy.get_auth_header.return_value = {
            "Authorization": "Bearer token123"
        }

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/metadata",
            additional_config={
                "correlation_id_param": "assetId",
                "additional_headers": {
                    "x-api-key": "config-key-value",  # This should be overridden
                    "x-config-only": "config-value",  # This should remain
                },
            },
        )

        adapter = GenericRestAdapter(adapter_config, mock_auth_strategy)

        auth_result = AuthResult(
            success=True,
            access_token="token123",
            token_type="Bearer",
        )

        credential_headers = {
            "x-api-key": "secret-key-value",  # Should override config value
            "x-secret-only": "secret-value",  # Additional header from secret
        }

        # Mock the requests.get call
        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"title": "Test Asset"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, credential_headers)

            # Assert
            assert result.success is True

            call_kwargs = mock_get.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

            # Credential header should override config header
            assert headers["x-api-key"] == "secret-key-value"
            # Config-only header should still be present
            assert headers["x-config-only"] == "config-value"
            # Secret-only header should be present
            assert headers["x-secret-only"] == "secret-value"

    def test_none_credential_headers_works(self):
        """
        Test that passing None for credential_headers works correctly.

        This is the default case when no additional headers are in the secret.
        """
        # Arrange
        mock_auth_strategy = MagicMock()
        mock_auth_strategy.get_auth_header.return_value = {
            "Authorization": "Bearer token123"
        }

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/metadata",
            additional_config={
                "correlation_id_param": "assetId",
            },
        )

        adapter = GenericRestAdapter(adapter_config, mock_auth_strategy)

        auth_result = AuthResult(
            success=True,
            access_token="token123",
            token_type="Bearer",
        )

        # Mock the requests.get call
        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"title": "Test Asset"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            # Act - pass None explicitly
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is True
            mock_get.assert_called_once()

    def test_empty_credential_headers_works(self):
        """
        Test that passing empty dict for credential_headers works correctly.
        """
        # Arrange
        mock_auth_strategy = MagicMock()
        mock_auth_strategy.get_auth_header.return_value = {
            "Authorization": "Bearer token123"
        }

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/metadata",
            additional_config={
                "correlation_id_param": "assetId",
            },
        )

        adapter = GenericRestAdapter(adapter_config, mock_auth_strategy)

        auth_result = AuthResult(
            success=True,
            access_token="token123",
            token_type="Bearer",
        )

        # Mock the requests.get call
        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"title": "Test Asset"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            # Act - pass empty dict
            result = adapter.fetch_metadata("ABC123", auth_result, {})

            # Assert
            assert result.success is True
            mock_get.assert_called_once()
