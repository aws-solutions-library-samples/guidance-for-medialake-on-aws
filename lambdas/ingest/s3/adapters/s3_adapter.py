"""
S3 and DynamoDB adapter for asset processing.

This module handles all interactions with AWS S3, DynamoDB, and OpenSearch
for asset storage, retrieval, and management operations.
"""

import concurrent.futures
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()


class S3Adapter:
    """
    Adapter for AWS S3, DynamoDB, and OpenSearch operations.

    This class encapsulates all AWS service interactions needed for
    asset processing, providing a clean interface for the service layer.
    """

    def __init__(self):
        """Initialize AWS clients with connection reuse for Lambda optimization."""
        self.s3_client = boto3.client("s3")
        self.dynamodb = boto3.resource("dynamodb")

        # Initialize table references
        self.assets_table = self.dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

        # Optional services (only initialize if configured)
        self.opensearch_client = None
        if os.environ.get("OPENSEARCH_ENDPOINT"):
            from aws_requests_auth.aws_auth import AWSRequestsAuth
            from opensearchpy import OpenSearch, RequestsHttpConnection

            host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
            awsauth = AWSRequestsAuth(
                aws_access_key=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                aws_token=os.environ.get("AWS_SESSION_TOKEN"),
                aws_host=host,
                aws_region=os.environ.get("AWS_REGION", "us-east-1"),
                aws_service="es",
            )

            self.opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
            )

    def object_exists(self, bucket: str, key: str) -> bool:
        """Check if an S3 object exists."""
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def get_object_metadata_and_tags(self, bucket: str, key: str) -> Tuple[Dict, Dict]:
        """Get S3 object metadata and tags in parallel for better performance."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            head_future = executor.submit(
                self.s3_client.head_object, Bucket=bucket, Key=key
            )
            tag_future = executor.submit(
                self.s3_client.get_object_tagging, Bucket=bucket, Key=key
            )

            # Wait for both to complete
            concurrent.futures.wait([head_future, tag_future])

            try:
                metadata = head_future.result()
            except Exception as e:
                logger.exception(
                    "Error getting S3 object metadata", extra={"error": str(e)}
                )
                raise

            try:
                tags_response = tag_future.result()
                tags = {
                    tag["Key"]: tag["Value"] for tag in tags_response.get("TagSet", [])
                }
            except Exception as e:
                logger.warning("Error getting S3 object tags", extra={"error": str(e)})
                tags = {}

        return metadata, tags

    def calculate_md5_hash(self, bucket: str, key: str, chunk_size: int = 8192) -> str:
        """Calculate MD5 hash with optimal chunk size for memory efficiency."""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            md5_hash = hashlib.md5(usedforsecurity=False)

            bytes_processed = 0
            for chunk in response["Body"].iter_chunks(chunk_size):
                md5_hash.update(chunk)
                bytes_processed += len(chunk)

            return md5_hash.hexdigest()
        except Exception as e:
            logger.exception(
                "Error calculating MD5 hash",
                extra={"bucket": bucket, "key": key, "error": str(e)},
            )
            raise

    def get_asset_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Get asset record by file hash to check for duplicates."""
        try:
            response = self.assets_table.query(
                IndexName="FileHashIndex",  # Assumes GSI exists
                KeyConditionExpression="FileHash = :hash",
                ExpressionAttributeValues={":hash": file_hash},
                Limit=1,
            )

            items = response.get("Items", [])
            return items[0] if items else None

        except Exception as e:
            logger.exception(
                "Error querying asset by hash",
                extra={"file_hash": file_hash, "error": str(e)},
            )
            raise

    def get_asset_by_location(self, bucket: str, key: str) -> Optional[Dict]:
        """Get asset record by S3 location."""
        try:
            # Query by bucket and key (assumes GSI exists)
            response = self.assets_table.query(
                IndexName="LocationIndex",  # Assumes GSI exists
                KeyConditionExpression="Bucket = :bucket AND ObjectKey = :key",
                ExpressionAttributeValues={":bucket": bucket, ":key": key},
                Limit=1,
            )

            items = response.get("Items", [])
            return items[0] if items else None

        except Exception as e:
            logger.exception(
                "Error querying asset by location",
                extra={"bucket": bucket, "key": key, "error": str(e)},
            )
            raise

    def store_asset(self, asset_record: Dict[str, Any]) -> None:
        """Store asset record in DynamoDB."""
        try:
            self.assets_table.put_item(Item=asset_record)
            logger.info(
                "Asset stored successfully",
                extra={"inventory_id": asset_record.get("InventoryID")},
            )
        except Exception as e:
            logger.exception(
                "Error storing asset",
                extra={
                    "inventory_id": asset_record.get("InventoryID"),
                    "error": str(e),
                },
            )
            raise

    def delete_asset(self, inventory_id: str) -> None:
        """Delete asset record from DynamoDB."""
        try:
            self.assets_table.delete_item(Key={"InventoryID": inventory_id})
            logger.info(
                "Asset deleted successfully", extra={"inventory_id": inventory_id}
            )
        except Exception as e:
            logger.exception(
                "Error deleting asset",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            raise

    def tag_object(self, bucket: str, key: str, tags: Dict[str, str]) -> None:
        """Apply tags to S3 object."""
        try:
            tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
            self.s3_client.put_object_tagging(
                Bucket=bucket, Key=key, Tagging={"TagSet": tag_set}
            )
        except Exception as e:
            logger.exception(
                "Error tagging S3 object",
                extra={"bucket": bucket, "key": key, "error": str(e)},
            )
            raise

    def should_process_deletion(
        self, bucket: str, key: str, version_id: Optional[str] = None
    ) -> bool:
        """
        Determine if a deletion should be processed based on versioning.
        Only process deletions for the latest version if versioning is enabled.
        """
        try:
            # Check if the bucket has versioning enabled
            try:
                versioning_response = self.s3_client.get_bucket_versioning(
                    Bucket=bucket
                )
                versioning_status = versioning_response.get("Status", "Suspended")

                # If versioning is not enabled or suspended, proceed with normal deletion
                if versioning_status not in ["Enabled"]:
                    return True

            except Exception as e:
                logger.warning(
                    "Could not check versioning status",
                    extra={"bucket": bucket, "error": str(e)},
                )
                return True

            # If we have a version_id from the event, check if it's the latest
            if version_id and version_id != "null":
                try:
                    versions_response = self.s3_client.list_object_versions(
                        Bucket=bucket, Prefix=key, MaxKeys=10
                    )

                    # Filter versions to match exact key
                    exact_versions = [
                        v
                        for v in versions_response.get("Versions", [])
                        if v.get("Key") == key
                    ]

                    if exact_versions:
                        # Sort by LastModified to get the latest version first
                        exact_versions.sort(
                            key=lambda x: x.get("LastModified", datetime.min),
                            reverse=True,
                        )
                        latest_version_id = exact_versions[0].get("VersionId")

                        # Only process if this is the latest version
                        return version_id == latest_version_id

                except Exception as e:
                    logger.warning(
                        "Error checking object versions",
                        extra={"bucket": bucket, "key": key, "error": str(e)},
                    )
                    return False

            return True

        except Exception as e:
            logger.exception(
                "Error in should_process_deletion",
                extra={"bucket": bucket, "key": key, "error": str(e)},
            )
            return False

    def index_asset_for_search(
        self, inventory_id: str, asset_record: Dict[str, Any]
    ) -> None:
        """Index asset in OpenSearch for search functionality."""
        if not self.opensearch_client:
            return

        try:
            # Create search document
            search_doc = {
                "inventory_id": inventory_id,
                "asset_type": asset_record.get("AssetType"),
                "bucket": asset_record.get("Bucket"),
                "object_key": asset_record.get("ObjectKey"),
                "file_hash": asset_record.get("FileHash"),
                "created_at": asset_record.get("CreatedAt"),
                "metadata": asset_record.get("Metadata", {}),
            }

            # Index in OpenSearch
            self.opensearch_client.index(
                index="assets", id=inventory_id, body=search_doc
            )

            logger.info(
                "Asset indexed for search", extra={"inventory_id": inventory_id}
            )

        except Exception as e:
            logger.exception(
                "Error indexing asset for search",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for search indexing errors

    def remove_from_search_index(self, inventory_id: str) -> None:
        """Remove asset from OpenSearch index."""
        if not self.opensearch_client:
            return

        try:
            self.opensearch_client.delete(index="assets", id=inventory_id)
            logger.info(
                "Asset removed from search index", extra={"inventory_id": inventory_id}
            )

        except Exception as e:
            logger.warning(
                "Error removing asset from search index",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for search removal errors

    def store_vector_embeddings(
        self, inventory_id: str, asset_metadata: Dict[str, Any]
    ) -> None:
        """Store vector embeddings in S3 Vector Store (placeholder implementation)."""
        vector_bucket = os.environ.get("S3_VECTOR_STORE_BUCKET")
        if not vector_bucket:
            return

        try:
            # This is a placeholder - actual implementation would generate embeddings
            # and store them in the vector store format
            vector_key = f"vectors/{inventory_id}.json"

            # Placeholder vector data
            vector_data = {
                "inventory_id": inventory_id,
                "embeddings": [],  # Would contain actual vector embeddings
                "metadata": asset_metadata,
            }

            self.s3_client.put_object(
                Bucket=vector_bucket,
                Key=vector_key,
                Body=str(vector_data),
                ContentType="application/json",
            )

            logger.info(
                "Vector embeddings stored", extra={"inventory_id": inventory_id}
            )

        except Exception as e:
            logger.exception(
                "Error storing vector embeddings",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for vector storage errors

    def delete_vector_embeddings(self, inventory_id: str) -> None:
        """Delete vector embeddings from S3 Vector Store."""
        vector_bucket = os.environ.get("S3_VECTOR_STORE_BUCKET")
        if not vector_bucket:
            return

        try:
            vector_key = f"vectors/{inventory_id}.json"

            self.s3_client.delete_object(Bucket=vector_bucket, Key=vector_key)

            logger.info(
                "Vector embeddings deleted", extra={"inventory_id": inventory_id}
            )

        except Exception as e:
            logger.warning(
                "Error deleting vector embeddings",
                extra={"inventory_id": inventory_id, "error": str(e)},
            )
            # Don't fail the main operation for vector deletion errors
