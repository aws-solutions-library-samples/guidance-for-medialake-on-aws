"""GET /settings/portal-themes/{id} — Get one theme with its full appearance."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalThemeModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_theme_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portal-themes-id-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-themes-id-get")


def _appearance_to_dict(appearance):
    """Return the stored appearance as a plain dict.

    A PynamoDB ``MapAttribute`` exposes ``as_dict()``; a value that is already a
    plain dict (e.g. under test) is returned as-is. ``None`` round-trips to
    ``None`` so an unset appearance stays absent.
    """
    if appearance is None:
        return None
    as_dict = getattr(appearance, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    return appearance


def register_route(app):
    @app.get("/settings/portal-themes/<theme_id>")
    @tracer.capture_method
    def portal_themes_id_get(theme_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_theme_pk(theme_id)
            try:
                item = PortalThemeModel.get(pk, METADATA_SK)
            except PortalThemeModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Theme {theme_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            data = {
                "themeId": item.themeId,
                "name": item.name,
                "description": getattr(item, "description", None),
                "appearance": _appearance_to_dict(getattr(item, "appearance", None)),
                "createdBy": getattr(item, "createdBy", None),
                "createdAt": getattr(item, "createdAt", None),
                "updatedAt": getattr(item, "updatedAt", None),
            }

            return create_success_response(data=data, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error getting theme", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
