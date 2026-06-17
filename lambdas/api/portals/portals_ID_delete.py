"""DELETE /settings/portals/{id} — Delete a portal and all related records."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError
from custom_exceptions import ForbiddenError
from db_models import (
    PortalDestinationModel,
    PortalMetadataModel,
    PortalSlugIndexModel,
    PortalTokenModel,
)
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import (
    DEST_SK_PREFIX,
    INDEX_SK,
    METADATA_SK,
    TOKEN_SK_PREFIX,
    get_portal_pk,
    get_slug_pk,
)
from response_utils import create_error_response, create_success_response

logger = Logger(service="portals-id-delete", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-id-delete")

RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX", "medialake-dev")
secretsmanager_client = boto3.client("secretsmanager")


def register_route(app):
    @app.delete("/settings/portals/<portal_id>")
    @tracer.capture_method
    def portals_id_delete(portal_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_portal_pk(portal_id)

            # Fetch & check metadata
            try:
                metadata_item = PortalMetadataModel.get(pk, METADATA_SK)
            except PortalMetadataModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Portal {portal_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            slug = metadata_item.slug

            # Delete destinations
            for dest in PortalDestinationModel.query(
                pk, PortalDestinationModel.SK.startswith(DEST_SK_PREFIX)
            ):
                dest.delete()

            # Delete tokens
            for token in PortalTokenModel.query(
                pk, PortalTokenModel.SK.startswith(TOKEN_SK_PREFIX)
            ):
                token.delete()

            # Delete slug index
            if slug:
                try:
                    slug_item = PortalSlugIndexModel.get(get_slug_pk(slug), INDEX_SK)
                    slug_item.delete()
                except PortalSlugIndexModel.DoesNotExist:
                    pass

            # Delete session secret
            secret_name = f"{RESOURCE_PREFIX}/portals/{portal_id}/session-secret"
            try:
                secretsmanager_client.delete_secret(
                    SecretId=secret_name, ForceDeleteWithoutRecovery=True
                )
            except ClientError as e:
                logger.warning(f"Failed to delete secret: {e}")

            # Delete metadata last to prevent orphaned children on partial failure
            metadata_item.delete()

            return create_success_response(data=None, request_id=request_id)

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error deleting portal", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
