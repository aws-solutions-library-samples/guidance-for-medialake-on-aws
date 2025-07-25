"""
Unit tests for the Lambda handler.

Tests the thin handler layer that processes AWS S3 events
and delegates to the service layer.
"""

import json
from unittest.mock import Mock, patch

import pytest

from lambdas.ingest.s3.handler import lambda_handler


class TestLambdaHandler:
    """Test cases for the Lambda handler function."""

    @pytest.fixture
    def s3_event(self):
        """Sample S3 event for testing."""
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
                            "key": "test-folder/test-file.jpg",
                            "size": 1024,
                            "eTag": "d41d8cd98f00b204e9800998ecf8427e",  # pragma: allowlist secret
                            "sequencer": "0055AED6DCD90281E5",  # pragma: allowlist secret
                        },
                    },
                }
            ]
        }

    @pytest.fixture
    def s3_delete_event(self):
        """Sample S3 delete event for testing."""
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
                            "key": "test-folder/test-file.jpg",
                            "sequencer": "0055AED6DCD90281E5",  # pragma: allowlist secret
                        },
                    },
                }
            ]
        }

    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_create_event_success(self, mock_service_class, s3_event):
        """Test successful processing of S3 create event."""
        # Setup mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.process_asset.return_value = {
            "inventory_id": "test-123",
            "status": "processed",
        }

        # Call handler
        result = lambda_handler(s3_event, {})

        # Verify service was called correctly
        mock_service.process_asset.assert_called_once_with(
            bucket="test-bucket", object_key="test-folder/test-file.jpg"
        )

        # Verify response
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["message"] == "Successfully processed 1 records"
        assert len(response_body["results"]) == 1
        assert response_body["results"][0]["inventory_id"] == "test-123"

    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_delete_event_success(
        self, mock_service_class, s3_delete_event
    ):
        """Test successful processing of S3 delete event."""
        # Setup mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_asset.return_value = {
            "inventory_id": "test-123",
            "status": "deleted",
        }

        # Call handler
        result = lambda_handler(s3_delete_event, {})

        # Verify service was called correctly
        mock_service.delete_asset.assert_called_once_with(
            bucket="test-bucket", object_key="test-folder/test-file.jpg"
        )

        # Verify response
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["message"] == "Successfully processed 1 records"
        assert len(response_body["results"]) == 1
        assert response_body["results"][0]["inventory_id"] == "test-123"

    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_service_error(self, mock_service_class, s3_event):
        """Test handler response when service raises an error."""
        # Setup mock service to raise exception
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.process_asset.side_effect = Exception("Service error")

        # Call handler
        result = lambda_handler(s3_event, {})

        # Verify error response
        assert result["statusCode"] == 500
        response_body = json.loads(result["body"])
        assert "error" in response_body
        assert "Service error" in response_body["error"]

    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_multiple_records(self, mock_service_class):
        """Test handler processing multiple S3 records."""
        # Setup event with multiple records
        multi_record_event = {
            "Records": [
                {
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "file1.jpg"},
                    },
                },
                {
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "file2.jpg"},
                    },
                },
            ]
        }

        # Setup mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.process_asset.side_effect = [
            {"inventory_id": "test-1", "status": "processed"},
            {"inventory_id": "test-2", "status": "processed"},
        ]

        # Call handler
        result = lambda_handler(multi_record_event, {})

        # Verify both records were processed
        assert mock_service.process_asset.call_count == 2
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert len(response_body["results"]) == 2

    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_partial_failure(self, mock_service_class):
        """Test handler response when some records fail."""
        # Setup event with multiple records
        multi_record_event = {
            "Records": [
                {
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "file1.jpg"},
                    },
                },
                {
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "file2.jpg"},
                    },
                },
            ]
        }

        # Setup mock service with one success, one failure
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.process_asset.side_effect = [
            {"inventory_id": "test-1", "status": "processed"},
            Exception("Processing failed"),
        ]

        # Call handler
        result = lambda_handler(multi_record_event, {})

        # Verify partial success response
        assert result["statusCode"] == 207  # Multi-status
        response_body = json.loads(result["body"])
        assert len(response_body["results"]) == 2
        assert response_body["results"][0]["status"] == "processed"
        assert "error" in response_body["results"][1]

    def test_lambda_handler_invalid_event(self):
        """Test handler response to invalid event format."""
        invalid_event = {"invalid": "event"}

        result = lambda_handler(invalid_event, {})

        assert result["statusCode"] == 400
        response_body = json.loads(result["body"])
        assert "error" in response_body
        assert "Invalid event format" in response_body["error"]

    def test_lambda_handler_empty_records(self):
        """Test handler response to event with no records."""
        empty_event = {"Records": []}

        result = lambda_handler(empty_event, {})

        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["message"] == "Successfully processed 0 records"
        assert response_body["results"] == []

    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_unsupported_event_type(self, mock_service_class):
        """Test handler response to unsupported S3 event type."""
        unsupported_event = {
            "Records": [
                {
                    "eventName": "ObjectCreated:Copy",  # Unsupported event
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "file1.jpg"},
                    },
                }
            ]
        }

        result = lambda_handler(unsupported_event, {})

        # Should skip unsupported events
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert len(response_body["results"]) == 1
        assert response_body["results"][0]["status"] == "skipped"
        assert "Unsupported event type" in response_body["results"][0]["message"]

    @patch.dict(
        "os.environ", {"DYNAMODB_TABLE_NAME": "test-table", "AWS_REGION": "us-east-1"}
    )
    @patch("lambdas.ingest.s3.handler.AssetProcessingService")
    def test_lambda_handler_environment_setup(self, mock_service_class, s3_event):
        """Test that handler properly initializes service with environment."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.process_asset.return_value = {"status": "processed"}

        lambda_handler(s3_event, {})

        # Verify service was instantiated (environment variables are available)
        mock_service_class.assert_called_once()
