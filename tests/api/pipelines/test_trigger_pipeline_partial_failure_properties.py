"""
Property-based tests for pipeline trigger API partial failure handling.

These tests verify that the trigger_pipeline Lambda correctly handles
batches with a mix of valid and invalid assets, continuing to process
remaining assets when individual assets fail.

**Feature: external-metadata-enrichment, Property 5: Partial Failure Handling**
**Validates: Requirements 3.5, 7.4, 11.7**
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Mock boto3 before importing the module under test
mock_boto3 = MagicMock()
sys.modules["boto3"] = mock_boto3


# Import the functions under test
from lambdas.api.pipelines.trigger_pipeline.index import (
    DEFAULT_MAX_BATCH_SIZE,
    _build_step_function_input,
    lambda_handler,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid inventory IDs (non-empty strings)
valid_inventory_id = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="_-"  # Letters, Numbers
    ),
).filter(
    lambda x: x.strip()
)  # Ensure non-whitespace

# Strategy for (inventory_id, should_succeed) pairs
# This represents assets where some will succeed and some will fail
asset_success_pair = st.tuples(valid_inventory_id, st.booleans())

# Strategy for lists of asset success pairs with unique inventory_ids
# (min 1, max 50 as per requirements)
asset_success_pairs_list = st.lists(
    asset_success_pair,
    min_size=1,
    max_size=DEFAULT_MAX_BATCH_SIZE,
    unique_by=lambda x: x[0],  # Ensure unique inventory_ids
)


def create_mock_event(pipeline_id: str, assets: list) -> dict:
    """Create a mock API Gateway event for testing."""
    return {
        "pathParameters": {"pipelineId": pipeline_id},
        "body": json.dumps({"assets": assets}),
    }


def setup_mocks_for_partial_failure(
    mock_dynamodb,
    mock_stepfunctions,
    pipeline_id: str,
    asset_success_map: dict,
):
    """
    Set up mocks to simulate partial failure scenario.

    Args:
        mock_dynamodb: Mock DynamoDB resource
        mock_stepfunctions: Mock Step Functions client
        pipeline_id: The pipeline ID
        asset_success_map: Dict mapping inventory_id -> should_succeed (bool)
    """
    # Mock DynamoDB table
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    # Mock pipeline exists with manual trigger capability
    mock_table.get_item.return_value = {
        "Item": {
            "id": pipeline_id,
            "type": "Manual Trigger Pipeline",
            "stateMachineArn": f"arn:aws:states:us-east-1:123456789012:stateMachine:{pipeline_id}",
        }
    }

    # Mock Step Functions to succeed or fail based on asset_success_map
    def start_execution_side_effect(**kwargs):
        input_data = json.loads(kwargs.get("input", "{}"))
        inventory_id = input_data.get("item", {}).get("inventory_id", "")

        # Check if this asset should succeed
        should_succeed = asset_success_map.get(inventory_id, True)

        if should_succeed:
            return {
                "executionArn": f"arn:aws:states:us-east-1:123456789012:execution:{pipeline_id}:{inventory_id}"
            }
        else:
            raise Exception(f"Simulated failure for asset {inventory_id}")

    mock_stepfunctions.start_execution.side_effect = start_execution_side_effect


@pytest.mark.unit
class TestPartialFailureHandlingProperty:
    """Property-based tests for partial failure handling."""

    @given(asset_pairs=asset_success_pairs_list)
    @settings(max_examples=100)
    def test_partial_failure_continues_processing(self, asset_pairs: list):
        """
        Property 5: Partial Failure Handling - Continues processing.

        *For any* batch with a mix of valid and invalid assets, the pipeline
        trigger SHALL continue processing remaining assets when individual
        assets fail.

        **Validates: Requirements 3.5, 7.4, 11.7**

        This property ensures that:
        1. All assets in the batch are attempted
        2. Failures don't stop processing of subsequent assets
        3. Both successful and failed executions are tracked
        """
        # Skip if all assets would succeed or all would fail (not a partial failure case)
        successes = [s for _, s in asset_pairs]
        assume(
            any(successes) and not all(successes)
        )  # At least one success and one failure

        # Arrange
        pipeline_id = "test-pipeline-123"
        assets = [{"inventory_id": inv_id, "params": {}} for inv_id, _ in asset_pairs]

        # Create success map
        asset_success_map = {
            inv_id: should_succeed for inv_id, should_succeed in asset_pairs
        }

        event = create_mock_event(pipeline_id, assets)

        with patch.dict(
            os.environ,
            {
                "PIPELINES_TABLE": "TestPipelinesTable",
                "MAX_BATCH_SIZE": str(DEFAULT_MAX_BATCH_SIZE),
            },
        ):
            with patch(
                "lambdas.api.pipelines.trigger_pipeline.index.boto3"
            ) as mock_boto3_module:
                # Set up mocks
                mock_dynamodb = MagicMock()
                mock_stepfunctions = MagicMock()
                mock_boto3_module.resource.return_value = mock_dynamodb
                mock_boto3_module.client.return_value = mock_stepfunctions

                setup_mocks_for_partial_failure(
                    mock_dynamodb,
                    mock_stepfunctions,
                    pipeline_id,
                    asset_success_map,
                )

                # Act
                response = lambda_handler(event, None)

        # Assert
        assert (
            response["statusCode"] == 200
        ), "Should return 200 even with partial failures"

        body = json.loads(response["body"])

        # Verify all assets were processed
        assert body["total_assets"] == len(assets), "All assets should be counted"

        # Verify execution counts match expected
        expected_successes = sum(1 for _, s in asset_pairs if s)
        expected_failures = sum(1 for _, s in asset_pairs if not s)

        assert (
            body["successful_executions"] == expected_successes
        ), f"Expected {expected_successes} successes, got {body['successful_executions']}"
        assert (
            body["failed_executions"] == expected_failures
        ), f"Expected {expected_failures} failures, got {body['failed_executions']}"

        # Verify each execution has correct status
        executions = body["executions"]
        assert len(executions) == len(
            assets
        ), "Should have execution record for each asset"

        for execution in executions:
            inv_id = execution["inventory_id"]
            expected_success = asset_success_map.get(inv_id, True)

            if expected_success:
                assert (
                    execution["status"] == "started"
                ), f"Asset {inv_id} should have status 'started'"
                assert execution[
                    "execution_arn"
                ], f"Asset {inv_id} should have execution_arn"
            else:
                assert (
                    execution["status"] == "failed"
                ), f"Asset {inv_id} should have status 'failed'"
                assert "error" in execution, f"Asset {inv_id} should have error message"

    @given(
        num_assets=st.integers(min_value=2, max_value=20),
        failure_indices=st.lists(
            st.integers(min_value=0, max_value=19), min_size=1, max_size=10
        ),
    )
    @settings(max_examples=100)
    def test_partial_failure_reports_correct_counts(
        self, num_assets: int, failure_indices: list
    ):
        """
        Property 5: Partial Failure Handling - Correct count reporting.

        *For any* batch with specific failure indices, the response SHALL
        correctly report the count of successful and failed executions.

        **Validates: Requirements 3.5, 7.4, 11.7**
        """
        # Normalize failure indices to be within range
        failure_indices = list(set(i % num_assets for i in failure_indices))

        # Skip if all would fail or none would fail
        assume(len(failure_indices) < num_assets and len(failure_indices) > 0)

        # Arrange
        pipeline_id = "test-pipeline-counts"
        assets = [
            {"inventory_id": f"asset-{i}", "params": {}} for i in range(num_assets)
        ]

        # Create success map based on failure indices
        asset_success_map = {
            f"asset-{i}": i not in failure_indices for i in range(num_assets)
        }

        event = create_mock_event(pipeline_id, assets)

        with patch.dict(
            os.environ,
            {
                "PIPELINES_TABLE": "TestPipelinesTable",
                "MAX_BATCH_SIZE": str(DEFAULT_MAX_BATCH_SIZE),
            },
        ):
            with patch(
                "lambdas.api.pipelines.trigger_pipeline.index.boto3"
            ) as mock_boto3_module:
                mock_dynamodb = MagicMock()
                mock_stepfunctions = MagicMock()
                mock_boto3_module.resource.return_value = mock_dynamodb
                mock_boto3_module.client.return_value = mock_stepfunctions

                setup_mocks_for_partial_failure(
                    mock_dynamodb,
                    mock_stepfunctions,
                    pipeline_id,
                    asset_success_map,
                )

                # Act
                response = lambda_handler(event, None)

        # Assert
        body = json.loads(response["body"])

        expected_failures = len(failure_indices)
        expected_successes = num_assets - expected_failures

        assert (
            body["successful_executions"] == expected_successes
        ), f"Expected {expected_successes} successes"
        assert (
            body["failed_executions"] == expected_failures
        ), f"Expected {expected_failures} failures"
        assert body["total_assets"] == num_assets, f"Expected {num_assets} total assets"

    @given(asset_pairs=asset_success_pairs_list)
    @settings(max_examples=100)
    def test_partial_failure_preserves_params(self, asset_pairs: list):
        """
        Property 5: Partial Failure Handling - Params preservation.

        *For any* batch with partial failures, the response SHALL preserve
        the params for each asset in the execution records.

        **Validates: Requirements 3.5, 11.7**
        """
        # Arrange
        pipeline_id = "test-pipeline-params"
        assets = [
            {"inventory_id": inv_id, "params": {"correlation_id": f"corr-{inv_id}"}}
            for inv_id, _ in asset_pairs
        ]

        asset_success_map = {
            inv_id: should_succeed for inv_id, should_succeed in asset_pairs
        }

        event = create_mock_event(pipeline_id, assets)

        with patch.dict(
            os.environ,
            {
                "PIPELINES_TABLE": "TestPipelinesTable",
                "MAX_BATCH_SIZE": str(DEFAULT_MAX_BATCH_SIZE),
            },
        ):
            with patch(
                "lambdas.api.pipelines.trigger_pipeline.index.boto3"
            ) as mock_boto3_module:
                mock_dynamodb = MagicMock()
                mock_stepfunctions = MagicMock()
                mock_boto3_module.resource.return_value = mock_dynamodb
                mock_boto3_module.client.return_value = mock_stepfunctions

                setup_mocks_for_partial_failure(
                    mock_dynamodb,
                    mock_stepfunctions,
                    pipeline_id,
                    asset_success_map,
                )

                # Act
                response = lambda_handler(event, None)

        # Assert
        body = json.loads(response["body"])
        executions = body["executions"]

        for execution in executions:
            inv_id = execution["inventory_id"]
            expected_params = {"correlation_id": f"corr-{inv_id}"}

            assert (
                execution.get("params") == expected_params
            ), f"Asset {inv_id} should have preserved params"


@pytest.mark.unit
class TestStepFunctionInputBuildingProperty:
    """Property-based tests for Step Function input building."""

    @given(
        inventory_id=valid_inventory_id,
        correlation_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100)
    def test_step_function_input_format(self, inventory_id: str, correlation_id: str):
        """
        Property 5 (extended): Step Function input format.

        *For any* asset with params, the _build_step_function_input() function
        SHALL create input in the format expected by lambda_middleware.

        **Validates: Requirements 11.5**
        """
        # Arrange
        asset = {
            "inventory_id": inventory_id,
            "params": {"correlation_id": correlation_id},
        }
        pipeline_id = "test-pipeline"

        # Act
        result = _build_step_function_input(asset, pipeline_id)

        # Assert
        assert "item" in result, "Should have 'item' key for middleware"
        assert (
            result["item"]["inventory_id"] == inventory_id
        ), "item.inventory_id should match"
        assert (
            result["item"]["params"]["correlation_id"] == correlation_id
        ), "item.params.correlation_id should match"
        assert result["pipeline_id"] == pipeline_id, "Should include pipeline_id"
        assert result["trigger_type"] == "manual", "Should be manual trigger"
        assert "timestamp" in result, "Should include timestamp"
