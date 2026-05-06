"""OpenSearch client for Collections Backfill Lambda.

Provides OpenSearch connectivity using IAM Sigv4 auth, following the same
pattern as the existing opensearch_utils.py in the Collections API.

Dependencies (opensearch-py, requests_aws4auth) come from SearchLayer.
"""

import json
import os
import random
import time
from decimal import Decimal

import boto3
from aws_lambda_powertools import Logger
from opensearchpy import OpenSearch, RequestsAWSV4SignerAuth, RequestsHttpConnection

logger = Logger(service="collections-backfill-os-client")


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj == int(obj) else float(obj)
        return super().default(obj)


# Cache for OpenSearch client
_opensearch_client = None
_client_created_at = 0.0
_CLIENT_TTL_SECONDS = (
    45 * 60
)  # Refresh client every 45 minutes (credentials expire ~1h)


def get_opensearch_client() -> OpenSearch:
    """Create and return a cached OpenSearch client with credential TTL.

    The client is cached for performance but refreshed every 45 minutes to
    avoid stale IAM credentials on warm Lambda containers. Temporary
    credentials from the execution role expire after ~1 hour; refreshing
    at 45 minutes provides a safe margin.

    Returns:
        Configured OpenSearch client instance
    """
    global _opensearch_client, _client_created_at

    now = time.time()
    if (
        _opensearch_client is not None
        and (now - _client_created_at) < _CLIENT_TTL_SECONDS
    ):
        return _opensearch_client

    host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
    region = os.environ["OS_DOMAIN_REGION"]

    credentials = boto3.Session().get_credentials()
    auth = RequestsAWSV4SignerAuth(credentials, region, "es")

    _opensearch_client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
        max_retries=2,
        retry_on_timeout=True,
    )
    _client_created_at = now

    logger.info("OpenSearch client initialized successfully")
    return _opensearch_client


def bulk_index(client: OpenSearch, index: str, actions: list) -> dict:
    """Execute a bulk API request.

    Args:
        client: OpenSearch client instance
        index: Target index name
        actions: List of bulk action dicts (each with _op_type, _id, etc.)

    Returns:
        OpenSearch bulk API response dict
    """
    if not actions:
        return {"errors": False, "items": []}

    body = ""
    for action in actions:
        op_type = action.get("_op_type", "index")

        if op_type == "delete":
            body += (
                json.dumps({"delete": {"_index": index, "_id": action["_id"]}}) + "\n"
            )
        else:
            meta = {"index": {"_index": index, "_id": action["_id"]}}
            body += json.dumps(meta) + "\n"
            body += json.dumps(action["_source"], cls=DecimalEncoder) + "\n"

    response = client.bulk(body=body)
    return response


def delete_document(client: OpenSearch, index: str, doc_id: str) -> None:
    """Delete a single document by ID.

    Args:
        client: OpenSearch client instance
        index: Target index name
        doc_id: Document ID to delete
    """
    try:
        client.delete(index=index, id=doc_id)
        logger.info("Document deleted", extra={"index": index, "doc_id": doc_id})
    except Exception as e:
        # 404 is expected if document doesn't exist (e.g., race condition)
        if hasattr(e, "status_code") and e.status_code == 404:
            logger.warning(
                "Document not found for deletion",
                extra={"index": index, "doc_id": doc_id},
            )
        else:
            raise


def create_index_if_not_exists(client: OpenSearch, index: str, mapping: dict) -> bool:
    """Create index with mapping if it doesn't already exist.

    Args:
        client: OpenSearch client instance
        index: Index name to create
        mapping: Index mapping/settings dict

    Returns:
        True if index was created, False if it already existed
    """
    if client.indices.exists(index=index):
        logger.info("Index already exists", extra={"index": index})
        return False

    client.indices.create(index=index, body=mapping)
    logger.info("Index created", extra={"index": index})
    return True


class DocumentNotFoundError(Exception):
    """Raised when an update targets a document that doesn't exist yet."""


def update_document(client: OpenSearch, index: str, doc_id: str, script: dict) -> None:
    """Update a document using a painless script.

    Raises DocumentNotFoundError on 404 so the caller can report the record
    as a batchItemFailure for retry.

    Args:
        client: OpenSearch client instance
        index: Target index name
        doc_id: Document ID to update
        script: Painless script dict with 'source' and 'params' keys

    Raises:
        DocumentNotFoundError: If the target document doesn't exist (404).
        Exception: For any other OpenSearch error.
    """
    try:
        client.update(index=index, id=doc_id, body={"script": script})
        logger.info("Document updated", extra={"index": index, "doc_id": doc_id})
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code == 404:
            logger.warning(
                "Document not found for update — will be retried via batchItemFailure",
                extra={"index": index, "doc_id": doc_id},
            )
            raise DocumentNotFoundError(
                f"Document {doc_id} not found in index {index}"
            ) from e
        else:
            raise


def bulk_index_with_retry(
    client: OpenSearch, index: str, actions: list, max_retries: int = 3
) -> dict:
    """Execute a bulk API request with retry logic and exponential backoff.

    Args:
        client: OpenSearch client instance
        index: Target index name
        actions: List of bulk action dicts
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        OpenSearch bulk API response dict

    Raises:
        Exception: If all retry attempts are exhausted
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            response = bulk_index(client, index, actions)
            return response
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Bulk index attempt {attempt + 1} failed, retrying in {delay:.1f}s",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay": delay,
                        "error": str(e),
                    },
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"All {max_retries + 1} bulk index attempts failed",
                    extra={"error": str(e), "action_count": len(actions)},
                )

    raise last_exception
