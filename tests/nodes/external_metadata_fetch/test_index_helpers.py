"""
Unit tests for helper functions in index.py.

Tests the internal helper functions that support the main Lambda handler,
including _get_existing_external_id() which implements the smart correlation
ID resolution logic based on previous lookup status.

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
from nodes.external_metadata_fetch.index import _get_existing_external_id


@pytest.mark.unit
class TestGetExistingExternalId:
    """
    Tests for _get_existing_external_id() function.

    This function should only return the existing ExternalAssetId if:
    1. ExternalAssetId is present and non-empty
    2. ExternalMetadataStatus.status is "success"

    This prevents re-using a bad correlation ID from a failed attempt.
    """

    def test_returns_id_when_status_is_success(self):
        """
        Test that ExternalAssetId is returned when status is "success".

        This is the happy path - previous lookup succeeded, so we trust the ID.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "EXT-001234",
            "ExternalMetadataStatus": {
                "status": "success",
                "lastAttempt": "2024-01-15T10:30:00Z",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result == "EXT-001234"

    def test_returns_none_when_status_is_failed(self):
        """
        Test that None is returned when status is "failed".

        This prevents re-using a bad correlation ID that was set during
        a failed attempt (e.g., extracted from filename but API returned no data).
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "bad-id-from-filename",  # Bad ID from filename extraction
            "ExternalMetadataStatus": {
                "status": "failed",
                "errorMessage": "Asset not found in external system",
                "lastAttempt": "2024-01-15T10:30:00Z",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_status_is_pending(self):
        """
        Test that None is returned when status is "pending".

        Pending status means a lookup is in progress - don't trust the ID yet.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "ABC123",
            "ExternalMetadataStatus": {
                "status": "pending",
                "lastAttempt": "2024-01-15T10:30:00Z",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_no_external_asset_id(self):
        """
        Test that None is returned when ExternalAssetId is not present.

        This is the case for new assets that haven't been processed yet.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            # No ExternalAssetId
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_external_asset_id_is_empty(self):
        """
        Test that None is returned when ExternalAssetId is empty string.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "",
            "ExternalMetadataStatus": {
                "status": "success",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_external_asset_id_is_whitespace(self):
        """
        Test that None is returned when ExternalAssetId is whitespace only.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "   ",
            "ExternalMetadataStatus": {
                "status": "success",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_no_metadata_status(self):
        """
        Test that None is returned when ExternalMetadataStatus is not present.

        Without status info, we can't verify the ID is good.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "EXT-001234",
            # No ExternalMetadataStatus
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_metadata_status_is_not_dict(self):
        """
        Test that None is returned when ExternalMetadataStatus is not a dict.

        Handles malformed data gracefully.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "EXT-001234",
            "ExternalMetadataStatus": "success",  # String instead of dict
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_status_field_missing(self):
        """
        Test that None is returned when status field is missing from ExternalMetadataStatus.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "EXT-001234",
            "ExternalMetadataStatus": {
                "lastAttempt": "2024-01-15T10:30:00Z",
                # No status field
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_strips_whitespace_from_external_asset_id(self):
        """
        Test that ExternalAssetId is stripped of whitespace before returning.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "  EXT-001234  ",  # With surrounding whitespace
            "ExternalMetadataStatus": {
                "status": "success",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result == "EXT-001234"

    def test_returns_none_when_external_asset_id_is_none(self):
        """
        Test that None is returned when ExternalAssetId is explicitly None.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": None,
            "ExternalMetadataStatus": {
                "status": "success",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_returns_none_when_external_asset_id_is_not_string(self):
        """
        Test that None is returned when ExternalAssetId is not a string.

        Handles malformed data gracefully.
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": 12345,  # Integer instead of string
            "ExternalMetadataStatus": {
                "status": "success",
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None

    def test_case_sensitive_status_check(self):
        """
        Test that status check is case-sensitive ("success" not "Success").
        """
        # Arrange
        asset = {
            "InventoryID": "asset:uuid:12345",
            "ExternalAssetId": "EXT-001234",
            "ExternalMetadataStatus": {
                "status": "Success",  # Wrong case
            },
        }

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None  # Should not match

    def test_empty_asset_dict(self):
        """
        Test that empty asset dict returns None gracefully.
        """
        # Arrange
        asset = {}

        # Act
        result = _get_existing_external_id(asset)

        # Assert
        assert result is None
