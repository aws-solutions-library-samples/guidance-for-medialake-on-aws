"""Shared image upload utilities for portal asset endpoints (logo, banner, favicon)."""

import base64
import binascii
import os
import time
from dataclasses import dataclass
from typing import Optional

import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="portals-image-upload")

IAC_ASSETS_BUCKET_NAME = os.environ.get("IAC_ASSETS_BUCKET_NAME", "")
s3_client = boto3.client("s3")

# Presigned-URL lifetime for portal images (logo/banner/favicon). The portal
# assets live in the private, KMS-encrypted IAC assets bucket, which is NOT a
# CloudFront origin, so they are served to the browser via presigned S3 GET
# URLs. The frontend re-resolves these URLs on every portal read (editor load
# and public page load), so a moderate lifetime is sufficient — and in practice
# the URL is further capped by the Lambda execution role's credential lifetime.
PORTAL_ASSET_URL_EXPIRATION = 6 * 60 * 60  # 6 hours


def resolve_portal_asset_url(
    s3_key: Optional[str],
    expiration: int = PORTAL_ASSET_URL_EXPIRATION,
) -> Optional[str]:
    """Resolve a portal image S3 key to a presigned GET URL for browser display.

    Portal images are stored privately in the IAC assets bucket (SSE-KMS) and
    are therefore served via presigned S3 GET URLs rather than a CloudFront
    path. Returns ``None`` when ``s3_key`` is falsy or the URL cannot be
    generated, so callers can safely fall back to "no image".
    """
    if not s3_key:
        return None
    try:
        from url_utils import generate_presigned_url

        return generate_presigned_url(
            IAC_ASSETS_BUCKET_NAME, s3_key, expiration=expiration
        )
    except Exception:
        logger.warning("Could not resolve portal asset URL", extra={"key": s3_key})
        return None


ALLOWED_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
}


@dataclass
class ImageUploadResult:
    """Result of a successful image upload."""

    s3_key: str


@dataclass
class ImageUploadError:
    """Result of a failed image upload validation."""

    code: str
    message: str
    status_code: int


def validate_and_decode_image(
    body: dict,
    allowed_types: Optional[dict] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[ImageUploadError]]:
    """Validate request body and decode the base64 image data.

    Args:
        body: The parsed JSON request body with ``data`` and ``contentType``.
        allowed_types: Optional override for allowed content types.
            Defaults to the module-level ``ALLOWED_CONTENT_TYPES``.

    Returns:
        Tuple of (image_bytes, content_type, error).
        On success: (bytes, str, None).
        On failure: (None, None, ImageUploadError).
    """
    if allowed_types is None:
        allowed_types = ALLOWED_CONTENT_TYPES

    image_data = body.get("data", "")
    content_type = body.get("contentType", "")

    if content_type not in allowed_types:
        return (
            None,
            None,
            ImageUploadError(
                code="VALIDATION_ERROR",
                message=f"contentType must be one of: {', '.join(allowed_types)}",
                status_code=400,
            ),
        )

    # Strip data-URL prefix if present (e.g. "data:image/png;base64,...")
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(image_data, validate=True)
    except (binascii.Error, ValueError):
        return (
            None,
            None,
            ImageUploadError(
                code="VALIDATION_ERROR",
                message="Invalid base64 image data",
                status_code=400,
            ),
        )

    return image_bytes, content_type, None


def upload_portal_image(
    *,
    image_bytes: bytes,
    content_type: str,
    slug: str,
    asset_name: str,
    allowed_types: Optional[dict] = None,
) -> ImageUploadResult:
    """Upload an image to S3 under the portal's slug-based path.

    S3 key format: ``upload-portals/{slug}/{asset_name}_{timestamp}.{ext}``

    A Unix timestamp is embedded in the key so that each upload produces a
    unique object.  This guarantees CloudFront never serves a stale cached
    version of a previous upload — the URL itself changes on every upload.

    Args:
        image_bytes: The decoded image bytes.
        content_type: MIME type of the image.
        slug: The portal's URL slug (used in the S3 key path).
        asset_name: The asset identifier (e.g. "logo", "banner", "favicon").
        allowed_types: Optional override for the content-type → extension map.

    Returns:
        ImageUploadResult with the S3 key.
    """
    if allowed_types is None:
        allowed_types = ALLOWED_CONTENT_TYPES

    ext = allowed_types[content_type]
    # Include a timestamp so each upload gets a unique key → no CloudFront cache issues
    ts = int(time.time())
    s3_key = f"upload-portals/{slug}/{asset_name}_{ts}.{ext}"

    s3_client.put_object(
        Bucket=IAC_ASSETS_BUCKET_NAME,
        Key=s3_key,
        Body=image_bytes,
        ContentType=content_type,
    )

    return ImageUploadResult(s3_key=s3_key)


def delete_s3_object(s3_key: str) -> None:
    """Best-effort deletion of an S3 object. Logs but does not raise on failure."""
    try:
        s3_client.delete_object(Bucket=IAC_ASSETS_BUCKET_NAME, Key=s3_key)
    except Exception:
        logger.warning("Failed to delete S3 object", extra={"key": s3_key})
