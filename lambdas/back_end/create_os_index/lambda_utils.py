import os
import time
from functools import wraps
from typing import Any, Callable, Dict, TypeVar, Union, cast

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate
from typing_extensions import Concatenate, ParamSpec

# Type variables for better type hinting
P = ParamSpec("P")
R = TypeVar("R")

# Initialize core utilities with service name from environment variable
service_name = os.getenv("SERVICE_NAME", "undefined_service")
namespace = os.getenv("RESOURCE_PREFIX", "undefined_namespace")

# Validate and set log level
valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
if log_level not in valid_log_levels:
    log_level = "WARNING"

logger = Logger(service=service_name, level=log_level)
tracer = Tracer(service=service_name)
metrics = Metrics(namespace="RESOURCE_PREFIX", service=service_name)


def handle_error(error: Exception) -> Dict[str, Any]:
    """
    Standardized error handling for Lambda functions

    Args:
        error: The exception that was raised

    Returns:
        Dict containing standardized error response
    """
    error_type = error.__class__.__name__
    logger.exception(f"Error occurred: {error_type}")

    return {
        "statusCode": 500,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "error": error_type,
            "message": str(error),
            "correlationId": logger.get_correlation_id(),
            "requestId": logger.__dict__.get("lambda_context", {}).get(
                "aws_request_id", "unknown"
            ),
        },
    }


def validate_input(schema: Dict[str, Any]) -> Callable:
    """
    Decorator to validate input against JSON schema using Powertools v3 validate_request

    Args:
        schema: JSON schema to validate against

    Returns:
        Decorator function
    """

    def decorator(
        func: Callable[Concatenate[Dict[str, Any], LambdaContext, P], R],
    ) -> Callable[Concatenate[Dict[str, Any], LambdaContext, P], R]:
        @wraps(func)
        def wrapper(
            event: Dict[str, Any],
            context: LambdaContext,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            try:
                validate(event=event, schema=schema)
                return func(event, context, *args, **kwargs)
            except Exception as e:
                return cast(R, handle_error(e))

        return wrapper

    return decorator


def _truncate_floats(obj, max_items=15):
    """
    Recursively walk obj (which can be a dict, list, or primitive),
    and whenever you see a list of floats longer than max_items,
    replace it with the first max_items floats plus an indicator.
    """
    if isinstance(obj, dict):
        return {k: _truncate_floats(v, max_items) for k, v in obj.items()}
    if isinstance(obj, list):
        # if this is a flat list of floats, truncate it
        if obj and all(isinstance(x, float) for x in obj):
            if len(obj) > max_items:
                return obj[:max_items] + [f"... (+{len(obj)-max_items} more)"]
            return obj
        # otherwise recurse into each element
        return [_truncate_floats(x, max_items) for x in obj]
    return obj  # primitives unchanged


def lambda_handler_decorator(cors: bool = True) -> Callable:
    """
    Common decorator for Lambda handlers with tracing, metrics, and logging

    Args:
        cors: Whether to add CORS headers to response

    Returns:
        Decorator function
    """

    def decorator(
        func: Callable[Concatenate[Dict[str, Any], LambdaContext, P], R],
    ) -> Callable[Concatenate[Dict[str, Any], LambdaContext, P], R]:
        @wraps(func)
        @tracer.capture_lambda_handler
        @logger.inject_lambda_context(
            correlation_id_path=correlation_paths.API_GATEWAY_REST
        )
        @metrics.log_metrics(capture_cold_start_metric=True)
        def wrapper(
            event: Dict[str, Any],
            context: LambdaContext,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            start_time = time.time()

            try:
                # Add standard dimensions for metrics
                metrics.add_dimension(
                    name="Environment", value=os.getenv("ENVIRONMENT", "undefined")
                )
                metrics.add_dimension(name="FunctionName", value=context.function_name)

                # Log standard request information
                logger.append_keys(request_id=context.aws_request_id)
                logger.info(
                    "Lambda invocation started",
                    extra={
                        "function_name": context.function_name,
                        "function_memory": context.memory_limit_in_mb,
                        "function_arn": context.invoked_function_arn,
                        "function_request_id": context.aws_request_id,
                    },
                )

                # Execute handler
                response = func(event, context, *args, **kwargs)

                # Record execution time metric
                execution_time = (time.time() - start_time) * 1000
                metrics.add_metric(
                    name="ExecutionTime",
                    unit=MetricUnit.Milliseconds,
                    value=execution_time,
                )

                # Add CORS headers if enabled
                if cors and isinstance(response, dict):
                    if "headers" not in response:
                        response["headers"] = {}

                    response["headers"].update(
                        {
                            "Access-Control-Allow-Origin": os.getenv(
                                "CORS_ALLOW_ORIGIN", "*"
                            ),
                            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
                            "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE",
                        }
                    )

                return response

            except Exception as error:
                metrics.add_metric(name="Errors", unit=MetricUnit.Count, value=1)
                return cast(R, handle_error(error))

            finally:
                # Log standard completion information
                logger.info(
                    "Lambda invocation completed",
                    extra={"execution_time_ms": (time.time() - start_time) * 1000},
                )

        return wrapper

    return decorator


def parse_api_event(event: Dict[str, Any]) -> APIGatewayProxyEvent:
    """
    Safely parse API Gateway event into strongly typed class

    Args:
        event: Raw API Gateway event

    Returns:
        Parsed APIGatewayProxyEvent
    """
    return APIGatewayProxyEvent(event)


def add_business_metric(
    name: str,
    unit: MetricUnit,
    value: Union[float, int],
    dimensions: Dict[str, str] = None,
) -> None:
    """
    Add business metric with standard dimensions

    Args:
        name: Metric name
        unit: Metric unit
        value: Metric value
        dimensions: Additional dimensions to add
    """
    metrics.add_metric(name=name, unit=unit, value=value)
    metrics.add_dimension(
        name="Environment", value=os.getenv("ENVIRONMENT", "undefined")
    )

    if dimensions:
        for dim_name, dim_value in dimensions.items():
            metrics.add_dimension(name=dim_name, value=dim_value)
