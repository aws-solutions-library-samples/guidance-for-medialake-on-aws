"""
MediaConvert Utility Module
────────────────────────────
Provides centralized MediaConvert client management with module-level caching
and intelligent retry logic to minimize API throttling.

Key Features:
- Module-level endpoint caching (persists across warm Lambda invocations)
- Exponential backoff with jitter for throttling errors
- Timeout-aware retry logic to prevent Lambda timeouts
- CloudWatch metrics emission for monitoring
- Error classification for proper handling

Usage:
    from mediaconvert_utils import get_mediaconvert_client_with_cache

    client = get_mediaconvert_client_with_cache(
        region="us-east-1",
        timeout_buffer_seconds=30
    )

    # Use client for MediaConvert operations
    response = client.create_job(...)
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize Powertools
logger = Logger(child=True)
metrics = Metrics()

# Module-level cache (persists across warm Lambda invocations)
_mediaconvert_endpoint_cache: Dict[str, str] = {}
_mediaconvert_client_cache: Dict[str, Any] = {}


# ============================================================================
# Custom Exception Classes
# ============================================================================


class MediaConvertError(Exception):
    """Base exception for MediaConvert operations."""


class MediaConvertEndpointError(MediaConvertError):
    """Raised when endpoint cannot be retrieved."""


class MediaConvertThrottlingError(MediaConvertError):
    """Raised when MediaConvert API is throttled."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class MediaConvertTimeoutError(MediaConvertError):
    """Raised when approaching Lambda timeout."""

    def __init__(self, message: str, remaining_time_ms: int):
        super().__init__(message)
        self.remaining_time_ms = remaining_time_ms


# ============================================================================
# Cache Management Functions
# ============================================================================


def get_cached_endpoint(region: str) -> Optional[str]:
    """
    Retrieve cached MediaConvert endpoint from module-level cache.

    Args:
        region: AWS region

    Returns:
        Cached endpoint URL or None if not found
    """
    endpoint = _mediaconvert_endpoint_cache.get(region)
    if endpoint:
        logger.debug(f"Cache hit for region {region}: {endpoint}")
    else:
        logger.debug(f"Cache miss for region {region}")
    return endpoint


def cache_endpoint(region: str, endpoint: str) -> None:
    """
    Cache MediaConvert endpoint in module-level memory.

    Args:
        region: AWS region
        endpoint: MediaConvert endpoint URL
    """
    _mediaconvert_endpoint_cache[region] = endpoint
    logger.info(f"Cached endpoint for region {region}: {endpoint}")


def get_cached_client(region: str) -> Optional[Any]:
    """
    Retrieve cached MediaConvert client from module-level cache.

    Args:
        region: AWS region

    Returns:
        Cached boto3 client or None if not found
    """
    return _mediaconvert_client_cache.get(region)


def cache_client(region: str, client: Any) -> None:
    """
    Cache MediaConvert client in module-level memory.

    Args:
        region: AWS region
        client: boto3 MediaConvert client
    """
    _mediaconvert_client_cache[region] = client
    logger.debug(f"Cached client for region {region}")


# ============================================================================
# Endpoint Retrieval with Retry Logic
# ============================================================================


