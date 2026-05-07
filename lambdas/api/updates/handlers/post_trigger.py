"""
Handler for POST /updates/trigger endpoint.
Triggers immediate upgrade to selected version.
"""

import logging
import uuid
from typing import Any, Dict

from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
)
from models.requests import TriggerUpgradeRequest
from models.responses import TriggerUpgradeResponseData
from pydantic import ValidationError
from services.dynamodb_service import DynamoDBService
from services.pipeline_service import PipelineService
from utils.response import create_success_response

logger = logging.getLogger(__name__)


def handle_post_trigger(
    request_body: Dict[str, Any], user_email: str
) -> Dict[str, Any]:
    """
    Handle POST /updates/trigger request.

    Args:
        request_body: Request body data
        user_email: Email of the requesting user

    Returns:
        Standardized API response with trigger result

    Raises:
        BadRequestError: If request validation fails or upgrade conflict detected
        InternalServerError: If upgrade triggering fails
    """
    try:
        # Validate request using Pydantic v2
        try:
            request = TriggerUpgradeRequest.model_validate(request_body)
        except ValidationError as e:
            logger.warning(f"Request validation failed: {e}")
            raise BadRequestError(f"Invalid request: {e}")

        # Check if confirmation was provided
        if not request.confirm_upgrade:
            raise BadRequestError(
                "Upgrade confirmation is required. Set 'confirm_upgrade' to true."
            )

        logger.info(
            f"Triggering upgrade to {request.target_version} ({request.version_type}) for user: {user_email}"
        )

        # Initialize services
        dynamodb_service = DynamoDBService()
        pipeline_service = PipelineService()

        # Check for active upgrades (conflict detection)
        active_upgrade = dynamodb_service.get_active_upgrade()
        if active_upgrade:
            logger.warning(
                f"Upgrade conflict detected. Active upgrade: {active_upgrade.get('upgrade_id')}"
            )
            raise BadRequestError(
                f"An upgrade is already in progress to version {active_upgrade.get('to_version')}. "
                f"Please wait for it to complete before starting a new upgrade."
            )

        # Get current version for logging
        current_version_info = dynamodb_service.get_current_version()
        current_version = (
            current_version_info.get("version", "unknown")
            if current_version_info
            else "unknown"
        )

        logger.info(
            f"Current version: {current_version}, Target version: {request.target_version}"
        )

        # Check if trying to upgrade to the same version
        if current_version == request.target_version:
            logger.warning(
                f"Attempted to upgrade to current version: {current_version}"
            )
            raise BadRequestError(
                f"System is already running version {current_version}. "
                "Please select a different version to upgrade."
            )

        # Generate unique upgrade ID
        upgrade_id = f"upgrade-{uuid.uuid4().hex[:12]}"

        # Trigger the pipeline
        try:
            pipeline_result = pipeline_service.trigger_upgrade(
                target_version=request.target_version,
                version_type=request.version_type,
                user_email=user_email,
            )
        except Exception as e:
            logger.error(f"Failed to trigger pipeline: {e}")
            raise InternalServerError(f"Failed to trigger upgrade pipeline: {str(e)}")

        # Create upgrade record in DynamoDB
        try:
            upgrade_record = dynamodb_service.create_upgrade_record(
                upgrade_id=upgrade_id,
                target_version=request.target_version,
                version_type=request.version_type,
                pipeline_execution_id=pipeline_result["pipeline_execution_id"],
                user_email=user_email,
            )
        except Exception as e:
            logger.error(f"Failed to create upgrade record: {e}")
            # Pipeline is already triggered, log error but don't fail the request
            logger.warning("Upgrade triggered but failed to create tracking record")

        # Prepare response
        response_data = TriggerUpgradeResponseData(
            message=f"Upgrade to version {request.target_version} initiated successfully",
            upgrade_id=upgrade_id,
            target_version=request.target_version,
            pipeline_execution_id=pipeline_result["pipeline_execution_id"],
            estimated_duration="15-20 minutes",
        )

        logger.info(
            f"Successfully triggered upgrade {upgrade_id} from {current_version} to {request.target_version}. "
            f"Pipeline execution: {pipeline_result['pipeline_execution_id']}"
        )

        return create_success_response(response_data.model_dump())

    except BadRequestError:
        # Re-raise BadRequestError as-is
        raise
    except InternalServerError:
        # Re-raise InternalServerError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error triggering upgrade: {str(e)}", exc_info=True)
        raise InternalServerError(f"Failed to trigger upgrade: {str(e)}")
