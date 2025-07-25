"""
Unit tests for the adapter classes.

Tests the S3 and notification adapters that handle AWS service integrations.
"""

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from lambdas.ingest.s3.adapters.notify import NotificationAdapter
from lambdas.ingest.s3.adapters.s3_adapter import S3Adapter


class TestS3Adapter:
    """Test cases for the S3Adapter class."""

    @pytest.fixture
    def s3_adapter(self):
        """Create S3Adapter instance with mocked AWS clients."""
        with patch("boto3.client"), patch("boto3.resource"), patch.dict(
            "os.environ",
            {"DYNAMODB_TABLE_NAME": "test-table", "AWS_REGION": "us-east-1"},
        ):
            return S3Adapter()

    def test_object_exists_true(self, s3_adapter):
        """Test object_exists when object exists."""
        s3_adapter.s3_client.head_object.return_value = {"ContentLength": 1024}

        result = s3_adapter.object_exists("test-bucket", "test-key")

        assert result is True
        s3_adapter.s3_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-key"
        )

    def test_object_exists_false(self, s3_adapter):
        """Test object_exists when object doesn't exist."""
        error = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        s3_adapter.s3_client.head_object.side_effect = error

        result = s3_adapter.object_exists("test-bucket", "test-key")

        assert result is False

    def test_object_exists_other_error(self, s3_adapter):
        """Test object_exists with non-404 error."""
        error = ClientError({"Error": {"Code": "403"}}, "HeadObject")
        s3_adapter.s3_client.head_object.side_effect = error

        with pytest.raises(ClientError):
            s3_adapter.object_exists("test-bucket", "test-key")

    @patch("concurrent.futures.ThreadPoolExecutor")
    def test_get_object_metadata_and_tags(self, mock_executor, s3_adapter):
        """Test parallel retrieval of metadata and tags."""
        # Setup mock executor
        mock_future1 = Mock()
        mock_future1.result.return_value = {"ContentType": "image/jpeg"}
        mock_future2 = Mock()
        mock_future2.result.return_value = {
            "TagSet": [{"Key": "title", "Value": "Test"}]
        }

        mock_executor_instance = Mock()
        mock_executor_instance.submit.side_effect = [mock_future1, mock_future2]
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.__exit__.return_value = None
        mock_executor.return_value = mock_executor_instance

        metadata, tags = s3_adapter.get_object_metadata_and_tags("bucket", "key")

        assert metadata == {"ContentType": "image/jpeg"}
        assert tags == {"title": "Test"}
        assert mock_executor_instance.submit.call_count == 2

    def test_calculate_md5_hash(self, s3_adapter):
        """Test MD5 hash calculation."""
        # Mock S3 response with streaming body
        mock_body = Mock()
        mock_body.iter_chunks.return_value = [b"test", b"data"]
        s3_adapter.s3_client.get_object.return_value = {"Body": mock_body}

        result = s3_adapter.calculate_md5_hash("bucket", "key")

        # Verify hash calculation (MD5 of 'testdata')
        import hashlib

        expected_hash = hashlib.md5(b"testdata", usedforsecurity=False).hexdigest()
        assert result == expected_hash

    def test_get_asset_by_hash(self, s3_adapter):
        """Test querying asset by hash."""
        s3_adapter.assets_table.query.return_value = {
            "Items": [{"InventoryID": "test-123", "FileHash": "abc123"}]
        }

        result = s3_adapter.get_asset_by_hash("abc123")

        assert result["InventoryID"] == "test-123"
        s3_adapter.assets_table.query.assert_called_once()

    def test_get_asset_by_hash_not_found(self, s3_adapter):
        """Test querying asset by hash when not found."""
        s3_adapter.assets_table.query.return_value = {"Items": []}

        result = s3_adapter.get_asset_by_hash("nonexistent")

        assert result is None

    def test_store_asset(self, s3_adapter):
        """Test storing asset record."""
        asset_record = {"InventoryID": "test-123", "Bucket": "test-bucket"}

        s3_adapter.store_asset(asset_record)

        s3_adapter.assets_table.put_item.assert_called_once_with(Item=asset_record)

    def test_delete_asset(self, s3_adapter):
        """Test deleting asset record."""
        s3_adapter.delete_asset("test-123")

        s3_adapter.assets_table.delete_item.assert_called_once_with(
            Key={"InventoryID": "test-123"}
        )

    def test_tag_object(self, s3_adapter):
        """Test tagging S3 object."""
        tags = {"key1": "value1", "key2": "value2"}

        s3_adapter.tag_object("bucket", "key", tags)

        expected_tag_set = [
            {"Key": "key1", "Value": "value1"},
            {"Key": "key2", "Value": "value2"},
        ]
        s3_adapter.s3_client.put_object_tagging.assert_called_once_with(
            Bucket="bucket", Key="key", Tagging={"TagSet": expected_tag_set}
        )

    def test_should_process_deletion_no_versioning(self, s3_adapter):
        """Test deletion processing when versioning is disabled."""
        s3_adapter.s3_client.get_bucket_versioning.return_value = {
            "Status": "Suspended"
        }

        result = s3_adapter.should_process_deletion("bucket", "key")

        assert result is True

    def test_should_process_deletion_latest_version(self, s3_adapter):
        """Test deletion processing for latest version."""
        s3_adapter.s3_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
        s3_adapter.s3_client.list_object_versions.return_value = {
            "Versions": [
                {"Key": "key", "VersionId": "v2", "LastModified": "2023-01-02"},
                {"Key": "key", "VersionId": "v1", "LastModified": "2023-01-01"},
            ]
        }

        result = s3_adapter.should_process_deletion("bucket", "key", "v2")

        assert result is True

    def test_should_process_deletion_old_version(self, s3_adapter):
        """Test deletion processing for old version."""
        s3_adapter.s3_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
        s3_adapter.s3_client.list_object_versions.return_value = {
            "Versions": [
                {"Key": "key", "VersionId": "v2", "LastModified": "2023-01-02"},
                {"Key": "key", "VersionId": "v1", "LastModified": "2023-01-01"},
            ]
        }

        result = s3_adapter.should_process_deletion("bucket", "key", "v1")

        assert result is False


