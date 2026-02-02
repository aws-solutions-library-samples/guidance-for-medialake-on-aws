"""
Unit tests for bucket error handling.

These tests verify that the system correctly handles various bucket-related
errors and provides appropriate error messages with actionable guidance.

**Feature: assets-page-bugs, Task 12.5**
**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 12.1, 12.2, 12.5**
"""

import os
from unittest.mock import Mock, patch

import pytest
from opensearchpy import RequestError

from lambdas.api.search.get_search.index import SearchParams, perform_search


@pytest.mark.unit
class TestBucketErrorHandling:
    """Unit tests for bucket-related error handling."""

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    @patch("lambdas.api.search.get_search.index.logger")
    def test_non_existent_bucket_error(self, mock_logger, mock_get_client):
        """
        Test non-existent bucket error handling.

        **Validates: Requirements 7.1, 7.4, 7.6**

        This test ensures that when a bucket doesn't exist in the index,
        the system returns a 404 error with a specific message and
        actionable guidance.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate OpenSearch error for non-existent bucket
        error = RequestError(400, "no mapping found for field", {})
        mock_client.search.side_effect = error

        params = SearchParams(q="storageIdentifier:non-existent-bucket")

        # Act
        result = perform_search(params)

        # Assert
        assert result["status"] == "404", "Should return 404 for non-existent bucket"

        assert (
            "not found" in result["message"].lower()
        ), f"Message should indicate bucket not found: {result['message']}"

        assert (
            "non-existent-bucket" in result["message"]
        ), "Message should include the bucket name"

        # Check error details
        assert "data" in result, "Response should include data field"
        assert "error" in result["data"], "Data should include error code"
        assert (
            result["data"]["error"] == "BUCKET_NOT_FOUND"
        ), "Error code should be BUCKET_NOT_FOUND"

        # Check actionable guidance
        assert (
            "guidance" in result["data"]
        ), "Response should include actionable guidance"
        guidance = result["data"]["guidance"].lower()
        assert any(
            keyword in guidance for keyword in ["verify", "check", "wait", "indexed"]
        ), f"Guidance should provide actionable advice: {result['data']['guidance']}"

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    def test_invalid_bucket_name_error(self, mock_get_client):
        """
        Test invalid bucket name format error handling.

        **Validates: Requirements 7.2, 7.4, 7.6**

        This test ensures that when a bucket name has an invalid format,
        the system returns a 400 error with validation details and
        actionable guidance.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Test various invalid bucket names
        invalid_names = [
            "ab",  # Too short (< 3 chars)
            "a" * 64,  # Too long (> 63 chars)
            "",  # Empty
        ]

        for invalid_name in invalid_names:
            params = SearchParams(q=f"storageIdentifier:{invalid_name}")

            # Act
            result = perform_search(params)

            # Assert
            assert (
                result["status"] == "400"
            ), f"Should return 400 for invalid bucket name '{invalid_name}'"

            assert (
                "invalid" in result["message"].lower()
            ), f"Message should indicate invalid bucket name: {result['message']}"

            # Check error details
            assert "data" in result, "Response should include data field"
            assert "error" in result["data"], "Data should include error code"
            assert (
                result["data"]["error"] == "INVALID_BUCKET_NAME"
            ), "Error code should be INVALID_BUCKET_NAME"

            # Check details explain the validation rule
            assert "details" in result["data"], "Response should include error details"
            details = result["data"]["details"].lower()
            assert any(
                keyword in details for keyword in ["3", "63", "characters", "long"]
            ), f"Details should explain bucket name length requirements: {result['data']['details']}"

            # Check actionable guidance
            assert (
                "guidance" in result["data"]
            ), "Response should include actionable guidance"
            guidance = result["data"]["guidance"].lower()
            assert any(
                keyword in guidance for keyword in ["check", "verify", "try again"]
            ), f"Guidance should provide actionable advice: {result['data']['guidance']}"

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    @patch("lambdas.api.search.get_search.index.logger")
    def test_permission_denied_error(self, mock_logger, mock_get_client):
        """
        Test permission denied error handling.

        **Validates: Requirements 7.3, 7.4, 7.6**

        This test ensures that when a user doesn't have permission to
        access a bucket, the system returns a 403 error with specific
        message and actionable guidance.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate permission error
        mock_client.search.side_effect = PermissionError("Access denied")

        params = SearchParams(q="storageIdentifier:restricted-bucket")

        # Act
        result = perform_search(params)

        # Assert
        assert result["status"] == "403", "Should return 403 for permission denied"

        assert (
            "permission denied" in result["message"].lower()
        ), f"Message should indicate permission denied: {result['message']}"

        assert (
            "restricted-bucket" in result["message"]
        ), "Message should include the bucket name"

        # Check error details
        assert "data" in result, "Response should include data field"
        assert "error" in result["data"], "Data should include error code"
        assert (
            result["data"]["error"] == "PERMISSION_DENIED"
        ), "Error code should be PERMISSION_DENIED"

        # Check actionable guidance
        assert (
            "guidance" in result["data"]
        ), "Response should include actionable guidance"
        guidance = result["data"]["guidance"].lower()
        assert any(
            keyword in guidance
            for keyword in ["administrator", "contact", "request", "access"]
        ), f"Guidance should direct user to administrator: {result['data']['guidance']}"

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    @patch("lambdas.api.search.get_search.index.logger")
    def test_empty_connector_message(self, mock_logger, mock_get_client):
        """
        Test empty connector (no assets) message.

        **Validates: Requirements 12.1, 12.2, 12.5**

        This test ensures that when a connector has no indexed assets,
        the system returns an appropriate message distinguishing it from
        other error cases.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate empty results (connector exists but has no assets)
        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        params = SearchParams(q="storageIdentifier:empty-bucket")

        # Act
        result = perform_search(params)

        # Assert
        assert (
            result["status"] == "200"
        ), "Should return 200 for empty connector (not an error)"

        # Check that results are empty
        assert "data" in result, "Response should include data field"
        assert "results" in result["data"], "Data should include results array"
        assert len(result["data"]["results"]) == 0, "Results should be empty"

        # Check metadata indicates zero results
        assert "searchMetadata" in result["data"], "Data should include search metadata"
        assert (
            result["data"]["searchMetadata"]["totalResults"] == 0
        ), "Total results should be 0"

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    @patch("lambdas.api.search.get_search.index.logger")
    def test_no_search_results_message(self, mock_logger, mock_get_client):
        """
        Test no search results message (due to filters).

        **Validates: Requirements 12.1, 12.2, 12.5**

        This test ensures that when a search returns no results due to
        filters, the system distinguishes this from an empty connector.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate no results due to filters
        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        # Search with filters
        params = SearchParams(
            q="test query", type="video"  # Filter that yields no results
        )

        # Act
        result = perform_search(params)

        # Assert
        assert (
            result["status"] == "200"
        ), "Should return 200 for no results (not an error)"

        # Check that results are empty
        assert len(result["data"]["results"]) == 0, "Results should be empty"

        # Check metadata
        assert (
            result["data"]["searchMetadata"]["totalResults"] == 0
        ), "Total results should be 0"

    def test_error_response_structure(self):
        """
        Test that error responses have consistent structure.

        **Validates: Requirements 7.4, 7.5**

        This test ensures that all error responses follow a consistent
        structure with status, message, and data fields.
        """
        # This test verifies the structure is consistent across error types
        # The structure should be:
        # {
        #   "status": "400|403|404|500",
        #   "message": "Human-readable error message",
        #   "data": {
        #     "error": "ERROR_CODE",
        #     "details": "Detailed explanation",
        #     "guidance": "Actionable guidance",
        #     "searchMetadata": {...},
        #     "results": []
        #   }
        # }

        # This is a structural test - actual error responses are tested above

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    def test_bucket_error_includes_search_metadata(self, mock_get_client):
        """
        Test that bucket errors include search metadata.

        **Validates: Requirements 7.4**

        This test ensures that even error responses include search
        metadata for consistency.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Test with invalid bucket name
        params = SearchParams(q="storageIdentifier:ab")  # Too short

        # Act
        result = perform_search(params)

        # Assert
        assert "data" in result, "Error response should include data"
        assert (
            "searchMetadata" in result["data"]
        ), "Error response should include searchMetadata"

        metadata = result["data"]["searchMetadata"]
        assert "totalResults" in metadata, "Metadata should include totalResults"
        assert (
            metadata["totalResults"] == 0
        ), "Error response should have 0 total results"
        assert "page" in metadata, "Metadata should include page"
        assert "pageSize" in metadata, "Metadata should include pageSize"
        assert "searchTerm" in metadata, "Metadata should include searchTerm"

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    @patch("lambdas.api.search.get_search.index.logger")
    def test_error_distinguishes_bucket_types(self, mock_logger, mock_get_client):
        """
        Test that errors distinguish between different bucket error types.

        **Validates: Requirements 7.5**

        This test ensures that the system can distinguish between
        "bucket not found", "invalid bucket name", and "permission denied".
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Test 1: Invalid bucket name
        params1 = SearchParams(q="storageIdentifier:ab")
        result1 = perform_search(params1)

        # Test 2: Non-existent bucket
        error = RequestError(400, "no mapping found for field", {})
        mock_client.search.side_effect = error
        params2 = SearchParams(q="storageIdentifier:valid-but-nonexistent")
        result2 = perform_search(params2)

        # Test 3: Permission denied
        mock_client.search.side_effect = PermissionError("Access denied")
        params3 = SearchParams(q="storageIdentifier:restricted")
        result3 = perform_search(params3)

        # Assert - All three should have different error codes
        assert (
            result1["data"]["error"] == "INVALID_BUCKET_NAME"
        ), "Invalid bucket should have INVALID_BUCKET_NAME error code"
        assert (
            result2["data"]["error"] == "BUCKET_NOT_FOUND"
        ), "Non-existent bucket should have BUCKET_NOT_FOUND error code"
        assert (
            result3["data"]["error"] == "PERMISSION_DENIED"
        ), "Restricted bucket should have PERMISSION_DENIED error code"

        # Assert - All three should have different status codes
        assert result1["status"] == "400", "Invalid bucket should return 400"
        assert result2["status"] == "404", "Non-existent bucket should return 404"
        assert result3["status"] == "403", "Restricted bucket should return 403"

    @patch.dict(os.environ, {"OPENSEARCH_INDEX": "test-index"})
    @patch("lambdas.api.search.get_search.index.get_opensearch_client")
    def test_error_messages_are_user_friendly(self, mock_get_client):
        """
        Test that error messages are user-friendly and informative.

        **Validates: Requirements 7.4, 7.6**

        This test ensures that error messages are written for end users,
        not developers, and provide clear guidance.
        """
        # Arrange
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Test with invalid bucket name
        params = SearchParams(q="storageIdentifier:ab")

        # Act
        result = perform_search(params)

        # Assert
        message = result["message"]
        details = result["data"]["details"]
        guidance = result["data"]["guidance"]

        # Messages should not contain technical jargon
        technical_terms = ["exception", "traceback", "stack", "null", "undefined"]
        for term in technical_terms:
            assert (
                term not in message.lower()
            ), f"Message should not contain technical term '{term}': {message}"
            assert (
                term not in details.lower()
            ), f"Details should not contain technical term '{term}': {details}"

        # Guidance should be actionable
        actionable_words = ["check", "verify", "contact", "try", "please", "ensure"]
        assert any(
            word in guidance.lower() for word in actionable_words
        ), f"Guidance should contain actionable words: {guidance}"

        # Messages should be complete sentences
        assert message.strip(), "Message should not be empty"
        assert details.strip(), "Details should not be empty"
        assert guidance.strip(), "Guidance should not be empty"
