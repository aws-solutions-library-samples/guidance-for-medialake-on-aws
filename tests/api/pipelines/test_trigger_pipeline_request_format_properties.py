"""
Property-based tests for pipeline trigger API request format validation.

These tests verify that the trigger_pipeline Lambda correctly validates
request formats, supporting both the new assets format and legacy inventory_ids format.

**Feature: external-metadata-enrichment, Property 4: Request Format Validation**
**Validates: Requirements 2.2, 3.2, 11.1**
"""

import json
import sys
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Mock boto3 before importing the module under test
mock_boto3 = MagicMock()
sys.modules["boto3"] = mock_boto3


# Import the functions under test
from lambdas.api.pipelines.trigger_pipeline.index import (
    DEFAULT_MAX_BATCH_SIZE,
    _normalize_assets,
    _parse_request_body,
    _validate_batch_size,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid inventory IDs (non-empty strings)
valid_inventory_id = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Pd"),  # Letters, Numbers, Dashes
        whitelist_characters="_-",
    ),
).filter(
    lambda x: x.strip()
)  # Ensure non-whitespace

# Strategy for valid params dictionaries
valid_params = st.dictionaries(
    keys=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    values=st.text(max_size=200),
    max_size=10,
)

# Strategy for valid asset objects in new format
valid_asset = st.fixed_dictionaries(
    {"inventory_id": valid_inventory_id, "params": valid_params}
)

# Strategy for valid assets list (new format)
valid_assets_list = st.lists(valid_asset, min_size=1, max_size=50)


