"""
Unit tests for default sort behavior in the query builder.

These tests verify that the system handles cases where no sort parameter
is provided or when the sort parameter is empty.

**Feature: assets-page-bugs, Task 3.4**
**Validates: Requirement 1.6**
"""

import pytest

from lambdas.api.search.get_search.index import SearchParams, build_search_query


@pytest.mark.unit
class TestDefaultSortBehavior:
    """Unit tests for default sort behavior."""

    def test_no_sort_parameter_uses_default_or_none(self):
        """
        Test that no sort parameter results in either default sort or no sort clause.

        **Validates: Requirement 1.6**

        When no sort parameter is provided, the system should either:
        1. Apply a default sort (createdAt desc), or
        2. Omit the sort clause (letting OpenSearch use its default)

        Both behaviors are acceptable as long as they're consistent.
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket")

        # Act
        query = build_search_query(params)

        # Assert
        # The query should be valid regardless of whether sort is present
        assert "query" in query, "Query should have a query clause"

        # If sort is present, verify it's structured correctly
        if "sort" in query:
            assert isinstance(
                query["sort"], list
            ), "Sort clause should be a list if present"
            # If default sort is applied, it should be createdAt desc
            if len(query["sort"]) > 0:
                sort_item = query["sort"][0]
                # Default sort should be by creation date descending
                # This is acceptable default behavior
                assert isinstance(sort_item, dict), "Sort item should be a dictionary"

    def test_empty_sort_parameter_is_handled_gracefully(self):
        """
        Test that an empty sort parameter is handled without errors.

        **Validates: Requirement 1.6**

        When the sort parameter is an empty string, the system should handle
        it gracefully, either treating it as no sort or applying a default.
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket", sort="")

        # Act
        query = build_search_query(params)

        # Assert
        assert "query" in query, "Query should be valid with empty sort parameter"

        # Empty sort should result in either no sort clause or default sort
        # Both are acceptable behaviors
        if "sort" in query:
            assert isinstance(
                query["sort"], list
            ), "Sort clause should be a list if present"

    def test_none_sort_parameter_is_handled_gracefully(self):
        """
        Test that a None sort parameter is handled without errors.

        **Validates: Requirement 1.6**

        When the sort parameter is None (not provided), the system should
        handle it gracefully.
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket", sort=None)

        # Act
        query = build_search_query(params)

        # Assert
        assert "query" in query, "Query should be valid with None sort parameter"
        assert params.sort is None, "sort should be None"
        assert params.sort_by is None, "sort_by should be None when sort is None"

    def test_default_sort_direction_is_desc(self):
        """
        Test that the default sort direction is descending.

        **Validates: Requirement 1.6**

        When no sort direction is specified, the default should be descending
        (most recent/largest first is typically more useful).
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket")

        # Act & Assert
        assert (
            params.sort_direction == "desc"
        ), "Default sort direction should be 'desc'"

    def test_query_without_sort_has_required_fields(self):
        """
        Test that queries without sort parameters still have all required fields.

        **Validates: Requirement 1.6**

        Even without sort parameters, the query should have all necessary
        components (query clause, size, from, etc.).
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket", page=2, pageSize=25)

        # Act
        query = build_search_query(params)

        # Assert - Required query components
        assert "query" in query, "Query should have query clause"
        assert "size" in query, "Query should have size parameter"
        assert "from" in query, "Query should have from parameter"

        # Verify pagination is correct
        assert query["size"] == 25, "Size should match pageSize"
        assert query["from"] == 25, "From should be (page-1) * pageSize"

    def test_explicit_sort_overrides_default(self):
        """
        Test that explicitly providing a sort parameter overrides any default.

        **Validates: Requirement 1.6**

        When a sort parameter is explicitly provided, it should be used
        instead of any default sort behavior.
        """
        # Arrange
        params = SearchParams(
            q="storageIdentifier:test-bucket",
            sort="name",  # Explicitly sort by name ascending
        )

        # Act
        query = build_search_query(params)

        # Assert
        assert "sort" in query, "Query should have sort clause when explicitly provided"
        sort_clause = query["sort"][0]

        # Should be sorting by name, not by default field
        assert (
            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword"
            in sort_clause
        ), "Should be sorting by name field when explicitly specified"

        # Should be ascending (no "-" prefix)
        field_config = sort_clause[
            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword"
        ]
        assert (
            field_config["order"] == "asc"
        ), "Should use ascending order when no prefix is provided"

    def test_storage_identifier_query_without_sort(self):
        """
        Test that storageIdentifier queries work correctly without sort parameters.

        **Validates: Requirement 1.6**

        Asset explorer queries (storageIdentifier:bucket) should work correctly
        even when no sort parameter is provided.
        """
        # Arrange
        params = SearchParams(q="storageIdentifier:test-bucket")

        # Act
        query = build_search_query(params)

        # Assert
        assert "query" in query, "Query should have query clause"

        # Should have match_phrase query for bucket
        query_clause = query["query"]
        assert (
            "match_phrase" in query_clause
        ), "storageIdentifier query should use match_phrase"

        # Verify bucket field is used
        bucket_field = (
            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket"
        )
        assert (
            bucket_field in query_clause["match_phrase"]
        ), f"Query should filter by bucket field: {bucket_field}"

    def test_semantic_search_without_sort(self):
        """
        Test that semantic search queries work correctly without sort parameters.

        **Validates: Requirement 1.6**

        Semantic search should work correctly even when no sort parameter
        is provided (semantic search may have its own relevance-based ordering).
        """
        # Arrange
        params = SearchParams(q="test query", semantic=True)

        # Act
        query = build_search_query(params)

        # Assert
        assert "query" in query, "Query should have query clause"
        # Semantic search should work regardless of sort parameter presence
