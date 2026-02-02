"""
Property-based tests for sort parameter extraction in SearchParams.

These tests verify that the SearchParams model correctly extracts sort field
and direction from the sort parameter format.

**Feature: assets-page-bugs, Property 1: Sort Parameter Extraction**
**Validates: Requirements 8.2, 8.3**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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

# Strategy for valid sort field names
valid_sort_field = st.sampled_from(VALID_SORT_FIELDS)

# Strategy for sort parameter with descending order (prefix with "-")
descending_sort_param = valid_sort_field.map(lambda field: f"-{field}")

# Strategy for sort parameter with ascending order (no prefix)
ascending_sort_param = valid_sort_field


@pytest.mark.unit
class TestSortParameterExtractionProperty:
    """Property-based tests for sort parameter extraction."""

    @given(field_name=valid_sort_field)
    @settings(max_examples=100)
    def test_descending_sort_extraction(self, field_name: str):
        """
        Property 1: Sort Parameter Extraction - Descending order.

        *For any* sort parameter in the format "-fieldName", the SearchParams
        model SHALL extract "fieldName" as sort_by and "desc" as sort_direction.

        **Validates: Requirements 8.2**

        This property ensures that the "-" prefix correctly indicates descending order.
        """
        # Arrange
        sort_param = f"-{field_name}"
        params_data = {"q": "test query", "sort": sort_param}

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert (
            params.sort_by == field_name
        ), f"sort_by should be '{field_name}' (without prefix), got '{params.sort_by}'"
        assert (
            params.sort_direction == "desc"
        ), f"sort_direction should be 'desc' for '-{field_name}', got '{params.sort_direction}'"
        assert params.sort == sort_param, f"Original sort parameter should be preserved"

    @given(field_name=valid_sort_field)
    @settings(max_examples=100)
    def test_ascending_sort_extraction(self, field_name: str):
        """
        Property 1: Sort Parameter Extraction - Ascending order.

        *For any* sort parameter in the format "fieldName" (no prefix), the
        SearchParams model SHALL extract "fieldName" as sort_by and "asc" as
        sort_direction.

        **Validates: Requirements 8.3**

        This property ensures that no prefix correctly indicates ascending order.
        """
        # Arrange
        params_data = {"q": "test query", "sort": field_name}

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert (
            params.sort_by == field_name
        ), f"sort_by should be '{field_name}', got '{params.sort_by}'"
        assert (
            params.sort_direction == "asc"
        ), f"sort_direction should be 'asc' for '{field_name}', got '{params.sort_direction}'"
        assert params.sort == field_name, f"Original sort parameter should be preserved"

    @given(field_name=valid_sort_field)
    @settings(max_examples=100)
    def test_sort_extraction_preserves_original(self, field_name: str):
        """
        Property 1: Sort Parameter Extraction - Original preservation.

        *For any* sort parameter, the SearchParams model SHALL preserve the
        original sort parameter value while extracting sort_by and sort_direction.

        **Validates: Requirements 8.2, 8.3**

        This property ensures that the original sort parameter is not lost during parsing.
        """
        # Arrange - Test both ascending and descending
        asc_params_data = {"q": "test query", "sort": field_name}
        desc_params_data = {"q": "test query", "sort": f"-{field_name}"}

        # Act
        asc_params = SearchParams(**asc_params_data)
        desc_params = SearchParams(**desc_params_data)

        # Assert - Ascending
        assert (
            asc_params.sort == field_name
        ), "Original ascending sort parameter should be preserved"
        assert (
            asc_params.sort_by == field_name
        ), "sort_by should match field name for ascending"
        assert asc_params.sort_direction == "asc", "sort_direction should be 'asc'"

        # Assert - Descending
        assert (
            desc_params.sort == f"-{field_name}"
        ), "Original descending sort parameter should be preserved"
        assert (
            desc_params.sort_by == field_name
        ), "sort_by should be field name without prefix for descending"
        assert desc_params.sort_direction == "desc", "sort_direction should be 'desc'"

    def test_no_sort_parameter_defaults(self):
        """
        Property 1: Sort Parameter Extraction - Default values.

        When no sort parameter is provided, the SearchParams model SHALL
        have None for sort and sort_by, and "desc" as the default sort_direction.

        **Validates: Requirements 8.2, 8.3**

        This property ensures proper default behavior when sorting is not specified.
        """
        # Arrange
        params_data = {"q": "test query"}

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert params.sort is None, "sort should be None when not provided"
        assert (
            params.sort_by is None
        ), "sort_by should be None when sort is not provided"
        assert (
            params.sort_direction == "desc"
        ), "sort_direction should default to 'desc'"

    @given(
        field_name=valid_sort_field,
        page=st.integers(min_value=1, max_value=100),
        page_size=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_sort_extraction_with_other_params(
        self, field_name: str, page: int, page_size: int
    ):
        """
        Property 1: Sort Parameter Extraction - Interaction with other parameters.

        *For any* sort parameter combined with other query parameters (page, pageSize),
        the SearchParams model SHALL correctly extract sort_by and sort_direction
        without affecting other parameters.

        **Validates: Requirements 8.2, 8.3**

        This property ensures that sort parameter extraction doesn't interfere
        with other parameter processing.
        """
        # Arrange
        params_data = {
            "q": "test query",
            "sort": f"-{field_name}",
            "page": page,
            "pageSize": page_size,
        }

        # Act
        params = SearchParams(**params_data)

        # Assert - Sort parameters
        assert params.sort_by == field_name, "sort_by should be extracted correctly"
        assert params.sort_direction == "desc", "sort_direction should be 'desc'"

        # Assert - Other parameters unchanged
        assert params.page == page, f"page should be {page}, got {params.page}"
        assert (
            params.pageSize == page_size
        ), f"pageSize should be {page_size}, got {params.pageSize}"
        assert params.q == "test query", "query should be preserved"
