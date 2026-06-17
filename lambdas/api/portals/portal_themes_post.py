"""POST /settings/portal-themes — Create a reusable appearance theme."""

import os
import uuid

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalThemeModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import GSI1_PK_THEMES_VALUE, METADATA_SK, get_theme_pk
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(service="portal-themes-post", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portal-themes-post")


def register_route(app):
    @app.post("/settings/portal-themes")
    @tracer.capture_method
    def portal_themes_post():
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            body = app.current_event.json_body or {}
            name = body.get("name", "")

            if not name:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="name is required",
                    status_code=400,
                    request_id=request_id,
                )

            # Reject a non-object appearance before any write (Req 16.6).
            appearance = body.get("appearance")
            if appearance is not None and not isinstance(appearance, dict):
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="appearance must be an object",
                    status_code=400,
                    request_id=request_id,
                )

            theme_id = str(uuid.uuid4())
            now = now_iso()

            theme = PortalThemeModel()
            theme.PK = get_theme_pk(theme_id)
            theme.SK = METADATA_SK
            theme.themeId = theme_id
            theme.name = name
            theme.description = body.get("description")
            theme.appearance = appearance
            theme.createdBy = user_context.get("user_id")
            theme.createdAt = now
            theme.updatedAt = now
            theme.GSI1_PK = GSI1_PK_THEMES_VALUE
            theme.GSI1_SK = now
            theme.save()

            response_data = {
                "themeId": theme_id,
                "name": name,
                "description": body.get("description"),
                "createdAt": now,
                "updatedAt": now,
            }

            return create_success_response(
                data=response_data, status_code=201, request_id=request_id
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error creating theme", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
