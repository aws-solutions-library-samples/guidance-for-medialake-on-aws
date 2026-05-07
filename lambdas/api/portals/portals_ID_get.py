"""GET /settings/portals/{id} — Get portal details with destinations."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalDestinationModel, PortalMetadataModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import DEST_SK_PREFIX, METADATA_SK, get_portal_pk
from response_utils import create_error_response, create_success_response

logger = Logger(service="portals-id-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-id-get")


def register_route(app):
    @app.get("/settings/portals/<portal_id>")
    @tracer.capture_method
    def portals_id_get(portal_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_portal_pk(portal_id)

            # Fetch metadata record
            try:
                item = PortalMetadataModel.get(pk, METADATA_SK)
            except PortalMetadataModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Portal {portal_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            metadata = {
                "portalId": item.portalId,
                "slug": item.slug,
                "name": item.name,
                "description": getattr(item, "description", None),
                "logoS3Key": getattr(item, "logoS3Key", None),
                "accessMode": getattr(item, "accessMode", None),
                "isActive": item.isActive,
                "tokenBypassesPassphrase": item.tokenBypassesPassphrase,
                "structuredPathMode": item.structuredPathMode,
                "maxFileSizeBytes": getattr(item, "maxFileSizeBytes", None),
                "maxFilesPerSession": getattr(item, "maxFilesPerSession", None),
                "allowedGroups": getattr(item, "allowedGroups", None),
                "ipAllowlist": getattr(item, "ipAllowlist", None),
                "metadataFields": getattr(item, "metadataFields", None),
                "createdBy": getattr(item, "createdBy", None),
                "createdAt": getattr(item, "createdAt", None),
                "updatedAt": getattr(item, "updatedAt", None),
                "expiresAt": getattr(item, "expiresAt", None),
            }

            # Fetch destinations with correctly-typed model
            destinations = []
            for dest in PortalDestinationModel.query(
                pk, PortalDestinationModel.SK.startswith(DEST_SK_PREFIX)
            ):
                destinations.append(
                    {
                        "destinationId": dest.destinationId,
                        "friendlyName": dest.friendlyName,
                        "connectorId": dest.connectorId,
                        "rootPath": dest.rootPath,
                        "allowBrowsing": dest.allowBrowsing,
                        "allowFolderCreation": dest.allowFolderCreation,
                        "order": dest.order,
                        "pathSegments": getattr(dest, "pathSegments", None),
                    }
                )

            metadata["destinations"] = destinations
            return create_success_response(data=metadata, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error getting portal", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
