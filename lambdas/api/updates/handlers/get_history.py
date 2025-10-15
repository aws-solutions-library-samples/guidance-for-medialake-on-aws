"""
Handler for GET /updates/history endpoint.
Gets upgrade history with pagination.
"""

import base64
import json
import logging
from typing import Any, Dict, List, Optional

from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
)
from models.requests import GetHistoryRequest
from models.responses import PaginationInfo, UpgradeRecord
from pydantic import ValidationError
from services.dynamodb_service import DynamoDBService
from utils.response import create_success_response

logger = logging.getLogger(__name__)


def encode_cursor(last_evaluated_key: Optional[Dict[str, Any]]) -> Optional[str]:
    """Encode DynamoDB LastEvaluatedKey as base64 cursor."""
    if not last_evaluated_key:
        return None
    try:
        json_str = json.dumps(last_evaluated_key)
        return base64.b64encode(json_str.encode()).decode()
    except Exception as e:
        logger.warning(f"Failed to encode cursor: {e}")
        return None


def decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode base64 cursor to DynamoDB LastEvaluatedKey."""
    if not cursor:
        return None
    try:
        json_str = base64.b64decode(cursor.encode()).decode()
        return json.loads(json_str)
    except Exception as e:
        logger.warning(f"Failed to decode cursor: {e}")
        return None


def handle_get_history(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /updates/history request.

    Args:
        query_params: Query string parameters

    Returns:
        Standardized API response with upgrade history

    Raises:
        BadRequestError: If request validation fails
        InternalServerError: If history retrieval fails
    """
    try:
        # Validate query parameters using Pydantic v2
        try:
            request = GetHistoryRequest.model_validate(query_params)
        except ValidationError as e:
            logger.warning(f"Request validation failed: {e}")
            raise BadRequestError(f"Invalid request: {e}")

        logger.info(
            f"Fetching upgrade history with limit: {request.limit}, cursor: {request.cursor}"
        )

        # Initialize DynamoDB service
        dynamodb_service = DynamoDBService()

        # Decode cursor if provided
        last_evaluated_key = decode_cursor(request.cursor)

        # Get history from DynamoDB
        history_result = dynamodb_service.get_upgrade_history(
            limit=request.limit, last_evaluated_key=last_evaluated_key
        )

        # Transform to response format
        upgrade_history: List[UpgradeRecord] = []
        for item in history_result["items"]:
            try:
                upgrade_record = UpgradeRecord(
                    upgrade_id=item.get("upgrade_id", ""),
                    from_version=item.get("from_version", ""),
                    to_version=item.get("to_version", ""),
                    status=item.get("status", "unknown"),
                    start_time=item.get("start_time", ""),
                    end_time=item.get("end_time", ""),
                    duration=item.get("duration", 0),
                    triggered_by=item.get("triggered_by", ""),
                    pipeline_execution_id=item.get("pipeline_execution_id", ""),
                    error_message=item.get("error_message"),
                )
                upgrade_history.append(upgrade_record)
            except Exception as e:
                logger.warning(f"Failed to parse history item: {e}")
                continue

        # Encode next cursor
        next_cursor = encode_cursor(history_result.get("last_evaluated_key"))

        # Create pagination info
        pagination = PaginationInfo(
            next_cursor=next_cursor,
            prev_cursor=None,  # Previous cursor not supported in this implementation
            has_next_page=next_cursor is not None,
            has_prev_page=False,
            limit=request.limit,
        )

        logger.info(
            f"Successfully fetched {len(upgrade_history)} upgrade history records"
        )

        return create_success_response(
            [record.model_dump() for record in upgrade_history], pagination=pagination
        )

    except BadRequestError:
        # Re-raise BadRequestError as-is
        raise
    except Exception as e:
        logger.error(f"Failed to fetch upgrade history: {str(e)}", exc_info=True)
        raise InternalServerError(f"Failed to fetch upgrade history: {str(e)}")
