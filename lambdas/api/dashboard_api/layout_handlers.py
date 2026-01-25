"""Dashboard layout handlers - GET, PUT, and RESET endpoints."""

import os
from datetime import datetime, timezone

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from dashboard_defaults import DEFAULT_LAYOUT
from dashboard_validation import validate_layout
from db_models import (
    LAYOUT_SK_ACTIVE,
    LAYOUT_SK_DEFAULT,
    SYSTEM_PK,
    USER_PK_PREFIX,
    DashboardLayoutModel,
)
from event_publisher import publish_layout_updated
from pynamodb.exceptions import DoesNotExist, PutError

logger = Logger(service="dashboard-layout", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="dashboard-layout")
metrics = Metrics(namespace="medialake", service="dashboard")


def register_layout_routes(app):
    """Register all layout routes."""

    @app.get("/dashboard/layout")
    @tracer.capture_method
    def layout_get():
        """Get user's active dashboard layout."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            logger.info("Getting dashboard layout", extra={"user_id": user_id})

            # Try to get user's active layout
            layout_data = _get_user_layout(user_id)

            if not layout_data:
                layout_data = _get_system_default()

            if not layout_data:
                layout_data = _get_hardcoded_default()

            metrics.add_metric(name="LayoutRetrievals", unit=MetricUnit.Count, value=1)
            return _success_response(layout_data)

        except Exception as e:
            logger.exception("Error getting dashboard layout", exc_info=e)
            metrics.add_metric(
                name="LayoutRetrievalErrors", unit=MetricUnit.Count, value=1
            )
            return _error_response(500, "INTERNAL_ERROR", "Failed to get layout")

    @app.put("/dashboard/layout")
    @tracer.capture_method
    def layout_put():
        """Save user's dashboard layout."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            body = app.current_event.json_body or {}
            widgets = body.get("widgets", [])
            layouts = body.get("layouts", {})

            logger.info(
                "Saving dashboard layout",
                extra={
                    "user_id": user_id,
                    "widget_count": len(widgets),
                },
            )

            validation_result = validate_layout(widgets, layouts)
            if not validation_result.is_valid:
                errors = [
                    {"field": e.field, "message": e.message}
                    for e in validation_result.errors
                ]
                return _validation_error_response(errors)

            current_version = _get_current_version(user_id)
            new_version = current_version + 1
            now = datetime.now(timezone.utc).isoformat()

            pk = f"{USER_PK_PREFIX}{user_id}"
            layout = DashboardLayoutModel(
                PK=pk,
                SK=LAYOUT_SK_ACTIVE,
                userId=user_id,
                layoutVersion=new_version,
                widgets=widgets,
                layouts=layouts,
                createdAt=(
                    now if current_version == 0 else _get_created_at(user_id, now)
                ),
                updatedAt=now,
            )
            layout.save()

            publish_layout_updated(user_id, new_version, len(widgets), action="save")
            metrics.add_metric(name="LayoutSaves", unit=MetricUnit.Count, value=1)

            return _success_response({"layoutVersion": new_version, "updatedAt": now})

        except PutError as e:
            logger.exception("DynamoDB error saving layout", exc_info=e)
            return _error_response(500, "DATABASE_ERROR", "Failed to save layout")
        except Exception as e:
            logger.exception("Error saving dashboard layout", exc_info=e)
            metrics.add_metric(name="LayoutSaveErrors", unit=MetricUnit.Count, value=1)
            return _error_response(500, "INTERNAL_ERROR", "Failed to save layout")

    @app.post("/dashboard/layout/reset")
    @tracer.capture_method
    def layout_reset_post():
        """Reset user's dashboard to default layout."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            logger.info("Resetting dashboard layout", extra={"user_id": user_id})

            default_layout = _get_default_layout()
            now = datetime.now(timezone.utc).isoformat()
            current_version = _get_current_version(user_id)
            new_version = current_version + 1

            pk = f"{USER_PK_PREFIX}{user_id}"
            layout = DashboardLayoutModel(
                PK=pk,
                SK=LAYOUT_SK_ACTIVE,
                userId=user_id,
                layoutVersion=new_version,
                widgets=default_layout["widgets"],
                layouts=default_layout["layouts"],
                createdAt=(
                    now if current_version == 0 else _get_created_at(user_id, now)
                ),
                updatedAt=now,
            )
            layout.save()

            publish_layout_updated(
                user_id, new_version, len(default_layout["widgets"]), action="reset"
            )

            metrics.add_metric(name="LayoutResets", unit=MetricUnit.Count, value=1)

            return _success_response(
                {
                    "layoutVersion": new_version,
                    "widgets": default_layout["widgets"],
                    "layouts": default_layout["layouts"],
                    "updatedAt": now,
                }
            )

        except PutError as e:
            logger.exception("DynamoDB error resetting layout", exc_info=e)
            return _error_response(500, "DATABASE_ERROR", "Failed to reset layout")
        except Exception as e:
            logger.exception("Error resetting dashboard layout", exc_info=e)
            metrics.add_metric(name="LayoutResetErrors", unit=MetricUnit.Count, value=1)
            return _error_response(500, "INTERNAL_ERROR", "Failed to reset layout")


# Helper functions
@tracer.capture_method
def _get_user_layout(user_id: str) -> dict | None:
    """Get user's active layout from DynamoDB."""
    try:
        layout = DashboardLayoutModel.get(
            f"{USER_PK_PREFIX}{user_id}", LAYOUT_SK_ACTIVE
        )
        return {
            "layoutVersion": layout.layoutVersion,
            "widgets": layout.widgets if layout.widgets else [],
            "layouts": layout.layouts if layout.layouts else {},
            "updatedAt": layout.updatedAt,
        }
    except DoesNotExist:
        return None


