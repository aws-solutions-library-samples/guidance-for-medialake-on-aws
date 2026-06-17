"""GET /settings/portal-templates — List all reusable portal templates."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalTemplateModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import GSI1_PK_TEMPLATES_VALUE
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portal-templates-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-templates-get")


def register_route(app):
    @app.get("/settings/portal-templates")
    @tracer.capture_method
    def portal_templates_get():
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            items = []
            for item in PortalTemplateModel.query(
                GSI1_PK_TEMPLATES_VALUE,
                index_name="GSI1",
            ):
                items.append(
                    {
                        "templateId": item.templateId,
                        "name": item.name,
                        "description": getattr(item, "description", None),
                        "themeId": getattr(item, "themeId", None),
                        "createdBy": getattr(item, "createdBy", None),
                        "createdAt": getattr(item, "createdAt", None),
                        "updatedAt": getattr(item, "updatedAt", None),
                    }
                )

            return create_success_response(data=items, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error listing templates", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