@pytest.mark.unit
class TestRequestFormatValidationProperty:
    """Property-based tests for request format validation."""

    @given(assets=valid_assets_list)
    @settings(max_examples=100)
    def test_valid_new_format_is_accepted(self, assets: list):
        """
        Property 4: Request Format Validation - Valid new format acceptance.

        *For any* valid assets list in the new format, the _normalize_assets()
        function SHALL return the normalized assets without error.

        **Validates: Requirements 2.2, 11.1**

        This property ensures that:
        1. Valid new format requests are accepted
        2. Each asset has inventory_id preserved
        3. Each asset has params preserved (or defaulted to empty dict)
        """
        # Arrange
        body = {"assets": assets}

        # Act
        result, error = _normalize_assets(body)

        # Assert
        assert error is None, f"Valid new format should not produce error: {error}"
        assert result is not None, "Valid new format should return assets"
        assert len(result) == len(assets), "Should return same number of assets"

        # Verify each asset has required fields
        for i, asset in enumerate(result):
            assert "inventory_id" in asset, f"Asset {i} should have inventory_id"
            assert "params" in asset, f"Asset {i} should have params"
            assert isinstance(asset["params"], dict), f"Asset {i} params should be dict"

    @given(inventory_ids=st.lists(valid_inventory_id, min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_valid_legacy_format_is_accepted(self, inventory_ids: list):
        """
        Property 4: Request Format Validation - Valid legacy format acceptance.

        *For any* valid inventory_ids list in the legacy format, the _normalize_assets()
        function SHALL convert it to the new format without error.

        **Validates: Requirements 2.2, 3.2**

        This property ensures backward compatibility with the legacy format.
        """
        # Arrange
        body = {"inventory_ids": inventory_ids}

        # Act
        result, error = _normalize_assets(body)

        # Assert
        assert error is None, f"Valid legacy format should not produce error: {error}"
        assert result is not None, "Valid legacy format should return assets"
        assert len(result) == len(inventory_ids), "Should return same number of assets"

        # Verify conversion to new format
        for i, asset in enumerate(result):
            assert (
                asset["inventory_id"] == inventory_ids[i]
            ), f"Asset {i} inventory_id should match original"
            assert (
                asset["params"] == {}
            ), f"Asset {i} params should be empty dict for legacy format"

    @given(
        inventory_id=valid_inventory_id,
        correlation_id=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100)
    def test_correlation_id_param_is_preserved(
        self, inventory_id: str, correlation_id: str
    ):
        """
        Property 4: Request Format Validation - correlation_id preservation.

        *For any* asset with a correlation_id in params, the _normalize_assets()
        function SHALL preserve the correlation_id in the output.

        **Validates: Requirements 2.2, 11.1**

        This property ensures that pipeline-specific parameters like correlation_id
        are correctly passed through.
        """
        # Arrange
        body = {
            "assets": [
                {
                    "inventory_id": inventory_id,
                    "params": {"correlation_id": correlation_id},
                }
            ]
        }

        # Act
        result, error = _normalize_assets(body)

        # Assert
        assert error is None, f"Should not produce error: {error}"
        assert result is not None, "Should return assets"
        assert len(result) == 1, "Should return one asset"
        assert (
            result[0]["params"]["correlation_id"] == correlation_id
        ), "correlation_id should be preserved in params"

    @given(
        invalid_body=st.one_of(
            st.just({}),  # Empty body
            st.just({"other_field": "value"}),  # Missing both assets and inventory_ids
            st.just({"assets": "not_a_list"}),  # assets is not a list
            st.just({"inventory_ids": "not_a_list"}),  # inventory_ids is not a list
            st.just({"inventory_ids": []}),  # Empty inventory_ids
        )
    )
    @settings(max_examples=100)
    def test_invalid_format_is_rejected(self, invalid_body: dict):
        """
        Property 4: Request Format Validation - Invalid format rejection.

        *For any* invalid request body format, the _normalize_assets()
        function SHALL return an error message.

        **Validates: Requirements 2.2, 3.2, 11.1**

        This property ensures proper validation of request format.
        """
        # Act
        result, error = _normalize_assets(invalid_body)

        # Assert
        assert (
            error is not None
        ), f"Invalid format should produce error for body: {invalid_body}"
        assert result is None, "Invalid format should not return assets"

    @given(
        assets=st.lists(
            st.fixed_dictionaries({"params": valid_params}),  # Missing inventory_id
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=100)
    def test_missing_inventory_id_is_rejected(self, assets: list):
        """
        Property 4: Request Format Validation - Missing inventory_id rejection.

        *For any* asset missing the required inventory_id field, the _normalize_assets()
        function SHALL return an error message.

        **Validates: Requirements 2.2, 11.1**

        This property ensures that inventory_id is required for each asset.
        """
        # Arrange
        body = {"assets": assets}

        # Act
        result, error = _normalize_assets(body)

        # Assert
        assert error is not None, "Missing inventory_id should produce error"
        assert (
            "inventory_id" in error.lower()
        ), f"Error message should mention inventory_id: {error}"

    @given(
        inventory_id=valid_inventory_id,
        invalid_params=st.one_of(
            st.just("not_a_dict"),
            st.just(123),
            st.just(["list", "not", "dict"]),
        ),
    )
    @settings(max_examples=100)
    def test_invalid_params_type_is_rejected(self, inventory_id: str, invalid_params):
        """
        Property 4: Request Format Validation - Invalid params type rejection.

        *For any* asset with params that is not a dictionary, the _normalize_assets()
        function SHALL return an error message.

        **Validates: Requirements 2.2, 11.1**

        This property ensures that params must be a dictionary.
        """
        # Arrange
        body = {"assets": [{"inventory_id": inventory_id, "params": invalid_params}]}

        # Act
        result, error = _normalize_assets(body)

        # Assert
        assert (
            error is not None
        ), f"Invalid params type should produce error: {invalid_params}"
        assert (
            "params" in error.lower()
        ), f"Error message should mention params: {error}"


@pytest.mark.unit
class TestBatchSizeValidationProperty:
    """Property-based tests for batch size validation."""

    @given(num_assets=st.integers(min_value=1, max_value=DEFAULT_MAX_BATCH_SIZE))
    @settings(max_examples=100)
    def test_valid_batch_size_is_accepted(self, num_assets: int):
        """
        Property 4 (extended): Valid batch size acceptance.

        *For any* batch size between 1 and the maximum (inclusive), the
        _validate_batch_size() function SHALL return None (no error).

        **Validates: Requirements 3.2, 11.1**
        """
        # Arrange
        assets = [{"inventory_id": f"id-{i}", "params": {}} for i in range(num_assets)]

        # Act
        error = _validate_batch_size(assets, DEFAULT_MAX_BATCH_SIZE)

        # Assert
        assert error is None, f"Batch size {num_assets} should be valid"

    @given(num_assets=st.integers(min_value=DEFAULT_MAX_BATCH_SIZE + 1, max_value=200))
    @settings(max_examples=100)
    def test_oversized_batch_is_rejected(self, num_assets: int):
        """
        Property 4 (extended): Oversized batch rejection.

        *For any* batch size exceeding the maximum, the _validate_batch_size()
        function SHALL return an error message.

        **Validates: Requirements 3.2, 11.1**
        """
        # Arrange
        assets = [{"inventory_id": f"id-{i}", "params": {}} for i in range(num_assets)]

        # Act
        error = _validate_batch_size(assets, DEFAULT_MAX_BATCH_SIZE)

        # Assert
        assert error is not None, f"Batch size {num_assets} should be rejected"
        assert str(num_assets) in error, "Error should mention the batch size"
        assert str(DEFAULT_MAX_BATCH_SIZE) in error, "Error should mention the maximum"

    def test_empty_batch_is_rejected(self):
        """
        Property 4 (extended): Empty batch rejection.

        An empty assets list SHALL be rejected with an appropriate error.

        **Validates: Requirements 3.2, 11.1**
        """
        # Arrange
        assets = []

        # Act
        error = _validate_batch_size(assets, DEFAULT_MAX_BATCH_SIZE)

        # Assert
        assert error is not None, "Empty batch should be rejected"
        assert (
            "at least one" in error.lower()
        ), f"Error should mention minimum requirement: {error}"


@pytest.mark.unit
class TestRequestBodyParsingProperty:
    """Property-based tests for request body JSON parsing."""

    @given(
        body_dict=st.dictionaries(
            keys=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
            values=st.one_of(
                st.text(max_size=100),
                st.integers(),
                st.booleans(),
                st.lists(st.text(max_size=20), max_size=5),
            ),
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_valid_json_is_parsed(self, body_dict: dict):
        """
        Property 4 (extended): Valid JSON parsing.

        *For any* valid JSON string, the _parse_request_body() function
        SHALL parse it without error.

        **Validates: Requirements 2.2, 11.1**
        """
        # Arrange
        body_str = json.dumps(body_dict)

        # Act
        result, error = _parse_request_body(body_str)

        # Assert
        assert error is None, f"Valid JSON should not produce error: {error}"
        assert result == body_dict, "Parsed result should match original dict"

    @given(
        invalid_json=st.one_of(
            st.just("{invalid json}"),
            st.just("not json at all"),
            st.just('{"unclosed": '),
            st.just("[1, 2, 3"),  # Unclosed array
        )
    )
    @settings(max_examples=100)
    def test_invalid_json_is_rejected(self, invalid_json: str):
        """
        Property 4 (extended): Invalid JSON rejection.

        *For any* invalid JSON string, the _parse_request_body() function
        SHALL return an error message.

        **Validates: Requirements 2.2, 11.1**
        """
        # Act
        result, error = _parse_request_body(invalid_json)

        # Assert
        assert error is not None, f"Invalid JSON should produce error: {invalid_json}"
        assert "json" in error.lower(), f"Error should mention JSON: {error}"

    def test_empty_body_returns_empty_dict(self):
        """
        Property 4 (extended): Empty body handling.

        An empty or None body SHALL be parsed as an empty dictionary.

        **Validates: Requirements 2.2, 11.1**
        """
        # Act
        result1, error1 = _parse_request_body("")
        result2, error2 = _parse_request_body(None)

        # Assert - Empty string case
        assert error1 is None, "Empty string should not produce error"
        assert result1 == {}, "Empty string should parse to empty dict"

        # Assert - None case (handled by the or "{}" in the function)
        assert error2 is None, "None body should not produce error"
        assert result2 == {}, "None body should parse to empty dict"
