"""
Asset Deletion Lambda Handler
─────────────────────────────
• Deletes S3 objects, DynamoDB record **and matching OpenSearch docs**
• Uses low-level SigV4-signed HTTPS calls (no opensearch-py)
• Structured logging, tracing, metrics with AWS Lambda Powertools
"""

from __future__ import annotations

import http.client
import json
import os
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# ── Powertools ───────────────────────────────────────────────────────────────
logger = Logger(service="asset-deletion-service")
tracer = Tracer(service="asset-deletion-service")
metrics = Metrics(namespace="AssetDeletionService", service="asset-deletion-service")

# ── AWS clients / resources ──────────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])

# ── OpenSearch settings ──────────────────────────────────────────────────────
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
INDEX_NAME = os.getenv("INDEX_NAME", "media")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
OPENSEARCH_SERVICE = os.getenv("OPENSEARCH_SERVICE", "es")  # "es" for both ES & OS

# ── S3 Vector Store settings ─────────────────────────────────────────────────
VECTOR_BUCKET_NAME = os.getenv("VECTOR_BUCKET_NAME", "")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "media-vectors")

_session = boto3.Session()
_credentials = _session.get_credentials()


# ── Low-level SigV4 helper ───────────────────────────────────────────────────
def _signed_request(
    method: str,
    url: str,
    credentials,
    service: str,
    region: str,
    payload: dict | None = None,
    extra_headers: dict | None = None,
    timeout: int = 30,
) -> tuple[int, str]:
    """
    Build, sign and send an HTTPS request with SigV4 auth.
    Returns (status_code, response_body)
    """
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
    conn.request(
        prepared.method, path, body=prepared.body, headers=dict(prepared.headers)
    )
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    return resp.status, body


# ── S3 Vector Store client ───────────────────────────────────────────────────
def get_s3_vector_client():
    """Initialize S3 Vector Store client"""
    try:
        session = boto3.Session()
        return session.client("s3vectors", region_name=AWS_REGION)
    except Exception as e:
        logger.error(f"Failed to initialize S3 Vector client: {e}")
        raise


