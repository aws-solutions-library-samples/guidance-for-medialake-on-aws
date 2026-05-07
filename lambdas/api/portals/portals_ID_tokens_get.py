"""GET /settings/portals/{id}/tokens — List tokens for a portal."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalMetadataModel, PortalTokenModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, TOKEN_SK_PREFIX, get_portal_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portals-id-tokens-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portals-id-tokens-get")


def register_route(app):
    @app.get("/settings/portals/<portal_id>/tokens")
    @tracer.capture_method
    def portals_id_tokens_get(portal_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_portal_pk(portal_id)

            # Verify portal exists
            try:
                PortalMetadataModel.get(pk, METADATA_SK)
            except PortalMetadataModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Portal {portal_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            tokens = []
            for item in PortalTokenModel.query(
                pk, PortalTokenModel.SK.startswith(TOKEN_SK_PREFIX)
            ):
                tokens.append(
                    {
                        "tokenId": item.tokenId,
                        "associatedEmail": item.associatedEmail,
                        "createdAt": item.createdAt,
                        "expiresAt": getattr(item, "expiresAt", None),
                        "isRevoked": item.isRevoked,
                        "prePopulatedParams": getattr(item, "prePopulatedParams", None),
                    }
                )

            return create_success_response(data=tokens, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error listing tokens", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
