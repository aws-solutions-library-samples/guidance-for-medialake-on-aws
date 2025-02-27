import os
import json
import time
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar, Union
from typing_extensions import ParamSpec

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Type variables for better type hinting
P = ParamSpec("P")
R = TypeVar("R")


class LambdaMiddleware:
    """
    Middleware for AWS Lambda functions that provides:
    - Event bus integration for progress/status updates
    - CloudWatch metrics for monitoring
    - Payload size management with S3 fallback
    - Standardized error handling
    - Input/output payload standardization
    """

    def __init__(
        self,
        event_bus_name: str,
        metrics_namespace: str = "MediaLake",
        max_event_size: int = 256000,  # EventBridge max size is 256KB
        cleanup_s3: bool = True,
        large_payload_bucket: Optional[str] = None,
        max_retries: int = 3,
        standardize_payloads: bool = True,
    ):
        """
        Initialize the middleware.

        Args:
            event_bus_name: Name of the EventBridge event bus
            metrics_namespace: Namespace for CloudWatch metrics
            max_event_size: Maximum size for EventBridge events in bytes
            cleanup_s3: Whether to cleanup S3 objects used for large payloads
            large_payload_bucket: S3 bucket for storing large payloads
            max_retries: Maximum number of retries for recoverable errors
        """
        self.event_bus = boto3.client("events")
        self.event_bus_name = event_bus_name
        self.max_event_size = max_event_size
        self.cleanup_s3 = cleanup_s3
        self.max_retries = max_retries

        # Initialize AWS clients
        self.s3 = boto3.client("s3")

        # Set up large payload handling
        self.large_payload_bucket = large_payload_bucket or os.environ.get(
            "LARGE_PAYLOAD_BUCKET"
        )
        if not self.large_payload_bucket:
            raise ValueError(
                "large_payload_bucket must be provided or LARGE_PAYLOAD_BUCKET environment variable must be set"
            )

        # Initialize Powertools utilities
        self.service_name = os.getenv("SERVICE_NAME", "undefined_service")
        self.logger = Logger(service=self.service_name)
        self.metrics = Metrics(namespace=metrics_namespace, service=self.service_name)
        self.tracer = Tracer(service=self.service_name)

        # Track temporary S3 objects for cleanup
        self.temp_s3_objects = []
        self.standardize_payloads = standardize_payloads

        # Initialize retry tracking
        self.retry_count = 0
        self.retry_errors = set()

    def should_retry(self, error: Exception) -> bool:
        """
        Determine if an error should trigger a retry.

        Args:
            error: The exception that occurred

        Returns:
            Boolean indicating if retry should be attempted
        """
        # List of error types that should trigger retries
        RETRYABLE_ERRORS = (
            "RequestTimeout",
            "InternalServerError",
            "ServiceUnavailable",
            "ConnectionError",
            "ThrottlingException",
            "TooManyRequestsException",
            "ProvisionedThroughputExceededException",
        )

        error_type = error.__class__.__name__

        # Track unique error types for metrics
        self.retry_errors.add(error_type)

        return self.retry_count < self.max_retries and any(
            err in error_type for err in RETRYABLE_ERRORS
        )

    def emit_progress(
        self,
        context: LambdaContext,
        progress: float,
        status: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a progress update event.

        Args:
            context: Lambda context
            progress: Progress percentage (0-100)
            status: Current status message
            detail: Additional details to include
        """
        progress_details = {
            "function_name": context.function_name,
            "request_id": context.aws_request_id,
            "progress": progress,
            "status": status,
            "timestamp": int(time.time()),
        }

        if detail:
            progress_details.update(detail)

        self.emit_event(
            detail_type="FunctionExecutionProgress",
            detail=progress_details,
            resources=[context.invoked_function_arn],
        )

    def standardize_input(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize the input event format.

        Args:
            event: Raw Lambda event

        Returns:
            Standardized event
        """
        if not self.standardize_payloads:
            return event

        # Check if payload is in S3
        if "s3_bucket" in event and "s3_key" in event:
            try:
                response = self.s3.get_object(
                    Bucket=event["s3_bucket"], Key=event["s3_key"]
                )
                event = json.loads(response["Body"].read().decode("utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to fetch payload from S3: {str(e)}")
                raise

        # Add standard metadata if not present
        if "metadata" not in event:
            event["metadata"] = {}

        event["metadata"].update(
            {
                "timestamp": int(time.time()),
                "service": self.service_name,
            }
        )

        return event

    def standardize_output(self, result: Any) -> Dict[str, Any]:
        """
        Standardize the output format.

        Args:
            result: Handler result

        Returns:
            Standardized result
        """
        if not self.standardize_payloads:
            return result

        if not isinstance(result, dict):
            result = {"data": result}

        # Add standard metadata
        if "metadata" not in result:
            result["metadata"] = {}

        result["metadata"].update(
            {
                "timestamp": int(time.time()),
                "service": self.service_name,
            }
        )

        return result

    def emit_event(
        self, detail_type: str, detail: Dict[str, Any], resources: Optional[list] = None
    ) -> None:
        """
        Emit an event to EventBridge, handling large payloads via S3 if needed.

        Args:
            detail_type: Type of the event
            detail: Event details
            resources: List of AWS resources involved
        """
        try:
            event = {
                "Source": self.service_name,
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": self.event_bus_name,
                "Resources": resources or [],
            }

            # Check if payload is too large
            event_size = len(json.dumps(event).encode("utf-8"))
            if event_size > self.max_event_size:
                self.logger.info(
                    f"Event size {event_size} exceeds limit {self.max_event_size}, using S3"
                )

                # Store detail in S3
                key = f"events/{int(time.time())}-{detail_type}.json"
                self.s3.put_object(
                    Bucket=self.large_payload_bucket, Key=key, Body=json.dumps(detail)
                )
                self.temp_s3_objects.append(key)

                # Update event with S3 reference
                event["Detail"] = json.dumps(
                    {
                        "s3_bucket": self.large_payload_bucket,
                        "s3_key": key,
                        "original_size": event_size,
                    }
                )

            self.event_bus.put_events(Entries=[event])

        except Exception as e:
            self.logger.error(f"Failed to emit event: {str(e)}")
            self.metrics.add_metric(name="FailedEvents", unit=MetricUnit.Count, value=1)

    def cleanup_temp_s3_objects(self) -> None:
        """Clean up any temporary S3 objects created for large payloads."""
        if not self.cleanup_s3 or not self.temp_s3_objects:
            return

        try:
            self.s3.delete_objects(
                Bucket=self.large_payload_bucket,
                Delete={"Objects": [{"Key": key} for key in self.temp_s3_objects]},
            )
            self.temp_s3_objects = []
        except Exception as e:
            self.logger.error(f"Failed to cleanup S3 objects: {str(e)}")

    def handle_failure(self, error: Exception, context: LambdaContext) -> None:
        """
        Handle function execution failures.

        Args:
            error: The exception that occurred
            context: Lambda context
        """
        error_type = error.__class__.__name__
        error_details = {
            "error_type": error_type,
            "error_message": str(error),
            "function_name": context.function_name,
            "request_id": context.aws_request_id,
            "function_version": context.function_version,
        }

        # Log error
        self.logger.exception("Function execution failed")

        # Emit failure event
        self.emit_event(
            detail_type="FunctionExecutionFailure",
            detail=error_details,
            resources=[context.invoked_function_arn],
        )

        # Record metrics
        self.metrics.add_metric(name="Errors", unit=MetricUnit.Count, value=1)
        self.metrics.add_metric(
            name=f"Errors_{error_type}", unit=MetricUnit.Count, value=1
        )

    def __call__(self, handler: Callable[..., R]) -> Callable[..., R]:
        """
        Decorator that wraps the Lambda handler with middleware functionality.

        Args:
            handler: The Lambda handler function to wrap

        Returns:
            Wrapped handler function
        """

        @wraps(handler)
        def wrapper(
            event: Dict[str, Any],
            context: LambdaContext,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            start_time = time.time()

            try:
                # Emit start event
                self.emit_event(
                    detail_type="FunctionExecutionStart",
                    detail={
                        "function_name": context.function_name,
                        "request_id": context.aws_request_id,
                        "remaining_time": context.get_remaining_time_in_millis(),
                    },
                    resources=[context.invoked_function_arn],
                )

                # Add standard dimensions for metrics
                self.metrics.add_dimension(
                    name="FunctionName", value=context.function_name
                )
                self.metrics.add_dimension(
                    name="Environment", value=os.getenv("ENVIRONMENT", "undefined")
                )

                # Standardize input
                processed_event = self.standardize_input(event)

                # Add progress method to context
                context.emit_progress = (
                    lambda progress, status, detail=None: self.emit_progress(
                        context, progress, status, detail
                    )
                )

                # Initialize retry state
                self.retry_count = 0
                self.retry_errors.clear()

                while True:
                    try:
                        # Execute handler
                        result = handler(processed_event, context, *args, **kwargs)
                        break
                    except Exception as e:
                        if self.should_retry(e):
                            self.retry_count += 1
                            retry_delay = min(
                                2**self.retry_count, 30
                            )  # Exponential backoff capped at 30s

                            self.logger.warning(
                                f"Retrying after error (attempt {self.retry_count}/{self.max_retries})",
                                extra={
                                    "error": str(e),
                                    "error_type": e.__class__.__name__,
                                    "retry_delay": retry_delay,
                                },
                            )

                            # Emit retry event
                            self.emit_event(
                                detail_type="FunctionExecutionRetry",
                                detail={
                                    "function_name": context.function_name,
                                    "request_id": context.aws_request_id,
                                    "error": str(e),
                                    "error_type": e.__class__.__name__,
                                    "retry_count": self.retry_count,
                                    "retry_delay": retry_delay,
                                },
                                resources=[context.invoked_function_arn],
                            )

                            time.sleep(retry_delay)
                            continue
                        raise

                # Record retry metrics if any occurred
                if self.retry_count > 0:
                    self.metrics.add_metric(
                        name="RetryAttempts",
                        unit=MetricUnit.Count,
                        value=self.retry_count,
                    )
                    for error_type in self.retry_errors:
                        self.metrics.add_metric(
                            name=f"RetryErrors_{error_type}",
                            unit=MetricUnit.Count,
                            value=1,
                        )

                # Standardize output
                processed_result = self.standardize_output(result)

                # Calculate execution time
                execution_time = (time.time() - start_time) * 1000

                # Record success metrics
                self.metrics.add_metric(
                    name="Invocations", unit=MetricUnit.Count, value=1
                )
                self.metrics.add_metric(
                    name="ExecutionTime",
                    unit=MetricUnit.Milliseconds,
                    value=execution_time,
                )
                self.metrics.add_metric(
                    name="MemoryUsed",
                    unit=MetricUnit.Megabytes,
                    value=context.memory_limit_in_mb,
                )

                # Add cold start metric
                if not hasattr(LambdaMiddleware, "_cold_start_recorded"):
                    self.metrics.add_metric(
                        name="ColdStart", unit=MetricUnit.Count, value=1
                    )
                    LambdaMiddleware._cold_start_recorded = True

                # Emit completion event
                self.emit_event(
                    detail_type="FunctionExecutionComplete",
                    detail={
                        "function_name": context.function_name,
                        "request_id": context.aws_request_id,
                        "execution_time_ms": execution_time,
                        "memory_used": context.memory_limit_in_mb,
                    },
                    resources=[context.invoked_function_arn],
                )

                return processed_result

            except Exception as e:
                self.handle_failure(e, context)
                raise

            finally:
                # Cleanup any temporary S3 objects
                self.cleanup_temp_s3_objects()

        return wrapper


def lambda_middleware(
    event_bus_name: str,
    metrics_namespace: str = "MediaLake",
    max_event_size: int = 256000,
    cleanup_s3: bool = True,
    large_payload_bucket: Optional[str] = None,
    max_retries: int = 3,
    standardize_payloads: bool = True,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator factory for creating Lambda middleware instances.

    Args:
        event_bus_name: Name of the EventBridge event bus
        metrics_namespace: Namespace for CloudWatch metrics
        max_event_size: Maximum size for EventBridge events in bytes
        cleanup_s3: Whether to cleanup S3 objects used for large payloads
        large_payload_bucket: S3 bucket for storing large payloads
        max_retries: Maximum number of retries for recoverable errors

    Returns:
        Decorator function that wraps Lambda handlers with middleware functionality

    Example:
        @lambda_middleware(
            event_bus_name="MediaProcessingEvents",
            metrics_namespace="MediaLake",
            max_retries=3
        )
        def process_media(event, context):
            # Handler implementation
            pass
    """
    middleware = LambdaMiddleware(
        event_bus_name=event_bus_name,
        metrics_namespace=metrics_namespace,
        max_event_size=max_event_size,
        cleanup_s3=cleanup_s3,
        large_payload_bucket=large_payload_bucket,
        max_retries=max_retries,
        standardize_payloads=standardize_payloads,
    )
    return middleware
