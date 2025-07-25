"""
Integration tests for the simplified Lambda architecture.

Tests the complete flow from handler through service to adapters.
"""

import json
from unittest.mock import Mock, patch

import pytest

from lambdas.ingest.s3.handler import lambda_handler


class TestIntegration:
    """Integration test cases for the complete asset processing flow."""

    @pytest.fixture
    def s3_create_event(self):
        """Sample S3 create event for integration testing."""
        return {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "awsRegion": "us-east-1",
                    "eventTime": "2023-01-01T12:00:00.000Z",
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "s3SchemaVersion": "1.0",
                        "configurationId": "test-config",
                        "bucket": {
                            "name": "test-bucket",
                            "arn": "arn:aws:s3:::test-bucket",
                        },
                        "object": {
                            "key": "images/test-photo.jpg",
                            "size": 2048,
                            "eTag": "d41d8cd98f00b204e9800998ecf8427e",  # pragma: allowlist secret
                            "sequencer": "0055AED6DCD90281E5",  # pragma: allowlist secret
                        },
                    },
                }
            ]
        }

    @pytest.fixture
    def s3_delete_event(self):
        """Sample S3 delete event for integration testing."""
        return {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "awsRegion": "us-east-1",
                    "eventTime": "2023-01-01T12:00:00.000Z",
                    "eventName": "ObjectRemoved:Delete",
                    "s3": {
                        "s3SchemaVersion": "1.0",
                        "configurationId": "test-config",
                        "bucket": {
                            "name": "test-bucket",
                            "arn": "arn:aws:s3:::test-bucket",
                        },
                        "object": {
                            "key": "images/test-photo.jpg",
                            "sequencer": "0055AED6DCD90281E5",  # pragma: allowlist secret
                        },
                    },
                }
            ]
        }

    @patch.dict(
        "os.environ",
        {
            "DYNAMODB_TABLE_NAME": "test-assets-table",
            "EVENT_BUS_NAME": "test-event-bus",
            "EVENT_SOURCE": "medialake.test",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("lambdas.ingest.s3.adapters.s3_adapter.boto3")
    @patch("lambdas.ingest.s3.adapters.notify.boto3")
    def test_end_to_end_asset_creation(
        self, mock_notify_boto3, mock_s3_boto3, s3_create_event
    ):
        """Test complete asset creation flow from handler to adapters."""
        # Setup S3 adapter mocks
        mock_s3_client = Mock()
        mock_dynamodb_resource = Mock()
        mock_table = Mock()

        mock_s3_boto3.client.return_value = mock_s3_client
        mock_s3_boto3.resource.return_value = mock_dynamodb_resource
        mock_dynamodb_resource.Table.return_value = mock_table

        # Setup S3 operations
        mock_s3_client.head_object.return_value = {"ContentLength": 2048}
        mock_s3_client.get_object_tagging.return_value = {"TagSet": []}
        mock_s3_client.get_object.return_value = {
            "Body": Mock(iter_chunks=Mock(return_value=[b"test", b"data"]))
        }

        # Setup DynamoDB operations
        mock_table.query.return_value = {"Items": []}  # No duplicates
        mock_table.put_item.return_value = {}

        # Setup notification adapter mocks
        mock_eventbridge_client = Mock()
        mock_notify_boto3.client.return_value = mock_eventbridge_client
        mock_eventbridge_client.put_events.return_value = {"FailedEntryCount": 0}

        # Execute the handler
        result = lambda_handler(s3_create_event, {})

        # Verify handler response
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["message"] == "Successfully processed 1 records"
        assert len(response_body["results"]) == 1
        assert response_body["results"][0]["status"] == "processed"

        # Verify S3 operations were called
        mock_s3_client.head_object.assert_called_with(
            Bucket="test-bucket", Key="images/test-photo.jpg"
        )
        mock_s3_client.get_object_tagging.assert_called_with(
            Bucket="test-bucket", Key="images/test-photo.jpg"
        )

        # Verify DynamoDB operations
        mock_table.query.assert_called()  # Duplicate check
        mock_table.put_item.assert_called()  # Asset storage

        # Verify event publishing
        mock_eventbridge_client.put_events.assert_called()

        # Verify the stored asset record structure
        put_item_call = mock_table.put_item.call_args
        stored_item = put_item_call[1]["Item"]
        assert "InventoryID" in stored_item
        assert stored_item["Bucket"] == "test-bucket"
        assert stored_item["ObjectKey"] == "images/test-photo.jpg"
        assert stored_item["AssetType"] == "image"

    @patch.dict(
        "os.environ",
        {
            "DYNAMODB_TABLE_NAME": "test-assets-table",
            "EVENT_BUS_NAME": "test-event-bus",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("lambdas.ingest.s3.adapters.s3_adapter.boto3")
    @patch("lambdas.ingest.s3.adapters.notify.boto3")
    def test_end_to_end_asset_deletion(
        self, mock_notify_boto3, mock_s3_boto3, s3_delete_event
    ):
        """Test complete asset deletion flow from handler to adapters."""
        # Setup S3 adapter mocks
        mock_s3_client = Mock()
        mock_dynamodb_resource = Mock()
        mock_table = Mock()

        mock_s3_boto3.client.return_value = mock_s3_client
        mock_s3_boto3.resource.return_value = mock_dynamodb_resource
        mock_dynamodb_resource.Table.return_value = mock_table

        # Setup versioning check (no versioning)
        mock_s3_client.get_bucket_versioning.return_value = {"Status": "Suspended"}

        # Setup existing asset lookup
        mock_table.query.return_value = {
            "Items": [{"InventoryID": "test-asset-123", "AssetType": "image"}]
        }
        mock_table.delete_item.return_value = {}

        # Setup notification adapter mocks
        mock_eventbridge_client = Mock()
        mock_notify_boto3.client.return_value = mock_eventbridge_client
        mock_eventbridge_client.put_events.return_value = {"FailedEntryCount": 0}

        # Execute the handler
        result = lambda_handler(s3_delete_event, {})

        # Verify handler response
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["message"] == "Successfully processed 1 records"
        assert len(response_body["results"]) == 1
        assert response_body["results"][0]["status"] == "deleted"
        assert response_body["results"][0]["inventory_id"] == "test-asset-123"

        # Verify deletion operations
        mock_table.query.assert_called()  # Asset lookup
        mock_table.delete_item.assert_called_with(Key={"InventoryID": "test-asset-123"})

        # Verify event publishing
        mock_eventbridge_client.put_events.assert_called()

    @patch.dict(
        "os.environ",
        {"DYNAMODB_TABLE_NAME": "test-assets-table", "AWS_REGION": "us-east-1"},
    )
    @patch("lambdas.ingest.s3.adapters.s3_adapter.boto3")
    @patch("lambdas.ingest.s3.adapters.notify.boto3")
    def test_duplicate_detection_flow(
        self, mock_notify_boto3, mock_s3_boto3, s3_create_event
    ):
        """Test duplicate detection in the complete flow."""
        # Setup S3 adapter mocks
        mock_s3_client = Mock()
        mock_dynamodb_resource = Mock()
        mock_table = Mock()

        mock_s3_boto3.client.return_value = mock_s3_client
        mock_s3_boto3.resource.return_value = mock_dynamodb_resource
        mock_dynamodb_resource.Table.return_value = mock_table

        # Setup S3 operations
        mock_s3_client.head_object.return_value = {"ContentLength": 2048}
        mock_s3_client.get_object_tagging.return_value = {"TagSet": []}
        mock_s3_client.get_object.return_value = {
            "Body": Mock(iter_chunks=Mock(return_value=[b"test", b"data"]))
        }

        # Setup duplicate detection
        mock_table.query.return_value = {
            "Items": [{"InventoryID": "existing-123", "Bucket": "other-bucket"}]
        }

        # Setup notification adapter mocks
        mock_eventbridge_client = Mock()
        mock_notify_boto3.client.return_value = mock_eventbridge_client
        mock_eventbridge_client.put_events.return_value = {"FailedEntryCount": 0}

        # Execute the handler
        result = lambda_handler(s3_create_event, {})

        # Verify duplicate handling
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["results"][0]["status"] == "duplicate"
        assert response_body["results"][0]["original_inventory_id"] == "existing-123"

        # Verify no storage operation for duplicate
        mock_table.put_item.assert_not_called()

        # Verify duplicate event was published
        mock_eventbridge_client.put_events.assert_called()

    @patch.dict(
        "os.environ",
        {"DYNAMODB_TABLE_NAME": "test-assets-table", "AWS_REGION": "us-east-1"},
    )
    @patch("lambdas.ingest.s3.adapters.s3_adapter.boto3")
    @patch("lambdas.ingest.s3.adapters.notify.boto3")
    def test_error_handling_flow(
        self, mock_notify_boto3, mock_s3_boto3, s3_create_event
    ):
        """Test error handling in the complete flow."""
        # Setup S3 adapter mocks to fail
        mock_s3_client = Mock()
        mock_s3_boto3.client.return_value = mock_s3_client
        mock_s3_client.head_object.side_effect = Exception("S3 connection failed")

        # Setup notification adapter mocks
        mock_eventbridge_client = Mock()
        mock_notify_boto3.client.return_value = mock_eventbridge_client
        mock_eventbridge_client.put_events.return_value = {"FailedEntryCount": 0}

        # Execute the handler
        result = lambda_handler(s3_create_event, {})

        # Verify error response
        assert result["statusCode"] == 500
        response_body = json.loads(result["body"])
        assert "error" in response_body
        assert "S3 connection failed" in response_body["error"]

        # Verify error event was published
        mock_eventbridge_client.put_events.assert_called()

    @patch.dict(
        "os.environ",
        {"DYNAMODB_TABLE_NAME": "test-assets-table", "AWS_REGION": "us-east-1"},
    )
    @patch("lambdas.ingest.s3.adapters.s3_adapter.boto3")
    @patch("lambdas.ingest.s3.adapters.notify.boto3")
    def test_utility_functions_integration(
        self, mock_notify_boto3, mock_s3_boto3, s3_create_event
    ):
        """Test that utility functions are properly integrated in the flow."""
        # Setup mocks
        mock_s3_client = Mock()
        mock_dynamodb_resource = Mock()
        mock_table = Mock()

        mock_s3_boto3.client.return_value = mock_s3_client
        mock_s3_boto3.resource.return_value = mock_dynamodb_resource
        mock_dynamodb_resource.Table.return_value = mock_table

        # Setup S3 operations with specific metadata
        mock_s3_client.head_object.return_value = {
            "ContentType": "image/jpeg",
            "ContentLength": 2048,
            "Metadata": {"title": "Test Image"},
        }
        mock_s3_client.get_object_tagging.return_value = {
            "TagSet": [{"Key": "category", "Value": "photos"}]
        }
        mock_s3_client.get_object.return_value = {
            "Body": Mock(iter_chunks=Mock(return_value=[b"test", b"data"]))
        }

        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.return_value = {}

        # Setup notification mocks
        mock_eventbridge_client = Mock()
        mock_notify_boto3.client.return_value = mock_eventbridge_client
        mock_eventbridge_client.put_events.return_value = {"FailedEntryCount": 0}

        # Execute the handler
        result = lambda_handler(s3_create_event, {})

        # Verify successful processing
        assert result["statusCode"] == 200

        # Verify that utility functions processed the data correctly
        put_item_call = mock_table.put_item.call_args
        stored_item = put_item_call[1]["Item"]

        # Check that asset type was determined correctly
        assert stored_item["AssetType"] == "image"

        # Check that metadata was extracted and processed
        assert "Metadata" in stored_item
        metadata = stored_item["Metadata"]
        assert "content_type" in metadata  # From S3 metadata extraction
        assert "tag_category" in metadata  # From tag extraction

        # Check that file hash was calculated
        assert "FileHash" in stored_item
        assert len(stored_item["FileHash"]) == 32  # MD5 hash length

    def test_concurrent_processing_simulation(self):
        """Test that the architecture can handle concurrent processing."""
        # This is a simplified test - in a real scenario, you'd use threading
        # or async processing to simulate true concurrency

        events = [
            {
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {"name": "bucket1"},
                            "object": {"key": f"file{i}.jpg", "size": 1024},
                        },
                    }
                ]
            }
            for i in range(3)
        ]

        results = []

        with patch.dict(
            "os.environ",
            {"DYNAMODB_TABLE_NAME": "test-table", "AWS_REGION": "us-east-1"},
        ), patch("lambdas.ingest.s3.adapters.s3_adapter.boto3") as mock_s3_boto3, patch(
            "lambdas.ingest.s3.adapters.notify.boto3"
        ) as mock_notify_boto3:

            # Setup mocks
            mock_s3_client = Mock()
            mock_dynamodb_resource = Mock()
            mock_table = Mock()

            mock_s3_boto3.client.return_value = mock_s3_client
            mock_s3_boto3.resource.return_value = mock_dynamodb_resource
            mock_dynamodb_resource.Table.return_value = mock_table

            mock_s3_client.head_object.return_value = {"ContentLength": 1024}
            mock_s3_client.get_object_tagging.return_value = {"TagSet": []}
            mock_s3_client.get_object.return_value = {
                "Body": Mock(iter_chunks=Mock(return_value=[b"data"]))
            }
            mock_table.query.return_value = {"Items": []}
            mock_table.put_item.return_value = {}

            mock_eventbridge_client = Mock()
            mock_notify_boto3.client.return_value = mock_eventbridge_client
            mock_eventbridge_client.put_events.return_value = {"FailedEntryCount": 0}

            # Process events sequentially (simulating concurrent Lambda invocations)
            for event in events:
                result = lambda_handler(event, {})
                results.append(result)

        # Verify all events were processed successfully
        for result in results:
            assert result["statusCode"] == 200
            response_body = json.loads(result["body"])
            assert response_body["results"][0]["status"] == "processed"

        # Verify each event was processed independently
        assert len(results) == 3
        assert mock_table.put_item.call_count == 3
