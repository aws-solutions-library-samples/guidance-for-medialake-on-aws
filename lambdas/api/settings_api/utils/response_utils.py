"""Response utilities for collections API following 2025 API Design Standards."""

import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

logger = Logger(service="response-utils")


def now_iso() -> str:
    """Return current timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_request_id() -> str:
    """Generate unique request ID."""
    return f"req_{uuid4().hex[:12]}"


def create_meta(request_id: Optional[str] = None) -> Dict[str, str]:
    """
    Create standard meta object.

    Args:
        request_id: Optional request ID (generated if not provided)

    Returns:
        Meta dictionary with timestamp, version, request_id
    """
    return {
        "timestamp": now_iso(),
        "version": "v1",
        "request_id": request_id or generate_request_id(),
    }


def create_success_response(
    data: Any,
    pagination: Optional[Dict] = None,
    status_code: int = 200,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized success response.

    AWS Lambda Powertools' APIGatewayRestResolver expects handlers to return
    just the response body (not wrapped in statusCode/body). The resolver
    handles the Lambda proxy response format automatically.

    Args:
        data: Response data
        pagination: Optional pagination object
        status_code: HTTP status code (used by Powertools)
        request_id: Optional request ID

    Returns:
        Response dictionary (body only, Powertools handles wrapping)
    """
    response = {"success": True, "data": data, "meta": create_meta(request_id)}

    if pagination:
        response["pagination"] = pagination

    return response


def create_error_response(
    code: str,
    message: str,
    details: Optional[List[Dict]] = None,
    status_code: int = 500,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized error response.

    AWS Lambda Powertools' APIGatewayRestResolver expects handlers to return
    just the response body (not wrapped in statusCode/body). The resolver
    handles the Lambda proxy response format automatically.

    Args:
        code: Error code (e.g., 'VALIDATION_ERROR')
        message: Error message
        details: Optional list of error details (field-level errors)
        status_code: HTTP status code (used by Powertools)
        request_id: Optional request ID

    Returns:
        Error response dictionary (body only, Powertools handles wrapping)
    """
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details or []},
        "meta": create_meta(request_id),
    }


def encode_cursor(payload: Dict[str, Any]) -> str:
    """
    Encode cursor payload to base64.

    Args:
        payload: Cursor data to encode

    Returns:
        Base64 encoded cursor string
    """
    try:
        json_str = json.dumps(payload, separators=(",", ":"))
        return base64.urlsafe_b64encode(json_str.encode()).decode()
    except Exception as e:
        logger.error(f"Error encoding cursor: {e}")
        return ""


def decode_cursor(cursor: str) -> Optional[Dict[str, Any]]:
    """
    Decode base64 cursor to payload.

    Args:
        cursor: Base64 encoded cursor string

    Returns:
        Decoded cursor data or None if invalid

    Raises:
        BadRequestError: If cursor is invalid
    """
    if not cursor:
        return None

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(decoded)
    except Exception as e:
        logger.error(f"Invalid cursor: {cursor}", extra={"error": str(e)})
        raise BadRequestError("Invalid or expired cursor")


def create_pagination_response(
    has_next: bool,
    has_prev: bool,
    limit: int,
    next_cursor: Optional[str] = None,
    prev_cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized pagination response object.

    Args:
        has_next: Whether there is a next page
        has_prev: Whether there is a previous page
        limit: Page size limit
        next_cursor: Next page cursor
        prev_cursor: Previous page cursor

    Returns:
        Pagination response dictionary
    """
    pagination = {"has_next_page": has_next, "has_prev_page": has_prev, "limit": limit}

    if next_cursor:
        pagination["next_cursor"] = next_cursor
    if prev_cursor:
        pagination["prev_cursor"] = prev_cursor

    return pagination
