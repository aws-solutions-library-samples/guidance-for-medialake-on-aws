"""POST /collections/<collection_id>/thumbnail - Set collection thumbnail."""

import base64
import io
import json
import os
from datetime import datetime
from enum import Enum

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from db_models import CollectionModel
from PIL import Image
from pynamodb.exceptions import DoesNotExist, UpdateError
from user_auth import extract_user_context

logger = Logger(
    service="collections-ID-thumbnail-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-thumbnail-post")
metrics = Metrics(namespace="medialake", service="collection-thumbnail")

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Thumbnail settings
MAX_THUMBNAIL_SIZE = 512  # Max width/height in pixels
THUMBNAIL_FORMAT = "PNG"
THUMBNAIL_CONTENT_TYPE = "image/png"
MAX_UPLOAD_SIZE_MB = 10  # Maximum upload size in MB


class ThumbnailSource(str, Enum):
    """Source type for thumbnail."""

    UPLOAD = "upload"  # Base64 encoded image data
    ASSET = "asset"  # Copy from existing asset
    FRAME = "frame"  # Captured video frame (base64 encoded)


def register_route(app):
    """Register POST /collections/<collection_id>/thumbnail route"""

    @app.post("/collections/<collection_id>/thumbnail")
    @tracer.capture_method
    def collections_ID_thumbnail_post(collection_id: str):
        """
        Set a thumbnail for a collection.

        Supports three sources:
        1. upload: Base64-encoded image data
        2. asset: Copy thumbnail from an existing asset
        3. frame: Base64-encoded video frame capture

        Request body:
        {
            "source": "upload" | "asset" | "frame",
            "data": "<base64-encoded-image>" (for upload/frame),
            "assetId": "<asset-id>" (for asset source)
        }
        """
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            # Get the collection
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
            except DoesNotExist:
                raise NotFoundError(f"Collection '{collection_id}' not found")

            # Check ownership (only owner can set thumbnail)
            if collection.ownerId != user_id:
                raise BadRequestError("Only the collection owner can set the thumbnail")

            # Parse request body
            body = app.current_event.json_body
            if not body:
                raise BadRequestError("Request body is required")

            source = body.get("source")
            if not source:
                raise BadRequestError("'source' field is required")

            try:
                source_type = ThumbnailSource(source)
            except ValueError:
                raise BadRequestError(
                    f"Invalid source type. Must be one of: {[s.value for s in ThumbnailSource]}"
                )

            current_timestamp = datetime.utcnow().isoformat() + "Z"
            media_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME")
            if not media_bucket:
                raise BadRequestError("MEDIA_ASSETS_BUCKET_NAME not configured")

            thumbnail_s3_key = f"collections/{collection_id}/thumbnail.png"

            if source_type == ThumbnailSource.ASSET:
                # Copy thumbnail from existing asset
                asset_id = body.get("assetId")
                if not asset_id:
                    raise BadRequestError("'assetId' is required for asset source")

                thumbnail_s3_key = _copy_asset_thumbnail(
                    asset_id, collection_id, media_bucket
                )
                thumbnail_value = asset_id

            elif source_type in (ThumbnailSource.UPLOAD, ThumbnailSource.FRAME):
                # Process uploaded image or video frame
                image_data = body.get("data")
                if not image_data:
                    raise BadRequestError(
                        "'data' field is required for upload/frame source"
                    )

                thumbnail_s3_key = _process_and_upload_thumbnail(
                    image_data, collection_id, media_bucket
                )
                thumbnail_value = None  # No asset reference for uploads/frames

            # Update collection with thumbnail info
            actions = [
                CollectionModel.updatedAt.set(current_timestamp),
                CollectionModel.thumbnailType.set(source_type.value),
                CollectionModel.thumbnailS3Key.set(thumbnail_s3_key),
            ]

            if thumbnail_value:
                actions.append(CollectionModel.thumbnailValue.set(thumbnail_value))
            else:
                # Clear thumbnailValue if not referencing an asset
                actions.append(CollectionModel.thumbnailValue.remove())

            try:
                collection.update(actions=actions)
            except UpdateError as e:
                logger.error(f"Error updating collection thumbnail: {e}")
                raise BadRequestError("Failed to update collection thumbnail")

            logger.info(
                f"Collection thumbnail set: {collection_id}",
                extra={
                    "collection_id": collection_id,
                    "source": source_type.value,
                    "s3_key": thumbnail_s3_key,
                },
            )
            metrics.add_metric(
                name="SuccessfulThumbnailUpdates", unit=MetricUnit.Count, value=1
            )

            # Generate CloudFront URL for response
            from url_utils import generate_cloudfront_url

            thumbnail_url = generate_cloudfront_url(media_bucket, thumbnail_s3_key)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "id": collection_id,
                            "thumbnailType": source_type.value,
                            "thumbnailUrl": thumbnail_url,
                            "updatedAt": current_timestamp,
                        },
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except (BadRequestError, NotFoundError):
            raise
        except Exception as e:
            logger.exception("Error setting collection thumbnail", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )


