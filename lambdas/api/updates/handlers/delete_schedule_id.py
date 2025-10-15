"""
Handler for DELETE /updates/schedule/{scheduleId} endpoint.
Cancels a scheduled upgrade.
"""

import logging
from typing import Any, Dict

from aws_lambda_powertools.event_handler.exceptions import InternalServerError
from models.responses import CancelScheduleResponseData
from utils.response import create_success_response

logger = logging.getLogger(__name__)


def handle_delete_schedule_id(schedule_id: str, user_email: str) -> Dict[str, Any]:
    """
    Handle DELETE /updates/schedule/{scheduleId} request.

    Args:
        schedule_id: ID of the schedule to cancel
        user_email: Email of the requesting user

    Returns:
        Standardized API response with cancellation result

    Raises:
        NotFoundError: If schedule is not found
        InternalServerError: If cancellation fails
    """
    try:
        logger.info(
            f"Cancelling scheduled upgrade {schedule_id} for user: {user_email}"
        )

        # TODO: Implement actual schedule cancellation logic
        # This is a placeholder implementation

        # For now, just return a placeholder response
        response_data = CancelScheduleResponseData(
            message="Scheduled upgrade cancelled successfully",
            schedule_id=schedule_id,
            target_version="placeholder-version",
            original_scheduled_time="2024-01-20T02:00:00Z",
            cancelled_at="2024-01-15T14:30:00Z",
        )

        logger.info(
            f"Successfully cancelled scheduled upgrade {schedule_id} for user: {user_email}"
        )

        return create_success_response(response_data.model_dump())

    except Exception as e:
        logger.error(f"Failed to cancel scheduled upgrade {schedule_id}: {str(e)}")
        raise InternalServerError(f"Failed to cancel scheduled upgrade: {str(e)}")
