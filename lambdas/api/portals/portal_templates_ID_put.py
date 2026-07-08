"""PUT /settings/portal-templates/{id} — Update a reusable portal template.

Updates ONLY the ``PORTALTEMPLATE#{templateId}`` record with the modified
structure snapshot (Req 17.9). It re-runs the same structural validation as on
create when structure-bearing fields are present (rejecting an invalid template
with a 400), and it NEVER persists a passphrase (Req 17.7) — there is no
passphrase attribute on the model and ``passphrase`` is absent from the
``field_map``, so any passphrase in the body is ignored.
"""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalTemplateModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, _validate_portal_structure, get_template_pk
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(
    service="portal-templates-id-put", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-templates-id-put")


def register_route(app):
    @app.put("/settings/portal-templates/<template_id>")
    @tracer.capture_method
    def portal_templates_id_put(template_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_template_pk(template_id)
            try:
                existing = PortalTemplateModel.get(pk, METADATA_SK)
            except PortalTemplateModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Template {template_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            body = app.current_event.json_body or {}

            # Reject a non-object appearance before any write.
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

            # Re-run the same structural invariants as on create, but only when
            # structure-bearing fields are present in this update (Req 17.9 /
            # Property 13).
            if any(k in body for k in ("pages", "destinations", "metadataFields")):
                structure_error = _validate_portal_structure(body)
                if structure_error:
                    return create_error_response(
                        code="VALIDATION_ERROR",
                        message=structure_error,
                        status_code=400,
                        request_id=request_id,
                    )

            now = now_iso()
            actions = [PortalTemplateModel.updatedAt.set(now)]

            # Persist the FULL modified snapshot. ``passphrase`` is intentionally
            # absent here so it can never be persisted (Req 17.7).
            field_map = {
                "name": PortalTemplateModel.name,
                "description": PortalTemplateModel.description,
                "themeId": PortalTemplateModel.themeId,
                "pages": PortalTemplateModel.pages,
                "metadataFields": PortalTemplateModel.metadataFields,
                "destinations": PortalTemplateModel.destinations,
                "appearance": PortalTemplateModel.appearance,
                "accessMode": PortalTemplateModel.accessMode,
                "allowedGroups": PortalTemplateModel.allowedGroups,
                "ipAllowlist": PortalTemplateModel.ipAllowlist,
                "tokenBypassesPassphrase": PortalTemplateModel.tokenBypassesPassphrase,
                "structuredPathMode": PortalTemplateModel.structuredPathMode,
                "captchaEnabled": PortalTemplateModel.captchaEnabled,
                "formSubmissionEnabled": PortalTemplateModel.formSubmissionEnabled,
                "maxFileSizeBytes": PortalTemplateModel.maxFileSizeBytes,
                "maxFilesPerSession": PortalTemplateModel.maxFilesPerSession,
            }
            for field_name, attr in field_map.items():
                if field_name in body:
                    actions.append(attr.set(body[field_name]))

            existing.update(actions=actions)

            return create_success_response(
                data={"templateId": template_id, "updatedAt": now},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error updating template", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
