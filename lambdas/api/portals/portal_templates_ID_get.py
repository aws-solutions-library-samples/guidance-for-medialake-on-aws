"""GET /settings/portal-templates/{id} — Get one template's full structure snapshot."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalTemplateModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_template_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portal-templates-id-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portal-templates-id-get")


def _appearance_to_dict(appearance):
    """Return the stored appearance as a plain dict.

    A PynamoDB ``MapAttribute`` exposes ``as_dict()``; a value that is already a
    plain dict (e.g. under test) is returned as-is. ``None`` round-trips to
    ``None`` so an unset appearance stays absent. Mirrors the theme get handler.
    """
    if appearance is None:
        return None
    as_dict = getattr(appearance, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    return appearance


def _attr_to_plain(value):
    """Recursively convert PynamoDB attribute values (e.g. ``pages`` — a list of
    ``PortalPageMap``) into plain JSON-serializable structures.

    Without this, ``json.dumps(..., default=str)`` stringifies ``PortalPageMap``
    instances into their Python ``repr`` (``"PortalPageMap(...)"``), which the
    frontend cannot parse. Plain ``list``/``dict`` inputs are walked recursively;
    scalars (and ``None``) pass through unchanged.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return [_attr_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _attr_to_plain(item) for key, item in value.items()}
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        return {key: _attr_to_plain(item) for key, item in as_dict().items()}
    return value


def register_route(app):
    @app.get("/settings/portal-templates/<template_id>")
    @tracer.capture_method
    def portal_templates_id_get(template_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_template_pk(template_id)
            try:
                item = PortalTemplateModel.get(pk, METADATA_SK)
            except PortalTemplateModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Template {template_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            # Return the full structure snapshot equal in key set, nested
            # structure, element order, and scalar values to what was sent
            # (Req 17.10). NOTE: there is intentionally no passphrase field.
            data = {
                "templateId": item.templateId,
                "name": item.name,
                "description": getattr(item, "description", None),
                "themeId": getattr(item, "themeId", None),
                "pages": _attr_to_plain(getattr(item, "pages", None)),
                "metadataFields": _attr_to_plain(getattr(item, "metadataFields", None)),
                "destinations": _attr_to_plain(getattr(item, "destinations", None)),
                "appearance": _appearance_to_dict(getattr(item, "appearance", None)),
                "accessMode": getattr(item, "accessMode", None),
                "allowedGroups": getattr(item, "allowedGroups", None),
                "ipAllowlist": getattr(item, "ipAllowlist", None),
                "tokenBypassesPassphrase": getattr(
                    item, "tokenBypassesPassphrase", None
                ),
                "structuredPathMode": getattr(item, "structuredPathMode", None),
                "captchaEnabled": getattr(item, "captchaEnabled", None),
                "formSubmissionEnabled": getattr(item, "formSubmissionEnabled", None),
                "maxFileSizeBytes": getattr(item, "maxFileSizeBytes", None),
                "maxFilesPerSession": getattr(item, "maxFilesPerSession", None),
                "createdBy": getattr(item, "createdBy", None),
                "createdAt": getattr(item, "createdAt", None),
                "updatedAt": getattr(item, "updatedAt", None),
            }

            return create_success_response(data=data, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error getting template", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
