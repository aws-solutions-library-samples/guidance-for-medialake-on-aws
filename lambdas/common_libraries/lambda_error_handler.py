"""
Lambda Error Handler

A comprehensive error handling utility for Lambda functions that provides:
1. Response status code checking
2. Custom exception classes for different error types
3. Decorators for wrapping Lambda functions with error handling
4. Integration with aws_lambda_powertools for logging
5. Reusable error handling patterns across Lambda nodes

Usage:
    from lambda_error_handler import (
        check_response_status,
        ResponseError,
        ApiError,
        handle_api_response,
        with_error_handling
    )

    # Check a response status code
    check_response_status(response, "OpenSearch")

    # Use the decorator for a Lambda function
    @with_error_handling
    def lambda_handler(event, context):
        # Your Lambda function code here
        return {"statusCode": 200, "body": "Success"}

    # Handle an API response
    response = requests.get("https://api.example.com")
    result = handle_api_response(response, "Example API")
"""

import functools
import json
import traceback
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Type variables for better type hinting
T = TypeVar("T")
R = TypeVar("R")

# Initialize logger
logger = Logger()

# ─────────────────────────────────────────────────────────────────────────────
# Custom Exception Classes
# ─────────────────────────────────────────────────────────────────────────────


class LambdaError(Exception):
    """Base class for all Lambda errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ResponseError(LambdaError):
    """Error for handling non-successful response status codes"""

    def __init__(
        self,
        message: str,
        status_code: int,
        operation: str,
        response: Dict[str, Any],
        service: str = "Unknown",
    ):
        details = {
            "status_code": status_code,
            "operation": operation,
            "service": service,
            "response": response,
        }
        super().__init__(message, details)
        self.status_code = status_code
        self.operation = operation
        self.service = service
        self.response = response


class ApiError(ResponseError):
    """Error for handling API response errors"""

    def __init__(
        self,
        message: str,
        status_code: int,
        api_name: str,
        endpoint: str,
        response: Dict[str, Any],
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            operation=endpoint,
            response=response,
            service=api_name,
        )
        self.api_name = api_name
        self.endpoint = endpoint


class ValidationError(LambdaError):
    """Error for handling validation failures"""

    def __init__(self, message: str, field: str, value: Any):
        details = {"field": field, "value": value}
        super().__init__(message, details)
        self.field = field
        self.value = value


class ConfigurationError(LambdaError):
    """Error for handling configuration issues"""

    def __init__(self, message: str, missing_configs: List[str]):
        details = {"missing_configs": missing_configs}
        super().__init__(message, details)
        self.missing_configs = missing_configs


# ─────────────────────────────────────────────────────────────────────────────
# Response Status Checking Functions
# ─────────────────────────────────────────────────────────────────────────────


def check_response_status(
    response: Dict[str, Any],
    service: str,
    operation: str = "operation",
    success_codes: List[int] = None,
) -> None:
    """
    Check if a response has a successful status code and raise an exception if not.

    Args:
        response: The response dictionary to check
        service: The name of the service that provided the response
        operation: The operation that was performed
        success_codes: List of status codes considered successful (default: [200, 201])

    Raises:
        ResponseError: If the response status code is not in success_codes
    """
    success_codes = success_codes or [200, 201]
    status = response.get("status", response.get("statusCode", 0))

    if status not in success_codes:
        error_msg = "Unknown error"

        # Try to extract error message from different response formats
        if isinstance(response.get("error"), dict) and response["error"].get("reason"):
            error_msg = response["error"]["reason"]
        elif isinstance(response.get("body"), dict) and response["body"].get("message"):
            error_msg = response["body"]["message"]
        elif isinstance(response.get("message"), str):
            error_msg = response["message"]

        logger.error(
            f"{service} {operation} failed",
            extra={
                "status": status,
                "error": error_msg,
                "service": service,
                "operation": operation,
                "response": response,
            },
        )

        raise ResponseError(
            message=f"{service} {operation} failed: {error_msg} (status: {status})",
            status_code=status,
            operation=operation,
            response=response,
            service=service,
        )


def handle_api_response(
    response: Any, api_name: str, endpoint: str = "", success_codes: List[int] = None
) -> Dict[str, Any]:
    """
    Handle an API response, checking status code and returning the parsed JSON.

    This function works with both requests library responses and dictionary responses.

    Args:
        response: The API response (requests.Response or dict)
        api_name: The name of the API
        endpoint: The API endpoint that was called
        success_codes: List of status codes considered successful (
                                                                       default: [200,
                                                                       201,
                                                                       202,
                                                                       204]
                                                                   )

    Returns:
        The parsed JSON response as a dictionary

    Raises:
        ApiError: If the response status code is not in success_codes
    """
    success_codes = success_codes or [200, 201, 202, 204]

    # Handle requests library Response objects
    if hasattr(response, "json") and callable(response.json):
        status_code = response.status_code
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"text": response.text}
    # Handle dictionary responses
    elif isinstance(response, dict):
        status_code = response.get("statusCode", 0)
        if isinstance(response.get("body"), str):
            try:
                response_data = json.loads(response["body"])
            except ValueError:
                response_data = {"body": response["body"]}
        else:
            response_data = response.get("body", response)
    else:
        raise TypeError(f"Unsupported response type: {type(response)}")

    # Check status code
    if status_code not in success_codes:
        error_msg = "Unknown error"

        # Try to extract error message from different response formats
        if isinstance(response_data, dict):
            error_msg = (
                response_data.get("message")
                or response_data.get("error")
                or response_data.get("errorMessage")
                or error_msg
            )

        logger.error(
            f"{api_name} API call to {endpoint} failed",
            extra={
                "status_code": status_code,
                "api_name": api_name,
                "endpoint": endpoint,
                "response": response_data,
            },
        )

        raise ApiError(
            message=f"{api_name} API call failed: {error_msg}",
            status_code=status_code,
            api_name=api_name,
            endpoint=endpoint,
            response=response_data,
        )

    return response_data


# ─────────────────────────────────────────────────────────────────────────────
# Decorators
# ─────────────────────────────────────────────────────────────────────────────


def with_error_handling(func: Callable[..., R]) -> Callable[..., R]:
    """
    Decorator to add standardized error handling to Lambda functions.

    Args:
        func: The Lambda handler function to wrap

    Returns:
        Wrapped function with error handling
    """

    @functools.wraps(func)
    def wrapper(
        event: Dict[str, Any], context: LambdaContext, *args: Any, **kwargs: Any
    ) -> R:
        try:
            # Log the Lambda invocation
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

            # Execute the handler
            result = func(event, context, *args, **kwargs)

            # Check if the result has a status code and it's not successful
            if (
                isinstance(result, dict)
                and "statusCode" in result
                and result["statusCode"] not in [200, 201, 202, 204]
            ):
                logger.warning(
                    "Lambda returned non-success status code",
                    extra={
                        "status_code": result["statusCode"],
                        "body": result.get("body", {}),
                    },
                )

            return result

        except LambdaError as e:
            # Handle our custom exceptions
            logger.exception(
                f"Lambda error: {e.message}",
                extra={"error_type": e.__class__.__name__, "details": e.details},
            )

            # Determine appropriate status code
            status_code = 500
            if isinstance(e, ResponseError):
                status_code = e.status_code

            return cast(
                R,
                {
                    "statusCode": status_code,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(
                        {
                            "error": e.__class__.__name__,
                            "message": e.message,
                            "details": e.details,
                            "correlationId": logger.get_correlation_id(),
                            "requestId": context.aws_request_id,
                        }
                    ),
                },
            )

        except Exception as e:
            # Handle unexpected exceptions
            error_type = e.__class__.__name__
            logger.exception(
                f"Unhandled error: {error_type}",
                extra={
                    "error_type": error_type,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                },
            )

            return cast(
                R,
                {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(
                        {
                            "error": error_type,
                            "message": str(e),
                            "correlationId": logger.get_correlation_id(),
                            "requestId": context.aws_request_id,
                        }
                    ),
                },
            )

    return wrapper


def validate_response(service: str, operation: str = "operation") -> Callable:
    """
    Decorator to validate the response from a function.

    Args:
        service: The name of the service
        operation: The operation being performed

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            response = func(*args, **kwargs)
            check_response_status(response, service, operation)
            return response

        return wrapper

    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────


def format_error_response(
    error: Exception,
    status_code: int = 500,
    request_id: str = "",
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Format an error into a standardized API response.

    Args:
        error: The exception that occurred
        status_code: HTTP status code to return
        request_id: AWS request ID
        correlation_id: Correlation ID for tracing

    Returns:
        Formatted error response
    """
    error_type = error.__class__.__name__

    # Extract details if it's our custom error
    details = {}
    if isinstance(error, LambdaError):
        details = error.details

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "error": error_type,
                "message": str(error),
                "details": details,
                "requestId": request_id,
                "correlationId": correlation_id or logger.get_correlation_id(),
            }
        ),
    }


def check_required_env_vars(required_vars: List[str]) -> None:
    """
    Check if all required environment variables are set.

    Args:
        required_vars: List of required environment variable names

    Raises:
        ConfigurationError: If any required variables are missing
    """
    import os

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        raise ConfigurationError(
            message=f"Missing required environment variables: {', '.join(missing)}",
            missing_configs=missing,
        )
