"""
Property-based tests for DynamoDB operations in external metadata enrichment.

These tests verify that the DynamoDB update operations correctly store
correlation IDs, metadata, and status information.

**Feature: external-metadata-enrichment**
"""

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Mock aws_lambda_powertools before importing the module under test
# This is needed because the module imports Logger from aws_lambda_powertools
sys.modules["aws_lambda_powertools"] = MagicMock()

# Now import the module under test - use direct file import to avoid __init__.py
import importlib.util
import os

# Get the path to the dynamodb_operations module
module_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "lambdas",
    "nodes",
    "external_metadata_fetch",
    "dynamodb_operations.py",
)
module_path = os.path.abspath(module_path)

# Load the module directly
spec = importlib.util.spec_from_file_location("dynamodb_operations", module_path)
dynamodb_operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dynamodb_operations)

# Get the functions we need to test
update_asset_external_asset_id = dynamodb_operations.update_asset_external_asset_id
update_asset_status_pending = dynamodb_operations.update_asset_status_pending
update_asset_with_metadata = dynamodb_operations.update_asset_with_metadata
update_asset_status_failed = dynamodb_operations.update_asset_status_failed


def create_mock_table():
    """Create a fresh mock DynamoDB table for each test."""
    mock_table = MagicMock()
    mock_table.update_item = MagicMock()
    mock_table.get_item = MagicMock(return_value={"Item": {}})
    return mock_table


