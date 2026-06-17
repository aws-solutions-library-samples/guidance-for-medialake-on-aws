"""PUT /settings/portal-themes/{id} — Update a reusable appearance theme."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalThemeModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_theme_pk
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(
    service="portal-themes-id-put", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-themes-id-put")


def register_route(app):
    @app.put("/settings/portal-themes/<theme_id>")
    @tracer.capture_method
    def portal_themes_id_put(theme_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_theme_pk(theme_id)
            try:
                existing = PortalThemeModel.get(pk, METADATA_SK)
            except PortalThemeModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Theme {theme_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            body = app.current_event.json_body or {}

            # Reject a non-object appearance before any write (Req 16.6).
            appearance = body.get("appearance")
            if "appearance" in body and not (
                appearance is None or isinstance(appearance, dict)
            ):
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="appearance must be an object",
                    status_code=400,
                    request_id=request_id,
                )

            now = now_iso()
            actions = [PortalThemeModel.updatedAt.set(now)]

            field_map = {
                "name": PortalThemeModel.name,
                "description": PortalThemeModel.description,
                "appearance": PortalThemeModel.appearance,
            }
            for field_name, attr in field_map.items():
                if field_name in body:
                    actions.append(attr.set(body[field_name]))

            existing.update(actions=actions)

            return create_success_response(
                data={"themeId": theme_id, "updatedAt": now},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error updating theme", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
