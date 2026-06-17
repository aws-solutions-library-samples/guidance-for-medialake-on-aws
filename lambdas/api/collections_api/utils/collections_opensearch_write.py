"""Write-through utilities for indexing collection documents directly to OpenSearch.

Provides synchronous write-through to OpenSearch after DynamoDB writes succeed,
eliminating the eventual consistency gap between DynamoDB and OpenSearch for
collection CRUD operations. The DynamoDB Streams sync pipeline remains as a
redundant safety net.

Uses ``refresh="wait_for"`` so the document is searchable immediately after
the call returns (~1s overhead, acceptable for infrequent collection CRUD).
"""

import os
from typing import Any, Dict

from aws_lambda_powertools import Logger
from utils.opensearch_utils import get_opensearch_client

logger = Logger(service="collections-opensearch-write")

COLLECTIONS_INDEX_NAME = os.environ.get("COLLECTIONS_INDEX_NAME", "")


def _build_collection_document(
    collection_id: str,
    collection_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an OpenSearch document from collection attributes.

    Mirrors the field mapping in
    ``lambdas/sync/collections_sync/document_transformer.py::transform_collection``
    so that write-through documents are identical to stream-synced ones.
    """
    doc: Dict[str, Any] = {
        "id": collection_id,
        "name": collection_dict.get("name", ""),
        "description": collection_dict.get("description"),
        "ownerId": collection_dict.get("ownerId", ""),
        "status": collection_dict.get("status", "unknown"),
        "isPublic": collection_dict.get("isPublic", False),
        "collectionTypeId": collection_dict.get("collectionTypeId"),
        "tags": collection_dict.get("tags"),
        "childCollectionCount": collection_dict.get("childCollectionCount", 0),
        "itemCount": collection_dict.get("itemCount", 0),
        "sharedWithUserIds": collection_dict.get("sharedWithUserIds", []),
        "createdAt": collection_dict.get("createdAt", ""),
        "updatedAt": collection_dict.get("updatedAt", ""),
        "thumbnailType": collection_dict.get("thumbnailType"),
        "thumbnailValue": collection_dict.get("thumbnailValue"),
        "thumbnailS3Key": collection_dict.get("thumbnailS3Key"),
        "customMetadata": collection_dict.get("customMetadata"),
        "expiresAt": collection_dict.get("expiresAt"),
        "documentType": "collection",
    }

    # Only include parentId when present — omitting it ensures OpenSearch's
    # "exists" query correctly identifies root collections.
    parent_id = collection_dict.get("parentId")
    if parent_id:
        doc["parentId"] = parent_id

    return doc


def index_collection(
    collection_id: str,
    collection_dict: Dict[str, Any],
) -> bool:
    """Index (create or overwrite) a collection document in OpenSearch.

    Args:
        collection_id: The collection ID (without the ``COLL#`` prefix).
        collection_dict: Flat dict of collection attributes.

    Returns:
        True if the document was indexed successfully, False on failure.
    """
    client = get_opensearch_client()
    if not client or not COLLECTIONS_INDEX_NAME:
        logger.warning(
            "OpenSearch write-through skipped — client or index not configured"
        )
        return False

    doc = _build_collection_document(collection_id, collection_dict)

    try:
        client.index(
            index=COLLECTIONS_INDEX_NAME,
            id=collection_id,
            body=doc,
            refresh="wait_for",
        )
        logger.info(
            "Collection indexed via write-through",
            extra={"collection_id": collection_id},
        )
        return True
    except Exception as e:
        # Non-fatal — the DynamoDB stream sync will catch up
        logger.warning(
            "OpenSearch write-through failed — stream sync will retry",
            extra={"collection_id": collection_id, "error": str(e)},
        )
        return False


def update_collection_document(
    collection_id: str,
    updated_fields: Dict[str, Any],
) -> bool:
    """Partially update a collection document in OpenSearch.

    Uses the OpenSearch Update API with ``doc`` merge semantics so only the
    supplied fields are overwritten.

    Args:
        collection_id: The collection ID (without the ``COLL#`` prefix).
        updated_fields: Dict of field names to new values.

    Returns:
        True on success, False on failure.
    """
    client = get_opensearch_client()
    if not client or not COLLECTIONS_INDEX_NAME:
        logger.warning(
            "OpenSearch write-through skipped — client or index not configured"
        )
        return False

    try:
        client.update(
            index=COLLECTIONS_INDEX_NAME,
            id=collection_id,
            body={"doc": updated_fields},
            refresh="wait_for",
        )
        logger.info(
            "Collection updated via write-through",
            extra={"collection_id": collection_id},
        )
        return True
    except Exception as e:
        logger.warning(
            "OpenSearch write-through update failed — stream sync will retry",
            extra={"collection_id": collection_id, "error": str(e)},
        )
        return False


def delete_collection_document(collection_id: str) -> bool:
    """Delete a collection document from OpenSearch.

    Args:
        collection_id: The collection ID (without the ``COLL#`` prefix).

    Returns:
        True on success (including 404 — already deleted), False on failure.
    """
    client = get_opensearch_client()
    if not client or not COLLECTIONS_INDEX_NAME:
        logger.warning(
            "OpenSearch write-through skipped — client or index not configured"
        )
        return False

    try:
        client.delete(
            index=COLLECTIONS_INDEX_NAME,
            id=collection_id,
            refresh="wait_for",
        )
        logger.info(
            "Collection deleted via write-through",
            extra={"collection_id": collection_id},
        )
        return True
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code == 404:
            logger.info(
                "Collection already absent from OpenSearch",
                extra={"collection_id": collection_id},
            )
            return True
        logger.warning(
            "OpenSearch write-through delete failed — stream sync will retry",
            extra={"collection_id": collection_id, "error": str(e)},
        )
        return False


# ---------------------------------------------------------------------------
# Collection Group write-through
# ---------------------------------------------------------------------------


def _build_group_document(
    group_id: str,
    group_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an OpenSearch document from collection group attributes.

    Mirrors the field mapping in
    ``lambdas/sync/collections_sync/document_transformer.py::transform_collection_group``
    so that write-through documents are identical to stream-synced ones.
    """
    return {
        "id": group_id,
        "name": group_dict.get("name", ""),
        "description": group_dict.get("description"),
        "ownerId": group_dict.get("ownerId", ""),
        "isPublic": group_dict.get("isPublic", False),
        "collectionIds": group_dict.get("collectionIds", []),
        "createdAt": group_dict.get("createdAt", ""),
        "updatedAt": group_dict.get("updatedAt", ""),
        "documentType": "collection_group",
    }


def index_collection_group(
    group_id: str,
    group_dict: Dict[str, Any],
) -> bool:
    """Index (create or overwrite) a collection group document in OpenSearch.

    Args:
        group_id: The group ID (without the ``GROUP#`` prefix).
        group_dict: Flat dict of group attributes.

    Returns:
        True if the document was indexed successfully, False on failure.
    """
    client = get_opensearch_client()
    if not client or not COLLECTIONS_INDEX_NAME:
        logger.warning(
            "OpenSearch group write-through skipped — client or index not configured"
        )
        return False

    doc = _build_group_document(group_id, group_dict)

    try:
        client.index(
            index=COLLECTIONS_INDEX_NAME,
            id=group_id,
            body=doc,
            refresh="wait_for",
        )
        logger.info(
            "Collection group indexed via write-through",
            extra={"group_id": group_id},
        )
        return True
    except Exception as e:
        logger.warning(
            "OpenSearch group write-through failed — stream sync will retry",
            extra={"group_id": group_id, "error": str(e)},
        )
        return False


def delete_collection_group_document(group_id: str) -> bool:
    """Delete a collection group document from OpenSearch.

    Args:
        group_id: The group ID (without the ``GROUP#`` prefix).

    Returns:
        True on success (including 404 — already deleted), False on failure.
    """
    client = get_opensearch_client()
    if not client or not COLLECTIONS_INDEX_NAME:
        logger.warning(
            "OpenSearch group write-through skipped — client or index not configured"
        )
        return False

    try:
        client.delete(
            index=COLLECTIONS_INDEX_NAME,
            id=group_id,
            refresh="wait_for",
        )
        logger.info(
            "Collection group deleted via write-through",
            extra={"group_id": group_id},
        )
        return True
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code == 404:
            logger.info(
                "Collection group already absent from OpenSearch",
                extra={"group_id": group_id},
            )
            return True
        logger.warning(
            "OpenSearch group write-through delete failed — stream sync will retry",
            extra={"group_id": group_id, "error": str(e)},
        )
        return False
