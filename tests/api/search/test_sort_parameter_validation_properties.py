"""
Property-based tests for sort parameter validation in SearchParams.

These tests verify that the SearchParams model correctly validates sort field
names and directions, rejecting invalid values.

**Feature: assets-page-bugs, Property 2: Sort Parameter Validation**
**Validates: Requirements 8.4, 8.5, 8.6**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from lambdas.api.search.get_search.index import SearchParams

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid sortable field names
VALID_SORT_FIELDS = [
    "createdAt",
    "name",
    "size",
    "type",
    "format",
    "DigitalSourceAsset.CreateDate",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
    "DigitalSourceAsset.Type",
    "DigitalSourceAsset.MainRepresentation.Format",
]

# Strategy for invalid sort field names (not in allowed list)
invalid_sort_field = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Pd"), whitelist_characters="._-"
    ),
).filter(lambda x: x not in VALID_SORT_FIELDS and x.strip())

# Strategy for valid sort field names
valid_sort_field = st.sampled_from(VALID_SORT_FIELDS)


@pytest.mark.unit
class TestSortParameterValidationProperty:
    """Property-based tests for sort parameter validation."""

    @given(invalid_field=invalid_sort_field)
    @settings(max_examples=100)
    def test_invalid_sort_field_is_rejected(self, invalid_field: str):
        """
        Property 2: Sort Parameter Validation - Invalid field rejection.

        *For any* sort parameter with an invalid field name (not in the allowed
        list), the SearchParams model SHALL raise a ValidationError.

        **Validates: Requirements 8.4, 8.6**

        This property ensures that only recognized sortable fields are accepted.
        """
        # Arrange
        params_data = {"q": "test query", "sort": invalid_field}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error message mentions the invalid field
        error_message = str(exc_info.value)
        assert (
            "Invalid sort field" in error_message or "sort_by" in error_message
        ), f"Error message should indicate invalid sort field: {error_message}"

    @given(invalid_field=invalid_sort_field)
    @settings(max_examples=100)
    def test_invalid_descending_sort_field_is_rejected(self, invalid_field: str):
        """
        Property 2: Sort Parameter Validation - Invalid descending field rejection.

        *For any* sort parameter with "-" prefix and an invalid field name,
        the SearchParams model SHALL raise a ValidationError.

        **Validates: Requirements 8.4, 8.6**

        This property ensures validation works for descending sort parameters.
        """
        # Arrange
        params_data = {"q": "test query", "sort": f"-{invalid_field}"}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error message
        error_message = str(exc_info.value)
        assert (
            "Invalid sort field" in error_message or "sort_by" in error_message
        ), f"Error message should indicate invalid sort field: {error_message}"

    @given(valid_field=valid_sort_field)
    @settings(max_examples=100)
    def test_valid_sort_field_is_accepted(self, valid_field: str):
        """
        Property 2: Sort Parameter Validation - Valid field acceptance.

        *For any* sort parameter with a valid field name from the allowed list,
        the SearchParams model SHALL accept it without raising a ValidationError.

        **Validates: Requirements 8.4, 8.5**

        This property ensures that all allowed sortable fields are accepted.
        """
        # Arrange - Test both ascending and descending
        asc_params_data = {"q": "test query", "sort": valid_field}
        desc_params_data = {"q": "test query", "sort": f"-{valid_field}"}

        # Act & Assert - Should not raise
        asc_params = SearchParams(**asc_params_data)
        desc_params = SearchParams(**desc_params_data)

        # Verify correct extraction
        assert asc_params.sort_by == valid_field
        assert asc_params.sort_direction == "asc"
        assert desc_params.sort_by == valid_field
        assert desc_params.sort_direction == "desc"

    def test_sort_direction_validation_asc(self):
        """
        Property 2: Sort Parameter Validation - Ascending direction validation.

        When sort_direction is explicitly set to "asc", the SearchParams model
        SHALL accept it as valid.

        **Validates: Requirements 8.5**

        This property ensures "asc" is a valid sort direction.
        """
        # Arrange
        params_data = {"q": "test query", "sort": "createdAt", "sort_direction": "asc"}

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert params.sort_direction == "asc", "sort_direction 'asc' should be valid"

    def test_sort_direction_validation_desc(self):
        """
        Property 2: Sort Parameter Validation - Descending direction validation.

        When sort_direction is explicitly set to "desc", the SearchParams model
        SHALL accept it as valid.

        **Validates: Requirements 8.5**

        This property ensures "desc" is a valid sort direction.
        """
        # Arrange
        params_data = {
            "q": "test query",
            "sort": "-createdAt",
            "sort_direction": "desc",
        }

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert params.sort_direction == "desc", "sort_direction 'desc' should be valid"

    @given(
        valid_field=valid_sort_field,
        invalid_direction=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in ["asc", "desc"] and x.strip()
        ),
    )
    @settings(max_examples=100)
    def test_invalid_sort_direction_is_rejected(
        self, valid_field: str, invalid_direction: str
    ):
        """
        Property 2: Sort Parameter Validation - Invalid direction rejection.

        *For any* sort_direction that is not "asc" or "desc", the SearchParams
        model SHALL raise a ValidationError.

        **Validates: Requirements 8.5, 8.6**

        This property ensures that only "asc" and "desc" are valid sort directions.
        """
        # Arrange
        params_data = {
            "q": "test query",
            "sort": valid_field,
            "sort_direction": invalid_direction,
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error message mentions sort direction
        error_message = str(exc_info.value)
        assert (
            "sort_direction" in error_message.lower()
            or "direction" in error_message.lower()
        ), f"Error message should indicate invalid sort direction: {error_message}"

    @given(
        valid_field=valid_sort_field,
        page=st.integers(min_value=1, max_value=100),
        page_size=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_validation_with_other_valid_params(
        self, valid_field: str, page: int, page_size: int
    ):
        """
        Property 2: Sort Parameter Validation - Validation with other parameters.

        *For any* valid sort parameter combined with other valid parameters,
        the SearchParams model SHALL accept all parameters without error.

        **Validates: Requirements 8.4, 8.5**

        This property ensures that sort validation doesn't interfere with
        validation of other parameters.
        """
        # Arrange
        params_data = {
            "q": "test query",
            "sort": f"-{valid_field}",
            "page": page,
            "pageSize": page_size,
            "semantic": False,
        }

        # Act
        params = SearchParams(**params_data)

        # Assert - All parameters should be valid
        assert params.sort_by == valid_field
        assert params.sort_direction == "desc"
        assert params.page == page
        assert params.pageSize == page_size
        assert params.semantic is False

    def test_empty_sort_parameter_is_handled(self):
        """
        Property 2: Sort Parameter Validation - Empty sort parameter handling.

        When sort parameter is an empty string, the SearchParams model SHALL
        handle it gracefully (either accept with None values or reject clearly).

        **Validates: Requirements 8.6**

        This property ensures edge case handling for empty sort parameters.
        """
        # Arrange
        params_data = {"q": "test query", "sort": ""}

        # Act
        params = SearchParams(**params_data)

        # Assert - Empty string should result in no sort being applied
        # The validator should handle this gracefully
        assert (
            params.sort == "" or params.sort is None
        ), "Empty sort parameter should be handled gracefully"
        assert (
            params.sort_by is None or params.sort_by == ""
        ), "sort_by should be None or empty for empty sort parameter"

    @given(valid_field=valid_sort_field)
    @settings(max_examples=100)
    def test_case_sensitive_field_validation(self, valid_field: str):
        """
        Property 2: Sort Parameter Validation - Case sensitivity.

        *For any* valid sort field, the validation SHALL be case-sensitive,
        accepting the exact field name but potentially rejecting variations
        with different casing.

        **Validates: Requirements 8.4**

        This property ensures consistent case-sensitive field name validation.
        """
        # Arrange - Use exact field name
        params_data = {"q": "test query", "sort": valid_field}

        # Act
        params = SearchParams(**params_data)

        # Assert - Exact match should work
        assert (
            params.sort_by == valid_field
        ), f"Exact field name '{valid_field}' should be accepted"

        # Test case variation (if field has letters)
        if any(c.isalpha() for c in valid_field):
            # Try with different case
            case_varied = valid_field.swapcase()
            if case_varied != valid_field:  # Only test if case actually changed
                params_data_varied = {"q": "test query", "sort": case_varied}
                # This should fail validation since field names are case-sensitive
                with pytest.raises(ValidationError):
                    SearchParams(**params_data_varied)
