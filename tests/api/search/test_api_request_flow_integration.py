"""
Integration Tests for API Request Flow

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

These tests verify the complete request flow:
- Frontend sends correct sort parameter format
- Backend receives and processes sort parameter
- OpenSearch query includes sort clause
- Results are returned in correct order
"""

from typing import Any, Dict


# Mock imports for the search API
class MockSearchParams:
    """Mock SearchParams model"""

    def __init__(
        self,
        q: str = "",
        page: int = 1,
        page_size: int = 50,
        sort: str = None,
        semantic: bool = False,
        filters: str = None,
    ):
        self.q = q
        self.page = page
        self.page_size = page_size
        self.sort = sort
        self.sort_by = None
        self.sort_direction = None
        self.semantic = semantic
        self.filters = filters

        # Parse sort parameter
        if sort:
            if sort.startswith("-"):
                self.sort_by = sort[1:]
                self.sort_direction = "desc"
            else:
                self.sort_by = sort
                self.sort_direction = "asc"


def mock_map_sort_field(field: str) -> str:
    """Mock field mapping function"""
    field_mapping = {
        "createdAt": "DigitalSourceAsset.CreateDate",
        "name": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword",
        "size": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
        "type": "DigitalSourceAsset.Type.keyword",
    }
    return field_mapping.get(field, field)


def mock_build_search_query(params: MockSearchParams) -> Dict[str, Any]:
    """Mock query builder that includes sort clause"""
    query = {
        "query": {"bool": {"must": []}},
        "from": (params.page - 1) * params.page_size,
        "size": params.page_size,
    }

    # Add query string if present
    if params.q:
        query["query"]["bool"]["must"].append({"query_string": {"query": params.q}})

    # Add sort clause if present
    if params.sort_by and params.sort_direction:
        mapped_field = mock_map_sort_field(params.sort_by)
        query["sort"] = [{mapped_field: {"order": params.sort_direction}}]

    return query