def describe_endpoints_with_retry(
    region: str,
    max_retries: int = 5,
    timeout_buffer_seconds: int = 30,
    context: Optional[Any] = None,
) -> str:
    """
    Call describe_endpoints with intelligent retry logic.

    Implements exponential backoff with jitter and timeout awareness to handle
    MediaConvert API throttling gracefully.

    Args:
        region: AWS region
        max_retries: Maximum retry attempts (default: 5)
        timeout_buffer_seconds: Time buffer before Lambda timeout (default: 30)
        context: Lambda context for timeout checking (optional)

    Returns:
        MediaConvert endpoint URL

    Raises:
        MediaConvertThrottlingError: If throttled beyond retry limit
        MediaConvertTimeoutError: If approaching Lambda timeout
        MediaConvertEndpointError: If endpoint cannot be retrieved
    """
    base_delay = 1.0  # Base delay in seconds
    max_delay = 60.0  # Maximum delay in seconds
    backoff_rate = 2.0  # Exponential backoff multiplier

    # Create a basic MediaConvert client for describe_endpoints
    mediaconvert_client = boto3.client("mediaconvert", region_name=region)

    for attempt in range(max_retries):
        try:
            # Check timeout before attempting
            if context:
                remaining_time_ms = context.get_remaining_time_in_millis()
                if remaining_time_ms < (timeout_buffer_seconds * 1000):
                    raise MediaConvertTimeoutError(
                        f"Aborting retry due to approaching timeout. "
                        f"Remaining: {remaining_time_ms}ms",
                        remaining_time_ms=remaining_time_ms,
                    )

            logger.info(
                f"Attempting describe_endpoints (attempt {attempt + 1}/{max_retries})"
            )

            # Call describe_endpoints
            response = mediaconvert_client.describe_endpoints()

            if not response.get("Endpoints"):
                raise MediaConvertEndpointError(
                    "No endpoints returned from describe_endpoints"
                )

            endpoint = response["Endpoints"][0]["Url"]
            logger.info(f"Successfully retrieved endpoint: {endpoint}")

            # Emit success metric
            emit_mediaconvert_metrics(
                metric_name="DescribeEndpointsSuccess",
                value=1,
                dimensions={"Region": region},
            )

            return endpoint

        except MediaConvertTimeoutError:
            # Re-raise timeout errors immediately
            raise

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # Check if this is a throttling error
            if error_code in ["ThrottlingException", "TooManyRequestsException"]:
                logger.warning(f"Throttled on attempt {attempt + 1}: {e}")

                # Emit throttling metric
                emit_mediaconvert_metrics(
                    metric_name="DescribeEndpointsThrottled",
                    value=1,
                    dimensions={"Region": region},
                )

                # Check if we have retries left
                if attempt < max_retries - 1:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (backoff_rate**attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                    total_delay = delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f} seconds...")
                    time.sleep(total_delay)
                else:
                    # Out of retries
                    raise MediaConvertThrottlingError(
                        f"Exceeded max retries ({max_retries}) due to throttling",
                        retry_after=None,
                    )
            else:
                # Non-retriable error
                logger.error(f"Non-retriable error: {error_code} - {e}")
                raise MediaConvertEndpointError(f"Failed to describe endpoints: {e}")

        except Exception as e:
            logger.error(f"Unexpected error during describe_endpoints: {e}")
            raise MediaConvertEndpointError(f"Unexpected error: {e}")

    # Should not reach here, but just in case
    raise MediaConvertEndpointError("Failed to retrieve endpoint after all retries")


# ============================================================================
# Main Entry Point
# ============================================================================


def get_mediaconvert_client_with_cache(
    region: str = "us-east-1",
    timeout_buffer_seconds: int = 30,
    context: Optional[Any] = None,
) -> Any:
    """
    Get MediaConvert client with module-level cached endpoint lookup.

    Uses module-level variables to cache endpoint and client across warm Lambda
    invocations, eliminating redundant describe_endpoints calls.

    Args:
        region: AWS region (default: us-east-1)
        timeout_buffer_seconds: Time buffer before Lambda timeout (default: 30)
        context: Lambda context for timeout checking (optional)

    Returns:
        Configured MediaConvert client

    Raises:
        MediaConvertEndpointError: If endpoint cannot be retrieved
        MediaConvertTimeoutError: If approaching Lambda timeout
    """
    # Check for cached client first
    cached_client = get_cached_client(region)
    if cached_client:
        logger.info("Reusing cached MediaConvert client")
        emit_mediaconvert_metrics(
            metric_name="ClientCacheHit", value=1, dimensions={"Region": region}
        )
        return cached_client

    # Check for cached endpoint
    endpoint = get_cached_endpoint(region)

    if endpoint:
        # Cache hit - use cached endpoint
        logger.info(f"Using cached endpoint: {endpoint}")
        emit_mediaconvert_metrics(
            metric_name="EndpointCacheHit", value=1, dimensions={"Region": region}
        )
    else:
        # Cache miss - retrieve endpoint with retry logic
        logger.info("Cache miss - retrieving endpoint")
        emit_mediaconvert_metrics(
            metric_name="EndpointCacheMiss", value=1, dimensions={"Region": region}
        )

        start_time = time.time()
        endpoint = describe_endpoints_with_retry(
            region=region,
            max_retries=5,
            timeout_buffer_seconds=timeout_buffer_seconds,
            context=context,
        )
        latency_ms = (time.time() - start_time) * 1000

        # Emit latency metric
        emit_mediaconvert_metrics(
            metric_name="DescribeEndpointsLatency",
            value=latency_ms,
            unit=MetricUnit.Milliseconds,
            dimensions={"Region": region},
        )

        # Cache the endpoint
        cache_endpoint(region, endpoint)

    # Create client with endpoint
    start_time = time.time()
    client = boto3.client("mediaconvert", region_name=region, endpoint_url=endpoint)
    latency_ms = (time.time() - start_time) * 1000

    # Emit client creation latency
    emit_mediaconvert_metrics(
        metric_name="ClientCreationLatency",
        value=latency_ms,
        unit=MetricUnit.Milliseconds,
        dimensions={"Region": region},
    )

    # Cache the client
    cache_client(region, client)

    logger.info("Successfully created MediaConvert client")
    return client


