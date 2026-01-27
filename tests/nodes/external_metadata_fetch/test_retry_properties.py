"""
Property-based tests for retry logic with exponential backoff.

These tests verify that the retry logic correctly handles transient errors
with exponential backoff and does not retry non-retryable errors.

**Feature: external-metadata-enrichment, Property 9: Retry with Exponential Backoff**
**Validates: Requirements 7.1**
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.retry import (
    NON_RETRYABLE_STATUS_CODES,
    RETRYABLE_STATUS_CODES,
    ErrorCategory,
    RetryConfig,
    calculate_backoff,
    classify_error,
    execute_with_retry,
    is_retryable_error,
)


class MockHTTPError(Exception):
    """Mock HTTP error with status code for testing."""

    def __init__(self, status_code: int, message: str = "HTTP Error"):
        self.response = MagicMock()
        self.response.status_code = status_code
        super().__init__(message)


@pytest.mark.unit
class TestRetryWithExponentialBackoffProperty:
    """Property-based tests for retry logic with exponential backoff."""

    @given(status_code=st.sampled_from([500, 502, 503, 429]))
    @settings(max_examples=100)
    def test_retryable_status_codes_trigger_retries(self, status_code: int):
        """
        Property 9: Retry with Exponential Backoff (retryable errors)

        *For any* transient error (HTTP 429, 5xx), the retry logic SHALL
        classify the error as retryable and trigger retry attempts.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. HTTP 429 (rate limiting) triggers retries
        2. HTTP 5xx (server errors) trigger retries
        3. The error is correctly classified as retryable
        """
        # Assert that the status code is classified as retryable
        assert is_retryable_error(
            status_code=status_code
        ), f"Status code {status_code} should be classified as retryable"

        # Assert the error category is RETRYABLE
        category = classify_error(status_code=status_code)
        assert category == ErrorCategory.RETRYABLE, (
            f"Status code {status_code} should have category RETRYABLE, "
            f"but got {category}"
        )

    @given(status_code=st.sampled_from([400, 401, 403, 404, 405, 409, 410, 422]))
    @settings(max_examples=100)
    def test_non_retryable_status_codes_do_not_trigger_retries(self, status_code: int):
        """
        Property 9: Retry with Exponential Backoff (non-retryable errors)

        *For any* non-retryable error (HTTP 400, 404, etc.), the retry logic
        SHALL NOT trigger retry attempts and fail immediately.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. HTTP 4xx client errors (except 429) do not trigger retries
        2. The error is correctly classified as non-retryable
        3. Resources are not wasted on permanent failures
        """
        # Assert that the status code is NOT classified as retryable
        assert not is_retryable_error(
            status_code=status_code
        ), f"Status code {status_code} should NOT be classified as retryable"

        # Assert the error category is NON_RETRYABLE
        category = classify_error(status_code=status_code)
        assert category == ErrorCategory.NON_RETRYABLE, (
            f"Status code {status_code} should have category NON_RETRYABLE, "
            f"but got {category}"
        )

    @given(
        max_retries=st.integers(min_value=1, max_value=5),
        status_code=st.sampled_from([500, 502, 503, 429]),
    )
    @settings(max_examples=100)
    @patch("nodes.external_metadata_fetch.retry.time.sleep")
    def test_retry_attempts_match_config(
        self, mock_sleep: MagicMock, max_retries: int, status_code: int
    ):
        """
        Property 9: Retry with Exponential Backoff (attempt count)

        *For any* retry configuration with max_retries N and a transient error,
        the retry logic SHALL make exactly N+1 total attempts (1 initial + N retries)
        before failing.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. The configured number of retries is respected
        2. Total attempts = max_retries + 1 (initial attempt + retries)
        3. All retry attempts are made for transient errors
        """
        # Track call count
        call_count = 0

        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise MockHTTPError(status_code, f"Server error {status_code}")

        config = RetryConfig(
            max_retries=max_retries,
            initial_backoff_seconds=0.001,  # Very short for testing
        )

        result = execute_with_retry(
            operation=failing_operation,
            config=config,
            operation_name="test_operation",
        )

        # Assert the operation was called the expected number of times
        expected_attempts = max_retries + 1
        assert call_count == expected_attempts, (
            f"Expected {expected_attempts} attempts (1 initial + {max_retries} retries), "
            f"but got {call_count}"
        )

        # Assert the result indicates failure
        assert not result.success, "Result should indicate failure"
        assert result.attempt_count == expected_attempts, (
            f"Result should report {expected_attempts} attempts, "
            f"but reported {result.attempt_count}"
        )

    @given(status_code=st.sampled_from([400, 401, 403, 404, 405, 409, 410, 422]))
    @settings(max_examples=100)
    @patch("nodes.external_metadata_fetch.retry.time.sleep")
    def test_non_retryable_errors_fail_immediately(
        self, mock_sleep: MagicMock, status_code: int
    ):
        """
        Property 9: Retry with Exponential Backoff (immediate failure)

        *For any* non-retryable error, the retry logic SHALL fail immediately
        after the first attempt without any retries.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. Non-retryable errors don't waste resources on retries
        2. Only 1 attempt is made for permanent failures
        3. No sleep/backoff occurs for non-retryable errors
        """
        call_count = 0

        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise MockHTTPError(status_code, f"Client error {status_code}")

        config = RetryConfig(max_retries=3)

        result = execute_with_retry(
            operation=failing_operation,
            config=config,
            operation_name="test_operation",
        )

        # Assert only 1 attempt was made (no retries)
        assert call_count == 1, (
            f"Non-retryable error should result in only 1 attempt, "
            f"but got {call_count}"
        )

        # Assert no sleep was called (no backoff for non-retryable)
        mock_sleep.assert_not_called()

        # Assert the result indicates failure
        assert not result.success, "Result should indicate failure"
        assert (
            result.attempt_count == 1
        ), f"Result should report 1 attempt, but reported {result.attempt_count}"

    @given(attempt=st.integers(min_value=0, max_value=5))
    @settings(max_examples=100)
    def test_exponential_backoff_calculation(self, attempt: int):
        """
        Property 9: Retry with Exponential Backoff (backoff calculation)

        *For any* retry attempt N, the backoff delay SHALL follow exponential
        growth: delay = initial_backoff * (multiplier ^ N), capped at max_backoff.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. Backoff grows exponentially with each attempt
        2. Backoff is capped at the maximum value
        3. The formula is correctly implemented
        """
        config = RetryConfig(
            initial_backoff_seconds=1.0,
            backoff_multiplier=2.0,
            max_backoff_seconds=8.0,
        )

        backoff = calculate_backoff(attempt, config)

        # Calculate expected backoff
        expected_raw = config.initial_backoff_seconds * (
            config.backoff_multiplier**attempt
        )
        expected_capped = min(expected_raw, config.max_backoff_seconds)

        assert backoff == expected_capped, (
            f"Backoff for attempt {attempt} should be {expected_capped}, "
            f"but got {backoff}"
        )

    @given(
        initial_backoff=st.floats(min_value=0.1, max_value=2.0),
        multiplier=st.floats(min_value=1.5, max_value=3.0),
        max_backoff=st.floats(min_value=4.0, max_value=16.0),
    )
    @settings(max_examples=100)
    def test_backoff_never_exceeds_max(
        self, initial_backoff: float, multiplier: float, max_backoff: float
    ):
        """
        Property 9: Retry with Exponential Backoff (max backoff cap)

        *For any* retry configuration, the calculated backoff SHALL never
        exceed the configured max_backoff_seconds value.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. Backoff is always capped at max_backoff_seconds
        2. Even with many retries, backoff doesn't grow unbounded
        """
        config = RetryConfig(
            initial_backoff_seconds=initial_backoff,
            backoff_multiplier=multiplier,
            max_backoff_seconds=max_backoff,
        )

        # Test multiple attempts
        for attempt in range(10):
            backoff = calculate_backoff(attempt, config)
            assert (
                backoff <= max_backoff
            ), f"Backoff {backoff} for attempt {attempt} exceeds max {max_backoff}"

    @given(status_code=st.sampled_from([500, 502, 503, 429]))
    @settings(max_examples=100)
    @patch("nodes.external_metadata_fetch.retry.time.sleep")
    def test_successful_retry_returns_result(
        self, mock_sleep: MagicMock, status_code: int
    ):
        """
        Property 9: Retry with Exponential Backoff (successful retry)

        *For any* transient error that succeeds on a subsequent retry,
        the retry logic SHALL return the successful result.

        **Validates: Requirements 7.1**

        This property ensures that:
        1. Successful retries return the correct result
        2. The operation stops retrying after success
        3. The result indicates success
        """
        call_count = 0
        expected_result = {"data": "success"}

        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise MockHTTPError(status_code, f"Transient error {status_code}")
            return expected_result

        config = RetryConfig(
            max_retries=3,
            initial_backoff_seconds=0.001,
        )

        result = execute_with_retry(
            operation=eventually_succeeds,
            config=config,
            operation_name="test_operation",
        )

        # Assert success
        assert result.success, "Result should indicate success"
        assert (
            result.result == expected_result
        ), f"Result should be {expected_result}, but got {result.result}"
        assert (
            result.attempt_count == 3
        ), f"Should have taken 3 attempts, but took {result.attempt_count}"

    @settings(max_examples=100)
    @given(status_code=st.sampled_from(list(RETRYABLE_STATUS_CODES)))
    def test_all_retryable_codes_in_set(self, status_code: int):
        """
        Property 9: Retry with Exponential Backoff (retryable set consistency)

        *For any* status code in RETRYABLE_STATUS_CODES, the is_retryable_error
        function SHALL return True.

        **Validates: Requirements 7.1**

        This property ensures consistency between the set definition
        and the classification function.
        """
        assert is_retryable_error(status_code=status_code), (
            f"Status code {status_code} is in RETRYABLE_STATUS_CODES "
            f"but is_retryable_error returned False"
        )

    @settings(max_examples=100)
    @given(status_code=st.sampled_from(list(NON_RETRYABLE_STATUS_CODES)))
    def test_all_non_retryable_codes_in_set(self, status_code: int):
        """
        Property 9: Retry with Exponential Backoff (non-retryable set consistency)

        *For any* status code in NON_RETRYABLE_STATUS_CODES, the is_retryable_error
        function SHALL return False.

        **Validates: Requirements 7.1**

        This property ensures consistency between the set definition
        and the classification function.
        """
        assert not is_retryable_error(status_code=status_code), (
            f"Status code {status_code} is in NON_RETRYABLE_STATUS_CODES "
            f"but is_retryable_error returned True"
        )
