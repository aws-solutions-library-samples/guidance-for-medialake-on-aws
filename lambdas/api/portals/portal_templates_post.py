"""POST /settings/portal-templates — Create a reusable portal template.

A Template is a point-in-time snapshot of a full portal structure. It is
validated with the SAME structural invariants as a portal (``_validate_portal_structure``)
so it can never seed an invalid portal (Req 17.3 / Property 13), and it NEVER
persists a passphrase (Req 17.7) — any passphrase in the body is ignored.
"""

import os
import uuid

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalTemplateModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import (
    GSI1_PK_TEMPLATES_VALUE,
    METADATA_SK,
    _validate_portal_structure,
    get_template_pk,
)
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(
    service="portal-templates-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-templates-post")


def register_route(app):
    @app.post("/settings/portal-templates")
    @tracer.capture_method
    def portal_templates_post():
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

            # Reject a non-object appearance before any write.
            appearance = body.get("appearance")
            if appearance is not None and not isinstance(appearance, dict):
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="appearance must be an object",
                    status_code=400,
                    request_id=request_id,
                )

            # Enforce the same structural invariants as a portal so a template
            # can never seed an invalid portal (Req 17.3 / Property 13).
            structure_error = _validate_portal_structure(body)
            if structure_error:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message=structure_error,
                    status_code=400,
                    request_id=request_id,
                )

            template_id = str(uuid.uuid4())
            now = now_iso()

            template = PortalTemplateModel()
            template.PK = get_template_pk(template_id)
            template.SK = METADATA_SK
            template.templateId = template_id
            template.name = name
            template.description = body.get("description")
            template.themeId = body.get("themeId")
            # Structure snapshot.
            template.pages = body.get("pages")
            template.metadataFields = body.get("metadataFields")
            template.destinations = body.get("destinations")
            template.appearance = appearance
            # Access settings + limits. NEVER read/store a passphrase (Req 17.7).
            template.accessMode = body.get("accessMode")
            template.allowedGroups = body.get("allowedGroups")
            template.ipAllowlist = body.get("ipAllowlist")
            template.tokenBypassesPassphrase = body.get(
                "tokenBypassesPassphrase", False
            )
            template.structuredPathMode = body.get("structuredPathMode", False)
            template.captchaEnabled = body.get("captchaEnabled", False)
            template.formSubmissionEnabled = body.get("formSubmissionEnabled", True)
            template.maxFileSizeBytes = body.get("maxFileSizeBytes")
            template.maxFilesPerSession = body.get("maxFilesPerSession")
            template.createdBy = user_context.get("user_id")
            template.createdAt = now
            template.updatedAt = now
            template.GSI1_PK = GSI1_PK_TEMPLATES_VALUE
            template.GSI1_SK = now
            template.save()

            response_data = {
                "templateId": template_id,
                "name": name,
                "description": body.get("description"),
                "themeId": body.get("themeId"),
                "createdAt": now,
                "updatedAt": now,
            }

            return create_success_response(
                data=response_data, status_code=201, request_id=request_id
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error creating template", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
