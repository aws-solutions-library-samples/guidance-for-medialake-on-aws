"""
Unit tests for the AssetProcessingService.

Tests the core business logic for asset processing operations.
"""

from unittest.mock import Mock, patch

import pytest

from lambdas.ingest.s3.service import AssetProcessingService


class TestAssetProcessingService:
    """Test cases for the AssetProcessingService class."""

    @pytest.fixture
    def mock_s3_adapter(self):
        """Mock S3 adapter for testing."""
        return Mock()

    @pytest.fixture
    def mock_notify_adapter(self):
        """Mock notification adapter for testing."""
        return Mock()

    @pytest.fixture
    def service(self, mock_s3_adapter, mock_notify_adapter):
        """Create service instance with mocked adapters."""
        with patch(
            "lambdas.ingest.s3.service.S3Adapter", return_value=mock_s3_adapter
        ), patch(
            "lambdas.ingest.s3.service.NotificationAdapter",
            return_value=mock_notify_adapter,
        ):
            return AssetProcessingService()

    def test_process_asset_success(self, service, mock_s3_adapter, mock_notify_adapter):
        """Test successful asset processing."""
        # Setup mocks
        mock_s3_adapter.object_exists.return_value = True
        mock_s3_adapter.get_object_metadata_and_tags.return_value = (
            {"ContentType": "image/jpeg", "ContentLength": 1024},
            {"title": "Test Image"},
        )
        mock_s3_adapter.calculate_md5_hash.return_value = "abc123"
        mock_s3_adapter.get_asset_by_hash.return_value = None  # No duplicate

        # Call service
        result = service.process_asset("test-bucket", "test-file.jpg")

        # Verify result
        assert result["status"] == "processed"
        assert "inventory_id" in result
        assert result["asset_type"] == "image"
        assert result["file_hash"] == "abc123"

        # Verify adapter calls
        mock_s3_adapter.store_asset.assert_called_once()
        mock_s3_adapter.index_asset_for_search.assert_called_once()
        mock_s3_adapter.store_vector_embeddings.assert_called_once()
        mock_notify_adapter.publish_asset_created_event.assert_called_once()

    def test_process_asset_duplicate_detected(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test processing when duplicate asset is detected."""
        # Setup mocks for duplicate detection
        mock_s3_adapter.object_exists.return_value = True
        mock_s3_adapter.get_object_metadata_and_tags.return_value = (
            {"ContentType": "image/jpeg", "ContentLength": 1024},
            {},
        )
        mock_s3_adapter.calculate_md5_hash.return_value = "abc123"
        mock_s3_adapter.get_asset_by_hash.return_value = {
            "InventoryID": "existing-123",
            "Bucket": "other-bucket",
            "ObjectKey": "other-file.jpg",
        }

        # Call service
        result = service.process_asset("test-bucket", "test-file.jpg")

        # Verify duplicate handling
        assert result["status"] == "duplicate"
        assert result["original_inventory_id"] == "existing-123"

        # Verify no storage operations for duplicate
        mock_s3_adapter.store_asset.assert_not_called()
        mock_notify_adapter.publish_duplicate_detected_event.assert_called_once()

    def test_process_asset_object_not_exists(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test processing when S3 object doesn't exist."""
        # Setup mock for non-existent object
        mock_s3_adapter.object_exists.return_value = False

        # Call service
        result = service.process_asset("test-bucket", "non-existent.jpg")

        # Verify error handling
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

        # Verify no processing operations
        mock_s3_adapter.store_asset.assert_not_called()
        mock_notify_adapter.publish_processing_error_event.assert_called_once()

    def test_process_asset_s3_error(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test processing when S3 operations fail."""
        # Setup mock to raise exception
        mock_s3_adapter.object_exists.side_effect = Exception("S3 error")

        # Call service
        result = service.process_asset("test-bucket", "test-file.jpg")

        # Verify error handling
        assert result["status"] == "error"
        assert "S3 error" in result["error"]

        # Verify error notification
        mock_notify_adapter.publish_processing_error_event.assert_called_once()

    def test_delete_asset_success(self, service, mock_s3_adapter, mock_notify_adapter):
        """Test successful asset deletion."""
        # Setup mocks
        mock_s3_adapter.should_process_deletion.return_value = True
        mock_s3_adapter.get_asset_by_location.return_value = {
            "InventoryID": "test-123",
            "AssetType": "image",
        }

        # Call service
        result = service.delete_asset("test-bucket", "test-file.jpg")

        # Verify result
        assert result["status"] == "deleted"
        assert result["inventory_id"] == "test-123"

        # Verify adapter calls
        mock_s3_adapter.delete_asset.assert_called_once_with("test-123")
        mock_s3_adapter.remove_from_search_index.assert_called_once_with("test-123")
        mock_s3_adapter.delete_vector_embeddings.assert_called_once_with("test-123")
        mock_notify_adapter.publish_asset_deleted_event.assert_called_once()

    def test_delete_asset_not_found(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test deletion when asset record not found."""
        # Setup mocks
        mock_s3_adapter.should_process_deletion.return_value = True
        mock_s3_adapter.get_asset_by_location.return_value = None

        # Call service
        result = service.delete_asset("test-bucket", "test-file.jpg")

        # Verify result
        assert result["status"] == "not_found"
        assert "not found" in result["message"].lower()

        # Verify no deletion operations
        mock_s3_adapter.delete_asset.assert_not_called()

    def test_delete_asset_should_not_process(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test deletion when should_process_deletion returns False."""
        # Setup mocks
        mock_s3_adapter.should_process_deletion.return_value = False

        # Call service
        result = service.delete_asset(
            "test-bucket", "test-file.jpg", version_id="old-version"
        )

        # Verify result
        assert result["status"] == "skipped"
        assert "not latest version" in result["message"].lower()

        # Verify no deletion operations
        mock_s3_adapter.delete_asset.assert_not_called()

    def test_delete_asset_error(self, service, mock_s3_adapter, mock_notify_adapter):
        """Test deletion when database operations fail."""
        # Setup mocks
        mock_s3_adapter.should_process_deletion.return_value = True
        mock_s3_adapter.get_asset_by_location.return_value = {"InventoryID": "test-123"}
        mock_s3_adapter.delete_asset.side_effect = Exception("Database error")

        # Call service
        result = service.delete_asset("test-bucket", "test-file.jpg")

        # Verify error handling
        assert result["status"] == "error"
        assert "Database error" in result["error"]

        # Verify error notification
        mock_notify_adapter.publish_processing_error_event.assert_called_once()

    @patch("lambdas.ingest.s3.service.generate_inventory_id")
    @patch("lambdas.ingest.s3.service.determine_asset_type")
    @patch("lambdas.ingest.s3.service.extract_metadata_from_tags")
    @patch("lambdas.ingest.s3.service.extract_metadata_from_s3_metadata")
    @patch("lambdas.ingest.s3.service.create_asset_record")
    def test_process_asset_utility_integration(
        self,
        mock_create_record,
        mock_extract_s3_meta,
        mock_extract_tags,
        mock_determine_type,
        mock_generate_id,
        service,
        mock_s3_adapter,
        mock_notify_adapter,
    ):
        """Test that service properly integrates with utility functions."""
        # Setup mocks
        mock_generate_id.return_value = "test-inventory-123"
        mock_determine_type.return_value = "image"
        mock_extract_tags.return_value = {"title": "Test"}
        mock_extract_s3_meta.return_value = {"content_type": "image/jpeg"}
        mock_create_record.return_value = {"InventoryID": "test-inventory-123"}

        mock_s3_adapter.object_exists.return_value = True
        mock_s3_adapter.get_object_metadata_and_tags.return_value = (
            {"ContentType": "image/jpeg"},
            {"title": "Test"},
        )
        mock_s3_adapter.calculate_md5_hash.return_value = "abc123"
        mock_s3_adapter.get_asset_by_hash.return_value = None

        # Call service
        result = service.process_asset("test-bucket", "test-file.jpg")

        # Verify utility function calls
        mock_generate_id.assert_called_once()
        mock_determine_type.assert_called_once_with("test-file.jpg", "image/jpeg")
        mock_extract_tags.assert_called_once_with({"title": "Test"})
        mock_extract_s3_meta.assert_called_once_with({"ContentType": "image/jpeg"})
        mock_create_record.assert_called_once()

        # Verify result
        assert result["status"] == "processed"
        assert result["inventory_id"] == "test-inventory-123"

    def test_process_asset_with_tagging(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test asset processing with S3 object tagging."""
        # Setup mocks
        mock_s3_adapter.object_exists.return_value = True
        mock_s3_adapter.get_object_metadata_and_tags.return_value = (
            {"ContentType": "image/jpeg", "ContentLength": 1024},
            {"category": "photos"},
        )
        mock_s3_adapter.calculate_md5_hash.return_value = "abc123"
        mock_s3_adapter.get_asset_by_hash.return_value = None

        # Call service
        result = service.process_asset("test-bucket", "test-file.jpg")

        # Verify tagging operation
        mock_s3_adapter.tag_object.assert_called_once()
        call_args = mock_s3_adapter.tag_object.call_args
        assert call_args[0][0] == "test-bucket"  # bucket
        assert call_args[0][1] == "test-file.jpg"  # key
        assert "InventoryID" in call_args[0][2]  # tags should include InventoryID

        assert result["status"] == "processed"

    def test_concurrent_processing_safety(
        self, service, mock_s3_adapter, mock_notify_adapter
    ):
        """Test that service handles concurrent processing safely."""
        # This test would be more comprehensive in a real scenario
        # For now, we verify that the service doesn't maintain state between calls

        # Setup mocks for first call
        mock_s3_adapter.object_exists.return_value = True
        mock_s3_adapter.get_object_metadata_and_tags.return_value = (
            {"ContentType": "image/jpeg"},
            {},
        )
        mock_s3_adapter.calculate_md5_hash.return_value = "hash1"
        mock_s3_adapter.get_asset_by_hash.return_value = None

        # First call
        result1 = service.process_asset("bucket1", "file1.jpg")

        # Setup mocks for second call with different data
        mock_s3_adapter.calculate_md5_hash.return_value = "hash2"

        # Second call
        result2 = service.process_asset("bucket2", "file2.jpg")

        # Verify both calls succeeded independently
        assert result1["status"] == "processed"
        assert result2["status"] == "processed"
        assert result1["file_hash"] == "hash1"
        assert result2["file_hash"] == "hash2"
