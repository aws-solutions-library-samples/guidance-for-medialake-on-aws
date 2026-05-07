"""
Main handler for MediaLake Auto-Upgrade System API endpoints.
Uses AWS Lambda Powertools APIGatewayRestResolver for routing.
"""

import logging
import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from handlers.delete_schedule_id import handle_delete_schedule_id
from handlers.get_history import handle_get_history
from handlers.get_scheduled import handle_get_scheduled
from handlers.get_status import handle_get_status
from handlers.get_versions import handle_get_versions
from handlers.post_schedule import handle_post_schedule
from handlers.post_trigger import handle_post_trigger
from utils.auth import validate_super_admin_access
from utils.response import create_error_response

# Initialize AWS Lambda Powertools
app = APIGatewayRestResolver(strip_prefixes=["/updates"])
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configure logging
logging.getLogger().setLevel(logging.INFO)


@app.get("/versions")
@tracer.capture_method
def get_versions():
    """Get available versions (branches and tags) from GitHub repository."""
    try:
        logger.info(">>> GET /versions - Starting request")

        # Validate super administrator access
        logger.info("Step 1: Validating super administrator access...")
        user_email = validate_super_admin_access(app.current_event.raw_event)
        logger.info(f"Step 1: ✓ Access validated for user: {user_email}")

        # Add custom metrics
        metrics.add_metric(name="GetVersionsRequests", unit=MetricUnit.Count, value=1)

        # Handle the request
        logger.info("Step 2: Fetching available versions from GitHub...")
        result = handle_get_versions()
        logger.info(f"Step 2: ✓ Successfully fetched versions")

        logger.info(
            f"<<< GET /versions - Request completed successfully for user: {user_email}"
        )
        return result

    except UnauthorizedError as e:
        logger.warning(f"✗ Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"✗ Error fetching versions: {str(e)}")
        logger.exception("Full exception details:")
        metrics.add_metric(name="GetVersionsErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to fetch versions: {str(e)}")


@app.post("/trigger")
@tracer.capture_method
def post_trigger():
    """Trigger immediate upgrade to selected version."""
    try:
        # Validate super administrator access
        user_email = validate_super_admin_access(app.current_event.raw_event)

        # Add custom metrics
        metrics.add_metric(
            name="TriggerUpgradeRequests", unit=MetricUnit.Count, value=1
        )

        # Handle the request
        result = handle_post_trigger(app.current_event.json_body, user_email)

        logger.info(f"Successfully triggered upgrade for user: {user_email}")
        return result

    except UnauthorizedError as e:
        logger.warning(f"Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except BadRequestError as e:
        logger.warning(f"Bad request for trigger upgrade: {str(e)}")
        metrics.add_metric(name="BadRequests", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"Error triggering upgrade: {str(e)}")
        metrics.add_metric(name="TriggerUpgradeErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to trigger upgrade: {str(e)}")


@app.get("/status")
@tracer.capture_method
def get_status():
    """Get current upgrade status and information."""
    try:
        logger.info(">>> GET /status - Starting request")

        # Validate super administrator access
        logger.info("Step 1: Validating super administrator access...")
        user_email = validate_super_admin_access(app.current_event.raw_event)
        logger.info(f"Step 1: ✓ Access validated for user: {user_email}")

        # Add custom metrics
        metrics.add_metric(name="GetStatusRequests", unit=MetricUnit.Count, value=1)

        # Handle the request
        logger.info("Step 2: Fetching current upgrade status...")
        result = handle_get_status()
        logger.info(f"Step 2: ✓ Successfully fetched status")

        logger.info(
            f"<<< GET /status - Request completed successfully for user: {user_email}"
        )
        return result

    except UnauthorizedError as e:
        logger.warning(f"✗ Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"✗ Error fetching status: {str(e)}")
        logger.exception("Full exception details:")
        metrics.add_metric(name="GetStatusErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to fetch status: {str(e)}")


@app.post("/schedule")
@tracer.capture_method
def post_schedule():
    """Schedule upgrade for future execution."""
    try:
        # Validate super administrator access
        user_email = validate_super_admin_access(app.current_event.raw_event)

        # Add custom metrics
        metrics.add_metric(
            name="ScheduleUpgradeRequests", unit=MetricUnit.Count, value=1
        )

        # Handle the request
        result = handle_post_schedule(app.current_event.json_body, user_email)

        logger.info(f"Successfully scheduled upgrade for user: {user_email}")
        return result

    except UnauthorizedError as e:
        logger.warning(f"Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except BadRequestError as e:
        logger.warning(f"Bad request for schedule upgrade: {str(e)}")
        metrics.add_metric(name="BadRequests", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"Error scheduling upgrade: {str(e)}")
        metrics.add_metric(name="ScheduleUpgradeErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to schedule upgrade: {str(e)}")


@app.get("/scheduled")
@tracer.capture_method
def get_scheduled():
    """List all scheduled upgrades."""
    try:
        # Validate super administrator access
        user_email = validate_super_admin_access(app.current_event.raw_event)

        # Add custom metrics
        metrics.add_metric(name="GetScheduledRequests", unit=MetricUnit.Count, value=1)

        # Handle the request
        result = handle_get_scheduled()

        logger.info(f"Successfully fetched scheduled upgrades for user: {user_email}")
        return result

    except UnauthorizedError as e:
        logger.warning(f"Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"Error fetching scheduled upgrades: {str(e)}")
        metrics.add_metric(name="GetScheduledErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to fetch scheduled upgrades: {str(e)}")


@app.delete("/schedule/<schedule_id>")
@tracer.capture_method
def delete_schedule_id(schedule_id: str):
    """Cancel a scheduled upgrade."""
    try:
        # Validate super administrator access
        user_email = validate_super_admin_access(app.current_event.raw_event)

        # Add custom metrics
        metrics.add_metric(
            name="CancelScheduleRequests", unit=MetricUnit.Count, value=1
        )

        # Handle the request
        result = handle_delete_schedule_id(schedule_id, user_email)

        logger.info(
            f"Successfully cancelled scheduled upgrade {schedule_id} for user: {user_email}"
        )
        return result

    except UnauthorizedError as e:
        logger.warning(f"Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except NotFoundError as e:
        logger.warning(f"Schedule not found: {str(e)}")
        metrics.add_metric(name="NotFoundErrors", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"Error cancelling scheduled upgrade: {str(e)}")
        metrics.add_metric(name="CancelScheduleErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to cancel scheduled upgrade: {str(e)}")


@app.get("/history")
@tracer.capture_method
def get_history():
    """Get upgrade history with pagination."""
    try:
        # Validate super administrator access
        user_email = validate_super_admin_access(app.current_event.raw_event)

        # Add custom metrics
        metrics.add_metric(name="GetHistoryRequests", unit=MetricUnit.Count, value=1)

        # Get query parameters
        query_params = app.current_event.query_string_parameters or {}

        # Handle the request
        result = handle_get_history(query_params)

        logger.info(f"Successfully fetched upgrade history for user: {user_email}")
        return result

    except UnauthorizedError as e:
        logger.warning(f"Unauthorized access attempt: {str(e)}")
        metrics.add_metric(name="UnauthorizedRequests", unit=MetricUnit.Count, value=1)
        raise
    except BadRequestError as e:
        logger.warning(f"Bad request for get history: {str(e)}")
        metrics.add_metric(name="BadRequests", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.error(f"Error fetching upgrade history: {str(e)}")
        metrics.add_metric(name="GetHistoryErrors", unit=MetricUnit.Count, value=1)
        raise InternalServerError(f"Failed to fetch upgrade history: {str(e)}")


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for auto-upgrade system API endpoints.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        logger.info("=" * 80)
        logger.info(f"INCOMING REQUEST: {event.get('httpMethod')} {event.get('path')}")
        logger.info(f"Request ID: {context.aws_request_id}")
        logger.info(f"Path parameters: {event.get('pathParameters')}")
        logger.info(f"Resource: {event.get('resource')}")
        logger.info(f"Event keys: {list(event.keys())}")
        logger.debug(f"Full event: {event}")

        # Add environment info to logs
        logger.append_keys(
            environment=os.environ.get("ENVIRONMENT", "unknown"),
            function_name=context.function_name,
            function_version=context.function_version,
            request_id=context.aws_request_id,
        )

        logger.info("Resolving request with APIGatewayRestResolver...")
        result = app.resolve(event, context)

        logger.info(
            f"Request completed successfully. Status: {result.get('statusCode')}"
        )
        logger.info(f"Response: {result}")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"UNHANDLED ERROR in lambda_handler: {str(e)}")
        logger.exception("Full exception details:")
        logger.error("=" * 80)
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)

        return create_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            error_message=f"An unexpected error occurred: {str(e)}",
            status_code=500,
        )
