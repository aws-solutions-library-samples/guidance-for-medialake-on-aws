"""DELETE /collections/<collection_id>/thumbnail - Remove collection thumbnail."""

import json
import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import COLLECTION_PK_PREFIX, METADATA_SK, create_error_response
from db_models import CollectionModel
from pynamodb.exceptions import DoesNotExist, UpdateError
from user_auth import extract_user_context

logger = Logger(
    service="collections-ID-thumbnail-delete",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
tracer = Tracer(service="collections-ID-thumbnail-delete")
metrics = Metrics(namespace="medialake", service="collection-thumbnail")

s3 = boto3.client("s3")


def register_route(app):
    """Register DELETE /collections/<collection_id>/thumbnail route"""

    @app.delete("/collections/<collection_id>/thumbnail")
    @tracer.capture_method
    def collections_ID_thumbnail_delete(collection_id: str):
        """
        Remove the thumbnail from a collection.

        This will:
        1. Delete the thumbnail image from S3 (if exists)
        2. Clear the thumbnail fields in DynamoDB
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

            # Check ownership (only owner can remove thumbnail)
            if collection.ownerId != user_id:
                raise BadRequestError(
                    "Only the collection owner can remove the thumbnail"
                )

            # Check if collection has a thumbnail
            if not collection.thumbnailType:
                raise BadRequestError("Collection does not have a thumbnail")

            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Delete thumbnail from S3 if it exists
            if collection.thumbnailS3Key:
                media_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME")
                if media_bucket:
                    try:
                        s3.delete_object(
                            Bucket=media_bucket, Key=collection.thumbnailS3Key
                        )
                        logger.info(
                            f"Deleted thumbnail from S3",
                            extra={
                                "collection_id": collection_id,
                                "s3_key": collection.thumbnailS3Key,
                            },
                        )
                    except Exception as e:
                        # Log but don't fail - the S3 object might not exist
                        logger.warning(
                            f"Failed to delete thumbnail from S3: {e}",
                            extra={
                                "collection_id": collection_id,
                                "s3_key": collection.thumbnailS3Key,
                            },
                        )

            # Clear thumbnail fields in DynamoDB
            actions = [
                CollectionModel.updatedAt.set(current_timestamp),
                CollectionModel.thumbnailType.remove(),
                CollectionModel.thumbnailValue.remove(),
                CollectionModel.thumbnailS3Key.remove(),
            ]

            try:
                collection.update(actions=actions)
            except UpdateError as e:
                logger.error(f"Error removing collection thumbnail: {e}")
                raise BadRequestError("Failed to remove collection thumbnail")

            logger.info(f"Collection thumbnail removed: {collection_id}")
            metrics.add_metric(
                name="SuccessfulThumbnailDeletions", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": {
                            "id": collection_id,
                            "thumbnailRemoved": True,
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
            logger.exception("Error removing collection thumbnail", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