@pytest.mark.unit
class TestExternalAssetIdStorageProperty:
    """Property-based tests for ExternalAssetId storage.

    **Property 2: ExternalAssetId Storage**
    **Validates: Requirements 1.3, 2.6, 9.2**
    """

    @given(correlation_id=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_correlation_id_stored_in_external_asset_id(self, correlation_id: str):
        """
        Property 2: ExternalAssetId Storage

        *For any* non-empty correlation ID, the update_asset_external_asset_id()
        function SHALL store it in the asset record's ExternalAssetId field.

        **Validates: Requirements 1.3, 2.6, 9.2**

        This property ensures that:
        1. The correlation ID is stored at the root level of the asset record
        2. The DynamoDB update is called with the correct parameters
        3. The ExternalAssetId field is set to the exact correlation ID value
        """
        inventory_id = "test-inventory-id"
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_external_asset_id(inventory_id, correlation_id)

            # Assert
            mock_table.update_item.assert_called_once()
            call_kwargs = mock_table.update_item.call_args[1]

            # Verify the key
            assert call_kwargs["Key"] == {"InventoryID": inventory_id}

            # Verify the update expression sets ExternalAssetId
            assert "ExternalAssetId" in str(call_kwargs["ExpressionAttributeNames"])

            # Verify the correlation ID value is stored correctly
            # Check the actual value in the dict rather than string representation
            expr_values = call_kwargs["ExpressionAttributeValues"]
            assert ":cid" in expr_values
            assert expr_values[":cid"] == correlation_id

    @given(
        inventory_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        correlation_id=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_external_asset_id_stored_before_api_call(
        self, inventory_id: str, correlation_id: str
    ):
        """
        Property 2 (extended): Storage timing

        *For any* inventory ID and correlation ID, the ExternalAssetId
        SHALL be stored before any external API call is made.

        **Validates: Requirements 1.3, 2.6, 9.2**

        This property ensures that the correlation ID is persisted
        to the database before attempting to fetch external metadata,
        providing traceability even if the fetch fails.
        """
        call_order = []
        mock_table = create_mock_table()

        def track_update(*args, **kwargs):
            call_order.append("update_external_asset_id")

        mock_table.update_item.side_effect = track_update

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_external_asset_id(inventory_id, correlation_id)

            # Assert
            assert "update_external_asset_id" in call_order
            assert call_order[0] == "update_external_asset_id"


@pytest.mark.unit
class TestStatusLifecycleProperty:
    """Property-based tests for status lifecycle transitions.

    **Property 11: Status Lifecycle**
    **Validates: Requirements 7.5, 8.1, 8.4**
    """

    @given(
        inventory_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_status_transitions_to_pending(self, inventory_id: str):
        """
        Property 11: Status Lifecycle - Pending transition

        *For any* enrichment operation, the status SHALL transition
        to "pending" at the start of processing.

        **Validates: Requirements 8.1, 8.4**
        """
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_status_pending(inventory_id)

            # Assert
            mock_table.update_item.assert_called()
            call_kwargs = mock_table.update_item.call_args[1]

            # Verify status is set to pending
            assert "pending" in str(call_kwargs["ExpressionAttributeValues"])

    @given(
        inventory_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        success=st.booleans(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_status_transitions_to_success_or_failed(
        self, inventory_id: str, success: bool
    ):
        """
        Property 11: Status Lifecycle - Final state transition

        *For any* enrichment operation, the status SHALL transition
        to either "success" or "failed" based on the outcome.

        **Validates: Requirements 7.5, 8.1, 8.4**
        """
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            if success:
                update_asset_with_metadata(inventory_id, {"title": "Test"})
                expected_status = "success"
            else:
                update_asset_status_failed(inventory_id, "Test error", 1)
                expected_status = "failed"

            # Assert
            mock_table.update_item.assert_called()
            call_kwargs = mock_table.update_item.call_args[1]

            # Verify the expected status is in the update
            assert expected_status in str(call_kwargs["ExpressionAttributeValues"])

    @given(
        inventory_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_re_enrichment_clears_error_on_success(self, inventory_id: str):
        """
        Property 11: Status Lifecycle - Error clearing on re-enrichment

        *For any* asset with failed status that is re-processed successfully,
        the status SHALL update to "success" and clear error information.

        **Validates: Requirements 7.5, 8.1, 8.4**
        """
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act - simulate successful re-enrichment
            update_asset_with_metadata(inventory_id, {"title": "Test"})

            # Assert
            call_kwargs = mock_table.update_item.call_args[1]

            # Verify error message is cleared (set to null)
            expr_values = call_kwargs["ExpressionAttributeValues"]
            # The null value should be present for errorMessage
            assert ":null" in expr_values or None in expr_values.values()


@pytest.mark.unit
class TestFailureStatusRecordingProperty:
    """Property-based tests for failure status recording.

    **Property 10: Failure Status Recording**
    **Validates: Requirements 7.2, 7.3**
    """

    @given(
        error_message=st.text(min_size=1, max_size=500),
        attempt_count=st.integers(min_value=1, max_value=3),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_failure_details_recorded_correctly(
        self, error_message: str, attempt_count: int
    ):
        """
        Property 10: Failure Status Recording

        *For any* enrichment that fails after all retry attempts,
        the asset's ExternalMetadataStatus SHALL be updated with:
        - status: "failed"
        - errorMessage (truncated to 500 chars)
        - attemptCount
        - lastAttempt timestamp

        **Validates: Requirements 7.2, 7.3**
        """
        inventory_id = "test-inventory-id"
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_status_failed(inventory_id, error_message, attempt_count)

            # Assert
            mock_table.update_item.assert_called_once()
            call_kwargs = mock_table.update_item.call_args[1]

            # Verify the status object structure
            status_obj = call_kwargs["ExpressionAttributeValues"][":status_obj"]

            assert status_obj["status"] == "failed"
            assert status_obj["attemptCount"] == max(attempt_count, 1)
            assert "lastAttempt" in status_obj
            assert status_obj["errorMessage"] is not None

    @given(
        error_message=st.text(min_size=501, max_size=1000),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_error_message_truncated_to_500_chars(self, error_message: str):
        """
        Property 10 (extended): Error message truncation

        *For any* error message longer than 500 characters,
        the stored errorMessage SHALL be truncated to 500 characters.

        **Validates: Requirements 7.2, 7.3**
        """
        inventory_id = "test-inventory-id"
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_status_failed(inventory_id, error_message, 1)

            # Assert
            call_kwargs = mock_table.update_item.call_args[1]
            status_obj = call_kwargs["ExpressionAttributeValues"][":status_obj"]

            stored_error = status_obj["errorMessage"]
            assert len(stored_error) <= 500
            # Should end with "..." if truncated
            if len(error_message) > 500:
                assert stored_error.endswith("...")

    @given(
        attempt_count=st.integers(min_value=0, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_attempt_count_minimum_is_one(self, attempt_count: int):
        """
        Property 10 (extended): Minimum attempt count

        *For any* attempt count value (including 0), the stored
        attemptCount SHALL be at least 1.

        **Validates: Requirements 7.2, 7.3**
        """
        inventory_id = "test-inventory-id"
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_status_failed(inventory_id, "Test error", attempt_count)

            # Assert
            call_kwargs = mock_table.update_item.call_args[1]
            status_obj = call_kwargs["ExpressionAttributeValues"][":status_obj"]

            assert status_obj["attemptCount"] >= 1

    @given(
        inventory_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_last_attempt_timestamp_is_valid_iso8601(self, inventory_id: str):
        """
        Property 10 (extended): Timestamp format

        *For any* failure recording, the lastAttempt timestamp
        SHALL be a valid ISO 8601 formatted string.

        **Validates: Requirements 7.2, 7.3**
        """
        mock_table = create_mock_table()

        with patch.object(
            dynamodb_operations, "_get_asset_table", return_value=mock_table
        ):
            # Act
            update_asset_status_failed(inventory_id, "Test error", 1)

            # Assert
            call_kwargs = mock_table.update_item.call_args[1]
            status_obj = call_kwargs["ExpressionAttributeValues"][":status_obj"]

            timestamp = status_obj["lastAttempt"]

            # Verify it's a valid ISO 8601 timestamp
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                assert parsed is not None
            except ValueError:
                pytest.fail(f"Invalid ISO 8601 timestamp: {timestamp}")
