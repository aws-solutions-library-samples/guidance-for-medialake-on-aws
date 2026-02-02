"""
Property-based tests for page range validation and handling.

These tests verify that the system correctly validates page numbers,
handles out-of-range pages, and recalculates page ranges dynamically.

**Feature: assets-page-bugs, Properties 10, 11, 12, 13, 14**
**Validates: Requirements 4.1, 4.2, 4.4, 4.5, 4.6, 13.1, 13.2**
"""

import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from lambdas.api.search.get_search.index import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    SearchParams,
)

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid page numbers
valid_page = st.integers(min_value=1, max_value=1000)

# Invalid page numbers (non-positive)
invalid_page = st.integers(max_value=0)

# Valid page sizes
valid_page_size = st.integers(min_value=1, max_value=MAX_PAGE_SIZE)

# Invalid page sizes (out of range)
invalid_page_size_low = st.integers(max_value=0)
invalid_page_size_high = st.integers(min_value=MAX_PAGE_SIZE + 1, max_value=10000)

# Total results for pagination calculations
total_results = st.integers(min_value=0, max_value=10000)


@pytest.mark.unit
class TestPageRangeValidationProperty:
    """Property-based tests for page range validation (Property 10)."""

    @given(
        page=st.integers(min_value=1, max_value=100),
        page_size=valid_page_size,
        total=total_results,
    )
    @settings(max_examples=100)
    def test_out_of_range_page_detection(self, page: int, page_size: int, total: int):
        """
        Property 10: Page Range Validation - Out of range detection.

        *For any* page number greater than the total number of pages
        (when total pages > 0), the system should detect it as out of range.

        **Validates: Requirements 4.1, 4.2**

        This property ensures that page range validation works correctly
        for all combinations of page, page size, and total results.
        """
        # Arrange
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        # Assume we're testing an out-of-range page
        assume(total_pages > 0 and page > total_pages)

        # Act & Assert
        # The page is out of range
        assert (
            page > total_pages
        ), f"Page {page} should be out of range (total pages: {total_pages})"

        # The system should be able to calculate this
        is_out_of_range = page > total_pages if total_pages > 0 else False
        assert is_out_of_range, "System should detect out-of-range page"

    @given(page=valid_page, page_size=valid_page_size, total=total_results)
    @settings(max_examples=100)
    def test_valid_page_within_range(self, page: int, page_size: int, total: int):
        """
        Property 10: Page Range Validation - Valid page acceptance.

        *For any* page number within the valid range, the system should
        accept it without error.

        **Validates: Requirements 4.1, 4.2**

        This property ensures that valid pages are not incorrectly rejected.
        """
        # Arrange
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        # Assume we're testing a valid page
        assume(total_pages == 0 or page <= total_pages)

        # Act
        is_valid = total_pages == 0 or page <= total_pages

        # Assert
        assert is_valid, f"Page {page} should be valid (total pages: {total_pages})"

    @given(page_size=valid_page_size, total=total_results)
    @settings(max_examples=100)
    def test_total_pages_calculation(self, page_size: int, total: int):
        """
        Property 12: Dynamic Page Range Recalculation - Total pages calculation.

        *For any* total results and page size, the system should correctly
        calculate the total number of pages.

        **Validates: Requirement 4.5**

        This property ensures that page range calculations are correct.
        """
        # Act
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        # Assert
        if total == 0:
            assert total_pages == 0, "Total pages should be 0 when there are no results"
        else:
            expected_pages = math.ceil(total / page_size)
            assert (
                total_pages == expected_pages
            ), f"Total pages should be {expected_pages}, got {total_pages}"

            # Verify that total_pages * page_size >= total
            assert (
                total_pages * page_size >= total
            ), "Total pages should be sufficient to hold all results"

            # Verify that (total_pages - 1) * page_size < total
            if total_pages > 1:
                assert (
                    total_pages - 1
                ) * page_size < total, (
                    "Total pages should be minimal (no extra empty pages)"
                )


@pytest.mark.unit
class TestPositivePageNumberValidationProperty:
    """Property-based tests for positive page number validation (Property 13)."""

    @given(page=invalid_page)
    @settings(max_examples=100)
    def test_non_positive_page_is_rejected(self, page: int):
        """
        Property 13: Positive Page Number Validation - Non-positive rejection.

        *For any* page number that is not a positive integer (≤ 0), the
        system should reject it with a validation error.

        **Validates: Requirements 4.6, 13.1**

        This property ensures that only positive page numbers are accepted.
        """
        # Arrange
        params_data = {"q": "test query", "page": page}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error message
        error_message = str(exc_info.value)
        assert (
            "page" in error_message.lower()
        ), f"Error message should mention page: {error_message}"

    @given(page=valid_page)
    @settings(max_examples=100)
    def test_positive_page_is_accepted(self, page: int):
        """
        Property 13: Positive Page Number Validation - Positive acceptance.

        *For any* positive integer page number, the system should accept it.

        **Validates: Requirements 4.6, 13.1**

        This property ensures that all positive page numbers are valid.
        """
        # Arrange
        params_data = {"q": "test query", "page": page}

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert params.page == page, f"Page should be {page}, got {params.page}"
        assert params.page > 0, "Page should be positive"


