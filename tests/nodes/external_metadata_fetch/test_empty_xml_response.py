"""
Unit tests for empty XML response handling in GenericRestAdapter.

Tests that the adapter correctly detects and handles empty XML responses,
including responses that contain only an XML declaration with no actual content.

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

# Now we can import from the adapters submodule
from nodes.external_metadata_fetch.adapters.generic_rest import GenericRestAdapter
from nodes.external_metadata_fetch.auth.base import AuthResult


@pytest.mark.unit
class TestEmptyXmlResponseHandling:
    """Tests for empty XML response detection and handling."""

    def _create_adapter(self, response_format: str = "xml") -> GenericRestAdapter:
        """Create a GenericRestAdapter configured for XML responses."""
        mock_auth_strategy = MagicMock()
        mock_auth_strategy.get_auth_header.return_value = {
            "Authorization": "Bearer token123"
        }

        adapter_config = AdapterConfig(
            metadata_endpoint="https://api.example.com/metadata",
            additional_config={
                "correlation_id_param": "assetId",
                "response_format": response_format,
            },
        )

        return GenericRestAdapter(adapter_config, mock_auth_strategy)

    def _create_auth_result(self) -> AuthResult:
        """Create a valid AuthResult for testing."""
        return AuthResult(
            success=True,
            access_token="token123",
            token_type="Bearer",
        )

    def test_empty_xml_declaration_only_returns_error(self):
        """
        Test that an XML response with only declaration (no content) returns error.

        This handles the case where the API returns:
        <?xml version="1.0" encoding="utf-8"?>

        With no actual XML content.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = '<?xml version="1.0" encoding="utf-8"?>'
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is False
            assert "Empty XML response" in result.error_message
            assert "ABC123" in result.error_message

    def test_empty_xml_declaration_with_whitespace_returns_error(self):
        """
        Test that XML declaration followed by whitespace only returns error.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = '<?xml version="1.0" encoding="utf-8"?>   \n\n  '
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is False
            assert "Empty XML response" in result.error_message

    def test_empty_xml_with_bom_returns_error(self):
        """
        Test that XML with BOM (Byte Order Mark) and no content returns error.

        Some APIs return BOM characters at the start of XML responses.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            # BOM + XML declaration + no content
            mock_response.text = '\ufeff<?xml version="1.0" encoding="utf-8"?>'
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is False
            assert "Empty XML response" in result.error_message

    def test_valid_xml_response_succeeds(self):
        """
        Test that a valid XML response with content is processed successfully.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
            <asset>
                <title>Test Asset</title>
                <description>A test asset</description>
            </asset>"""
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is True
            assert result.raw_metadata is not None
            assert "asset" in result.raw_metadata

    def test_completely_empty_response_returns_error(self):
        """
        Test that a completely empty response returns error.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = ""
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is False
            assert "Empty response" in result.error_message

    def test_whitespace_only_response_returns_error(self):
        """
        Test that a whitespace-only response returns error.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = "   \n\n   "
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is False
            assert "Empty response" in result.error_message

    def test_json_empty_response_returns_error(self):
        """
        Test that empty JSON response also returns error.
        """
        adapter = self._create_adapter(response_format="json")
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = ""
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is False
            assert "Empty response" in result.error_message

    def test_xml_with_only_root_element_succeeds(self):
        """
        Test that XML with just a root element (minimal valid XML) succeeds.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = '<?xml version="1.0"?><root/>'
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is True
            assert result.raw_metadata is not None

    def test_xml_without_declaration_succeeds(self):
        """
        Test that XML without declaration but with content succeeds.
        """
        adapter = self._create_adapter()
        auth_result = self._create_auth_result()

        with patch(
            "nodes.external_metadata_fetch.adapters.generic_rest.requests.get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.text = "<asset><title>Test</title></asset>"
            mock_response.headers = {"Content-Type": "application/xml"}
            mock_get.return_value = mock_response

            # Act
            result = adapter.fetch_metadata("ABC123", auth_result, None)

            # Assert
            assert result.success is True
            assert result.raw_metadata is not None
            assert "asset" in result.raw_metadata
