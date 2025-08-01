"""
Bedrock Utilities

A comprehensive utility library for AWS Bedrock operations that provides:
1. Retry logic with exponential backoff for throttling exceptions
2. Standardized error handling for Bedrock API calls
3. Reusable patterns for async invoke operations
4. Integration with aws_lambda_powertools for logging

Usage:
    from bedrock_utils import (
        with_bedrock_retry,
        bedrock_start_async_invoke_with_retry,
        BedrockThrottlingError
    )

    # Use the decorator for any Bedrock operation
    @with_bedrock_retry()
    def my_bedrock_operation():
        return bedrock_client.some_operation(...)

    # Use the helper function for start_async_invoke
    response = bedrock_start_async_invoke_with_retry(
        bedrock_client,
        model_id="my-model",
        model_input=input_data,
        output_data_config=config
    )
"""

import random
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

# Type variables for better type hinting
T = TypeVar("T")
R = TypeVar("R")

# Initialize logger
logger = Logger()


class BedrockThrottlingError(Exception):
    """Custom exception for Bedrock throttling errors"""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class BedrockRetryConfig:
    """Configuration for Bedrock retry behavior"""

    def __init__(
        self,
        max_retries: int = 30,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


def _is_throttling_error(error: Exception) -> bool:
    """
    Check if an error is a throttling error that should be retried.

    Args:
        error: The exception to check

    Returns:
        True if the error is a throttling error, False otherwise
    """
    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")
        error_message = error.response.get("Error", {}).get("Message", "").lower()

        # Check for various throttling error codes and messages
        throttling_codes = [
            "ThrottlingException",
            "Throttling",
            "TooManyRequestsException",
            "ServiceUnavailable",
            "RequestLimitExceeded",
        ]

        throttling_messages = [
            "too many requests",
            "rate exceeded",
            "throttling",
            "request limit exceeded",
            "service unavailable",
        ]

        return error_code in throttling_codes or any(
            msg in error_message for msg in throttling_messages
        )

    return False


def _calculate_delay(
    attempt: int, config: BedrockRetryConfig, retry_after: Optional[float] = None
) -> float:
    """
    Calculate the delay for the next retry attempt.

    Args:
        attempt: The current attempt number (0-based)
        config: Retry configuration
        retry_after: Optional retry-after hint from the service

    Returns:
        Delay in seconds
    """
    if retry_after:
        # If the service provides a retry-after hint, use it as the base
        delay = retry_after
    else:
        # Calculate exponential backoff delay
        delay = config.base_delay * (config.exponential_base**attempt)

    # Cap the delay at max_delay
    delay = min(delay, config.max_delay)

    # Add jitter to avoid thundering herd
    if config.jitter:
        jitter_range = delay * 0.1  # 10% jitter
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def with_bedrock_retry(
    config: Optional[BedrockRetryConfig] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic with exponential backoff for Bedrock operations.

    Args:
        config: Optional retry configuration. If None, uses default config.

    Returns:
        Decorator function
    """
    if config is None:
        config = BedrockRetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(
                            f"Bedrock operation succeeded after {attempt} retries",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "total_attempts": attempt + 1,
                            },
                        )
                    return result

                except Exception as e:
                    last_exception = e

                    if not _is_throttling_error(e):
                        # If it's not a throttling error, don't retry
                        logger.error(
                            f"Non-throttling error in Bedrock operation: {str(e)}",
                            extra={
                                "function": func.__name__,
                                "error_type": e.__class__.__name__,
                                "attempt": attempt,
                            },
                        )
                        raise e

                    if attempt >= config.max_retries:
                        # Max retries exceeded
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for Bedrock operation",
                            extra={
                                "function": func.__name__,
                                "total_attempts": attempt + 1,
                                "final_error": str(e),
                            },
                        )
                        raise BedrockThrottlingError(
                            f"Max retries exceeded for Bedrock operation: {str(e)}"
                        ) from e

                    # Extract retry-after hint if available
                    retry_after = None
                    if isinstance(e, ClientError):
                        retry_after_header = (
                            e.response.get("ResponseMetadata", {})
                            .get("HTTPHeaders", {})
                            .get("retry-after")
                        )
                        if retry_after_header:
                            try:
                                retry_after = float(retry_after_header)
                            except ValueError:
                                pass

                    # Calculate delay and wait
                    delay = _calculate_delay(attempt, config, retry_after)

                    logger.warning(
                        f"Bedrock throttling detected, retrying in {delay:.2f} seconds",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": config.max_retries,
                            "delay_seconds": delay,
                            "error": str(e),
                        },
                    )

                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError("Unexpected error in retry logic")

        return wrapper

    return decorator


def bedrock_start_async_invoke_with_retry(
    bedrock_client: Any,
    model_id: str,
    model_input: Dict[str, Any],
    output_data_config: Dict[str, Any],
    config: Optional[BedrockRetryConfig] = None,
) -> Dict[str, Any]:
    """
    Start an async Bedrock invoke operation with retry logic.

    Args:
        bedrock_client: Boto3 Bedrock runtime client
        model_id: The model ID to invoke
        model_input: Input data for the model
        output_data_config: Output configuration
        config: Optional retry configuration

    Returns:
        Response from the start_async_invoke operation

    Raises:
        BedrockThrottlingError: If max retries are exceeded
    """

    @with_bedrock_retry(config)
    def _start_async_invoke():
        return bedrock_client.start_async_invoke(
            modelId=model_id,
            modelInput=model_input,
            outputDataConfig=output_data_config,
        )

    return _start_async_invoke()


def bedrock_get_async_invoke_with_retry(
    bedrock_client: Any,
    invocation_arn: str,
    config: Optional[BedrockRetryConfig] = None,
) -> Dict[str, Any]:
    """
    Get the status of an async Bedrock invoke operation with retry logic.

    Args:
        bedrock_client: Boto3 Bedrock runtime client
        invocation_arn: The invocation ARN to check
        config: Optional retry configuration

    Returns:
        Response from the get_async_invoke operation

    Raises:
        BedrockThrottlingError: If max retries are exceeded
    """

    @with_bedrock_retry(config)
    def _get_async_invoke():
        return bedrock_client.get_async_invoke(invocationArn=invocation_arn)

    return _get_async_invoke()


def create_bedrock_client(region_name: str = "us-east-1") -> Any:
    """
    Create a Bedrock runtime client with standard configuration.

    Args:
        region_name: AWS region name

    Returns:
        Configured Bedrock runtime client
    """
    return boto3.client("bedrock-runtime", region_name=region_name)


# Predefined retry configurations for common scenarios
BEDROCK_RETRY_CONFIGS = {
    "default": BedrockRetryConfig(),
    "aggressive": BedrockRetryConfig(
        max_retries=50,
        base_delay=0.5,
        max_delay=120.0,
        exponential_base=2.0,
        jitter=True,
    ),
    "conservative": BedrockRetryConfig(
        max_retries=10,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=1.5,
        jitter=True,
    ),
    "fast": BedrockRetryConfig(
        max_retries=15,
        base_delay=0.1,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
    ),
}