# ── Utilities ────────────────────────────────────────────────────────────────
def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse S3 URI into bucket and key components"""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None, None

    # Remove s3:// prefix and split
    path = s3_uri[5:]  # Remove "s3://"
    parts = path.split("/", 1)

    if len(parts) != 2:
        return None, None

    return parts[0], parts[1]  # bucket, key


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class AssetDeletionError(Exception):
    def __init__(
        self, message: str, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        super().__init__(message)
        self.status_code = status_code


class DeleteRequest(BaseModel):
    inventoryId: str = Field(..., description="Inventory ID of the asset to delete")


@tracer.capture_method
def get_asset(inventory_id: str) -> Dict[str, Any]:
    try:
        resp = table.get_item(Key={"InventoryID": inventory_id})
        if "Item" not in resp:
            raise AssetDeletionError(
                f"Asset with ID {inventory_id} not found", HTTPStatus.NOT_FOUND
            )
        return json.loads(json.dumps(resp["Item"], cls=DecimalEncoder))
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        raise AssetDeletionError(f"Failed to retrieve asset: {e}")


@tracer.capture_method
def delete_s3_objects(asset: Dict[str, Any]) -> None:
    try:
        # Main representation
        main = asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]
        s3.delete_object(Bucket=main["Bucket"], Key=main["ObjectKey"]["FullPath"])
        logger.info(
            "Deleted main representation",
            extra={"bucket": main["Bucket"], "key": main["ObjectKey"]["FullPath"]},
        )

        # Derived
        for rep in asset.get("DerivedRepresentations", []):
            pl = rep.get("StorageInfo", {}).get("PrimaryLocation")
            if not pl:
                continue
            s3.delete_object(Bucket=pl["Bucket"], Key=pl["ObjectKey"]["FullPath"])
            logger.info(
                "Deleted derived representation",
                extra={"bucket": pl["Bucket"], "key": pl["ObjectKey"]["FullPath"]},
            )

        # Transcript files
        if transcript_uri := asset.get("TranscriptionS3Uri"):
            transcript_bucket, transcript_key = _parse_s3_uri(transcript_uri)
            if transcript_bucket and transcript_key:
                s3.delete_object(Bucket=transcript_bucket, Key=transcript_key)
                logger.info(
                    "Deleted transcript file",
                    extra={"bucket": transcript_bucket, "key": transcript_key},
                )

    except ClientError as e:
        logger.error(f"S3 deletion error: {e}")
        raise AssetDeletionError(f"Failed to delete S3 objects: {e}")


@tracer.capture_method
def delete_opensearch_docs(asset: Dict[str, Any]) -> None:
    """
    Delete OpenSearch documents whose DigitalSourceAsset.ID equals the asset’s ID.
    Uses _delete_by_query with SigV4-signed request.
    """
    if not OPENSEARCH_ENDPOINT:
        logger.info("OPENSEARCH_ENDPOINT not set – skipping OpenSearch deletion.")
        return

    host = OPENSEARCH_ENDPOINT.lstrip("https://").lstrip("http://")
    dsa_id = asset.get("DigitalSourceAsset", {}).get("ID")
    if not dsa_id:
        logger.warning("DigitalSourceAsset.ID missing – skipping OpenSearch deletion.")
        return

    query = {"query": {"term": {"DigitalSourceAsset.ID": dsa_id}}}

    url = f"https://{host}/{INDEX_NAME}/_delete_by_query?refresh=true&conflicts=proceed"
    logger.info(
        "Executing _delete_by_query",
        extra={"url": url, "query": query, "dsa_id": dsa_id},
    )

    status, body = _signed_request(
        "POST",
        url,
        _credentials,
        OPENSEARCH_SERVICE,
        AWS_REGION,
        payload=query,
        timeout=60,
    )

    if status not in (200, 202):
        logger.error(
            "OpenSearch deletion failed",
            extra={"status": status, "body": body, "dsa_id": dsa_id},
        )
        raise AssetDeletionError(f"Failed to delete OpenSearch docs (status {status})")

    deleted = 0
    try:
        deleted = json.loads(body).get("deleted", 0)
    except (ValueError, AttributeError):
        pass

    logger.info(
        "OpenSearch deletion complete",
        extra={"deleted_docs": deleted, "dsa_id": dsa_id},
    )
    metrics.add_metric("OpenSearchDocsDeleted", MetricUnit.Count, deleted)


@tracer.capture_method
def delete_s3_vectors(inventory_id: str) -> int:
    """
    Delete S3 vectors associated with inventory_id.
    Since list_vectors doesn't support prefix filtering, we'll list all vectors
    and filter by inventory_id in the metadata.
    """
    if not VECTOR_BUCKET_NAME:
        logger.info("VECTOR_BUCKET_NAME not set – skipping S3 vector deletion")
        return 0

    try:
        client = get_s3_vector_client()

        # List all vectors with metadata to filter by inventory_id
        # We need returnMetadata=True to access the inventory_id field
        vectors_to_delete = []
        next_token = None

        while True:
            list_params = {
                "vectorBucketName": VECTOR_BUCKET_NAME,
                "indexName": VECTOR_INDEX_NAME,
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
            logger.info(f"No vectors found for inventory_id: {inventory_id}")
            return 0

        logger.info(
            f"Found {len(vectors_to_delete)} vectors to delete for {inventory_id}",
            extra={"keys": vectors_to_delete[:10]},  # Log first 10 keys for debugging
        )

        # Batch delete vectors (S3 Vectors supports batch deletion)
        client.delete_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=VECTOR_INDEX_NAME,
            keys=vectors_to_delete,
        )

        logger.info(
            f"Successfully deleted {len(vectors_to_delete)} vectors for {inventory_id}"
        )
        metrics.add_metric("VectorsDeleted", MetricUnit.Count, len(vectors_to_delete))
        return len(vectors_to_delete)

    except Exception as e:
        logger.error(f"S3 vector deletion failed for {inventory_id}: {e}")
        metrics.add_metric("VectorDeletionErrors", MetricUnit.Count, 1)
        # Don't raise - vector deletion failure shouldn't block asset deletion
        return 0


def create_response(
    status: int, msg: str, data: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    body = {
        "status": "success" if status < 400 else "error",
        "message": msg,
        "data": data or {},
    }

    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


# ── Lambda entrypoint ────────────────────────────────────────────────────────
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: APIGatewayProxyEvent, _ctx: LambdaContext) -> Dict[str, Any]:
    inventory_id = None
    try:
        inventory_id = event.get("pathParameters", {}).get("id")
        if not inventory_id:
            raise AssetDeletionError("Missing inventory ID", HTTPStatus.BAD_REQUEST)

        # 1. Fetch asset (Dynamo)
        asset = get_asset(inventory_id)

        # 2. Delete from S3
        delete_s3_objects(asset)

        # 3. Delete DynamoDB row
        table.delete_item(Key={"InventoryID": inventory_id})
        metrics.add_metric("AssetDeletionsDynamo", MetricUnit.Count, 1)

        # 4. Delete from OpenSearch
        delete_opensearch_docs(asset)

        # 5. Delete S3 vectors
        vector_count = delete_s3_vectors(inventory_id)

        return create_response(
            HTTPStatus.OK,
            "Asset deleted successfully",
            {"inventoryId": inventory_id, "vectorsDeleted": vector_count},
        )

    except AssetDeletionError as e:
        logger.warning(
            "Asset deletion failed",
            extra={"inventory_id": inventory_id, "error": str(e)},
        )
        return create_response(e.status_code, str(e))

    except Exception:
        logger.exception(
            "Unexpected error during asset deletion",
            extra={"inventory_id": inventory_id},
        )
        metrics.add_metric("UnexpectedErrors", MetricUnit.Count, 1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error"
        )