@tracer.capture_method
def _get_system_default() -> dict | None:
    """Get system default layout from DynamoDB."""
    try:
        layout = DashboardLayoutModel.get(SYSTEM_PK, LAYOUT_SK_DEFAULT)
        return {
            "layoutVersion": layout.layoutVersion,
            "widgets": layout.widgets if layout.widgets else [],
            "layouts": layout.layouts if layout.layouts else {},
            "updatedAt": layout.updatedAt,
        }
    except DoesNotExist:
        return None


def _get_hardcoded_default() -> dict:
    """Get hardcoded default layout."""
    return {
        **DEFAULT_LAYOUT,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@tracer.capture_method
def _get_default_layout() -> dict:
    """Get default layout (system default or hardcoded)."""
    try:
        layout = DashboardLayoutModel.get(SYSTEM_PK, LAYOUT_SK_DEFAULT)
        return {
            "widgets": layout.widgets if layout.widgets else [],
            "layouts": layout.layouts if layout.layouts else {},
        }
    except DoesNotExist:
        return {
            "widgets": DEFAULT_LAYOUT["widgets"],
            "layouts": DEFAULT_LAYOUT["layouts"],
        }


@tracer.capture_method
def _get_current_version(user_id: str) -> int:
    """Get current layout version for user."""
    try:
        layout = DashboardLayoutModel.get(
            f"{USER_PK_PREFIX}{user_id}", LAYOUT_SK_ACTIVE
        )
        return layout.layoutVersion or 0
    except DoesNotExist:
        return 0


@tracer.capture_method
def _get_created_at(user_id: str, default: str) -> str:
    """Get original createdAt timestamp for user's layout."""
    try:
        layout = DashboardLayoutModel.get(
            f"{USER_PK_PREFIX}{user_id}", LAYOUT_SK_ACTIVE
        )
        return layout.createdAt or default
    except DoesNotExist:
        return default


def _success_response(data: dict) -> dict:
    return {"statusCode": 200, "body": {"success": True, "data": data}}


def _error_response(status_code: int, code: str, message: str) -> dict:
    return {
        "statusCode": status_code,
        "body": {"success": False, "error": {"code": code, "message": message}},
    }


def _validation_error_response(errors: list) -> dict:
    return {
        "statusCode": 400,
        "body": {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Layout validation failed",
                "details": errors,
            },
        },
    }
