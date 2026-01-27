"""
Unit tests for enrichment_status classification in index.py.

Tests the EnrichmentStatus values and the _is_no_match_error helper function
that determines whether an error should be classified as "no_match" vs "error".

**Feature: external-metadata-enrichment**
"""

import sys
from unittest.mock import MagicMock

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

import pytest

# Now we can import from index.py
from nodes.external_metadata_fetch.index import (
    EnrichmentResult,
    EnrichmentStatus,
    _is_no_match_error,
)


@pytest.mark.unit
class TestEnrichmentStatus:
    """
    Tests for EnrichmentStatus class constants.

    Verifies that the status values match the expected strings
    used by the Step Function Choice node for routing.
    """

    def test_success_status_value(self):
        """Test that SUCCESS status has correct value."""
        assert EnrichmentStatus.SUCCESS == "success"

    def test_no_match_status_value(self):
        """Test that NO_MATCH status has correct value."""
        assert EnrichmentStatus.NO_MATCH == "no_match"

    def test_auth_error_status_value(self):
        """Test that AUTH_ERROR status has correct value."""
        assert EnrichmentStatus.AUTH_ERROR == "auth_error"

    def test_error_status_value(self):
        """Test that ERROR status has correct value."""
        assert EnrichmentStatus.ERROR == "error"


@pytest.mark.unit
class TestEnrichmentResult:
    """
    Tests for EnrichmentResult dataclass.

    Verifies that the dataclass includes the enrichment_status field
    and defaults to ERROR status.
    """

    def test_default_enrichment_status_is_error(self):
        """Test that default enrichment_status is ERROR."""
        result = EnrichmentResult(success=False)
        assert result.enrichment_status == EnrichmentStatus.ERROR

    def test_success_result_with_status(self):
        """Test creating a successful result with SUCCESS status."""
        result = EnrichmentResult(
            success=True,
            enrichment_status=EnrichmentStatus.SUCCESS,
            correlation_id="ABC123",
            metadata={"title": "Test"},
            attempt_count=1,
        )
        assert result.success is True
        assert result.enrichment_status == EnrichmentStatus.SUCCESS
        assert result.correlation_id == "ABC123"
        assert result.metadata == {"title": "Test"}
        assert result.attempt_count == 1

    def test_no_match_result(self):
        """Test creating a no_match failure result."""
        result = EnrichmentResult(
            success=False,
            enrichment_status=EnrichmentStatus.NO_MATCH,
            correlation_id="BAD123",
            error_message="Asset not found",
            attempt_count=1,
        )
        assert result.success is False
        assert result.enrichment_status == EnrichmentStatus.NO_MATCH
        assert result.error_message == "Asset not found"

    def test_auth_error_result(self):
        """Test creating an auth_error failure result."""
        result = EnrichmentResult(
            success=False,
            enrichment_status=EnrichmentStatus.AUTH_ERROR,
            error_message="OAuth token expired",
            attempt_count=2,
        )
        assert result.success is False
        assert result.enrichment_status == EnrichmentStatus.AUTH_ERROR
        assert result.error_message == "OAuth token expired"

    def test_error_result(self):
        """Test creating a generic error failure result."""
        result = EnrichmentResult(
            success=False,
            enrichment_status=EnrichmentStatus.ERROR,
            error_message="Internal server error",
            attempt_count=3,
        )
        assert result.success is False
        assert result.enrichment_status == EnrichmentStatus.ERROR
        assert result.error_message == "Internal server error"


