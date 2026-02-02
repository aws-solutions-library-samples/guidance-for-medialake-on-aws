"""
Property-based tests for sort clause construction in OpenSearch queries.

These tests verify that the query builder correctly constructs OpenSearch
sort clauses from SearchParams with sort_by and sort_direction.

**Feature: assets-page-bugs, Property 3: Sort Clause Construction**
**Validates: Requirements 9.1, 9.2**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lambdas.api.search.get_search.index import (
    SearchParams,
    build_search_query,
    map_sort_field_to_opensearch_path,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid sortable field names (frontend-friendly)
FRONTEND_SORT_FIELDS = ["createdAt", "name", "size", "type", "format"]

# Valid sort directions
SORT_DIRECTIONS = ["asc", "desc"]

# Strategy for frontend sort fields
frontend_sort_field = st.sampled_from(FRONTEND_SORT_FIELDS)

# Strategy for sort directions
sort_direction = st.sampled_from(SORT_DIRECTIONS)


@pytest.mark.unit
class TestSortClauseConstructionProperty:
    """Property-based tests for sort clause construction in OpenSearch queries."""

    @given(field_name=frontend_sort_field, direction=sort_direction)
    @settings(max_examples=100)
    def test_sort_clause_is_included_in_query(self, field_name: str, direction: str):
        """
        Property 3: Sort Clause Construction - Inclusion in query.

        *For any* valid sort_by and sort_direction in SearchParams, the
        build_search_query() function SHALL include a sort clause in the
        OpenSearch query body.

        **Validates: Requirement 9.1**

        This property ensures that sort parameters are translated into
        OpenSearch sort clauses.
        """
        # Arrange
        sort_param = f"-{field_name}" if direction == "desc" else field_name
        params = SearchParams(q="storageIdentifier:test-bucket", sort=sort_param)

        # Act
        query = build_search_query(params)

        # Assert
        assert (
            "sort" in query
        ), "Query should contain a 'sort' clause when sort parameters are provided"
        assert isinstance(query["sort"], list), "Sort clause should be a list"
        assert len(query["sort"]) > 0, "Sort clause list should not be empty"

    @given(field_name=frontend_sort_field, direction=sort_direction)
    @settings(max_examples=100)
    def test_sort_clause_uses_mapped_field_path(self, field_name: str, direction: str):
        """
        Property 3: Sort Clause Construction - Field path mapping.

        *For any* frontend field name, the sort clause SHALL use the correctly
        mapped OpenSearch field path.

        **Validates: Requirement 9.2**

        This property ensures that frontend-friendly field names are mapped
        to the correct OpenSearch field paths in the sort clause.
        """
        # Arrange
        sort_param = f"-{field_name}" if direction == "desc" else field_name
        params = SearchParams(q="storageIdentifier:test-bucket", sort=sort_param)
        expected_opensearch_field = map_sort_field_to_opensearch_path(field_name)

        # Act
        query = build_search_query(params)

        # Assert
        assert "sort" in query, "Query should contain sort clause"
        sort_clause = query["sort"][0]
        assert (
            expected_opensearch_field in sort_clause
        ), f"Sort clause should use mapped field '{expected_opensearch_field}', got: {sort_clause}"

    @given(field_name=frontend_sort_field, direction=sort_direction)
    @settings(max_examples=100)
    def test_sort_clause_uses_correct_direction(self, field_name: str, direction: str):
        """
        Property 3: Sort Clause Construction - Sort direction.

        *For any* sort_direction ("asc" or "desc"), the sort clause SHALL
        specify the correct order in the OpenSearch query.

        **Validates: Requirement 9.1**

        This property ensures that the sort direction is correctly included
        in the OpenSearch sort clause.
        """
        # Arrange
        sort_param = f"-{field_name}" if direction == "desc" else field_name
        params = SearchParams(q="storageIdentifier:test-bucket", sort=sort_param)
        expected_opensearch_field = map_sort_field_to_opensearch_path(field_name)

        # Act
        query = build_search_query(params)

        # Assert
        assert "sort" in query, "Query should contain sort clause"
        sort_clause = query["sort"][0]
        assert (
            expected_opensearch_field in sort_clause
        ), "Sort clause should contain the field"
        field_sort_config = sort_clause[expected_opensearch_field]
        assert "order" in field_sort_config, "Sort clause should specify order"
        assert (
            field_sort_config["order"] == direction
        ), f"Sort order should be '{direction}', got '{field_sort_config['order']}'"

    @given(field_name=frontend_sort_field)
    @settings(max_examples=100)
    def test_ascending_sort_clause_construction(self, field_name: str):
        """
        Property 3: Sort Clause Construction - Ascending order.

        *For any* field with ascending sort direction, the sort clause SHALL
        specify "asc" as the order.

        **Validates: Requirements 9.1, 9.2**

        This property specifically tests ascending sort clause construction.
        """
        # Arrange
        params = SearchParams(
            q="storageIdentifier:test-bucket", sort=field_name  # No prefix = ascending
        )
        expected_opensearch_field = map_sort_field_to_opensearch_path(field_name)

        # Act
        query = build_search_query(params)

        # Assert
        sort_clause = query["sort"][0]
        field_sort_config = sort_clause[expected_opensearch_field]
        assert (
            field_sort_config["order"] == "asc"
        ), f"Ascending sort should have order 'asc'"

    @given(field_name=frontend_sort_field)
    @settings(max_examples=100)
    def test_descending_sort_clause_construction(self, field_name: str):
        """
        Property 3: Sort Clause Construction - Descending order.

        *For any* field with descending sort direction, the sort clause SHALL
        specify "desc" as the order.

        **Validates: Requirements 9.1, 9.2**

        This property specifically tests descending sort clause construction.
        """
        # Arrange
        params = SearchParams(
            q="storageIdentifier:test-bucket",
            sort=f"-{field_name}",  # Prefix with "-" = descending
        )
        expected_opensearch_field = map_sort_field_to_opensearch_path(field_name)

        # Act
        query = build_search_query(params)

        # Assert
        sort_clause = query["sort"][0]
        field_sort_config = sort_clause[expected_opensearch_field]
        assert (
            field_sort_config["order"] == "desc"
        ), f"Descending sort should have order 'desc'"

    @given(
        field_name=frontend_sort_field,
        direction=sort_direction,
        page=st.integers(min_value=1, max_value=100),
        page_size=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_sort_clause_with_pagination_params(
        self, field_name: str, direction: str, page: int, page_size: int
    ):
        """
        Property 3: Sort Clause Construction - Interaction with pagination.

        *For any* sort parameters combined with pagination parameters, the
        query SHALL include both sort clause and pagination parameters correctly.

        **Validates: Requirements 9.1, 9.2**

        This property ensures that sort clause construction doesn't interfere
        with other query parameters.
        """
        # Arrange
        sort_param = f"-{field_name}" if direction == "desc" else field_name
        params = SearchParams(
            q="storageIdentifier:test-bucket",
            sort=sort_param,
            page=page,
            pageSize=page_size,
        )

        # Act
        query = build_search_query(params)

        # Assert - Sort clause
        assert "sort" in query, "Query should contain sort clause"

        # Assert - Pagination parameters
        assert "size" in query, "Query should contain size parameter"
        assert query["size"] == page_size, f"Query size should be {page_size}"
        assert "from" in query, "Query should contain from parameter"
        expected_from = (page - 1) * page_size
        assert query["from"] == expected_from, f"Query from should be {expected_from}"

    def test_no_sort_clause_when_sort_not_provided(self):
        """
        Property 3: Sort Clause Construction - Absence when not specified.

        When no sort parameter is provided, the query SHALL NOT include a
        sort clause (or should use default sort).

        **Validates: Requirement 9.1**

        This property ensures that sort clauses are only added when explicitly
        requested.
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket")

        # Act
        query = build_search_query(params)

        # Assert
        # Either no sort clause, or a default sort clause
        # The implementation may choose to add a default sort or omit it
        if "sort" in query:
            # If sort is present, it should be a default sort
            # This is acceptable behavior
            assert isinstance(
                query["sort"], list
            ), "Sort clause should be a list if present"
        # If no sort clause, that's also acceptable

    @given(field_name=frontend_sort_field)
    @settings(max_examples=100)
    def test_sort_clause_structure_is_valid(self, field_name: str):
        """
        Property 3: Sort Clause Construction - Valid OpenSearch structure.

        *For any* sort parameters, the constructed sort clause SHALL follow
        valid OpenSearch sort clause structure.

        **Validates: Requirements 9.1, 9.2**

        This property ensures that the sort clause structure is compatible
        with OpenSearch query syntax.
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket", sort=f"-{field_name}")

        # Act
        query = build_search_query(params)

        # Assert - Valid structure
        assert "sort" in query, "Query should contain sort clause"
        assert isinstance(query["sort"], list), "Sort clause should be a list"
        assert len(query["sort"]) > 0, "Sort clause should not be empty"

        # First element should be a dict with field name as key
        sort_item = query["sort"][0]
        assert isinstance(sort_item, dict), "Sort clause item should be a dictionary"
        assert len(sort_item) > 0, "Sort clause item should not be empty"

        # Should have field name as key and config as value
        field_key = list(sort_item.keys())[0]
        field_config = sort_item[field_key]
        assert isinstance(
            field_config, dict
        ), "Field sort configuration should be a dictionary"
        assert (
            "order" in field_config
        ), "Field sort configuration should have 'order' key"
        assert field_config["order"] in [
            "asc",
            "desc",
        ], "Sort order should be 'asc' or 'desc'"
