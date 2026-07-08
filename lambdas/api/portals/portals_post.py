"""POST /settings/portals — Create a new upload portal."""

import os
import re
import secrets
import uuid

import bcrypt
import boto3
from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import (
    PortalDestinationModel,
    PortalMetadataModel,
    PortalSlugIndexModel,
)
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import (
    GSI1_PK_VALUE,
    INDEX_SK,
    METADATA_SK,
    _validate_portal_structure,
    get_dest_sk,
    get_portal_pk,
    get_slug_pk,
)
from pynamodb.exceptions import PutError
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(service="portals-post", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-post")

RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX", "medialake-dev")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")

secretsmanager_client = boto3.client("secretsmanager")


def register_route(app):
    @app.post("/settings/portals")
    @tracer.capture_method
    def portals_post():
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            body = app.current_event.json_body or {}
            slug = body.get("slug", "")
            name = body.get("name", "")

            if not name:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="name is required",
                    status_code=400,
                    request_id=request_id,
                )

            if not SLUG_PATTERN.match(slug):
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="slug must be 3-50 chars, lowercase alphanumeric and hyphens",
                    status_code=400,
                    request_id=request_id,
                )

            # Reject a non-object appearance before any write (Req 14.6).
            appearance = body.get("appearance")
            if appearance is not None and not isinstance(appearance, dict):
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="appearance must be an object",
                    status_code=400,
                    request_id=request_id,
                )

            # Enforce structural invariants server-side before any write.
            structure_error = _validate_portal_structure(body)
            if structure_error:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message=structure_error,
                    status_code=400,
                    request_id=request_id,
                )

            portal_id = str(uuid.uuid4())
            now = now_iso()
            secret_name = f"{RESOURCE_PREFIX}/portals/{portal_id}/session-secret"
            secret_created = False
            written_items = []

            try:
                # Claim slug atomically — first writer wins
                slug_index = PortalSlugIndexModel()
                slug_index.PK = get_slug_pk(slug)
                slug_index.SK = INDEX_SK
                slug_index.portalId = portal_id
                try:
                    slug_index.save(condition=PortalSlugIndexModel.PK.does_not_exist())
                except PutError as e:
                    if (
                        e.cause
                        and hasattr(e.cause, "response")
                        and e.cause.response["Error"]["Code"]
                        == "ConditionalCheckFailedException"
                    ):
                        return create_error_response(
                            code="SLUG_CONFLICT",
                            message=f"Slug '{slug}' is already in use",
                            status_code=409,
                            request_id=request_id,
                        )
                    raise
                written_items.append(slug_index)

                # Create session secret
                session_secret = secrets.token_urlsafe(32)
                secretsmanager_client.create_secret(
                    Name=secret_name,
                    SecretString=session_secret,
                )
                secret_created = True

                # Hash passphrase if provided
                passphrase_hash = None
                raw_passphrase = body.get("passphrase")
                if raw_passphrase:
                    passphrase_hash = bcrypt.hashpw(
                        raw_passphrase.encode(), bcrypt.gensalt()
                    ).decode()

                # Write portal metadata
                metadata = PortalMetadataModel()
                metadata.PK = get_portal_pk(portal_id)
                metadata.SK = METADATA_SK
                metadata.portalId = portal_id
                metadata.slug = slug
                metadata.name = name
                metadata.description = body.get("description")
                metadata.accessMode = body.get("accessMode")
                metadata.createdBy = user_context.get("user_id")
                metadata.createdAt = now
                metadata.updatedAt = now
                metadata.expiresAt = body.get("expiresAt")
                metadata.allowedGroups = body.get("allowedGroups")
                metadata.ipAllowlist = body.get("ipAllowlist")
                metadata.metadataFields = body.get("metadataFields")
                metadata.appearance = appearance
                metadata.pages = body.get("pages")
                metadata.passphrase = passphrase_hash
                metadata.tokenBypassesPassphrase = body.get(
                    "tokenBypassesPassphrase", False
                )
                metadata.structuredPathMode = body.get("structuredPathMode", False)
                metadata.captchaEnabled = body.get("captchaEnabled", False)
                metadata.formSubmissionEnabled = body.get("formSubmissionEnabled", True)
                metadata.isActive = body.get("isActive", True)
                metadata.accessVersion = 1
                metadata.maxFileSizeBytes = body.get("maxFileSizeBytes")
                metadata.maxFilesPerSession = body.get("maxFilesPerSession")
                metadata.automationTag = body.get("automationTag")
                # Tri-state allowed file types (see PortalMetadataModel). Persist
                # exactly what the client sends — including an empty list, which
                # means "allow any file type" — so the cleared state round-trips.
                metadata.allowedFileTypes = body.get("allowedFileTypes")
                metadata.GSI1_PK = GSI1_PK_VALUE
                metadata.GSI1_SK = now
                metadata.save()
                written_items.append(metadata)

                # Write destinations
                for dest in body.get("destinations", []):
                    dest_id = dest.get("destinationId", str(uuid.uuid4()))
                    d = PortalDestinationModel()
                    d.PK = get_portal_pk(portal_id)
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
                    d.save()
                    written_items.append(d)

            except Exception:
                logger.exception("Error creating portal, attempting cleanup")
                # Cleanup: delete written DDB items
                for item in written_items:
                    try:
                        item.delete()
                    except Exception:
                        logger.warning("Cleanup: failed to delete DDB item")
                # Cleanup: delete secret if created
                if secret_created:
                    try:
                        secretsmanager_client.delete_secret(
                            SecretId=secret_name, ForceDeleteWithoutRecovery=True
                        )
                    except Exception:
                        logger.warning("Cleanup: failed to delete secret")
                raise

            response_data = {
                "portalId": portal_id,
                "slug": slug,
                "name": name,
                "description": body.get("description"),
                "accessMode": body.get("accessMode"),
                "isActive": body.get("isActive", True),
                "createdAt": now,
                "updatedAt": now,
            }

            return create_success_response(
                data=response_data, status_code=201, request_id=request_id
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error creating portal", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
