"""Dashboard preset handlers - all preset management endpoints."""

import os
from datetime import datetime, timezone

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from dashboard_defaults import DEFAULT_LAYOUT
from db_models import (
    LAYOUT_SK_ACTIVE,
    PRESET_SK_PREFIX,
    USER_PK_PREFIX,
    DashboardLayoutModel,
    DashboardPresetModel,
)
from event_publisher import publish_layout_updated, publish_preset_created
from pynamodb.exceptions import DeleteError, DoesNotExist, PutError, UpdateError
from ulid import ULID

logger = Logger(service="dashboard-presets", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="dashboard-presets")
metrics = Metrics(namespace="medialake", service="dashboard")

MAX_PRESETS = 5


def register_preset_routes(app):
    """Register all preset routes."""

    @app.get("/dashboard/presets")
    @tracer.capture_method
    def presets_get():
        """List user's saved presets."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            logger.info("Listing presets", extra={"user_id": user_id})

            presets = []
            pk = f"{USER_PK_PREFIX}{user_id}"

            for preset in DashboardPresetModel.query(
                pk, DashboardPresetModel.SK.startswith(PRESET_SK_PREFIX)
            ):
                presets.append(
                    {
                        "presetId": preset.presetId,
                        "name": preset.name,
                        "description": preset.description,
                        "widgetCount": len(preset.widgets) if preset.widgets else 0,
                        "createdAt": preset.createdAt,
                        "updatedAt": preset.updatedAt,
                    }
                )

            metrics.add_metric(name="PresetListings", unit=MetricUnit.Count, value=1)
            return _success_response(presets)

        except Exception as e:
            logger.exception("Error listing presets", exc_info=e)
            metrics.add_metric(name="PresetListErrors", unit=MetricUnit.Count, value=1)
            return _error_response(500, "INTERNAL_ERROR", "Failed to list presets")

    @app.post("/dashboard/presets")
    @tracer.capture_method
    def presets_post():
        """Create a new preset from current layout."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            body = app.current_event.json_body or {}
            name = body.get("name", "").strip()
            description = body.get("description", "").strip() or None

            if not name:
                return _error_response(
                    400, "VALIDATION_ERROR", "Preset name is required"
                )
            if len(name) > 100:
                return _error_response(
                    400, "VALIDATION_ERROR", "Name exceeds 100 characters"
                )
            if description and len(description) > 500:
                return _error_response(
                    400, "VALIDATION_ERROR", "Description exceeds 500 characters"
                )

            logger.info(
                "Creating preset", extra={"user_id": user_id, "preset_name": name}
            )

            pk = f"{USER_PK_PREFIX}{user_id}"
            preset_count = _count_user_presets(pk)
            if preset_count >= MAX_PRESETS:
                return _error_response(
                    400,
                    "MAX_PRESETS_EXCEEDED",
                    f"Cannot create more than {MAX_PRESETS} saved presets",
                )

            layout_data = _get_user_layout(user_id)
            preset_id = str(ULID())
            now = datetime.now(timezone.utc).isoformat()

            preset = DashboardPresetModel(
                PK=pk,
                SK=f"{PRESET_SK_PREFIX}{preset_id}",
                presetId=preset_id,
                userId=user_id,
                name=name,
                description=description,
                widgets=layout_data["widgets"],
                layouts=layout_data["layouts"],
                createdAt=now,
                updatedAt=now,
            )
            preset.save()

            publish_preset_created(
                user_id, preset_id, name, len(layout_data["widgets"])
            )
            metrics.add_metric(name="PresetCreations", unit=MetricUnit.Count, value=1)

            return {
                "statusCode": 201,
                "body": {
                    "success": True,
                    "data": {
                        "presetId": preset_id,
                        "name": name,
                        "description": description,
                        "widgets": layout_data["widgets"],
                        "layouts": layout_data["layouts"],
                        "createdAt": now,
                        "updatedAt": now,
                    },
                },
            }

        except PutError as e:
            logger.exception("DynamoDB error creating preset", exc_info=e)
            return _error_response(500, "DATABASE_ERROR", "Failed to create preset")
        except Exception as e:
            logger.exception("Error creating preset", exc_info=e)
            metrics.add_metric(
                name="PresetCreateErrors", unit=MetricUnit.Count, value=1
            )
            return _error_response(500, "INTERNAL_ERROR", "Failed to create preset")

    @app.get("/dashboard/presets/<preset_id>")
    @tracer.capture_method
    def presets_ID_get(preset_id: str):
        """Get preset details."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            logger.info(
                "Getting preset", extra={"user_id": user_id, "preset_id": preset_id}
            )

            pk = f"{USER_PK_PREFIX}{user_id}"
            sk = f"{PRESET_SK_PREFIX}{preset_id}"

            try:
                preset = DashboardPresetModel.get(pk, sk)
            except DoesNotExist:
                return _error_response(404, "PRESET_NOT_FOUND", "Preset not found")

            metrics.add_metric(name="PresetRetrievals", unit=MetricUnit.Count, value=1)

            return {
                "statusCode": 200,
                "body": {
                    "success": True,
                    "data": {
                        "presetId": preset.presetId,
                        "name": preset.name,
                        "description": preset.description,
                        "widgets": list(preset.widgets) if preset.widgets else [],
                        "layouts": dict(preset.layouts) if preset.layouts else {},
                        "createdAt": preset.createdAt,
                        "updatedAt": preset.updatedAt,
                    },
                },
            }

        except Exception as e:
            logger.exception("Error getting preset", exc_info=e)
            metrics.add_metric(name="PresetGetErrors", unit=MetricUnit.Count, value=1)
            return _error_response(500, "INTERNAL_ERROR", "Failed to get preset")

    @app.put("/dashboard/presets/<preset_id>")
    @tracer.capture_method
    def presets_ID_put(preset_id: str):
        """Update preset."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            body = app.current_event.json_body or {}
            logger.info(
                "Updating preset", extra={"user_id": user_id, "preset_id": preset_id}
            )

            pk = f"{USER_PK_PREFIX}{user_id}"
            sk = f"{PRESET_SK_PREFIX}{preset_id}"

            try:
                preset = DashboardPresetModel.get(pk, sk)
            except DoesNotExist:
                return _error_response(404, "PRESET_NOT_FOUND", "Preset not found")

            if "name" in body:
                name = body["name"].strip()
                if not name:
                    return _error_response(
                        400, "VALIDATION_ERROR", "Name cannot be empty"
                    )
                if len(name) > 100:
                    return _error_response(
                        400, "VALIDATION_ERROR", "Name exceeds 100 characters"
                    )
                preset.name = name

            if "description" in body:
                desc = body["description"]
                if desc and len(desc) > 500:
                    return _error_response(
                        400, "VALIDATION_ERROR", "Description exceeds 500 characters"
                    )
                preset.description = desc.strip() if desc else None

            if "widgets" in body:
                preset.widgets = body["widgets"]

            if "layouts" in body:
                preset.layouts = body["layouts"]

            preset.updatedAt = datetime.now(timezone.utc).isoformat()
            preset.save()

            metrics.add_metric(name="PresetUpdates", unit=MetricUnit.Count, value=1)

            return {
                "statusCode": 200,
                "body": {
                    "success": True,
                    "data": {
                        "presetId": preset.presetId,
                        "name": preset.name,
                        "description": preset.description,
                        "widgets": list(preset.widgets) if preset.widgets else [],
                        "layouts": dict(preset.layouts) if preset.layouts else {},
                        "createdAt": preset.createdAt,
                        "updatedAt": preset.updatedAt,
                    },
                },
            }

        except UpdateError as e:
            logger.exception("DynamoDB error updating preset", exc_info=e)
            return _error_response(500, "DATABASE_ERROR", "Failed to update preset")
        except Exception as e:
            logger.exception("Error updating preset", exc_info=e)
            metrics.add_metric(
                name="PresetUpdateErrors", unit=MetricUnit.Count, value=1
            )
            return _error_response(500, "INTERNAL_ERROR", "Failed to update preset")

    @app.delete("/dashboard/presets/<preset_id>")
    @tracer.capture_method
    def presets_ID_delete(preset_id: str):
        """Delete preset."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            logger.info(
                "Deleting preset", extra={"user_id": user_id, "preset_id": preset_id}
            )

            pk = f"{USER_PK_PREFIX}{user_id}"
            sk = f"{PRESET_SK_PREFIX}{preset_id}"

            try:
                preset = DashboardPresetModel.get(pk, sk)
            except DoesNotExist:
                return _error_response(404, "PRESET_NOT_FOUND", "Preset not found")

            preset.delete()
            metrics.add_metric(name="PresetDeletions", unit=MetricUnit.Count, value=1)

            return {"statusCode": 204, "body": None}

        except DeleteError as e:
            logger.exception("DynamoDB error deleting preset", exc_info=e)
            return _error_response(500, "DATABASE_ERROR", "Failed to delete preset")
        except Exception as e:
            logger.exception("Error deleting preset", exc_info=e)
            metrics.add_metric(
                name="PresetDeleteErrors", unit=MetricUnit.Count, value=1
            )
            return _error_response(500, "INTERNAL_ERROR", "Failed to delete preset")

    @app.post("/dashboard/presets/<preset_id>/apply")
    @tracer.capture_method
    def presets_ID_apply_post(preset_id: str):
        """Apply preset as active layout."""
        from user_auth import extract_user_context

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return _error_response(401, "UNAUTHORIZED", "Authentication required")

            logger.info(
                "Applying preset", extra={"user_id": user_id, "preset_id": preset_id}
            )

            pk = f"{USER_PK_PREFIX}{user_id}"
            preset_sk = f"{PRESET_SK_PREFIX}{preset_id}"

            try:
                preset = DashboardPresetModel.get(pk, preset_sk)
            except DoesNotExist:
                return _error_response(404, "PRESET_NOT_FOUND", "Preset not found")

            current_version = _get_current_version(user_id)
            new_version = current_version + 1
            now = datetime.now(timezone.utc).isoformat()

            layout = DashboardLayoutModel(
                PK=pk,
                SK=LAYOUT_SK_ACTIVE,
                userId=user_id,
                layoutVersion=new_version,
                widgets=list(preset.widgets) if preset.widgets else [],
                layouts=dict(preset.layouts) if preset.layouts else {},
                createdAt=(
                    now if current_version == 0 else _get_created_at(user_id, now)
                ),
                updatedAt=now,
            )
            layout.save()

            widget_count = len(preset.widgets) if preset.widgets else 0
            publish_layout_updated(
                user_id, new_version, widget_count, action="apply_preset"
            )

            metrics.add_metric(
                name="PresetApplications", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 200,
                "body": {
                    "success": True,
                    "data": {
                        "layoutVersion": new_version,
                        "widgets": list(preset.widgets) if preset.widgets else [],
                        "layouts": dict(preset.layouts) if preset.layouts else {},
                        "updatedAt": now,
                    },
                },
            }

        except PutError as e:
            logger.exception("DynamoDB error applying preset", exc_info=e)
            return _error_response(500, "DATABASE_ERROR", "Failed to apply preset")
        except Exception as e:
            logger.exception("Error applying preset", exc_info=e)
            metrics.add_metric(name="PresetApplyErrors", unit=MetricUnit.Count, value=1)
            return _error_response(500, "INTERNAL_ERROR", "Failed to apply preset")


# Helper functions
@tracer.capture_method
def _count_user_presets(pk: str) -> int:
    """Count user's existing presets."""
    count = 0
    for _ in DashboardPresetModel.query(
        pk, DashboardPresetModel.SK.startswith(PRESET_SK_PREFIX)
    ):
        count += 1
    return count


@tracer.capture_method
def _get_user_layout(user_id: str) -> dict:
    """Get user's current active layout or default."""
    try:
        layout = DashboardLayoutModel.get(
            f"{USER_PK_PREFIX}{user_id}", LAYOUT_SK_ACTIVE
        )
        return {
            "widgets": list(layout.widgets) if layout.widgets else [],
            "layouts": dict(layout.layouts) if layout.layouts else {},
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


def _success_response(data) -> dict:
    return {"statusCode": 200, "body": {"success": True, "data": data}}


def _error_response(status_code: int, code: str, message: str) -> dict:
    return {
        "statusCode": status_code,
        "body": {"success": False, "error": {"code": code, "message": message}},
    }
