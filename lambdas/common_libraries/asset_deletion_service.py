"""
Centralized Asset Deletion Service
===================================
Provides a unified interface for deleting assets across the MediaLake system.
Used by both API delete endpoint and S3 connector delete events.

This service handles:
- S3 object deletion (main + derived representations)
- DynamoDB record deletion
- OpenSearch document deletion
- S3 vector deletion
- External service cleanup (Coactive, etc.)
- Event publishing
"""

from __future__ import annotations

import http.client
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config
from botocore.exceptions import ClientError
from external_service_manager import MediaLakeExternalServiceManager

logger = Logger(service="asset-deletion-service", child=True)
tracer = Tracer(service="asset-deletion-service")
metrics = Metrics(namespace="AssetDeletionService", service="asset-deletion-service")

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
eventbridge = boto3.client("events")

OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
INDEX_NAME = os.getenv("INDEX_NAME", "media")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
OPENSEARCH_SERVICE = os.getenv("OPENSEARCH_SERVICE", "es")
VECTOR_BUCKET_NAME = os.getenv("VECTOR_BUCKET_NAME", "")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "media-vectors")
DYNAMODB_TABLE_NAME = os.getenv("MEDIALAKE_ASSET_TABLE", "")

_session = boto3.Session()
_credentials = _session.get_credentials()


@dataclass
class DeletionResult:
    """Result of asset deletion operation"""

    success: bool
    inventory_id: str
    s3_objects_deleted: int = 0
    opensearch_docs_deleted: int = 0
    vectors_deleted: int = 0
    external_services_deleted: list = None
    dynamodb_deleted: bool = False
    event_published: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        if self.external_services_deleted is None:
            self.external_services_deleted = []


class AssetDeletionError(Exception):
    """Custom exception for asset deletion errors"""

    def __init__(self, message: str, inventory_id: str = None):
        super().__init__(message)
        self.inventory_id = inventory_id


