"""PUT /settings/portals/{id} — Update portal metadata."""

import os
import re

import bcrypt
from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalMetadataModel, PortalSlugIndexModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import INDEX_SK, METADATA_SK, get_portal_pk, get_slug_pk
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(service="portals-id-put", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-id-put")

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")

ACCESS_CONTROL_FIELDS = {
    "isActive",
    "expiresAt",
    "ipAllowlist",
    "accessMode",
    "allowedGroups",
    "passphrase",
    "tokenBypassesPassphrase",
}


def register_route(app):
    @app.put("/settings/portals/<portal_id>")
    @tracer.capture_method
    def portals_id_put(portal_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_portal_pk(portal_id)
            try:
                existing = PortalMetadataModel.get(pk, METADATA_SK)
            except PortalMetadataModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Portal {portal_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            body = app.current_event.json_body or {}
            now = now_iso()
            actions = [PortalMetadataModel.updatedAt.set(now)]

            # Handle slug change
            new_slug = body.get("slug")
            old_slug = None
            new_slug_value = None
            if new_slug and new_slug != existing.slug:
                if not SLUG_PATTERN.match(new_slug):
                    return create_error_response(
                        code="VALIDATION_ERROR",
                        message="slug must be 3-50 chars, lowercase alphanumeric and hyphens",
                        status_code=400,
                        request_id=request_id,
                    )
                try:
                    PortalSlugIndexModel.get(get_slug_pk(new_slug), INDEX_SK)
                    return create_error_response(
                        code="SLUG_CONFLICT",
                        message=f"Slug '{new_slug}' is already in use",
                        status_code=409,
                        request_id=request_id,
                    )
                except PortalSlugIndexModel.DoesNotExist:
                    pass

                old_slug = existing.slug
                new_slug_value = new_slug
                actions.append(PortalMetadataModel.slug.set(new_slug))

            # Update simple fields
            field_map = {
                "name": PortalMetadataModel.name,
                "description": PortalMetadataModel.description,
                "accessMode": PortalMetadataModel.accessMode,
                "expiresAt": PortalMetadataModel.expiresAt,
                "allowedGroups": PortalMetadataModel.allowedGroups,
                "ipAllowlist": PortalMetadataModel.ipAllowlist,
                "metadataFields": PortalMetadataModel.metadataFields,
                "tokenBypassesPassphrase": PortalMetadataModel.tokenBypassesPassphrase,
                "structuredPathMode": PortalMetadataModel.structuredPathMode,
                "isActive": PortalMetadataModel.isActive,
                "maxFileSizeBytes": PortalMetadataModel.maxFileSizeBytes,
                "maxFilesPerSession": PortalMetadataModel.maxFilesPerSession,
                "captchaEnabled": PortalMetadataModel.captchaEnabled,
            }
            for field_name, attr in field_map.items():
                if field_name in body:
                    actions.append(attr.set(body[field_name]))

            # Hash new passphrase if provided
            if "passphrase" in body:
                raw = body["passphrase"]
                if raw:
                    hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
                    actions.append(PortalMetadataModel.passphrase.set(hashed))
                else:
                    actions.append(PortalMetadataModel.passphrase.set(None))

            # Atomically increment accessVersion if any access-control field changed
            if ACCESS_CONTROL_FIELDS & body.keys():
                actions.append(PortalMetadataModel.accessVersion.add(1))

            existing.update(actions=actions)

            # Slug index operations — only after metadata update succeeds
            if old_slug and new_slug_value:
                try:
                    try:
                        old_slug_item = PortalSlugIndexModel.get(
                            get_slug_pk(old_slug), INDEX_SK
                        )
                        old_slug_item.delete()
                    except PortalSlugIndexModel.DoesNotExist:
                        pass

                    new_slug_item = PortalSlugIndexModel()
                    new_slug_item.PK = get_slug_pk(new_slug_value)
                    new_slug_item.SK = INDEX_SK
                    new_slug_item.portalId = portal_id
                    new_slug_item.save()
                except Exception:
                    logger.warning(
                        "Metadata slug updated successfully but slug index mutation failed; "
                        "reconciliation may be needed. old_slug=%s new_slug=%s",
                        old_slug,
                        new_slug_value,
                        exc_info=True,
                    )

            return create_success_response(
                data={"portalId": portal_id, "updatedAt": now},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error updating portal", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
