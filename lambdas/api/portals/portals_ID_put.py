"""PUT /settings/portals/{id} — Update portal metadata."""

import os
import re
import uuid

import bcrypt
from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import (
    PortalDestinationModel,
    PortalMetadataModel,
    PortalSlugIndexModel,
)
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import (
    DEST_SK_PREFIX,
    INDEX_SK,
    METADATA_SK,
    _validate_portal_structure,
    get_dest_sk,
    get_portal_pk,
    get_slug_pk,
)
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


def _reconcile_destinations(portal_id: str, incoming: list[dict]) -> None:
    """Diff-based reconcile of ``DEST#`` items for a portal.

    Preconditions:  ``incoming`` is the full desired destination set (each
                    item may carry a ``destinationId`` and ``pageNumber``).
    Postconditions: every incoming destination is created or overwritten;
                    every pre-existing ``DEST#`` item whose id is not in
                    ``incoming`` is deleted; the portal is never left with
                    zero destinations mid-operation because all upserts run
                    strictly before any delete (Req 4.3 / Property 4).

    The reconcile is idempotent: re-running with the same payload converges to
    the same stored set (Req 4.6). It is NOT transactional across items, which
    is acceptable for an admin-only config write. If any ``save()`` or
    ``delete()`` raises partway through, the ids reconciled so far are logged
    and the exception propagates so the handler returns 500 (Req 15.5).
    """
    pk = get_portal_pk(portal_id)
    existing = {
        d.destinationId: d
        for d in PortalDestinationModel.query(
            pk, PortalDestinationModel.SK.startswith(DEST_SK_PREFIX)
        )
    }
    incoming_ids: set[str] = set()
    succeeded_ids: list[str] = []

    try:
        # 1) Upsert every incoming destination FIRST (no zero-destination window).
        for dest in incoming:
            dest_id = dest.get("destinationId") or str(uuid.uuid4())
            incoming_ids.add(dest_id)
            d = PortalDestinationModel()
            d.PK = pk
            d.SK = get_dest_sk(dest_id)
            d.destinationId = dest_id
            d.friendlyName = dest.get("friendlyName", "")
            d.connectorId = dest.get("connectorId", "")
            d.rootPath = dest.get("rootPath", "/")
            d.allowBrowsing = dest.get("allowBrowsing", False)
            d.allowFolderCreation = dest.get("allowFolderCreation", False)
            d.order = dest.get("order", 0)
            d.pathSegments = dest.get("pathSegments")
            d.pageNumber = dest.get("pageNumber")
            d.save()  # full overwrite by PK+SK
            succeeded_ids.append(dest_id)

        # 2) Delete dest items no longer present — only after all upserts succeed.
        for dest_id, item in existing.items():
            if dest_id not in incoming_ids:
                item.delete()
                succeeded_ids.append(dest_id)
    except Exception:
        logger.exception(
            "Destination reconcile failed partway through; succeeded ids=%s",
            succeeded_ids,
        )
        raise


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

            # Reject a non-object appearance before any write (Req 14.6).
            appearance = body.get("appearance")
            if appearance is not None and not isinstance(appearance, dict):
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="appearance must be an object",
                    status_code=400,
                    request_id=request_id,
                )

            # Enforce structural invariants server-side before any write, but
            # only when structure-bearing fields are present in this update.
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
                "allowedFileTypes": PortalMetadataModel.allowedFileTypes,
                "captchaEnabled": PortalMetadataModel.captchaEnabled,
                "formSubmissionEnabled": PortalMetadataModel.formSubmissionEnabled,
                "automationTag": PortalMetadataModel.automationTag,
                "appearance": PortalMetadataModel.appearance,
                "pages": PortalMetadataModel.pages,
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

            # Diff-based destination reconcile — only after metadata update
            # succeeds, and only when destinations are part of this update.
            # Upserts run strictly before deletes so a concurrent reader never
            # observes zero destinations (Req 4.3). A mid-reconcile failure
            # propagates to the outer handler and returns 500 (Req 15.5).
            if "destinations" in body:
                _reconcile_destinations(portal_id, body["destinations"])

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
