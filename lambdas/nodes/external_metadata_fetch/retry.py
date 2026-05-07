"""
Retry logic with exponential backoff for external metadata fetch operations.

This module provides retry functionality for transient errors when fetching
metadata from external systems. It implements exponential backoff to avoid
overwhelming external APIs during temporary failures.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from aws_lambda_powertools import Logger

logger = Logger()

# Type variable for generic return type
T = TypeVar("T")


class ErrorCategory(Enum):
    """Categories of errors for retry decision making."""

    RETRYABLE = "retryable"  # Transient errors that should be retried
    NON_RETRYABLE = "non_retryable"  # Permanent errors that should not be retried


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3  # Maximum number of retry attempts
    initial_backoff_seconds: float = 1.0  # Initial backoff delay (1s)
    backoff_multiplier: float = 2.0  # Multiplier for exponential backoff
    max_backoff_seconds: float = 8.0  # Maximum backoff delay


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any | None = None
    error_message: str | None = None
    attempt_count: int = 0
    last_error: Exception | None = None


# HTTP status codes that indicate transient errors (should retry)
RETRYABLE_STATUS_CODES: set[int] = {
    429,  # Too Many Requests (rate limiting)
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# HTTP status codes that indicate permanent errors (should NOT retry)
NON_RETRYABLE_STATUS_CODES: set[int] = {
    400,  # Bad Request
    401,  # Unauthorized (auth issue, not transient)
    403,  # Forbidden
    404,  # Not Found
    405,  # Method Not Allowed
    409,  # Conflict
    410,  # Gone
    422,  # Unprocessable Entity
}


def classify_error(
    status_code: int | None = None,
    exception: Exception | None = None,
) -> ErrorCategory:
    """
    Classify an error as retryable or non-retryable.

    Args:
        status_code: HTTP status code from the response (if available)
        exception: Exception that was raised (if available)

    Returns:
        ErrorCategory indicating whether the error should be retried
    """
    # Check status code first
    if status_code is not None:
        if status_code in RETRYABLE_STATUS_CODES:
            return ErrorCategory.RETRYABLE
        if status_code in NON_RETRYABLE_STATUS_CODES:
            return ErrorCategory.NON_RETRYABLE
        # 5xx errors are generally retryable
        if 500 <= status_code < 600:
            return ErrorCategory.RETRYABLE
        # 4xx errors are generally non-retryable
        if 400 <= status_code < 500:
            return ErrorCategory.NON_RETRYABLE

    # Check exception type for network-related errors
    if exception is not None:
        exception_name = type(exception).__name__.lower()
        # Network/connection errors are typically transient
        if any(
            keyword in exception_name
            for keyword in ["timeout", "connection", "network", "socket"]
        ):
            return ErrorCategory.RETRYABLE

    # Default to non-retryable for unknown errors
    return ErrorCategory.NON_RETRYABLE


def is_retryable_error(
    status_code: int | None = None,
    exception: Exception | None = None,
) -> bool:
    """
    Determine if an error should trigger a retry.

    Args:
        status_code: HTTP status code from the response (if available)
        exception: Exception that was raised (if available)

    Returns:
        True if the error is transient and should be retried
    """
    return classify_error(status_code, exception) == ErrorCategory.RETRYABLE


def calculate_backoff(
    attempt: int,
    config: RetryConfig,
) -> float:
    """
    Calculate the backoff delay for a given retry attempt.

    Uses exponential backoff: delay = initial * (multiplier ^ attempt)
    Capped at max_backoff_seconds.

    Args:
        attempt: The current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Backoff delay in seconds
    """
    delay = config.initial_backoff_seconds * (config.backoff_multiplier**attempt)
    return min(delay, config.max_backoff_seconds)


def execute_with_retry(
    operation: Callable[[], T],
    config: RetryConfig | None = None,
    operation_name: str = "operation",
    get_status_code: Callable[[Exception], int | None] | None = None,
) -> RetryResult:
    """
    Execute an operation with retry logic and exponential backoff.

    This function will retry the operation for transient errors (HTTP 429, 5xx,
    network timeouts) up to the configured maximum retries. Non-retryable errors
    (HTTP 400, 404, etc.) will fail immediately without retrying.

    Args:
        operation: A callable that performs the operation and returns a result.
                   Should raise an exception on failure.
        config: Retry configuration. Uses defaults if not provided.
        operation_name: Name of the operation for logging purposes.
        get_status_code: Optional function to extract HTTP status code from exception.

    Returns:
        RetryResult containing success status, result or error information,
        and the number of attempts made.

    Example:
        ```python
        def fetch_metadata():
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

        result = execute_with_retry(
            operation=fetch_metadata,
            config=RetryConfig(max_retries=3),
            operation_name="fetch_metadata",
        )

        if result.success:
            metadata = result.result
        else:
            logger.error(f"Failed after {result.attempt_count} attempts: {result.error_message}")
        ```
    """
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None
    attempt_count = 0

    for attempt in range(config.max_retries + 1):
        attempt_count = attempt + 1

        try:
            result = operation()
            logger.info(
                f"{operation_name} succeeded",
                extra={
                    "operation": operation_name,
                    "attempt": attempt_count,
                    "total_attempts": attempt_count,
                },
            )
            return RetryResult(
                success=True,
                result=result,
                attempt_count=attempt_count,
            )

        except Exception as e:
            last_exception = e

            # Extract status code if possible
            status_code = None
            if get_status_code is not None:
                status_code = get_status_code(e)
            elif hasattr(e, "response") and hasattr(e.response, "status_code"):
                status_code = e.response.status_code

            # Check if error is retryable
            if not is_retryable_error(status_code=status_code, exception=e):
                logger.warning(
                    f"{operation_name} failed with non-retryable error",
                    extra={
                        "operation": operation_name,
                        "attempt": attempt_count,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "status_code": status_code,
                        "retryable": False,
                    },
                )
                return RetryResult(
                    success=False,
                    error_message=str(e),
                    attempt_count=attempt_count,
                    last_error=e,
                )

            # Check if we have retries remaining
            if attempt >= config.max_retries:
                logger.error(
                    f"{operation_name} failed after all retry attempts",
                    extra={
                        "operation": operation_name,
                        "total_attempts": attempt_count,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "status_code": status_code,
                    },
                )
                return RetryResult(
                    success=False,
                    error_message=str(e),
                    attempt_count=attempt_count,
                    last_error=e,
                )

            # Calculate backoff and wait
            backoff = calculate_backoff(attempt, config)
            logger.warning(
                f"{operation_name} failed, retrying in {backoff}s",
                extra={
                    "operation": operation_name,
                    "attempt": attempt_count,
                    "max_retries": config.max_retries + 1,
                    "backoff_seconds": backoff,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status_code": status_code,
                },
            )
            time.sleep(backoff)

    # Should not reach here, but handle edge case
    return RetryResult(
        success=False,
        error_message=str(last_exception) if last_exception else "Unknown error",
        attempt_count=attempt_count,
        last_error=last_exception,
    )


def retry_decorator(
    config: RetryConfig | None = None,
    operation_name: str | None = None,
    get_status_code: Callable[[Exception], int | None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that adds retry logic with exponential backoff to a function.

    Args:
        config: Retry configuration. Uses defaults if not provided.
        operation_name: Name for logging. Uses function name if not provided.
        get_status_code: Optional function to extract HTTP status code from exception.

    Returns:
        Decorated function that will retry on transient errors.

    Example:
        ```python
        @retry_decorator(config=RetryConfig(max_retries=3))
        def fetch_data():
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        ```
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            name = operation_name or func.__name__

            def operation() -> T:
                return func(*args, **kwargs)

            result = execute_with_retry(
                operation=operation,
                config=config,
                operation_name=name,
                get_status_code=get_status_code,
            )

            if result.success:
                return result.result
            else:
                # Re-raise the last exception
                if result.last_error:
                    raise result.last_error
                raise RuntimeError(result.error_message)

        return wrapper

    return decorator