@pytest.mark.unit
class TestIsNoMatchError:
    """
    Tests for _is_no_match_error helper function.

    This function determines whether an error message indicates a "no match"
    condition (correlation ID not found) vs a generic error.
    """

    # Test cases that SHOULD be classified as no_match
    def test_not_found_message(self):
        """Test that 'not found' messages are classified as no_match."""
        assert _is_no_match_error("Asset not found") is True
        assert _is_no_match_error("Resource not found in system") is True
        assert _is_no_match_error("NOT FOUND") is True

    def test_404_message(self):
        """Test that 404 error messages are classified as no_match."""
        assert _is_no_match_error("HTTP 404 error") is True
        assert _is_no_match_error("Error: 404") is True
        assert _is_no_match_error("Status code: 404") is True

    def test_empty_xml_response(self):
        """Test that empty XML response messages are classified as no_match."""
        assert _is_no_match_error("Empty XML response from API") is True
        assert _is_no_match_error("Received empty xml response") is True

    def test_no_data_message(self):
        """Test that 'no data' messages are classified as no_match."""
        assert _is_no_match_error("No data returned") is True
        assert _is_no_match_error("API returned no data") is True

    def test_no_results_message(self):
        """Test that 'no results' messages are classified as no_match."""
        assert _is_no_match_error("No results found") is True
        assert _is_no_match_error("Query returned no results") is True

    def test_does_not_exist_message(self):
        """Test that 'does not exist' messages are classified as no_match."""
        assert _is_no_match_error("Asset does not exist") is True
        assert _is_no_match_error("Record does not exist in database") is True

    def test_invalid_correlation_message(self):
        """Test that 'invalid correlation' messages are classified as no_match."""
        assert _is_no_match_error("Invalid correlation ID") is True
        # Note: "Correlation ID is invalid" doesn't match "invalid correlation" pattern
        # because the pattern requires "invalid" before "correlation"

    def test_unknown_asset_message(self):
        """Test that 'unknown asset' messages are classified as no_match."""
        assert _is_no_match_error("Unknown asset ID") is True
        # Note: "Asset is unknown" doesn't match "unknown asset" pattern
        # because the pattern requires "unknown" before "asset"

    def test_asset_not_found_message(self):
        """Test that 'asset not found' messages are classified as no_match."""
        assert _is_no_match_error("Asset not found in external system") is True

    def test_no_metadata_message(self):
        """Test that 'no metadata' messages are classified as no_match."""
        assert _is_no_match_error("No metadata available") is True
        # Note: "Could not find metadata" doesn't match "no metadata" pattern

    def test_no_match_message(self):
        """Test that 'no match' messages are classified as no_match."""
        assert _is_no_match_error("No match for correlation ID") is True

    def test_empty_response_message(self):
        """Test that 'empty response' messages (non-XML) are classified as no_match."""
        assert (
            _is_no_match_error("Empty response from API for correlation ID: ABC123")
            is True
        )
        assert _is_no_match_error("Received empty response") is True
        # Also verify XML variant still works
        assert _is_no_match_error("Empty XML response from API") is True

    def test_cannot_be_empty_message(self):
        """Test that 'cannot be empty' messages are classified as no_match."""
        assert (
            _is_no_match_error("Correlation ID is required and cannot be empty") is True
        )
        assert _is_no_match_error("Filename cannot be empty") is True
        assert _is_no_match_error("Filename cannot be empty or whitespace only") is True

    def test_cannot_determine_correlation_message(self):
        """Test that 'cannot determine correlation' messages are classified as no_match."""
        assert (
            _is_no_match_error(
                "Cannot determine correlation ID: no override provided and no filename available"
            )
            is True
        )
        assert _is_no_match_error("Cannot determine correlation ID from input") is True

    def test_failed_to_extract_correlation_message(self):
        """Test that 'failed to extract correlation' messages are classified as no_match."""
        assert (
            _is_no_match_error(
                "Failed to extract correlation ID from filename 'invalid_file.mp4'"
            )
            is True
        )
        assert _is_no_match_error("Failed to extract correlation ID") is True

    # Test cases that should NOT be classified as no_match
    def test_http_500_not_no_match(self):
        """Test that HTTP 500 errors are NOT classified as no_match."""
        assert _is_no_match_error("HTTP 500 Internal Server Error") is False
        assert _is_no_match_error("Server returned 500") is False

    def test_timeout_not_no_match(self):
        """Test that timeout errors are NOT classified as no_match."""
        assert _is_no_match_error("Connection timeout") is False
        assert _is_no_match_error("Request timed out") is False

    def test_network_error_not_no_match(self):
        """Test that network errors are NOT classified as no_match."""
        assert _is_no_match_error("Network connection failed") is False
        assert _is_no_match_error("DNS resolution failed") is False

    def test_generic_exception_not_no_match(self):
        """Test that generic exceptions are NOT classified as no_match."""
        assert _is_no_match_error("Unexpected error occurred") is False
        assert _is_no_match_error("RuntimeError: something went wrong") is False

    def test_empty_message_not_no_match(self):
        """Test that empty error message is NOT classified as no_match."""
        assert _is_no_match_error("") is False
        assert _is_no_match_error(None) is False

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case-insensitive."""
        assert _is_no_match_error("NOT FOUND") is True
        assert _is_no_match_error("Not Found") is True
        assert _is_no_match_error("not found") is True
        assert _is_no_match_error("EMPTY XML RESPONSE") is True