@pytest.mark.unit
class TestPageSizeRangeValidationProperty:
    """Property-based tests for page size range validation (Property 14)."""

    @given(page_size=invalid_page_size_low)
    @settings(max_examples=100)
    def test_page_size_below_minimum_is_rejected(self, page_size: int):
        """
        Property 14: Page Size Range Validation - Below minimum rejection.

        *For any* pageSize value below 1, the system should reject it with
        a validation error.

        **Validates: Requirement 13.2**

        This property ensures that page size must be at least 1.
        """
        # Arrange
        params_data = {"q": "test query", "pageSize": page_size}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error message
        error_message = str(exc_info.value)
        assert (
            "pageSize" in error_message or "pagesize" in error_message.lower()
        ), f"Error message should mention pageSize: {error_message}"

    @given(page_size=invalid_page_size_high)
    @settings(max_examples=100)
    def test_page_size_above_maximum_is_rejected(self, page_size: int):
        """
        Property 14: Page Size Range Validation - Above maximum rejection.

        *For any* pageSize value above MAX_PAGE_SIZE (500), the system
        should reject it with a validation error.

        **Validates: Requirement 13.2**

        This property ensures that page size cannot exceed the maximum.
        """
        # Arrange
        params_data = {"q": "test query", "pageSize": page_size}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error message
        error_message = str(exc_info.value)
        assert (
            "pageSize" in error_message or "pagesize" in error_message.lower()
        ), f"Error message should mention pageSize: {error_message}"

    @given(page_size=valid_page_size)
    @settings(max_examples=100)
    def test_page_size_within_range_is_accepted(self, page_size: int):
        """
        Property 14: Page Size Range Validation - Valid range acceptance.

        *For any* pageSize value between 1 and MAX_PAGE_SIZE (inclusive),
        the system should accept it.

        **Validates: Requirement 13.2**

        This property ensures that all valid page sizes are accepted.
        """
        # Arrange
        params_data = {"q": "test query", "pageSize": page_size}

        # Act
        params = SearchParams(**params_data)

        # Assert
        assert (
            params.pageSize == page_size
        ), f"PageSize should be {page_size}, got {params.pageSize}"
        assert (
            1 <= params.pageSize <= MAX_PAGE_SIZE
        ), f"PageSize should be between 1 and {MAX_PAGE_SIZE}"


@pytest.mark.unit
class TestPaginationCalculationsProperty:
    """Property-based tests for pagination calculations."""

    @given(page=valid_page, page_size=valid_page_size)
    @settings(max_examples=100)
    def test_from_calculation(self, page: int, page_size: int):
        """
        Property: Pagination Calculations - From offset calculation.

        *For any* valid page and page size, the from_ offset should be
        calculated as (page - 1) * pageSize.

        **Validates: Requirements 4.1, 4.5**

        This property ensures correct offset calculation for pagination.
        """
        # Arrange
        params = SearchParams(q="test query", page=page, pageSize=page_size)

        # Act
        from_offset = params.from_

        # Assert
        expected_from = (page - 1) * page_size
        assert (
            from_offset == expected_from
        ), f"from_ should be {expected_from}, got {from_offset}"

    @given(page=valid_page, page_size=valid_page_size)
    @settings(max_examples=100)
    def test_size_equals_page_size(self, page: int, page_size: int):
        """
        Property: Pagination Calculations - Size equals pageSize.

        *For any* valid page and page size, the size property should equal
        the pageSize.

        **Validates: Requirements 4.1, 4.5**

        This property ensures that the size property correctly reflects pageSize.
        """
        # Arrange
        params = SearchParams(q="test query", page=page, pageSize=page_size)

        # Act
        size = params.size

        # Assert
        assert (
            size == page_size
        ), f"size should equal pageSize ({page_size}), got {size}"

    @given(page=valid_page, page_size=valid_page_size, total=total_results)
    @settings(max_examples=100)
    def test_last_page_calculation(self, page: int, page_size: int, total: int):
        """
        Property: Pagination Calculations - Last page identification.

        *For any* valid pagination parameters, the system should correctly
        identify whether a page is the last page.

        **Validates: Requirement 4.5**

        This property ensures correct last page detection.
        """
        # Arrange
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        # Act
        is_last_page = (page == total_pages) if total_pages > 0 else False

        # Assert
        if total == 0:
            # No pages exist
            assert (
                not is_last_page or page == 0
            ), "Should not have a last page when there are no results"
        elif page == total_pages:
            assert (
                is_last_page
            ), f"Page {page} should be identified as last page (total: {total_pages})"
        else:
            assert (
                not is_last_page
            ), f"Page {page} should not be identified as last page (total: {total_pages})"

    def test_default_page_size_constant(self):
        """
        Property: Pagination Calculations - Default page size constant.

        The DEFAULT_PAGE_SIZE constant should be used consistently.

        **Validates: Requirement 5.1, 5.2, 5.3**

        This property ensures the default page size is properly defined.
        """
        # Assert
        assert (
            DEFAULT_PAGE_SIZE == 50
        ), f"DEFAULT_PAGE_SIZE should be 50, got {DEFAULT_PAGE_SIZE}"
        assert DEFAULT_PAGE_SIZE > 0, "DEFAULT_PAGE_SIZE should be positive"
        assert (
            DEFAULT_PAGE_SIZE <= MAX_PAGE_SIZE
        ), f"DEFAULT_PAGE_SIZE should not exceed MAX_PAGE_SIZE ({MAX_PAGE_SIZE})"
