"""GET /settings/portals — List all upload portals."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalMetadataModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import GSI1_PK_VALUE
from response_utils import create_error_response, create_success_response

logger = Logger(service="portals-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-get")


def register_route(app):
    @app.get("/settings/portals")
    @tracer.capture_method
    def portals_get():
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            items = []
            for item in PortalMetadataModel.query(
                GSI1_PK_VALUE,
                index_name="GSI1",
            ):
                items.append(
                    {
                        "portalId": item.portalId,
                        "slug": item.slug,
                        "name": item.name,
                        "description": getattr(item, "description", None),
                        "logoS3Key": getattr(item, "logoS3Key", None),
                        "accessMode": getattr(item, "accessMode", None),
                        "isActive": item.isActive,
                        "automationTag": getattr(item, "automationTag", None),
                        "expiresAt": getattr(item, "expiresAt", None),
                        "createdAt": getattr(item, "createdAt", None),
                        "updatedAt": getattr(item, "updatedAt", None),
                    }
                )

            return create_success_response(data=items, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error listing portals", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
