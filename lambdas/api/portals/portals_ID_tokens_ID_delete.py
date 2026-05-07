"""DELETE /settings/portals/{id}/tokens/{tokenId} — Revoke a token."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalTokenModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import get_portal_pk, get_token_sk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portals-id-tokens-id-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portals-id-tokens-id-delete")


def register_route(app):
    @app.delete("/settings/portals/<portal_id>/tokens/<token_id>")
    @tracer.capture_method
    def portals_id_tokens_id_delete(portal_id: str, token_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            try:
                token = PortalTokenModel.get(
                    get_portal_pk(portal_id), get_token_sk(token_id)
                )
            except PortalTokenModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Token {token_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            token.update(actions=[PortalTokenModel.isRevoked.set(True)])

            return create_success_response(
                data={"tokenId": token_id, "isRevoked": True},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error revoking token", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