class TestNotificationAdapter:
    """Test cases for the NotificationAdapter class."""

    @pytest.fixture
    def notify_adapter(self):
        """Create NotificationAdapter instance with mocked AWS clients."""
        with patch("boto3.client"), patch.dict(
            "os.environ", {"EVENT_BUS_NAME": "test-bus", "EVENT_SOURCE": "test.source"}
        ):
            return NotificationAdapter()

    def test_publish_asset_created_event(self, notify_adapter):
        """Test publishing asset created event."""
        asset_record = {
            "InventoryID": "test-123",
            "AssetType": "image",
            "Bucket": "test-bucket",
            "ObjectKey": "test.jpg",
        }

        notify_adapter.publish_asset_created_event("test-123", asset_record)

        notify_adapter.eventbridge_client.put_events.assert_called_once()
        call_args = notify_adapter.eventbridge_client.put_events.call_args
        entries = call_args[1]["Entries"]

        assert len(entries) == 1
        assert entries[0]["Source"] == "test.source"
        assert entries[0]["DetailType"] == "Asset Created"
        assert "test-123" in entries[0]["Detail"]

    def test_publish_asset_deleted_event(self, notify_adapter):
        """Test publishing asset deleted event."""
        notify_adapter.publish_asset_deleted_event("test-123", "bucket", "key")

        notify_adapter.eventbridge_client.put_events.assert_called_once()
        call_args = notify_adapter.eventbridge_client.put_events.call_args
        entries = call_args[1]["Entries"]

        assert entries[0]["DetailType"] == "Asset Deleted"
        assert "test-123" in entries[0]["Detail"]

    def test_publish_duplicate_detected_event(self, notify_adapter):
        """Test publishing duplicate detected event."""
        notify_adapter.publish_duplicate_detected_event(
            "new-123", "original-123", "bucket", "key", "hash123"
        )

        notify_adapter.eventbridge_client.put_events.assert_called_once()
        call_args = notify_adapter.eventbridge_client.put_events.call_args
        entries = call_args[1]["Entries"]

        assert entries[0]["DetailType"] == "Duplicate Asset Detected"
        detail = entries[0]["Detail"]
        assert "new-123" in detail
        assert "original-123" in detail

    def test_publish_processing_error_event(self, notify_adapter):
        """Test publishing processing error event."""
        notify_adapter.publish_processing_error_event(
            "bucket", "key", "Test error", "validation_error"
        )

        notify_adapter.eventbridge_client.put_events.assert_called_once()
        call_args = notify_adapter.eventbridge_client.put_events.call_args
        entries = call_args[1]["Entries"]

        assert entries[0]["DetailType"] == "Asset Processing Error"
        detail = entries[0]["Detail"]
        assert "Test error" in detail
        assert "validation_error" in detail

    def test_make_json_serializable(self, notify_adapter):
        """Test JSON serialization helper."""
        from datetime import datetime

        test_obj = {
            "string": "test",
            "number": 123,
            "datetime": datetime(2023, 1, 1, 12, 0, 0),
            "nested": {"list": [1, 2, 3], "bool": True},
        }

        result = notify_adapter._make_json_serializable(test_obj)

        assert result["string"] == "test"
        assert result["number"] == 123
        assert result["datetime"] == "2023-01-01T12:00:00"
        assert result["nested"]["list"] == [1, 2, 3]
        assert result["nested"]["bool"] is True

    def test_send_notification(self, notify_adapter):
        """Test sending general notification."""
        notify_adapter.send_notification("info", "Test message", {"key": "value"})

        notify_adapter.eventbridge_client.put_events.assert_called_once()
        call_args = notify_adapter.eventbridge_client.put_events.call_args
        entries = call_args[1]["Entries"]

        assert entries[0]["DetailType"] == "General Notification"
        detail = entries[0]["Detail"]
        assert "Test message" in detail
        assert "info" in detail

    def test_publish_batch_processing_event(self, notify_adapter):
        """Test publishing batch processing event."""
        notify_adapter.publish_batch_processing_event("batch-123", 100, 95, 5)

        notify_adapter.eventbridge_client.put_events.assert_called_once()
        call_args = notify_adapter.eventbridge_client.put_events.call_args
        entries = call_args[1]["Entries"]

        assert entries[0]["DetailType"] == "Batch Processing Completed"
        detail = entries[0]["Detail"]
        assert "batch-123" in detail
        assert "95.0" in detail  # Success rate calculation

    def test_event_publishing_error_handling(self, notify_adapter):
        """Test error handling in event publishing."""
        # Setup mock to raise exception
        notify_adapter.eventbridge_client.put_events.side_effect = Exception(
            "EventBridge error"
        )

        # Should not raise exception (errors are logged but not propagated)
        notify_adapter.publish_asset_created_event("test-123", {})

        # Verify the call was attempted
        notify_adapter.eventbridge_client.put_events.assert_called_once()

    def test_failed_entries_handling(self, notify_adapter):
        """Test handling of failed EventBridge entries."""
        notify_adapter.eventbridge_client.put_events.return_value = {
            "FailedEntryCount": 1,
            "Entries": [{"ErrorCode": "ValidationException"}],
        }

        # Should not raise exception but log the failure
        notify_adapter.publish_asset_created_event("test-123", {})

        notify_adapter.eventbridge_client.put_events.assert_called_once()
