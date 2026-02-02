"""
Property-based tests for parameter forwarding in unified search orchestrator.

These tests verify that the unified search orchestrator correctly forwards
all query parameters (including sort) to the legacy search function.

**Feature: assets-page-bugs, Property 21: Parameter Forwarding Completeness**
**Validates: Requirements 11.1, 11.2, 11.3, 11.4**
"""

from unittest.mock import Mock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lambdas.api.search.get_search.unified_search_orchestrator import (
    UnifiedSearchOrchestrator,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid sortable field names
VALID_SORT_FIELDS = ["createdAt", "name", "size", "type", "format"]

# Strategy for query parameters
query_string = st.text(min_size=1, max_size=100).filter(lambda x: x.strip())

# Strategy for page numbers
page_number = st.integers(min_value=1, max_value=100)

# Strategy for page sizes
page_size = st.integers(min_value=1, max_value=500)

# Strategy for sort parameters
sort_param = st.one_of(
    st.sampled_from(VALID_SORT_FIELDS),  # Ascending
    st.sampled_from(VALID_SORT_FIELDS).map(lambda f: f"-{f}"),  # Descending
)

# Strategy for boolean flags
boolean_flag = st.booleans()

# Strategy for min_score
min_score = st.floats(min_value=0.0, max_value=1.0)


@pytest.mark.unit
class TestParameterForwardingProperty:
    """Property-based tests for parameter forwarding completeness."""

    @given(query=query_string, sort=sort_param, page=page_number, page_size=page_size)
    @settings(max_examples=100)
    def test_sort_parameter_is_forwarded(
        self, query: str, sort: str, page: int, page_size: int
    ):
        """
        Property 21: Parameter Forwarding Completeness - Sort parameter.

        *For any* query parameters including sort, the unified search orchestrator
        SHALL forward the sort parameter to the legacy search function.

        **Validates: Requirements 11.1, 11.2, 11.3**

        This property ensures that sort parameters are not dropped during
        orchestration.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {"q": query, "sort": sort, "page": page, "pageSize": page_size}

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            orchestrator._execute_opensearch_search(query_params)

            # Assert
            mock_perform_search.assert_called_once()
            call_args = mock_perform_search.call_args

            # Get the SearchParams object that was passed
            search_params = call_args[0][0]

            # Verify sort parameter was forwarded
            assert hasattr(
                search_params, "sort"
            ), "SearchParams should have sort attribute"
            assert (
                search_params.sort == sort
            ), f"Sort parameter should be forwarded: expected '{sort}', got '{search_params.sort}'"

    @given(
        query=query_string,
        page=page_number,
        page_size=page_size,
        semantic=boolean_flag,
        min_score_val=min_score,
    )
    @settings(max_examples=100)
    def test_all_parameters_are_forwarded(
        self,
        query: str,
        page: int,
        page_size: int,
        semantic: bool,
        min_score_val: float,
    ):
        """
        Property 21: Parameter Forwarding Completeness - All parameters.

        *For any* set of query parameters, the unified search orchestrator
        SHALL forward all parameters to the legacy search function without
        dropping any.

        **Validates: Requirements 11.1, 11.4**

        This property ensures complete parameter forwarding.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {
            "q": query,
            "page": page,
            "pageSize": page_size,
            "semantic": semantic,
            "min_score": min_score_val,
        }

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            orchestrator._execute_opensearch_search(query_params)

            # Assert
            mock_perform_search.assert_called_once()
            call_args = mock_perform_search.call_args
            search_params = call_args[0][0]

            # Verify all parameters were forwarded
            assert search_params.q == query, "Query parameter should be forwarded"
            assert search_params.page == page, "Page parameter should be forwarded"
            assert (
                search_params.pageSize == page_size
            ), "PageSize parameter should be forwarded"
            assert (
                search_params.semantic == semantic
            ), "Semantic parameter should be forwarded"
            assert (
                search_params.min_score == min_score_val
            ), "min_score parameter should be forwarded"

    @given(query=query_string, sort=sort_param)
    @settings(max_examples=100)
    def test_sort_parameter_forwarding_preserves_format(self, query: str, sort: str):
        """
        Property 21: Parameter Forwarding Completeness - Format preservation.

        *For any* sort parameter format ("-fieldName" or "fieldName"), the
        orchestrator SHALL preserve the exact format when forwarding.

        **Validates: Requirements 11.2, 11.3**

        This property ensures that sort parameter format is not modified
        during forwarding.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {"q": query, "sort": sort}

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            orchestrator._execute_opensearch_search(query_params)

            # Assert
            call_args = mock_perform_search.call_args
            search_params = call_args[0][0]

            # Verify exact format is preserved
            assert (
                search_params.sort == sort
            ), f"Sort parameter format should be preserved: expected '{sort}', got '{search_params.sort}'"

            # Verify parsing happened correctly
            if sort.startswith("-"):
                assert (
                    search_params.sort_direction == "desc"
                ), "Descending sort should be parsed correctly"
                assert (
                    search_params.sort_by == sort[1:]
                ), "Field name should be extracted correctly"
            else:
                assert (
                    search_params.sort_direction == "asc"
                ), "Ascending sort should be parsed correctly"
                assert (
                    search_params.sort_by == sort
                ), "Field name should be extracted correctly"

    @given(
        query=query_string,
        filters=st.lists(
            st.fixed_dictionaries(
                {
                    "field": st.text(min_size=1, max_size=20),
                    "value": st.text(max_size=50),
                }
            ),
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_optional_parameters_are_forwarded(self, query: str, filters: list):
        """
        Property 21: Parameter Forwarding Completeness - Optional parameters.

        *For any* optional parameters (filters, search_fields, etc.), the
        orchestrator SHALL forward them when present.

        **Validates: Requirements 11.1, 11.4**

        This property ensures that optional parameters are not dropped.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {"q": query, "filters": filters}

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            orchestrator._execute_opensearch_search(query_params)

            # Assert
            call_args = mock_perform_search.call_args
            search_params = call_args[0][0]

            # Verify filters were forwarded
            assert (
                search_params.filters == filters
            ), "Filters parameter should be forwarded"

    def test_missing_sort_parameter_is_handled(self):
        """
        Property 21: Parameter Forwarding Completeness - Missing parameters.

        When sort parameter is not provided, the orchestrator SHALL handle
        it gracefully without errors.

        **Validates: Requirements 11.1, 11.4**

        This property ensures that missing optional parameters don't cause
        forwarding failures.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {"q": "test query"}

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            result = orchestrator._execute_opensearch_search(query_params)

            # Assert
            mock_perform_search.assert_called_once()
            assert (
                result is not None
            ), "Should return result even without sort parameter"

    @given(
        query=query_string,
        storage_identifier=st.text(min_size=1, max_size=100).filter(
            lambda x: x.strip()
        ),
    )
    @settings(max_examples=100)
    def test_storage_identifier_is_forwarded(self, query: str, storage_identifier: str):
        """
        Property 21: Parameter Forwarding Completeness - Storage identifier.

        *For any* storageIdentifier parameter, the orchestrator SHALL forward
        it to the legacy search function.

        **Validates: Requirements 11.1, 11.4**

        This property ensures that asset explorer queries work correctly
        through the orchestrator.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {"q": f"storageIdentifier:{storage_identifier}"}

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            orchestrator._execute_opensearch_search(query_params)

            # Assert
            call_args = mock_perform_search.call_args
            search_params = call_args[0][0]

            # Verify query with storageIdentifier was forwarded
            assert (
                storage_identifier in search_params.q
            ), f"Storage identifier should be in query: {search_params.q}"

    @given(
        query=query_string,
        param_name=st.sampled_from(["type", "extension", "filename"]),
        param_value=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100)
    def test_facet_parameters_are_forwarded(
        self, query: str, param_name: str, param_value: str
    ):
        """
        Property 21: Parameter Forwarding Completeness - Facet parameters.

        *For any* facet parameters (type, extension, filename), the orchestrator
        SHALL forward them to the legacy search function.

        **Validates: Requirements 11.1, 11.4**

        This property ensures that facet filtering works through the orchestrator.
        """
        # Arrange
        mock_logger = Mock()
        mock_metrics = Mock()
        orchestrator = UnifiedSearchOrchestrator(mock_logger, mock_metrics)

        query_params = {"q": query, param_name: param_value}

        # Mock the perform_search function
        with patch(
            "lambdas.api.search.get_search.unified_search_orchestrator.perform_search"
        ) as mock_perform_search:
            mock_perform_search.return_value = {
                "status": "200",
                "data": {"results": [], "searchMetadata": {}},
            }

            # Act
            orchestrator._execute_opensearch_search(query_params)

            # Assert
            call_args = mock_perform_search.call_args
            search_params = call_args[0][0]

            # Verify facet parameter was forwarded
            assert hasattr(
                search_params, param_name
            ), f"SearchParams should have {param_name} attribute"
            assert (
                getattr(search_params, param_name) == param_value
            ), f"{param_name} parameter should be forwarded"
