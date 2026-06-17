"""POST /settings/portals/{id}/favicon — Upload portal favicon."""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalMetadataModel
from image_upload_utils import (
    ALLOWED_CONTENT_TYPES,
    IAC_ASSETS_BUCKET_NAME,
    delete_s3_object,
    upload_portal_image,
    validate_and_decode_image,
)
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_portal_pk
from response_utils import create_error_response, create_success_response

logger = Logger(
    service="portals-id-favicon-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portals-id-favicon-post")

# Favicons support the standard image types plus ICO and SVG
FAVICON_CONTENT_TYPES = {
    **ALLOWED_CONTENT_TYPES,
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/svg+xml": "svg",
}


def register_route(app):
    @app.post("/settings/portals/<portal_id>/favicon")
    @tracer.capture_method
    def portals_id_favicon_post(portal_id: str):
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
            image_bytes, content_type, error = validate_and_decode_image(
                body, allowed_types=FAVICON_CONTENT_TYPES
            )
            if error:
                return create_error_response(
                    code=error.code,
                    message=error.message,
                    status_code=error.status_code,
                    request_id=request_id,
                )

            # Capture the old key so we can clean it up after a successful replace
            old_s3_key = getattr(item, "faviconS3Key", None)

            # Upload to S3: upload-portals/{slug}/favicon_{ts}.{ext}
            result = upload_portal_image(
                image_bytes=image_bytes,
                content_type=content_type,
                slug=item.slug,
                asset_name="favicon",
                allowed_types=FAVICON_CONTENT_TYPES,
            )

            # Update metadata; if this fails, clean up the uploaded object
            try:
                item.update(
                    actions=[PortalMetadataModel.faviconS3Key.set(result.s3_key)]
                )
            except Exception:
                logger.warning("Metadata update failed after S3 upload, cleaning up")
                delete_s3_object(result.s3_key)
                raise

            # Clean up the previous favicon object now that the new one is live
            if old_s3_key and old_s3_key != result.s3_key:
                delete_s3_object(old_s3_key)

            # Resolve the S3 key to a CloudFront URL for immediate frontend use
            favicon_url = None
            try:
                from url_utils import generate_cloudfront_url

                favicon_url = generate_cloudfront_url(
                    IAC_ASSETS_BUCKET_NAME, result.s3_key
                )
            except Exception:
                logger.warning(
                    "Could not resolve favicon URL", extra={"key": result.s3_key}
                )

            return create_success_response(
                data={"faviconS3Key": result.s3_key, "faviconUrl": favicon_url},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error uploading favicon", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
