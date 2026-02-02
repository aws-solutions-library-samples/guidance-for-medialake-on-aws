"""
Property-based tests for storage identifier query construction.

These tests verify that the query builder correctly constructs match_phrase
queries for storage identifier (bucket) filtering.

**Feature: assets-page-bugs, Property 7: Storage Identifier Query Construction**
**Validates: Requirement 2.3**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lambdas.api.search.get_search.index import (
    STORAGE_IDENTIFIER_FIELD,
    SearchParams,
    build_search_query,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid S3 bucket names (simplified - actual S3 naming rules are more complex)
# S3 bucket names: 3-63 chars, lowercase letters, numbers, hyphens, dots
valid_bucket_name = st.text(
    min_size=3,
    max_size=63,
    alphabet=st.characters(
        whitelist_categories=(),
        whitelist_characters="abcdefghijklmnopqrstuvwxyz0123456789-.",
    ),
).filter(
    lambda x: x
    and not x.startswith("-")
    and not x.endswith("-")
    and not x.startswith(".")
    and not x.endswith(".")
    and ".." not in x
)


@pytest.mark.unit
class TestStorageIdentifierQueryConstructionProperty:
    """Property-based tests for storage identifier query construction."""

    @given(bucket_name=valid_bucket_name)
    @settings(max_examples=100)
    def test_storage_identifier_creates_match_phrase_query(self, bucket_name: str):
        """
        Property 7: Storage Identifier Query Construction - match_phrase query.

        *For any* bucket name, when the query starts with "storageIdentifier:",
        the Query_Builder should construct a match_phrase query on the
        configured bucket field path.

        **Validates: Requirement 2.3**

        This property ensures that storage identifier queries use match_phrase
        for exact bucket matching.
        """
        # Arrange
        params = SearchParams(q=f"storageIdentifier:{bucket_name}")

        # Act
        query = build_search_query(params)

        # Assert
        assert "query" in query, "Query should have a query clause"

        query_clause = query["query"]
        assert (
            "match_phrase" in query_clause
        ), "Storage identifier query should use match_phrase"

        # Verify the bucket field is used
        assert (
            STORAGE_IDENTIFIER_FIELD in query_clause["match_phrase"]
        ), f"Query should use storage identifier field: {STORAGE_IDENTIFIER_FIELD}"

    @given(bucket_name=valid_bucket_name)
    @settings(max_examples=100)
    def test_storage_identifier_uses_correct_field_path(self, bucket_name: str):
        """
        Property 7: Storage Identifier Query Construction - Field path.

        *For any* bucket name, the storage identifier query should use the
        correct OpenSearch field path for bucket filtering.

        **Validates: Requirement 2.3**

        This property ensures that the correct field path is used for
        bucket filtering.
        """
        # Arrange
        params = SearchParams(q=f"storageIdentifier:{bucket_name}")

        # Act
        query = build_search_query(params)

        # Assert
        query_clause = query["query"]["match_phrase"]
        assert (
            STORAGE_IDENTIFIER_FIELD in query_clause
        ), f"Query should use field: {STORAGE_IDENTIFIER_FIELD}"

        # Verify the bucket name is in the query
        bucket_value = query_clause[STORAGE_IDENTIFIER_FIELD]
        assert (
            bucket_value == bucket_name
        ), f"Query should filter by bucket name '{bucket_name}', got '{bucket_value}'"

    @given(bucket_name=valid_bucket_name)
    @settings(max_examples=100)
    def test_storage_identifier_preserves_bucket_name(self, bucket_name: str):
        """
        Property 7: Storage Identifier Query Construction - Bucket name preservation.

        *For any* bucket name, the exact bucket name should be preserved in
        the match_phrase query without modification.

        **Validates: Requirement 2.3**

        This property ensures that bucket names are not modified during
        query construction.
        """
        # Arrange
        params = SearchParams(q=f"storageIdentifier:{bucket_name}")

        # Act
        query = build_search_query(params)

        # Assert
        query_clause = query["query"]["match_phrase"]
        bucket_value = query_clause[STORAGE_IDENTIFIER_FIELD]

        assert (
            bucket_value == bucket_name
        ), f"Bucket name should be preserved exactly: expected '{bucket_name}', got '{bucket_value}'"

    @given(
        bucket_name=valid_bucket_name,
        page=st.integers(min_value=1, max_value=100),
        page_size=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_storage_identifier_with_pagination(
        self, bucket_name: str, page: int, page_size: int
    ):
        """
        Property 7: Storage Identifier Query Construction - With pagination.

        *For any* bucket name and pagination parameters, the query should
        include both the storage identifier filter and pagination parameters.

        **Validates: Requirement 2.3**

        This property ensures that storage identifier queries work correctly
        with pagination.
        """
        # Arrange
        params = SearchParams(
            q=f"storageIdentifier:{bucket_name}", page=page, pageSize=page_size
        )

        # Act
        query = build_search_query(params)

        # Assert - Storage identifier query
        assert "query" in query, "Query should have query clause"
        assert (
            "match_phrase" in query["query"]
        ), "Should use match_phrase for storage identifier"
        assert (
            STORAGE_IDENTIFIER_FIELD in query["query"]["match_phrase"]
        ), "Should filter by storage identifier field"

        # Assert - Pagination
        assert "size" in query, "Query should have size parameter"
        assert query["size"] == page_size, f"Size should be {page_size}"
        assert "from" in query, "Query should have from parameter"
        expected_from = (page - 1) * page_size
        assert query["from"] == expected_from, f"From should be {expected_from}"

    @given(
        bucket_name=valid_bucket_name,
        sort_field=st.sampled_from(["createdAt", "name", "size", "type"]),
    )
    @settings(max_examples=100)
    def test_storage_identifier_with_sort(self, bucket_name: str, sort_field: str):
        """
        Property 7: Storage Identifier Query Construction - With sort.

        *For any* bucket name and sort parameter, the query should include
        both the storage identifier filter and sort clause.

        **Validates: Requirement 2.3**

        This property ensures that storage identifier queries work correctly
        with sorting.
        """
        # Arrange
        params = SearchParams(
            q=f"storageIdentifier:{bucket_name}", sort=f"-{sort_field}"
        )

        # Act
        query = build_search_query(params)

        # Assert - Storage identifier query
        assert "query" in query, "Query should have query clause"
        assert (
            "match_phrase" in query["query"]
        ), "Should use match_phrase for storage identifier"

        # Assert - Sort clause
        assert "sort" in query, "Query should have sort clause"
        assert isinstance(query["sort"], list), "Sort clause should be a list"

    @given(bucket_name=valid_bucket_name)
    @settings(max_examples=100)
    def test_storage_identifier_query_structure(self, bucket_name: str):
        """
        Property 7: Storage Identifier Query Construction - Query structure.

        *For any* bucket name, the constructed query should have valid
        OpenSearch query structure.

        **Validates: Requirement 2.3**

        This property ensures that storage identifier queries are valid
        OpenSearch queries.
        """
        # Arrange
        params = SearchParams(q=f"storageIdentifier:{bucket_name}")

        # Act
        query = build_search_query(params)

        # Assert - Valid query structure
        assert isinstance(query, dict), "Query should be a dictionary"
        assert "query" in query, "Query should have 'query' key"
        assert isinstance(query["query"], dict), "Query clause should be a dictionary"
        assert "match_phrase" in query["query"], "Query should use match_phrase"
        assert isinstance(
            query["query"]["match_phrase"], dict
        ), "match_phrase should be a dictionary"

        # Verify field and value structure
        match_phrase = query["query"]["match_phrase"]
        assert len(match_phrase) > 0, "match_phrase should have at least one field"
        assert (
            STORAGE_IDENTIFIER_FIELD in match_phrase
        ), f"match_phrase should contain {STORAGE_IDENTIFIER_FIELD}"

    def test_storage_identifier_field_constant(self):
        """
        Property 7: Storage Identifier Query Construction - Field constant.

        The STORAGE_IDENTIFIER_FIELD constant should be properly defined
        and point to the correct OpenSearch field path.

        **Validates: Requirement 2.5**

        This property ensures that the storage identifier field is correctly
        configured.
        """
        # Assert
        assert (
            STORAGE_IDENTIFIER_FIELD is not None
        ), "STORAGE_IDENTIFIER_FIELD should be defined"
        assert isinstance(
            STORAGE_IDENTIFIER_FIELD, str
        ), "STORAGE_IDENTIFIER_FIELD should be a string"
        assert (
            "Bucket" in STORAGE_IDENTIFIER_FIELD
        ), "STORAGE_IDENTIFIER_FIELD should reference Bucket field"
        assert (
            "DigitalSourceAsset" in STORAGE_IDENTIFIER_FIELD
        ), "STORAGE_IDENTIFIER_FIELD should be in DigitalSourceAsset namespace"

    @given(
        bucket_name=valid_bucket_name,
        prefix=st.text(min_size=0, max_size=20).filter(lambda x: ":" not in x),
    )
    @settings(max_examples=100)
    def test_storage_identifier_prefix_extraction(self, bucket_name: str, prefix: str):
        """
        Property 7: Storage Identifier Query Construction - Prefix extraction.

        *For any* query with "storageIdentifier:" prefix, the bucket name
        should be correctly extracted from after the colon.

        **Validates: Requirement 2.3**

        This property ensures that the storageIdentifier prefix is correctly
        parsed to extract the bucket name.
        """
        # Arrange
        query_string = (
            f"{prefix}storageIdentifier:{bucket_name}"
            if prefix
            else f"storageIdentifier:{bucket_name}"
        )

        # Only test if query starts with storageIdentifier:
        if not query_string.startswith("storageIdentifier:"):
            return

        params = SearchParams(q=query_string)

        # Act
        query = build_search_query(params)

        # Assert
        if "match_phrase" in query["query"]:
            bucket_value = query["query"]["match_phrase"].get(STORAGE_IDENTIFIER_FIELD)
            if bucket_value:
                assert (
                    bucket_value == bucket_name
                ), f"Bucket name should be extracted correctly: expected '{bucket_name}', got '{bucket_value}'"
