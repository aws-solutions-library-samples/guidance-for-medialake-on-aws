"""
Response utilities for standardized API responses.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
)
from models.responses import ApiError, PaginationInfo, ResponseMeta, StandardApiResponse

logger = logging.getLogger(__name__)


def create_success_response(
    data: Any,
    pagination: Optional[PaginationInfo] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: Response data
        pagination: Pagination information
        request_id: Request ID for tracking

    Returns:
        Standardized API response dictionary
    """
    logger.info("    → create_success_response: Creating response...")
    logger.debug(f"    → Data type: {type(data)}")
    logger.debug(
        f"    → Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
    )

    try:
        response = StandardApiResponse(
            success=True,
            data=data,
            pagination=pagination,
            meta=ResponseMeta(
                timestamp=datetime.now(timezone.utc).isoformat(),
                version="v1",
                request_id=request_id or str(uuid.uuid4()),
            ),
        )
        logger.info("    → ✓ StandardApiResponse created")
    except Exception as e:
        logger.error(f"    → ✗ Failed to create StandardApiResponse: {str(e)}")
        logger.exception("    → Full exception:")
        raise

    try:
        body_json = response.model_dump_json()
        logger.info(f"    → ✓ Response serialized to JSON ({len(body_json)} bytes)")
    except Exception as e:
        logger.error(f"    → ✗ Failed to serialize response to JSON: {str(e)}")
        logger.exception("    → Full exception:")
        raise

    result = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": body_json,
    }

    logger.info("    → ✓ create_success_response completed")
    return result


def create_error_response(
    error_code: str,
    error_message: str,
    status_code: int = 400,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        error_code: Error code
        error_message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details
        request_id: Request ID for tracking

    Returns:
        Standardized API error response dictionary
    """
    logger.warning(f"    → create_error_response: {error_code} - {error_message}")
    logger.debug(f"    → Status code: {status_code}, Details: {details}")

    response = StandardApiResponse(
        success=False,
        error=ApiError(code=error_code, message=error_message, details=details),
        meta=ResponseMeta(
            timestamp=datetime.now(timezone.utc).isoformat(),
            version="v1",
            request_id=request_id or str(uuid.uuid4()),
        ),
    )

    result = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": response.model_dump_json(),
    }

    logger.info(f"    → ✓ Error response created with status {status_code}")
    return result


def handle_exception(e: Exception, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Handle exceptions and convert them to standardized error responses.

    Args:
        e: Exception to handle
        request_id: Request ID for tracking

    Returns:
        Standardized API error response dictionary
    """
    if isinstance(e, BadRequestError):
        return create_error_response(
            error_code="BAD_REQUEST",
            error_message=str(e),
            status_code=400,
            request_id=request_id,
        )
    elif isinstance(e, NotFoundError):
        return create_error_response(
            error_code="NOT_FOUND",
            error_message=str(e),
            status_code=404,
            request_id=request_id,
        )
    elif isinstance(e, InternalServerError):
        return create_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            error_message=str(e),
            status_code=500,
            request_id=request_id,
        )
    else:
        return create_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            error_message="An unexpected error occurred",
            status_code=500,
            request_id=request_id,
        )
