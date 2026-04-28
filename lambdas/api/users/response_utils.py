"""Shared response utilities for user service handlers."""

import json
from typing import Any, Dict, Optional


def success_response(
    status_code: int, message: str, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        status_code: HTTP status code
        message: Success message
        data: Optional response data payload

    Returns:
        API Gateway proxy response dict
    """
    body: Dict[str, Any] = {"status": str(status_code), "message": message}
    if data is not None:
        body["data"] = data

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        status_code: HTTP status code
        message: Error message (should be safe for client consumption)

    Returns:
        API Gateway proxy response dict
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {"status": str(status_code), "message": message, "data": {}},
            default=str,
        ),
    }
