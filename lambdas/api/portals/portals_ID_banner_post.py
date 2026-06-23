"""POST /settings/portals/{id}/banner — Upload portal banner image."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalMetadataModel
from image_upload_utils import (
    delete_s3_object,
    resolve_portal_asset_url,
    upload_portal_image,
    validate_and_decode_image,
)
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_portal_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portals-id-banner-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portals-id-banner-post")


def register_route(app):
    @app.post("/settings/portals/<portal_id>/banner")
    @tracer.capture_method
    def portals_id_banner_post(portal_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            # Verify portal exists BEFORE any S3 write
            pk = get_portal_pk(portal_id)
            try:
                item = PortalMetadataModel.get(pk, METADATA_SK)
            except PortalMetadataModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Portal {portal_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            body = app.current_event.json_body or {}

            # Validate and decode the image
            image_bytes, content_type, error = validate_and_decode_image(body)
            if error:
                return create_error_response(
                    code=error.code,
                    message=error.message,
                    status_code=error.status_code,
                    request_id=request_id,
                )

            # Capture the old key so we can clean it up after a successful replace
            old_s3_key = getattr(item, "bannerS3Key", None)

            # Upload to S3: upload-portals/{slug}/banner_{ts}.{ext}
            result = upload_portal_image(
                image_bytes=image_bytes,
                content_type=content_type,
                slug=item.slug,
                asset_name="banner",
            )

            # Update metadata; if this fails, clean up the uploaded object
            try:
                item.update(
                    actions=[PortalMetadataModel.bannerS3Key.set(result.s3_key)]
                )
            except Exception:
                logger.warning("Metadata update failed after S3 upload, cleaning up")
                delete_s3_object(result.s3_key)
                raise

            # Clean up the previous banner object now that the new one is live
            if old_s3_key and old_s3_key != result.s3_key:
                delete_s3_object(old_s3_key)

            # Resolve the S3 key to a presigned GET URL for immediate frontend use
            banner_url = resolve_portal_asset_url(result.s3_key)

            return create_success_response(
                data={"bannerS3Key": result.s3_key, "bannerUrl": banner_url},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error uploading banner", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
