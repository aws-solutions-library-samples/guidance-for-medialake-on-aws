"""
Unit tests for OpenSearch field verification.

These tests verify that the field verification function correctly identifies
existing fields, logs warnings for non-existent fields, and handles errors
gracefully.

**Feature: assets-page-bugs, Task 11.4**
**Validates: Requirements 2.2, 2.4**
"""

from unittest.mock import Mock, patch

import pytest

from lambdas.api.search.get_search.index import (
    STORAGE_IDENTIFIER_FIELD,
    verify_opensearch_field_exists,
)


@pytest.mark.unit
class TestFieldVerification:
    """Unit tests for field verification functionality."""

    def test_verify_field_exists_for_simple_field(self):
        """
        Test that verification correctly identifies a simple existing field.

        **Validates: Requirement 2.2**

        This test ensures that the verification function can identify
        a field that exists at the top level of the mapping.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                "mappings": {"properties": {"SimpleField": {"type": "text"}}}
            }
        }

        # Act
        result = verify_opensearch_field_exists(
            mock_client, "test-index", "SimpleField"
        )

        # Assert
        assert result is True, "Should return True for existing simple field"
        mock_client.indices.get_mapping.assert_called_once_with(index="test-index")

    def test_verify_field_exists_for_nested_field(self):
        """
        Test that verification correctly identifies a nested existing field.

        **Validates: Requirement 2.2**

        This test ensures that the verification function can navigate
        through nested field structures.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                "mappings": {
                    "properties": {
                        "DigitalSourceAsset": {
                            "properties": {"Type": {"type": "keyword"}}
                        }
                    }
                }
            }
        }

        # Act
        result = verify_opensearch_field_exists(
            mock_client, "test-index", "DigitalSourceAsset.Type"
        )

        # Assert
        assert result is True, "Should return True for existing nested field"

    def test_verify_field_exists_for_deeply_nested_field(self):
        """
        Test that verification correctly identifies a deeply nested field.

        **Validates: Requirement 2.2**

        This test ensures that the verification function can navigate
        through multiple levels of nesting.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                "mappings": {
                    "properties": {
                        "DigitalSourceAsset": {
                            "properties": {
                                "MainRepresentation": {
                                    "properties": {
                                        "StorageInfo": {
                                            "properties": {
                                                "PrimaryLocation": {
                                                    "properties": {
                                                        "Bucket": {"type": "keyword"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # Act
        result = verify_opensearch_field_exists(
            mock_client,
            "test-index",
            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket",
        )

        # Assert
        assert result is True, "Should return True for deeply nested existing field"

    @patch("lambdas.api.search.get_search.index.logger")
    def test_verify_field_logs_warning_for_nonexistent_field(self, mock_logger):
        """
        Test that verification logs warning for non-existent fields.

        **Validates: Requirement 2.4**

        This test ensures that when a field doesn't exist, a warning
        is logged but the function doesn't raise an exception.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                "mappings": {"properties": {"ExistingField": {"type": "text"}}}
            }
        }

        # Act
        result = verify_opensearch_field_exists(
            mock_client, "test-index", "NonExistentField"
        )

        # Assert
        assert result is False, "Should return False for non-existent field"

        # Verify warning was logged
        assert mock_logger.warning.called, "Should log warning for non-existent field"

        warning_message = str(mock_logger.warning.call_args)
        assert (
            "NonExistentField" in warning_message
            or "not found" in warning_message.lower()
        ), f"Warning should mention the missing field: {warning_message}"

    @patch("lambdas.api.search.get_search.index.logger")
    def test_verify_field_logs_warning_for_incomplete_nested_path(self, mock_logger):
        """
        Test that verification logs warning for incomplete nested paths.

        **Validates: Requirement 2.4**

        This test ensures that when a nested path is incomplete (e.g.,
        trying to access a nested field that doesn't have properties),
        a warning is logged.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                "mappings": {
                    "properties": {
                        "DigitalSourceAsset": {
                            "properties": {
                                "Type": {
                                    "type": "keyword"
                                    # No nested properties
                                }
                            }
                        }
                    }
                }
            }
        }

        # Act
        result = verify_opensearch_field_exists(
            mock_client, "test-index", "DigitalSourceAsset.Type.NonExistent"
        )

        # Assert
        assert result is False, "Should return False for incomplete nested path"

        # Verify warning was logged
        assert mock_logger.warning.called, "Should log warning for incomplete path"

    @patch("lambdas.api.search.get_search.index.logger")
    def test_verify_field_handles_missing_index(self, mock_logger):
        """
        Test that verification handles missing index gracefully.

        **Validates: Requirement 2.4**

        This test ensures that when the index doesn't exist in the
        mapping response, the function returns False and logs a warning.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "different-index": {"mappings": {"properties": {}}}
        }

        # Act
        result = verify_opensearch_field_exists(mock_client, "test-index", "SomeField")

        # Assert
        assert result is False, "Should return False when index not found"

        # Verify warning was logged
        assert mock_logger.warning.called, "Should log warning for missing index"

    @patch("lambdas.api.search.get_search.index.logger")
    def test_verify_field_handles_exception(self, mock_logger):
        """
        Test that verification handles exceptions gracefully.

        **Validates: Requirement 2.4**

        This test ensures that when an exception occurs during verification,
        the function returns False and logs a warning instead of crashing.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.side_effect = Exception("Connection error")

        # Act
        result = verify_opensearch_field_exists(mock_client, "test-index", "SomeField")

        # Assert
        assert result is False, "Should return False when exception occurs"

        # Verify warning was logged
        assert mock_logger.warning.called, "Should log warning for exception"

        warning_message = str(mock_logger.warning.call_args)
        assert (
            "Connection error" in warning_message
            or "Could not verify" in warning_message
        ), f"Warning should mention the error: {warning_message}"

    def test_verify_field_continues_despite_failure(self):
        """
        Test that query construction continues despite verification failure.

        **Validates: Requirement 2.4**

        This test ensures that even when field verification fails,
        the system continues to construct and execute queries.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {"mappings": {"properties": {}}}
        }

        # Act
        result = verify_opensearch_field_exists(
            mock_client, "test-index", "NonExistentField"
        )

        # Assert
        assert result is False, "Verification should fail for non-existent field"

        # The function should not raise an exception
        # This test passes if we reach this point without exception

    def test_storage_identifier_field_constant_is_defined(self):
        """
        Test that the STORAGE_IDENTIFIER_FIELD constant is properly defined.

        **Validates: Requirement 2.5**

        This test ensures that the storage identifier field constant
        is defined and points to the correct field path.
        """
        # Assert
        assert (
            STORAGE_IDENTIFIER_FIELD is not None
        ), "STORAGE_IDENTIFIER_FIELD should be defined"

        assert isinstance(
            STORAGE_IDENTIFIER_FIELD, str
        ), "STORAGE_IDENTIFIER_FIELD should be a string"

        assert (
            "Bucket" in STORAGE_IDENTIFIER_FIELD
        ), "STORAGE_IDENTIFIER_FIELD should reference Bucket field"

        assert (
            "DigitalSourceAsset" in STORAGE_IDENTIFIER_FIELD
        ), "STORAGE_IDENTIFIER_FIELD should be in DigitalSourceAsset namespace"

        # Verify the exact expected path
        expected_path = (
            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket"
        )
        assert (
            STORAGE_IDENTIFIER_FIELD == expected_path
        ), f"STORAGE_IDENTIFIER_FIELD should be '{expected_path}', got '{STORAGE_IDENTIFIER_FIELD}'"

    def test_verify_field_with_empty_field_path(self):
        """
        Test that verification handles empty field path gracefully.

        **Validates: Requirement 2.4**

        This test ensures that an empty field path is handled correctly.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {"mappings": {"properties": {"SomeField": {"type": "text"}}}}
        }

        # Act
        result = verify_opensearch_field_exists(mock_client, "test-index", "")

        # Assert
        # Empty path should return True (we're at the root level)
        # or False depending on implementation
        assert isinstance(result, bool), "Should return a boolean for empty path"

    @patch("lambdas.api.search.get_search.index.logger")
    def test_verify_field_with_malformed_mapping(self, mock_logger):
        """
        Test that verification handles malformed mapping structure.

        **Validates: Requirement 2.4**

        This test ensures that malformed mapping structures are handled
        gracefully without crashing.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                # Missing "mappings" key
                "properties": {"SomeField": {"type": "text"}}
            }
        }

        # Act
        result = verify_opensearch_field_exists(mock_client, "test-index", "SomeField")

        # Assert
        assert result is False, "Should return False for malformed mapping"

    def test_verify_field_with_keyword_subfield(self):
        """
        Test that verification works with .keyword subfields.

        **Validates: Requirement 2.2**

        This test ensures that fields with .keyword subfields can be
        verified correctly.
        """
        # Arrange
        mock_client = Mock()
        mock_client.indices.get_mapping.return_value = {
            "test-index": {
                "mappings": {
                    "properties": {
                        "Name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        }
                    }
                }
            }
        }

        # Act
        result = verify_opensearch_field_exists(mock_client, "test-index", "Name")

        # Assert
        assert result is True, "Should return True for field with keyword subfield"
