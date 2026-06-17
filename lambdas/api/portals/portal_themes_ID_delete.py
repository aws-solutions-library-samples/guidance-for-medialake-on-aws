"""DELETE /settings/portal-themes/{id} — Delete a reusable appearance theme.

Deletes ONLY the ``PORTALTHEME#{themeId}`` record. It never touches any Portal
(``UPLOADPORTAL#``) or Template (``PORTALTEMPLATE#``) record — including a
Template whose ``themeId`` references the deleted Theme (Req 16.8). Because a
Theme is a single self-keyed item, a single ``model.delete()`` is the entire
operation: there are no child items to fan out to and no cross-entity writes.
"""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalThemeModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_theme_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portal-themes-id-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-themes-id-delete")


def register_route(app):
    @app.delete("/settings/portal-themes/<theme_id>")
    @tracer.capture_method
    def portal_themes_id_delete(theme_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_theme_pk(theme_id)
            try:
                theme_item = PortalThemeModel.get(pk, METADATA_SK)
            except PortalThemeModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Theme {theme_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            # Delete ONLY this theme record. No Portal/Template item is queried
            # or mutated here, so a Template referencing this themeId is left
            # intact (Req 16.8).
            theme_item.delete()

            return create_success_response(data=None, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error deleting theme", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