@tracer.capture_method
def _copy_asset_thumbnail(asset_id: str, collection_id: str, media_bucket: str) -> str:
    """
    Copy an asset's thumbnail to the collection thumbnail location.

    Args:
        asset_id: Source asset ID
        collection_id: Target collection ID
        media_bucket: S3 bucket name

    Returns:
        S3 key of the copied thumbnail
    """
    # Get the asset from DynamoDB to find its thumbnail
    asset_table_name = os.environ.get("MEDIALAKE_ASSET_TABLE")
    if not asset_table_name:
        raise BadRequestError("MEDIALAKE_ASSET_TABLE not configured")

    asset_table = dynamodb.Table(asset_table_name)

    # Clean asset ID format
    clean_asset_id = _clean_asset_id(asset_id)

    response = asset_table.get_item(Key={"InventoryID": clean_asset_id})
    asset = response.get("Item")

    if not asset:
        raise NotFoundError(f"Asset '{asset_id}' not found")

    # Find thumbnail in DerivedRepresentations
    derived_reps = asset.get("DerivedRepresentations", [])
    thumbnail_rep = next(
        (r for r in derived_reps if r.get("Purpose") == "thumbnail"), None
    )

    if not thumbnail_rep:
        raise BadRequestError(f"Asset '{asset_id}' has no thumbnail")

    # Get source thumbnail location
    source_location = thumbnail_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
    source_bucket = source_location.get("Bucket")
    source_key = source_location.get("ObjectKey", {}).get("FullPath")

    if not source_bucket or not source_key:
        raise BadRequestError(f"Asset '{asset_id}' thumbnail location is invalid")

    # Copy to collection thumbnail location
    dest_key = f"collections/{collection_id}/thumbnail.png"

    try:
        s3.copy_object(
            CopySource={"Bucket": source_bucket, "Key": source_key},
            Bucket=media_bucket,
            Key=dest_key,
            ContentType=THUMBNAIL_CONTENT_TYPE,
        )
        logger.info(
            f"Copied asset thumbnail to collection",
            extra={
                "source": f"s3://{source_bucket}/{source_key}",
                "dest": f"s3://{media_bucket}/{dest_key}",
            },
        )
    except Exception as e:
        logger.error(f"Failed to copy asset thumbnail: {e}")
        raise BadRequestError(f"Failed to copy asset thumbnail: {str(e)}")

    return dest_key


@tracer.capture_method
def _process_and_upload_thumbnail(
    image_data: str, collection_id: str, media_bucket: str
) -> str:
    """
    Process base64-encoded image data and upload as collection thumbnail.

    Args:
        image_data: Base64-encoded image data
        collection_id: Target collection ID
        media_bucket: S3 bucket name

    Returns:
        S3 key of the uploaded thumbnail
    """
    try:
        # Decode base64 data
        # Handle data URL format (e.g., "data:image/png;base64,...")
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(image_data)

        # Check size limit
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > MAX_UPLOAD_SIZE_MB:
            raise BadRequestError(
                f"Image too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB"
            )

        # Open and process image
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (handles RGBA, palette, etc.)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Resize to fit within max dimensions while maintaining aspect ratio
        img.thumbnail(
            (MAX_THUMBNAIL_SIZE, MAX_THUMBNAIL_SIZE), Image.Resampling.LANCZOS
        )

        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format=THUMBNAIL_FORMAT)
        buffer.seek(0)

        # Upload to S3
        dest_key = f"collections/{collection_id}/thumbnail.png"

        s3.put_object(
            Bucket=media_bucket,
            Key=dest_key,
            Body=buffer.getvalue(),
            ContentType=THUMBNAIL_CONTENT_TYPE,
        )

        logger.info(
            f"Uploaded collection thumbnail",
            extra={
                "collection_id": collection_id,
                "s3_key": dest_key,
                "original_size_mb": round(size_mb, 2),
                "dimensions": f"{img.width}x{img.height}",
            },
        )

        return dest_key

    except BadRequestError:
        raise
    except Exception as e:
        logger.error(f"Failed to process/upload thumbnail: {e}")
        raise BadRequestError(f"Failed to process image: {str(e)}")


def _clean_asset_id(raw: str) -> str:
    """
    Clean asset ID to standard format.

    Args:
        raw: Raw asset ID (may include prefixes)

    Returns:
        Cleaned asset ID in format asset:uuid:{uuid}
    """
    # If already in correct format, return as-is
    if raw.startswith("asset:uuid:"):
        return raw

    # Extract UUID part
    parts = raw.split(":")
    uuid_part = parts[-1] if parts[-1] != "master" else parts[-2]

    return f"asset:uuid:{uuid_part}"
