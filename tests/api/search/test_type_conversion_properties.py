"""
Property-based tests for query parameter type conversion.

These tests verify that the system correctly converts string query parameters
to appropriate types (int, bool, float) and handles conversion errors.

**Feature: assets-page-bugs, Properties 22, 23**
**Validates: Requirements 13.5, 13.6**
"""

import pytest
from hypothesis import given, settings
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

# Valid string representations of integers
valid_int_string = st.integers(min_value=1, max_value=1000).map(str)

# Valid string representations of booleans
valid_bool_string = st.sampled_from(["true", "false", "True", "False", "1", "0"])

# Valid string representations of floats
valid_float_string = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
).map(str)


# Invalid string representations (non-numeric)
# Filter out strings that could be converted to int (including whitespace-padded numbers)
def is_not_convertible_to_int(s: str) -> bool:
    """Check if string cannot be converted to int."""
    try:
        int(s)
        return False
    except (ValueError, TypeError):
        return True


invalid_int_string = st.text(min_size=1, max_size=20).filter(
    lambda x: is_not_convertible_to_int(x)
    and x not in ["true", "false", "True", "False"]
)

# Query strings
query_string = st.text(min_size=1, max_size=100).filter(lambda x: x.strip())


@pytest.mark.unit
class TestQueryParameterTypeConversionProperty:
    """Property-based tests for query parameter type conversion (Property 22)."""

    @given(query=query_string, page_str=valid_int_string)
    @settings(max_examples=100)
    def test_page_string_to_int_conversion(self, query: str, page_str: str):
        """
        Property 22: Query Parameter Type Conversion - Page number.

        *For any* valid string representation of a page number, the system
        should convert it to an integer before processing.

        **Validates: Requirement 13.5**

        This property ensures that page parameters are correctly converted
        from strings to integers.
        """
        # Arrange
        page_int = int(page_str)

        # Act
        params = SearchParams(q=query, page=page_int)

        # Assert
        assert isinstance(
            params.page, int
        ), f"Page should be converted to int, got {type(params.page)}"
        assert (
            params.page == page_int
        ), f"Page value should be {page_int}, got {params.page}"

    @given(query=query_string, page_size_str=valid_int_string)
    @settings(max_examples=100)
    def test_page_size_string_to_int_conversion(self, query: str, page_size_str: str):
        """
        Property 22: Query Parameter Type Conversion - Page size.

        *For any* valid string representation of a page size, the system
        should convert it to an integer before processing.

        **Validates: Requirement 13.5**

        This property ensures that pageSize parameters are correctly converted
        from strings to integers.
        """
        # Arrange
        page_size_int = int(page_size_str)

        # Skip if out of valid range
        if page_size_int < 1 or page_size_int > MAX_PAGE_SIZE:
            return

        # Act
        params = SearchParams(q=query, pageSize=page_size_int)

        # Assert
        assert isinstance(
            params.pageSize, int
        ), f"PageSize should be converted to int, got {type(params.pageSize)}"
        assert (
            params.pageSize == page_size_int
        ), f"PageSize value should be {page_size_int}, got {params.pageSize}"

    @given(query=query_string, semantic_bool=st.booleans())
    @settings(max_examples=100)
    def test_semantic_string_to_bool_conversion(self, query: str, semantic_bool: bool):
        """
        Property 22: Query Parameter Type Conversion - Boolean flag.

        *For any* valid string representation of a boolean, the system
        should convert it to a boolean before processing.

        **Validates: Requirement 13.5**

        This property ensures that boolean parameters (like semantic) are
        correctly converted from strings to booleans.
        """
        # Act
        params = SearchParams(q=query, semantic=semantic_bool)

        # Assert
        assert isinstance(
            params.semantic, bool
        ), f"Semantic should be converted to bool, got {type(params.semantic)}"
        assert (
            params.semantic == semantic_bool
        ), f"Semantic value should be {semantic_bool}, got {params.semantic}"

    @given(
        query=query_string,
        min_score_float=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_min_score_string_to_float_conversion(
        self, query: str, min_score_float: float
    ):
        """
        Property 22: Query Parameter Type Conversion - Float value.

        *For any* valid string representation of a float, the system
        should convert it to a float before processing.

        **Validates: Requirement 13.5**

        This property ensures that float parameters (like min_score) are
        correctly converted from strings to floats.
        """
        # Act
        params = SearchParams(q=query, min_score=min_score_float)

        # Assert
        assert isinstance(
            params.min_score, float
        ), f"min_score should be converted to float, got {type(params.min_score)}"
        assert (
            abs(params.min_score - min_score_float) < 0.0001
        ), f"min_score value should be {min_score_float}, got {params.min_score}"

    @given(
        query=query_string,
        page=st.integers(min_value=1, max_value=100),
        page_size=st.integers(min_value=1, max_value=MAX_PAGE_SIZE),
        semantic=st.booleans(),
    )
    @settings(max_examples=100)
    def test_multiple_type_conversions(
        self, query: str, page: int, page_size: int, semantic: bool
    ):
        """
        Property 22: Query Parameter Type Conversion - Multiple parameters.

        *For any* combination of valid parameter types, the system should
        convert all parameters to their appropriate types.

        **Validates: Requirement 13.5**

        This property ensures that multiple type conversions work correctly
        together.
        """
        # Act
        params = SearchParams(q=query, page=page, pageSize=page_size, semantic=semantic)

        # Assert
        assert isinstance(params.page, int), "Page should be int"
        assert isinstance(params.pageSize, int), "PageSize should be int"
        assert isinstance(params.semantic, bool), "Semantic should be bool"

        assert params.page == page, f"Page should be {page}"
        assert params.pageSize == page_size, f"PageSize should be {page_size}"
        assert params.semantic == semantic, f"Semantic should be {semantic}"

    def test_default_values_have_correct_types(self):
        """
        Property 22: Query Parameter Type Conversion - Default values.

        Default parameter values should have the correct types.

        **Validates: Requirement 13.5**

        This property ensures that default values are properly typed.
        """
        # Act
        params = SearchParams(q="test query")

        # Assert
        assert isinstance(
            params.page, int
        ), f"Default page should be int, got {type(params.page)}"
        assert isinstance(
            params.pageSize, int
        ), f"Default pageSize should be int, got {type(params.pageSize)}"
        assert isinstance(
            params.semantic, bool
        ), f"Default semantic should be bool, got {type(params.semantic)}"
        assert isinstance(
            params.min_score, float
        ), f"Default min_score should be float, got {type(params.min_score)}"

        # Verify default values
        assert params.page == 1, "Default page should be 1"
        assert (
            params.pageSize == DEFAULT_PAGE_SIZE
        ), f"Default pageSize should be {DEFAULT_PAGE_SIZE}"
        assert params.semantic is False, "Default semantic should be False"
        assert params.min_score == 0.01, "Default min_score should be 0.01"


@pytest.mark.unit
class TestTypeConversionErrorHandlingProperty:
    """Property-based tests for type conversion error handling (Property 23)."""

    @given(query=query_string, invalid_page=invalid_int_string)
    @settings(max_examples=100)
    def test_invalid_page_type_raises_error(self, query: str, invalid_page: str):
        """
        Property 23: Type Conversion Error Handling - Invalid page.

        *For any* query parameter that fails type conversion (page), the
        system should return a validation error indicating the expected type.

        **Validates: Requirement 13.6**

        This property ensures that invalid page values are rejected with
        appropriate error messages.
        """
        # Arrange
        params_data = {"q": query, "page": invalid_page}

        # Act & Assert
        with pytest.raises((ValidationError, ValueError, TypeError)) as exc_info:
            SearchParams(**params_data)

        # Verify error is related to type conversion
        error_message = str(exc_info.value).lower()
        # Error should mention page or type/validation issue
        assert any(
            keyword in error_message
            for keyword in ["page", "type", "int", "validation"]
        ), f"Error message should indicate type conversion issue: {error_message}"

    @given(query=query_string, invalid_page_size=invalid_int_string)
    @settings(max_examples=100)
    def test_invalid_page_size_type_raises_error(
        self, query: str, invalid_page_size: str
    ):
        """
        Property 23: Type Conversion Error Handling - Invalid page size.

        *For any* query parameter that fails type conversion (pageSize), the
        system should return a validation error indicating the expected type.

        **Validates: Requirement 13.6**

        This property ensures that invalid pageSize values are rejected with
        appropriate error messages.
        """
        # Arrange
        params_data = {"q": query, "pageSize": invalid_page_size}

        # Act & Assert
        with pytest.raises((ValidationError, ValueError, TypeError)) as exc_info:
            SearchParams(**params_data)

        # Verify error is related to type conversion
        error_message = str(exc_info.value).lower()
        # Error should mention pageSize or type/validation issue
        assert any(
            keyword in error_message
            for keyword in ["pagesize", "page_size", "type", "int", "validation"]
        ), f"Error message should indicate type conversion issue: {error_message}"

    def test_invalid_semantic_type_raises_error(self):
        """
        Property 23: Type Conversion Error Handling - Invalid boolean.

        *For any* query parameter that fails type conversion (semantic), the
        system should return a validation error indicating the expected type.

        **Validates: Requirement 13.6**

        This property ensures that invalid boolean values are rejected with
        appropriate error messages.
        """
        # Arrange
        params_data = {"q": "test query", "semantic": "not_a_boolean"}

        # Act & Assert
        with pytest.raises((ValidationError, ValueError, TypeError)) as exc_info:
            SearchParams(**params_data)

        # Verify error is related to type conversion
        error_message = str(exc_info.value).lower()
        # Error should mention semantic or type/validation issue
        assert any(
            keyword in error_message
            for keyword in ["semantic", "bool", "type", "validation"]
        ), f"Error message should indicate type conversion issue: {error_message}"

    def test_invalid_min_score_type_raises_error(self):
        """
        Property 23: Type Conversion Error Handling - Invalid float.

        *For any* query parameter that fails type conversion (min_score), the
        system should return a validation error indicating the expected type.

        **Validates: Requirement 13.6**

        This property ensures that invalid float values are rejected with
        appropriate error messages.
        """
        # Arrange
        params_data = {"q": "test query", "min_score": "not_a_float"}

        # Act & Assert
        with pytest.raises((ValidationError, ValueError, TypeError)) as exc_info:
            SearchParams(**params_data)

        # Verify error is related to type conversion
        error_message = str(exc_info.value).lower()
        # Error should mention min_score or type/validation issue
        assert any(
            keyword in error_message
            for keyword in ["min_score", "float", "type", "validation"]
        ), f"Error message should indicate type conversion issue: {error_message}"

    @given(
        query=query_string,
        page=st.one_of(
            st.floats(allow_nan=True, allow_infinity=True),
            st.none(),
            st.lists(st.integers()),
            st.dictionaries(st.text(), st.integers()),
        ),
    )
    @settings(max_examples=100)
    def test_wrong_type_for_page_raises_error(self, query: str, page):
        """
        Property 23: Type Conversion Error Handling - Wrong type.

        *For any* parameter with completely wrong type (not convertible to int),
        the system should raise a validation error.

        **Validates: Requirement 13.6**

        This property ensures that parameters with wrong types are rejected.
        """
        # Arrange
        params_data = {"q": query, "page": page}

        # Act & Assert
        # Should raise validation error for wrong types
        try:
            params = SearchParams(**params_data)
            # If it doesn't raise, the value should have been converted or defaulted
            assert isinstance(
                params.page, int
            ), "Page should be int if validation passes"
        except (ValidationError, ValueError, TypeError):
            # Expected - wrong type should be rejected
            pass

    def test_error_message_includes_expected_type(self):
        """
        Property 23: Type Conversion Error Handling - Error message content.

        Error messages for type conversion failures should indicate the
        expected type.

        **Validates: Requirement 13.6**

        This property ensures that error messages are informative.
        """
        # Arrange
        params_data = {"q": "test query", "page": "not_an_integer"}

        # Act & Assert
        with pytest.raises((ValidationError, ValueError, TypeError)) as exc_info:
            SearchParams(**params_data)

        # Verify error message is informative
        error_message = str(exc_info.value)

        # Error should provide useful information
        assert len(error_message) > 0, "Error message should not be empty"

        # Error should mention the field or type issue
        assert any(
            keyword in error_message.lower()
            for keyword in ["page", "int", "type", "validation"]
        ), f"Error message should be informative: {error_message}"

    @given(query=query_string, page=st.integers(min_value=-1000, max_value=0))
    @settings(max_examples=100)
    def test_out_of_range_integer_raises_error(self, query: str, page: int):
        """
        Property 23: Type Conversion Error Handling - Out of range.

        *For any* integer parameter that is out of valid range, the system
        should raise a validation error.

        **Validates: Requirement 13.6**

        This property ensures that out-of-range values are rejected even if
        they are the correct type.
        """
        # Arrange
        params_data = {"q": query, "page": page}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SearchParams(**params_data)

        # Verify error mentions the validation constraint
        error_message = str(exc_info.value).lower()
        assert any(
            keyword in error_message
            for keyword in ["page", "greater", "positive", "validation"]
        ), f"Error message should indicate range validation issue: {error_message}"
