"""
CORS utility functions for Lambda responses.

Provides standardized CORS headers that match the working Collections and Pipelines APIs.
Includes all required AWS headers for Cognito temporary credentials and AWS Signature V4.
"""

import json
from typing import Any, Dict, Optional


def get_cors_headers() -> Dict[str, str]:
    """
    Returns standard CORS headers for all Lambda responses.

    Includes all headers required by:
    - AWS Signature V4 (X-Amz-Date, X-Amz-Security-Token)
    - Cognito temporary credentials (X-Amz-Security-Token)
    - Custom security headers (X-Origin-Verify)

    Returns:
        Dictionary of CORS headers
    """
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Origin-Verify",
        "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD",
    }


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create standardized API Gateway response with CORS headers.

    Args:
        status_code: HTTP status code (e.g., 200, 400, 500)
        body: Response body as a dictionary (will be JSON serialized)

    Returns:
        API Gateway Lambda proxy integration response with CORS headers
    """
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps(body, default=str),
    }


def create_error_response(
    status_code: int, error_message: str, error_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create standardized error response with CORS headers.

    Args:
        status_code: HTTP error status code (e.g., 400, 404, 500)
        error_message: Human-readable error message
        error_code: Optional machine-readable error code

    Returns:
        API Gateway error response with CORS headers
    """
    error_body = {"success": False, "error": {"message": error_message}}

    if error_code:
        error_body["error"]["code"] = error_code

    return create_response(status_code, error_body)
