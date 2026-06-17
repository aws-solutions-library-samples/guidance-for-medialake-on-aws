"""DELETE /settings/portal-templates/{id} — Delete a reusable portal template.

Deletes ONLY the ``PORTALTEMPLATE#{templateId}`` record. Because a Template is a
self-contained snapshot (a single self-keyed item with destinations stored
inline, not as ``DEST#`` items), a single ``model.delete()`` is the entire
operation. It never touches any Portal (``UPLOADPORTAL#``) previously created
from this Template — those are independent snapshots (Req 17.9).
"""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalTemplateModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_template_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portal-templates-id-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-templates-id-delete")


def register_route(app):
    @app.delete("/settings/portal-templates/<template_id>")
    @tracer.capture_method
    def portal_templates_id_delete(template_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_template_pk(template_id)
            try:
                template_item = PortalTemplateModel.get(pk, METADATA_SK)
            except PortalTemplateModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Template {template_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            # Delete ONLY this template record. No Portal item is queried or
            # mutated here, so a Portal created from this template is left
            # intact (Req 17.9).
            template_item.delete()

            return create_success_response(data=None, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error deleting template", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