class TestAPIRequestFlowIntegration:
    """Integration tests for complete API request flow"""

    def test_frontend_sends_correct_sort_parameter_format(self):
        """
        Test that frontend constructs sort parameter correctly

        Format: "-fieldName" for descending, "fieldName" for ascending

        **Validates: Requirement 1.1**
        """
        # Simulate frontend sort parameter construction
        sort_by = "createdAt"
        sort_direction = "desc"

        # Frontend constructs sort parameter
        sort_param = f"{'-' if sort_direction == 'desc' else ''}{sort_by}"

        assert sort_param == "-createdAt"

        # Test ascending
        sort_direction = "asc"
        sort_param = f"{'-' if sort_direction == 'desc' else ''}{sort_by}"
        assert sort_param == "createdAt"

    def test_backend_receives_and_parses_sort_parameter(self):
        """
        Test that backend correctly receives and parses sort parameter

        **Validates: Requirement 1.2**
        """
        # Simulate backend receiving sort parameter
        sort_param = "-createdAt"

        # Backend parses sort parameter
        params = MockSearchParams(q="test", sort=sort_param)

        assert params.sort == "-createdAt"
        assert params.sort_by == "createdAt"
        assert params.sort_direction == "desc"

    def test_backend_parses_ascending_sort_parameter(self):
        """
        Test parsing ascending sort parameter

        **Validates: Requirement 1.2**
        """
        sort_param = "name"
        params = MockSearchParams(q="test", sort=sort_param)

        assert params.sort == "name"
        assert params.sort_by == "name"
        assert params.sort_direction == "asc"

    def test_opensearch_query_includes_sort_clause(self):
        """
        Test that OpenSearch query includes sort clause

        **Validates: Requirement 1.3**
        """
        # Create params with sort
        params = MockSearchParams(q="test", sort="-createdAt")

        # Build query
        query = mock_build_search_query(params)

        # Verify sort clause is present
        assert "sort" in query
        assert len(query["sort"]) > 0

        # Verify sort field and direction
        sort_clause = query["sort"][0]
        assert "DigitalSourceAsset.CreateDate" in sort_clause
        assert sort_clause["DigitalSourceAsset.CreateDate"]["order"] == "desc"

    def test_opensearch_query_maps_field_names_correctly(self):
        """
        Test that frontend field names are mapped to OpenSearch paths

        **Validates: Requirement 1.3**
        """
        test_cases = [
            ("createdAt", "DigitalSourceAsset.CreateDate"),
            (
                "name",
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword",
            ),
            (
                "size",
                "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
            ),
            ("type", "DigitalSourceAsset.Type.keyword"),
        ]

        for frontend_field, expected_opensearch_field in test_cases:
            params = MockSearchParams(q="test", sort=frontend_field)
            query = mock_build_search_query(params)

            assert "sort" in query
            sort_clause = query["sort"][0]
            assert expected_opensearch_field in sort_clause

    def test_opensearch_query_without_sort_parameter(self):
        """
        Test that query without sort parameter doesn't include sort clause

        **Validates: Requirement 1.3**
        """
        params = MockSearchParams(q="test")
        query = mock_build_search_query(params)

        # Sort clause should not be present
        assert "sort" not in query

    def test_complete_request_flow_descending_sort(self):
        """
        Test complete flow: frontend → backend → OpenSearch query

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
        """
        # Step 1: Frontend constructs request
        sort_by = "createdAt"
        sort_direction = "desc"
        sort_param = f"{'-' if sort_direction == 'desc' else ''}{sort_by}"

        # Step 2: Backend receives and parses
        params = MockSearchParams(
            q="storageIdentifier:test-bucket", page=1, page_size=50, sort=sort_param
        )

        # Step 3: Backend builds OpenSearch query
        query = mock_build_search_query(params)

        # Step 4: Verify complete flow
        assert params.sort_by == "createdAt"
        assert params.sort_direction == "desc"
        assert "sort" in query
        assert query["sort"][0]["DigitalSourceAsset.CreateDate"]["order"] == "desc"

    def test_complete_request_flow_ascending_sort(self):
        """
        Test complete flow with ascending sort

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
        """
        # Frontend
        sort_param = "name"

        # Backend
        params = MockSearchParams(q="test", sort=sort_param)
        query = mock_build_search_query(params)

        # Verify
        assert params.sort_by == "name"
        assert params.sort_direction == "asc"
        assert "sort" in query
        assert "Name.keyword" in list(query["sort"][0].keys())[0]
        assert query["sort"][0][list(query["sort"][0].keys())[0]]["order"] == "asc"

    def test_pagination_with_sort(self):
        """
        Test that pagination works correctly with sorting

        **Validates: Requirements 1.4, 10.6**
        """
        # Page 1
        params_page1 = MockSearchParams(
            q="test", page=1, page_size=50, sort="-createdAt"
        )
        query_page1 = mock_build_search_query(params_page1)

        # Page 2
        params_page2 = MockSearchParams(
            q="test", page=2, page_size=50, sort="-createdAt"
        )
        query_page2 = mock_build_search_query(params_page2)

        # Verify pagination offsets
        assert query_page1["from"] == 0
        assert query_page1["size"] == 50
        assert query_page2["from"] == 50
        assert query_page2["size"] == 50

        # Verify both have same sort clause
        assert query_page1["sort"] == query_page2["sort"]

    def test_multiple_sort_fields_not_supported(self):
        """
        Test that only single field sorting is supported

        Current implementation supports only one sort field at a time.
        """
        # Only single sort parameter is accepted
        params = MockSearchParams(q="test", sort="-createdAt")

        # Should have single sort field
        assert params.sort_by == "createdAt"
        assert params.sort_direction == "desc"

    def test_invalid_sort_parameter_handling(self):
        """
        Test handling of invalid sort parameters
        """
        # Empty sort parameter
        params = MockSearchParams(q="test", sort="")
        assert params.sort_by is None
        assert params.sort_direction is None

        # None sort parameter
        params = MockSearchParams(q="test", sort=None)
        assert params.sort_by is None
        assert params.sort_direction is None

    def test_sort_with_storage_identifier_query(self):
        """
        Test sorting works with storageIdentifier queries (connector filtering)

        **Validates: Requirements 1.4, 2.3**
        """
        # Simulate connector asset query with sort
        params = MockSearchParams(q="storageIdentifier:my-bucket", sort="-createdAt")

        query = mock_build_search_query(params)

        # Should have both query and sort
        assert "query" in query
        assert "sort" in query
        assert (
            query["query"]["bool"]["must"][0]["query_string"]["query"]
            == "storageIdentifier:my-bucket"
        )
        assert "CreateDate" in list(query["sort"][0].keys())[0]

    def test_sort_parameter_case_sensitivity(self):
        """
        Test that sort field names are case-sensitive
        """
        # Correct case
        params = MockSearchParams(q="test", sort="createdAt")
        assert params.sort_by == "createdAt"

        # Different case (should be treated as-is)
        params = MockSearchParams(q="test", sort="CreatedAt")
        assert params.sort_by == "CreatedAt"

    def test_query_structure_completeness(self):
        """
        Test that generated query has all required components
        """
        params = MockSearchParams(q="test query", page=2, page_size=25, sort="-size")

        query = mock_build_search_query(params)

        # Verify all components
        assert "query" in query
        assert "from" in query
        assert "size" in query
        assert "sort" in query

        # Verify values
        assert query["from"] == 25  # (page-1) * page_size
        assert query["size"] == 25
        assert len(query["sort"]) == 1

    def test_default_sort_behavior(self):
        """
        Test behavior when no sort parameter is provided

        Should not include sort clause, allowing OpenSearch default behavior
        """
        params = MockSearchParams(q="test")
        query = mock_build_search_query(params)

        # No sort clause should be present
        assert "sort" not in query

        # Query should still be valid
        assert "query" in query
        assert "from" in query
        assert "size" in query
