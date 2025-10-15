"""
Handler for GET /updates/status endpoint.
Gets current upgrade status and information.
"""

import logging
from typing import Any, Dict, Optional

from aws_lambda_powertools.event_handler.exceptions import InternalServerError
from models.responses import ActiveUpgrade, UpgradeProgress, UpgradeStatusResponseData
from services.dynamodb_service import DynamoDBService
from services.pipeline_service import PipelineService
from utils.response import create_success_response

logger = logging.getLogger(__name__)


def handle_get_status() -> Dict[str, Any]:
    """
    Handle GET /updates/status request.

    Returns:
        Standardized API response with current status

    Raises:
        InternalServerError: If status retrieval fails
    """
    try:
        logger.info("  → handle_get_status: Starting...")

        # Initialize services
        logger.info("  → Initializing DynamoDB service...")
        try:
            dynamodb_service = DynamoDBService()
            logger.info("  → ✓ DynamoDB service initialized")
        except Exception as e:
            logger.error(f"  → ✗ Failed to initialize DynamoDB service: {str(e)}")
            logger.exception("  → Full exception:")
            raise

        logger.info("  → Initializing Pipeline service...")
        try:
            pipeline_service = PipelineService()
            logger.info("  → ✓ Pipeline service initialized")
        except Exception as e:
            logger.error(f"  → ✗ Failed to initialize Pipeline service: {str(e)}")
            logger.exception("  → Full exception:")
            raise

        # Get current version
        logger.info("  → Fetching current version from DynamoDB...")
        try:
            current_version_info = dynamodb_service.get_current_version()
            logger.info(f"  → Current version info: {current_version_info}")
            current_version = (
                current_version_info.get("version", "unknown")
                if current_version_info
                else "unknown"
            )
            logger.info(f"  → ✓ Current version: {current_version}")
        except Exception as e:
            logger.error(f"  → ✗ Failed to get current version: {str(e)}")
            logger.exception("  → Full exception:")
            current_version = "unknown"

        # Check for active upgrade
        logger.info("  → Checking for active upgrade...")
        try:
            active_upgrade = dynamodb_service.get_active_upgrade()
            logger.info(f"  → Active upgrade data: {active_upgrade}")
        except Exception as e:
            logger.error(f"  → ✗ Failed to get active upgrade: {str(e)}")
            logger.exception("  → Full exception:")
            active_upgrade = None

        active_upgrade_info: Optional[ActiveUpgrade] = None
        upgrade_status = "idle"

        if active_upgrade:
            logger.info("  → Active upgrade found, processing...")
            upgrade_status = "in_progress"

            # Get real-time progress from CodePipeline
            try:
                pipeline_execution_id = active_upgrade.get("pipeline_execution_id")
                if pipeline_execution_id:
                    pipeline_status = pipeline_service.get_pipeline_execution_status(
                        pipeline_execution_id
                    )

                    # Update progress in active upgrade
                    progress_info = pipeline_status.get("progress", {})

                    # Map pipeline status to upgrade status
                    pipeline_state = pipeline_status.get("status", "InProgress")
                    if pipeline_state == "Succeeded":
                        upgrade_status = "completed"
                    elif pipeline_state in ["Failed", "Stopped", "Stopping"]:
                        upgrade_status = "failed"

                    active_upgrade_info = ActiveUpgrade(
                        upgrade_id=active_upgrade.get("upgrade_id", ""),
                        target_version=active_upgrade.get("to_version", ""),
                        start_time=active_upgrade.get("start_time", ""),
                        pipeline_execution_id=pipeline_execution_id,
                        progress=UpgradeProgress(
                            stage=progress_info.get("stage", "Unknown"),
                            percentage=progress_info.get("percentage", 0),
                            current_action=progress_info.get(
                                "current_action", "Processing"
                            ),
                        ),
                    )

                    logger.info(
                        f"Active upgrade progress: {progress_info.get('percentage', 0)}%"
                    )
                else:
                    # No pipeline execution ID, use stored progress
                    progress = active_upgrade.get("progress", {})
                    active_upgrade_info = ActiveUpgrade(
                        upgrade_id=active_upgrade.get("upgrade_id", ""),
                        target_version=active_upgrade.get("to_version", ""),
                        start_time=active_upgrade.get("start_time", ""),
                        pipeline_execution_id=active_upgrade.get(
                            "pipeline_execution_id", ""
                        ),
                        progress=UpgradeProgress(
                            stage=progress.get("stage", "Unknown"),
                            percentage=progress.get("percentage", 0),
                            current_action=progress.get("current_action", "Processing"),
                        ),
                    )
            except Exception as e:
                logger.warning(f"Failed to get real-time pipeline status: {e}")
                # Fall back to stored progress
                progress = active_upgrade.get("progress", {})
                active_upgrade_info = ActiveUpgrade(
                    upgrade_id=active_upgrade.get("upgrade_id", ""),
                    target_version=active_upgrade.get("to_version", ""),
                    start_time=active_upgrade.get("start_time", ""),
                    pipeline_execution_id=active_upgrade.get(
                        "pipeline_execution_id", ""
                    ),
                    progress=UpgradeProgress(
                        stage=progress.get("stage", "Unknown"),
                        percentage=progress.get("percentage", 0),
                        current_action=progress.get("current_action", "Processing"),
                    ),
                )

        # Get last upgrade from history
        last_upgrade = None
        try:
            history = dynamodb_service.get_upgrade_history(limit=1)
            if history["items"]:
                last_item = history["items"][0]
                last_upgrade = {
                    "version": last_item.get("to_version", ""),
                    "timestamp": last_item.get("end_time", ""),
                    "status": last_item.get("status", "unknown"),
                }
        except Exception as e:
            logger.warning(f"Failed to get last upgrade: {e}")

        logger.info("  → Creating response data...")
        try:
            response_data = UpgradeStatusResponseData(
                current_version=current_version,
                upgrade_status=upgrade_status,
                last_upgrade=last_upgrade,
                active_upgrade=active_upgrade_info,
            )
            logger.info("  → ✓ Response data created")
        except Exception as e:
            logger.error(f"  → ✗ Failed to create response data: {str(e)}")
            logger.exception("  → Full exception:")
            raise

        logger.info(
            f"  → ✓ handle_get_status completed: status={upgrade_status}, version={current_version}"
        )

        response = create_success_response(response_data.model_dump())
        logger.info(f"  → Response structure: {list(response.keys())}")
        return response

    except Exception as e:
        logger.error(f"  → ✗ Failed to fetch upgrade status: {str(e)}")
        logger.exception("  → Full exception details:")
        raise InternalServerError(f"Failed to fetch upgrade status: {str(e)}")
