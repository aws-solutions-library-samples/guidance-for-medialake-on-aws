"""
Core business logic for S3 asset processing.

This module contains the main AssetProcessingService that orchestrates
all asset processing operations including creation, deletion, and metadata handling.
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from adapters.notify import NotificationAdapter
from adapters.s3_adapter import S3Adapter
from aws_lambda_powertools import Logger
from utils import determine_asset_type, extract_file_extension, extract_path_components

logger = Logger()


class AssetProcessingService:
    """
    Main service class that handles all asset processing business logic.

    This service orchestrates calls to adapters and contains the core
    business rules for asset processing, deletion, and metadata handling.
    """

    def __init__(self):
        """Initialize the service with required adapters."""
        self.s3_adapter = S3Adapter()
        self.notification_adapter = NotificationAdapter()

        # Configuration from environment
        self.do_not_ingest_duplicates = (
            os.environ.get("DO_NOT_INGEST_DUPLICATES", "false").lower() == "true"
        )

    def process_asset(self, bucket: str, key: str) -> Dict[str, Any]:
        """
        Process a new or updated asset from S3.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Dictionary containing processing results

        Raises:
            Exception: If processing fails
        """
        try:
            logger.info(
                "Starting asset processing", extra={"bucket": bucket, "key": key}
            )

            # Check if object still exists (could have been deleted between event and processing)
            if not self.s3_adapter.object_exists(bucket, key):
                logger.warning(
                    "Object no longer exists, skipping processing",
                    extra={"bucket": bucket, "key": key},
                )
                return {"status": "skipped", "reason": "object_not_found"}

            # Get object metadata and calculate hash
            metadata, tags = self.s3_adapter.get_object_metadata_and_tags(bucket, key)
            md5_hash = self.s3_adapter.calculate_md5_hash(bucket, key)

            # Create asset metadata structure
            asset_metadata = self._create_asset_metadata(
                bucket, key, metadata, md5_hash
            )

            # Generate inventory ID
            inventory_id = self._generate_inventory_id(bucket, key, md5_hash)

            # Check for duplicates if configured
            if self.do_not_ingest_duplicates:
                existing_asset = self.s3_adapter.get_asset_by_hash(md5_hash)
                if existing_asset:
                    logger.info(
                        "Duplicate asset found, skipping ingestion",
                        extra={
                            "bucket": bucket,
                            "key": key,
                            "existing_inventory_id": existing_asset.get("InventoryID"),
                        },
                    )
                    return {
                        "status": "skipped",
                        "reason": "duplicate",
                        "existing_inventory_id": existing_asset.get("InventoryID"),
                    }

            # Store asset in database
            asset_record = {
                "InventoryID": inventory_id,
                "FileHash": md5_hash,
                "Bucket": bucket,
                "ObjectKey": key,
                "AssetType": self._determine_asset_type(
                    metadata.get("ContentType", ""), key
                ),
                "CreatedAt": datetime.utcnow().isoformat(),
                "Metadata": asset_metadata,
            }

            self.s3_adapter.store_asset(asset_record)

            # Tag the S3 object with inventory ID
            self.s3_adapter.tag_object(bucket, key, {"InventoryID": inventory_id})

            # Index in search if configured
            if os.environ.get("OPENSEARCH_ENDPOINT"):
                self.s3_adapter.index_asset_for_search(inventory_id, asset_record)

            # Store vector embeddings if configured
            if os.environ.get("S3_VECTOR_STORE_BUCKET"):
                self.s3_adapter.store_vector_embeddings(inventory_id, asset_metadata)

            # Send notification
            self.notification_adapter.publish_asset_created_event(
                inventory_id, asset_record["AssetType"], asset_metadata
            )

            logger.info(
                "Asset processing completed successfully",
                extra={"inventory_id": inventory_id, "bucket": bucket, "key": key},
            )

            return {
                "status": "success",
                "inventory_id": inventory_id,
                "asset_type": asset_record["AssetType"],
                "file_hash": md5_hash,
            }

        except Exception as e:
            logger.exception(
                "Error processing asset",
                extra={"bucket": bucket, "key": key, "error": str(e)},
            )
            raise

    def delete_asset(
        self, bucket: str, key: str, version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete an asset and clean up associated resources.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            version_id: Optional S3 object version ID

        Returns:
            Dictionary containing deletion results

        Raises:
            Exception: If deletion fails
        """
        try:
            logger.info(
                "Starting asset deletion",
                extra={"bucket": bucket, "key": key, "version_id": version_id},
            )

            # Check if we should process this deletion (handles versioning)
            if not self.s3_adapter.should_process_deletion(bucket, key, version_id):
                logger.info(
                    "Skipping deletion (not latest version or other reason)",
                    extra={"bucket": bucket, "key": key, "version_id": version_id},
                )
                return {"status": "skipped", "reason": "not_latest_version"}

            # Find the asset record by S3 location
            asset_record = self.s3_adapter.get_asset_by_location(bucket, key)
            if not asset_record:
                logger.warning(
                    "No asset record found for deletion",
                    extra={"bucket": bucket, "key": key},
                )
                return {"status": "skipped", "reason": "asset_not_found"}

            inventory_id = asset_record["InventoryID"]

            # Delete from database
            self.s3_adapter.delete_asset(inventory_id)

            # Remove from search index if configured
            if os.environ.get("OPENSEARCH_ENDPOINT"):
                self.s3_adapter.remove_from_search_index(inventory_id)

            # Delete vector embeddings if configured
            if os.environ.get("S3_VECTOR_STORE_BUCKET"):
                self.s3_adapter.delete_vector_embeddings(inventory_id)

            # Clean up associated files (thumbnails, etc.)
            self._cleanup_associated_files(inventory_id, bucket, key)

            # Send notification
            self.notification_adapter.publish_asset_deleted_event(inventory_id)

            logger.info(
                "Asset deletion completed successfully",
                extra={"inventory_id": inventory_id, "bucket": bucket, "key": key},
            )

            return {
                "status": "success",
                "inventory_id": inventory_id,
                "deleted_files": [
                    "main_asset"
                ],  # Could be expanded to list all deleted files
            }

        except Exception as e:
            logger.exception(
                "Error deleting asset",
                extra={"bucket": bucket, "key": key, "error": str(e)},
            )
            raise

    def _create_asset_metadata(
        self, bucket: str, key: str, s3_metadata: Dict, md5_hash: str
    ) -> Dict[str, Any]:
        """Create standardized asset metadata structure."""
        name, path = extract_path_components(key)

        return {
            "StorageInfo": {
                "PrimaryLocation": {
                    "StorageType": "s3",
                    "Bucket": bucket,
                    "ObjectKey": {
                        "Name": name,
                        "Path": path,
                        "FullPath": key,
                    },
                    "Status": "active",
                    "FileInfo": {
                        "Size": s3_metadata.get("ContentLength", 0),
                        "Hash": {
                            "Algorithm": "SHA256",
                            "Value": s3_metadata.get("ETag", "").strip('"'),
                            "MD5Hash": md5_hash,
                        },
                        "CreateDate": s3_metadata.get(
                            "LastModified", datetime.utcnow()
                        ).isoformat(),
                    },
                }
            },
            "Metadata": {
                "ObjectMetadata": {
                    "ExtractedDate": datetime.utcnow().isoformat(),
                    "S3": {
                        "Metadata": s3_metadata.get("Metadata", {}),
                        "ContentType": s3_metadata.get("ContentType", ""),
                        "LastModified": s3_metadata.get(
                            "LastModified", datetime.utcnow()
                        ).isoformat(),
                    },
                }
            },
        }

    def _generate_inventory_id(self, bucket: str, key: str, md5_hash: str) -> str:
        """Generate a unique inventory ID for the asset."""
        # Use a combination of bucket, key hash, and file hash for uniqueness
        import hashlib

        combined = f"{bucket}:{key}:{md5_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _determine_asset_type(self, content_type: str, key: str) -> str:
        """Determine asset type from content type and file extension."""
        file_extension = extract_file_extension(key)
        return determine_asset_type(content_type, file_extension)

    def _cleanup_associated_files(
        self, inventory_id: str, bucket: str, key: str
    ) -> None:
        """Clean up any associated files like thumbnails or derivatives."""
        try:
            # This could be expanded to clean up thumbnails, transcoded files, etc.
            # For now, just log that cleanup would happen here
            logger.info(
                "Cleaning up associated files",
                extra={"inventory_id": inventory_id, "bucket": bucket, "key": key},
            )

            # Example: Delete thumbnails if they exist
            # thumbnail_key = f"thumbnails/{inventory_id}.jpg"
            # self.s3_adapter.delete_object_if_exists(bucket, thumbnail_key)

        except Exception as e:
            logger.warning(
                "Error during associated file cleanup",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main deletion for cleanup errors