# ============================================================================
# Metrics and Monitoring
# ============================================================================


def emit_mediaconvert_metrics(
    metric_name: str,
    value: float,
    unit: str = MetricUnit.Count,
    dimensions: Optional[Dict[str, str]] = None,
) -> None:
    """
    Emit CloudWatch metrics for MediaConvert operations.

    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: CloudWatch metric unit (default: Count)
        dimensions: Additional dimensions (optional)
    """
    try:
        # Add default dimensions
        all_dimensions = {"Service": "MediaConvert", **(dimensions or {})}

        # Add function name if available
        function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        if function_name:
            all_dimensions["FunctionName"] = function_name

        # Emit metric using Powertools
        metrics.add_metric(name=metric_name, unit=unit, value=value)

        # Add dimensions
        for key, val in all_dimensions.items():
            metrics.add_dimension(name=key, value=val)

        logger.debug(f"Emitted metric: {metric_name}={value} {unit} {all_dimensions}")

    except Exception as e:
        # Don't fail the operation if metrics fail
        logger.warning(f"Failed to emit metric {metric_name}: {e}")


# ============================================================================
# Error Handling
# ============================================================================


def handle_mediaconvert_error(error: Exception, context: Optional[Any] = None) -> None:
    """
    Classify and handle MediaConvert errors appropriately.

    Args:
        error: The exception that occurred
        context: Lambda context for timeout checking (optional)

    Raises:
        MediaConvertTimeoutError: If approaching timeout
        MediaConvertThrottlingError: If throttling error
        MediaConvertError: For other retriable errors
        Exception: For non-retriable errors (re-raised)
    """
    # Check for timeout
    if context:
        remaining_time_ms = context.get_remaining_time_in_millis()
        if remaining_time_ms < 30000:  # Less than 30 seconds
            raise MediaConvertTimeoutError(
                f"Aborting due to approaching timeout. Remaining: {remaining_time_ms}ms",
                remaining_time_ms=remaining_time_ms,
            )

    # Handle ClientError
    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")

        # Throttling errors - retriable
        if error_code in ["ThrottlingException", "TooManyRequestsException"]:
            retry_after = error.response.get("Error", {}).get("RetryAfter")
            raise MediaConvertThrottlingError(
                f"MediaConvert throttled: {error}", retry_after=retry_after
            )

        # Service errors - retriable
        elif error_code in ["ServiceUnavailable", "InternalServerError"]:
            raise MediaConvertError(f"MediaConvert service error: {error}")

        # Permission/validation errors - non-retriable
        elif error_code in [
            "AccessDeniedException",
            "InvalidParameterException",
            "ValidationException",
        ]:
            logger.error(f"Non-retriable MediaConvert error: {error_code} - {error}")
            raise error  # Re-raise original exception

        # Unknown error - treat as retriable
        else:
            logger.warning(
                f"Unknown MediaConvert error, treating as retriable: {error_code} - {error}"
            )
            raise MediaConvertError(f"MediaConvert error: {error}")

    # Other exceptions - re-raise
    else:
        logger.error(f"Non-MediaConvert error: {error}")
        raise
