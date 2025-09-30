"""
TwelveLabs External Service Plugin
=================================
Plugin for handling TwelveLabs asset deletion operations.
This handles deletion of embeddings from OpenSearch and S3 Vector stores.
"""

import http.client
import json
import os
from typing import Any, Dict
from urllib.parse import urlparse

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from search_provider_models import AssetDeletionResult, ExternalServicePlugin


class TwelveLabsPlugin(ExternalServicePlugin):
    """Plugin for TwelveLabs external service integration"""

    def __init__(self, config: Dict[str, Any], logger, metrics):
        super().__init__(config, logger, metrics)

        # AWS clients
        self._session = boto3.Session()
        self._credentials = self._session.get_credentials()

        # Environment configuration
        self.opensearch_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
        self.opensearch_index = os.environ.get("INDEX_NAME", "media")
        self.opensearch_service = os.environ.get("OPENSEARCH_SERVICE", "es")
        self.aws_region = os.environ.get("AWS_REGION", "us-east-1")
        self.vector_bucket_name = os.environ.get("VECTOR_BUCKET_NAME", "")
        self.vector_index_name = os.environ.get("VECTOR_INDEX_NAME", "media-vectors")

        self._s3_vector_client = None

    def get_service_name(self) -> str:
        """Return the name of the external service"""
        return "twelvelabs"

    def is_available(self) -> bool:
        """Check if TwelveLabs service is available and properly configured"""
        try:
            # Check if we have either OpenSearch or S3 Vector Store configured
            has_opensearch = bool(self.opensearch_endpoint)
            has_s3_vectors = bool(self.vector_bucket_name)

            if not has_opensearch and not has_s3_vectors:
                self.logger.warning(
                    "Neither OpenSearch nor S3 Vector Store configured for TwelveLabs"
                )
                return False

            return True

        except Exception as e:
            self.logger.warning(f"TwelveLabs availability check failed: {str(e)}")
            return False

    def supports_asset_type(self, asset_type: str) -> bool:
        """Check if this plugin supports the given asset type"""
        # TwelveLabs supports images, videos, and audio
        supported_types = ["image", "video", "audio"]
        return asset_type.lower() in supported_types

    def delete_asset(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> AssetDeletionResult:
        """Delete asset embeddings from TwelveLabs-related storage"""
        try:
            asset_type = (
                asset_record.get("DigitalSourceAsset", {}).get("Type", "").lower()
            )
            asset_id = asset_record.get("DigitalSourceAsset", {}).get("ID", "")

            if not self.supports_asset_type(asset_type):
                return AssetDeletionResult(
                    success=True,  # Not an error, just not supported
                    message=f"Asset type '{asset_type}' not supported by TwelveLabs",
                    deleted_count=0,
                )

            deleted_count = 0
            errors = []

            # Delete from OpenSearch if configured
            if self.opensearch_endpoint:
                try:
                    opensearch_deleted = self._delete_from_opensearch(asset_id)
                    deleted_count += opensearch_deleted
                    if opensearch_deleted > 0:
                        self.logger.info(
                            f"Deleted {opensearch_deleted} documents from OpenSearch for asset {asset_id}"
                        )
                except Exception as e:
                    error_msg = f"Error deleting from OpenSearch: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            # Delete from S3 Vector Store if configured
            if self.vector_bucket_name:
                try:
                    vectors_deleted = self._delete_from_s3_vectors(inventory_id)
                    deleted_count += vectors_deleted
                    if vectors_deleted > 0:
                        self.logger.info(
                            f"Deleted {vectors_deleted} vectors from S3 Vector Store for inventory {inventory_id}"
                        )
                except Exception as e:
                    error_msg = f"Error deleting from S3 Vector Store: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            # Record metrics
            if deleted_count > 0:
                self.metrics.add_metric(
                    name="TwelveLabsEmbeddingsDeleted",
                    unit="Count",
                    value=deleted_count,
                )

            if errors:
                self.metrics.add_metric(
                    name="TwelveLabsDeletionErrors", unit="Count", value=len(errors)
                )

            success = deleted_count > 0 or len(errors) == 0
            message = f"Deleted {deleted_count} TwelveLabs embeddings/vectors"
            if errors:
                message += f" with {len(errors)} errors"

            return AssetDeletionResult(
                success=success,
                message=message,
                deleted_count=deleted_count,
                errors=errors,
            )

        except Exception as e:
            self.logger.error(
                f"TwelveLabs asset deletion failed for {inventory_id}: {str(e)}"
            )
            self.metrics.add_metric(
                name="TwelveLabsDeletionErrors", unit="Count", value=1
            )
            return AssetDeletionResult(
                success=False,
                message=f"TwelveLabs deletion failed: {str(e)}",
                errors=[str(e)],
            )

    def _delete_from_opensearch(self, asset_id: str) -> int:
        """Delete embeddings from OpenSearch"""
        if not self.opensearch_endpoint:
            return 0

        host = self.opensearch_endpoint.lstrip("https://").lstrip("http://")
        url = f"https://{host}/{self.opensearch_index}/_delete_by_query?refresh=true&conflicts=proceed"
        query = {"query": {"term": {"DigitalSourceAsset.ID": asset_id}}}

        status, body = self._signed_request("POST", url, payload=query)

        if status not in (200, 202):
            raise Exception(f"OpenSearch deletion failed (status={status}): {body}")

        deleted = 0
        try:
            deleted = json.loads(body).get("deleted", 0)
        except Exception:
            pass

        return deleted

    def _delete_from_s3_vectors(self, inventory_id: str) -> int:
        """Delete vectors from S3 Vector Store"""
        if not self.vector_bucket_name:
            return 0

        try:
            client = self._get_s3_vector_client()

            # List all vectors with metadata to filter by inventory_id
            vectors_to_delete = []
            next_token = None

            while True:
                list_params = {
                    "vectorBucketName": self.vector_bucket_name,
                    "indexName": self.vector_index_name,
                    "returnMetadata": True,
                    "maxResults": 500,  # Process in batches
                }

                if next_token:
                    list_params["nextToken"] = next_token

                response = client.list_vectors(**list_params)
                vectors = response.get("vectors", [])

                # Filter vectors by inventory_id in metadata
                for vector in vectors:
                    metadata = vector.get("metadata", {})
                    if (
                        isinstance(metadata, dict)
                        and metadata.get("inventory_id") == inventory_id
                    ):
                        vectors_to_delete.append(vector["key"])

                next_token = response.get("nextToken")
                if not next_token:
                    break

            if not vectors_to_delete:
                return 0

            # Batch delete vectors
            client.delete_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=self.vector_index_name,
                keys=vectors_to_delete,
            )

            return len(vectors_to_delete)

        except Exception as e:
            self.logger.error(f"S3 vector deletion failed for {inventory_id}: {e}")
            raise

    def _get_s3_vector_client(self):
        """Get S3 Vector Store client"""
        if self._s3_vector_client is None:
            try:
                self._s3_vector_client = boto3.client(
                    "s3vectors", region_name=self.aws_region
                )
            except Exception as e:
                raise Exception(f"Failed to initialize S3 Vector client: {e}")

        return self._s3_vector_client

    def _signed_request(
        self, method: str, url: str, payload: dict = None, timeout: int = 60
    ) -> tuple[int, str]:
        """Build, sign and send an HTTPS request with SigV4 auth"""
        headers = {"Content-Type": "application/json"}
        if payload:
            body = json.dumps(payload)
        else:
            body = None

        req = AWSRequest(method=method, url=url, data=body, headers=headers)

        SigV4Auth(self._credentials, self.opensearch_service, self.aws_region).add_auth(
            req
        )

        prepared = req.prepare()

        parsed = urlparse(prepared.url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        conn = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=timeout
        )
        conn.request(
            prepared.method, path, body=prepared.body, headers=dict(prepared.headers)
        )
        resp = conn.getresponse()
        resp_body = resp.read().decode("utf-8")
        conn.close()
        return resp.status, resp_body
