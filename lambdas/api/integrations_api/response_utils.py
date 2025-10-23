"""
Response utilities for integrations API.

Standard response formatting functions.
"""

from datetime import datetime
from typing import Any, Dict, Optional


def create_success_response(
    data: Any,
    message: str = "Operation completed successfully",
    status_code: int = 200,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Note: Lambda Powertools APIGatewayRestResolver automatically wraps
    the response with statusCode, so we only return the body content.

    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code (currently unused, kept for API compatibility)
        request_id: Optional request ID for tracking

    Returns:
        Standardized success response dictionary (body only)
    """
    response = {
        "success": True,
        "status": "success",
        "message": message,
        "data": data,
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "v1",
        },
    }

    if request_id:
        response["meta"]["request_id"] = request_id

    return response


def create_error_response(
    error_code: str,
    error_message: str,
    status_code: int = 500,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Note: Lambda Powertools APIGatewayRestResolver automatically wraps
    the response with statusCode, so we only return the body content.

    Args:
        error_code: Error code identifier
        error_message: Human-readable error message
        status_code: HTTP status code (currently unused, kept for API compatibility)
        request_id: Optional request ID for tracking
        details: Optional additional error details

    Returns:
        Standardized error response dictionary (body only)
    """
    response = {
        "success": False,
        "status": "error",
        "message": error_message,
        "error": {"code": error_code, "message": error_message},
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "v1",
        },
    }

    if details:
        response["error"]["details"] = details

    if request_id:
        response["meta"]["request_id"] = request_id

    return response