class AssetDeletionService:
    """
    Centralized service for asset deletion operations.

    Usage:
        service = AssetDeletionService(
            dynamodb_table_name="my-table",
            logger=logger,
            metrics=metrics
        )
        result = service.delete_asset(
            inventory_id="asset-123",
            asset_data=asset_dict  # optional, will fetch if not provided
        )
    """

    def __init__(
        self,
        dynamodb_table_name: str = None,
        logger: Logger = None,
        metrics: Metrics = None,
        tracer: Tracer = None,
    ):
        self.logger = logger or globals()["logger"]
        self.metrics = metrics or globals()["metrics"]
        self.tracer = tracer or globals()["tracer"]
        self.table_name = dynamodb_table_name or DYNAMODB_TABLE_NAME
        self.table = dynamodb.Table(self.table_name)
        self.external_manager = MediaLakeExternalServiceManager(
            self.logger, self.metrics
        )

    @tracer.capture_method
    def delete_asset(
        self,
        inventory_id: str,
        asset_data: Dict[str, Any] = None,
        publish_event: bool = True,
    ) -> DeletionResult:
        """
        Delete an asset and all associated resources.

        Args:
            inventory_id: The asset's inventory ID
            asset_data: Optional pre-fetched asset data (will fetch if not provided)
            publish_event: Whether to publish deletion event to EventBridge

        Returns:
            DeletionResult with details of what was deleted

        Raises:
            AssetDeletionError: If deletion fails
        """
        result = DeletionResult(success=False, inventory_id=inventory_id)

        try:
            self.logger.info(f"Starting deletion for asset: {inventory_id}")

            # 1. Fetch asset data if not provided
            if asset_data is None:
                asset_data = self._fetch_asset(inventory_id)

            # 2. Delete S3 objects (main + derived + transcripts)
            result.s3_objects_deleted = self._delete_s3_objects(asset_data)

            # 3. Delete OpenSearch documents
            result.opensearch_docs_deleted = self._delete_opensearch_docs(inventory_id)

            # 4. Delete S3 vectors
            result.vectors_deleted = self._delete_s3_vectors(inventory_id)

            # 5. Delete from external services
            result.external_services_deleted = self._delete_external_services(
                asset_data, inventory_id
            )

            # 6. Delete DynamoDB record
            self._delete_dynamodb_record(inventory_id)
            result.dynamodb_deleted = True

            # 7. Publish deletion event
            if publish_event:
                self._publish_deletion_event(inventory_id)
                result.event_published = True

            # Mark as successful
            result.success = True

            self.logger.info(
                f"Successfully deleted asset {inventory_id}",
                extra={
                    "s3_objects": result.s3_objects_deleted,
                    "opensearch_docs": result.opensearch_docs_deleted,
                    "vectors": result.vectors_deleted,
                },
            )

            self.metrics.add_metric("AssetDeletionSuccess", MetricUnit.Count, 1)

            return result

        except Exception as e:
            self.logger.error(
                f"Failed to delete asset {inventory_id}: {str(e)}", exc_info=True
            )
            result.error = str(e)
            self.metrics.add_metric("AssetDeletionFailure", MetricUnit.Count, 1)
            raise AssetDeletionError(f"Failed to delete asset: {str(e)}", inventory_id)

    @tracer.capture_method
    def _fetch_asset(self, inventory_id: str) -> Dict[str, Any]:
        """Fetch asset data from DynamoDB"""
        try:
            response = self.table.get_item(Key={"InventoryID": inventory_id})
            if "Item" not in response:
                raise AssetDeletionError(
                    f"Asset {inventory_id} not found in DynamoDB", inventory_id
                )

            # Convert Decimal to standard types
            return json.loads(json.dumps(response["Item"], cls=DecimalEncoder))
        except ClientError as e:
            self.logger.error(f"DynamoDB error fetching asset: {e}")
            raise AssetDeletionError(f"Failed to fetch asset: {e}", inventory_id)

    @tracer.capture_method
    def _delete_s3_objects(self, asset: Dict[str, Any]) -> int:
        """Delete all S3 objects associated with the asset"""
        deleted_count = 0

        try:
            # Delete main representation
            main = asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                "PrimaryLocation"
            ]
            bucket = main["Bucket"]
            key = main["ObjectKey"]["FullPath"]

            s3.delete_object(Bucket=bucket, Key=key)
            deleted_count += 1
            self.logger.info(f"Deleted main representation: s3://{bucket}/{key}")

            # Delete derived representations
            for rep in asset.get("DerivedRepresentations", []):
                pl = rep.get("StorageInfo", {}).get("PrimaryLocation")
                if pl:
                    s3.delete_object(
                        Bucket=pl["Bucket"], Key=pl["ObjectKey"]["FullPath"]
                    )
                    deleted_count += 1
                    self.logger.info(
                        f"Deleted derived representation: s3://{pl['Bucket']}/{pl['ObjectKey']['FullPath']}"
                    )

            # Delete transcript files
            if transcript_uri := asset.get("TranscriptionS3Uri"):
                transcript_bucket, transcript_key = self._parse_s3_uri(transcript_uri)
                if transcript_bucket and transcript_key:
                    s3.delete_object(Bucket=transcript_bucket, Key=transcript_key)
                    deleted_count += 1
                    self.logger.info(f"Deleted transcript: {transcript_uri}")

            self.metrics.add_metric("S3ObjectsDeleted", MetricUnit.Count, deleted_count)
            return deleted_count

        except ClientError as e:
            self.logger.error(f"S3 deletion error: {e}")
            raise AssetDeletionError(f"Failed to delete S3 objects: {e}")

    @tracer.capture_method
    def _delete_opensearch_docs(self, inventory_id: str) -> int:
        """Delete OpenSearch documents for the asset"""
        if not OPENSEARCH_ENDPOINT:
            self.logger.info(
                "OPENSEARCH_ENDPOINT not set, skipping OpenSearch deletion"
            )
            return 0

        try:
            host = OPENSEARCH_ENDPOINT.lstrip("https://").lstrip("http://")
            query = {"query": {"match_phrase": {"InventoryID": inventory_id}}}

            url = f"https://{host}/{INDEX_NAME}/_delete_by_query?refresh=true&conflicts=proceed"

            status, body = self._signed_request(
                "POST",
                url,
                _credentials,
                OPENSEARCH_SERVICE,
                AWS_REGION,
                payload=query,
                timeout=60,
            )

            if status not in (200, 202):
                self.logger.error(
                    f"OpenSearch deletion failed: status={status}, body={body}"
                )
                raise AssetDeletionError(
                    f"OpenSearch deletion failed (status {status})"
                )

            deleted = 0
            try:
                deleted = json.loads(body).get("deleted", 0)
            except (ValueError, AttributeError):
                pass

            self.logger.info(
                f"Deleted {deleted} OpenSearch documents for {inventory_id}"
            )
            self.metrics.add_metric("OpenSearchDocsDeleted", MetricUnit.Count, deleted)

            return deleted

        except Exception as e:
            self.logger.error(f"OpenSearch deletion error: {e}")
            # Don't fail the entire deletion for OpenSearch errors
            return 0

    @tracer.capture_method
    def _delete_s3_vectors(self, inventory_id: str) -> int:
        """Delete S3 vectors associated with the asset"""
        if not VECTOR_BUCKET_NAME:
            self.logger.info("VECTOR_BUCKET_NAME not set, skipping vector deletion")
            return 0

        try:
            # Configure retry strategy for transient errors
            retry_config = Config(
                retries={
                    "max_attempts": 10,
                    "mode": "adaptive",
                },
                connect_timeout=5,
                read_timeout=60,
            )

            client = boto3.client(
                "s3vectors", region_name=AWS_REGION, config=retry_config
            )

            # Find vectors by metadata
            vectors_to_delete = []
            next_token = None

            while True:
                params = {
                    "vectorBucketName": VECTOR_BUCKET_NAME,
                    "indexName": VECTOR_INDEX_NAME,
                    "returnMetadata": True,
                    "maxResults": 500,
                }

                if next_token:
                    params["nextToken"] = next_token

                response = client.list_vectors(**params)

                for vector in response.get("vectors", []):
                    metadata = vector.get("metadata", {})
                    if (
                        isinstance(metadata, dict)
                        and metadata.get("inventory_id") == inventory_id
                    ):
                        vectors_to_delete.append(vector["key"])

                next_token = response.get("nextToken")
                if not next_token:
                    break

            if vectors_to_delete:
                client.delete_vectors(
                    vectorBucketName=VECTOR_BUCKET_NAME,
                    indexName=VECTOR_INDEX_NAME,
                    keys=vectors_to_delete,
                )
                self.logger.info(
                    f"Deleted {len(vectors_to_delete)} vectors for {inventory_id}"
                )

            self.metrics.add_metric(
                "VectorsDeleted", MetricUnit.Count, len(vectors_to_delete)
            )
            return len(vectors_to_delete)

        except Exception as e:
            self.logger.error(f"S3 vector deletion error: {e}")
            # Don't fail the entire deletion for vector errors
            return 0

    @tracer.capture_method
    def _delete_external_services(
        self, asset: Dict[str, Any], inventory_id: str
    ) -> list:
        """Delete asset from external services like Coactive"""
        try:
            results = self.external_manager.delete_asset_from_external_services(
                asset, inventory_id
            )
            if results:
                self.logger.info(f"External service deletion results: {results}")
            return results or []
        except Exception as e:
            self.logger.error(f"External service deletion error: {e}")
            # Don't fail the entire deletion for external service errors
            return []

    @tracer.capture_method
    def _delete_dynamodb_record(self, inventory_id: str) -> None:
        """Delete the asset record from DynamoDB"""
        try:
            self.table.delete_item(Key={"InventoryID": inventory_id})
            self.logger.info(f"Deleted DynamoDB record for {inventory_id}")
            self.metrics.add_metric("DynamoDBRecordsDeleted", MetricUnit.Count, 1)
        except ClientError as e:
            self.logger.error(f"DynamoDB deletion error: {e}")
            raise AssetDeletionError(
                f"Failed to delete DynamoDB record: {e}", inventory_id
            )

    @tracer.capture_method
    def _publish_deletion_event(self, inventory_id: str) -> None:
        """Publish asset deletion event to EventBridge"""
        try:
            eventbridge.put_events(
                Entries=[
                    {
                        "Source": "medialake.assets",
                        "DetailType": "AssetDeleted",
                        "Detail": json.dumps(
                            {
                                "inventoryId": inventory_id,
                                "timestamp": self._get_timestamp(),
                            }
                        ),
                    }
                ]
            )
            self.logger.info(f"Published deletion event for {inventory_id}")
        except Exception as e:
            self.logger.error(f"Failed to publish deletion event: {e}")
            # Don't fail the entire deletion for event publishing errors

    @staticmethod
    def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
        """Parse S3 URI into bucket and key components"""
        if not s3_uri or not s3_uri.startswith("s3://"):
            return None, None

        path = s3_uri[5:]
        parts = path.split("/", 1)

        if len(parts) != 2:
            return None, None

        return parts[0], parts[1]

    @staticmethod
    def _signed_request(
        method: str,
        url: str,
        credentials,
        service: str,
        region: str,
        payload: dict = None,
        extra_headers: dict = None,
        timeout: int = 30,
    ) -> tuple[int, str]:
        """Build, sign and send an HTTPS request with SigV4 auth"""
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)

        req = AWSRequest(
            method=method,
            url=url,
            data=json.dumps(payload) if payload else None,
            headers=headers,
        )
        SigV4Auth(credentials, service, region).add_auth(req)
        prepared = req.prepare()

        parsed = urlparse(prepared.url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        conn = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=timeout
        )
        try:
            conn.request(
                prepared.method,
                path,
                body=prepared.body,
                headers=dict(prepared.headers),
            )
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            return resp.status, body
        finally:
            conn.close()

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime

        return datetime.utcnow().isoformat()


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)
