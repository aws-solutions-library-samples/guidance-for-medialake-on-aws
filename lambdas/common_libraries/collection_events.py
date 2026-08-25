"""Collection lifecycle event publishing for MediaLake.

This is the single, shared source of truth for collection-related EventBridge
events. Every code path that mutates a collection — the Collections REST API,
the ``collection_manager`` pipeline node, the ``asset_deleted_cleanup``
consumer, and the portal-upload collection-add path in the ingest Lambda —
publishes through these helpers so all events share one schema and land on the
pipelines event bus.

Why the pipelines event bus?
----------------------------
Pipeline *trigger* nodes attach their EventBridge rules to the pipelines event
bus (``PIPELINES_EVENT_BUS_NAME``) by default, exactly like the asset processor
publishes ``custom.asset.processor`` / ``AssetCreated`` there. Publishing
collection events to the same bus lets the new "Collection Event" trigger node
match them with a plain event pattern.

Event shape
-----------
``Source``      always ``custom.collection.processor`` (so one trigger pattern
                matches every collection event).
``DetailType``  one of the ``CollectionEvent`` detail-type constants below.
``Detail``      a JSON object that always carries ``collectionId`` plus, when
                known, ``collectionName``, ``collectionTypeId``, ``userId``,
                ``origin`` (which subsystem emitted it), and an ISO-8601
                ``timestamp``. Event-specific fields (e.g. ``assetIds``) are
                merged on top. Keeping ``collectionId`` / ``collectionTypeId``
                in every event means collection-ID or collection-type trigger
                filters can be added later without touching publishers.

Publishing is strictly best-effort: a failure to emit an event must never break
the collection mutation that triggered it, so every helper swallows and logs
errors and returns a bool.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="collection-events")

# All collection events share this source so a single trigger event pattern can
# match any of them (and optionally narrow by detail-type).
EVENT_SOURCE = "custom.collection.processor"

# Event bus to publish to. Set by CDK to the pipelines event bus name on every
# publisher Lambda. Falls back to "default" so the import never fails in
# environments where the variable is missing (events simply won't reach the
# pipelines bus there).
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")


# --- Detail-type constants -------------------------------------------------
# Keep these in sync with the trigger node template's "Event Types" options
# (s3_bucket_assets/pipeline_nodes/node_templates/trigger/trigger_collection_event.yaml)
# and the pattern builder in post_pipelines/eventbridge.py.
class CollectionEvent:
    """Canonical collection event detail-type names."""

    CREATED = "CollectionCreated"
    DELETED = "CollectionDeleted"
    METADATA_UPDATED = "CollectionMetadataUpdated"
    ASSETS_ADDED = "CollectionAssetAdded"
    ASSETS_REMOVED = "CollectionAssetRemoved"
    SHARED = "CollectionShared"
    SHARE_REMOVED = "CollectionShareRemoved"
    CHILD_ADDED = "CollectionChildAdded"
    CHILD_REMOVED = "CollectionChildRemoved"
    THUMBNAIL_UPDATED = "CollectionThumbnailUpdated"
    THUMBNAIL_REMOVED = "CollectionThumbnailRemoved"


# Ordered list of every detail-type — handy for the trigger UI / validation.
ALL_DETAIL_TYPES: List[str] = [
    CollectionEvent.CREATED,
    CollectionEvent.DELETED,
    CollectionEvent.METADATA_UPDATED,
    CollectionEvent.ASSETS_ADDED,
    CollectionEvent.ASSETS_REMOVED,
    CollectionEvent.SHARED,
    CollectionEvent.SHARE_REMOVED,
    CollectionEvent.CHILD_ADDED,
    CollectionEvent.CHILD_REMOVED,
    CollectionEvent.THUMBNAIL_UPDATED,
    CollectionEvent.THUMBNAIL_REMOVED,
]


_eventbridge_client = None


def _get_eventbridge_client():
    """Lazily create and cache the EventBridge client (reused across warm invokes)."""
    global _eventbridge_client
    if _eventbridge_client is None:
        _eventbridge_client = boto3.client("events")
    return _eventbridge_client


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with a trailing ``Z`` (matches the API's format)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(detail: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys whose value is ``None`` so events stay compact and predictable."""
    return {k: v for k, v in detail.items() if v is not None}


def _normalize_ids(asset_ids: Optional[Iterable[Any]]) -> List[str]:
    """Coerce an iterable of asset ids to a de-duplicated, order-preserving list of str."""
    if not asset_ids:
        return []
    seen = set()
    result: List[str] = []
    for raw in asset_ids:
        if raw is None:
            continue
        aid = str(raw).strip()
        if aid and aid not in seen:
            seen.add(aid)
            result.append(aid)
    return result


def publish_collection_event(
    detail_type: str,
    collection_id: str,
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    """Publish a single collection event to the pipelines event bus.

    This is the low-level primitive; prefer the typed ``publish_*`` helpers
    below, which document the event-specific fields. Always best-effort.

    Args:
        detail_type: One of the :class:`CollectionEvent` constants.
        collection_id: The collection the event is about (required).
        collection_name: Human-readable name, when known.
        collection_type_id: Collection type id, when known (enables type filters).
        user_id: The acting user, when known.
        origin: Which subsystem emitted the event (``collections-api``,
            ``pipeline-node``, ``asset-cleanup``, ``ingest-portal``).
        extra: Event-specific fields merged on top of the base envelope.

    Returns:
        ``True`` if the event was accepted by EventBridge, ``False`` otherwise.
    """
    if not collection_id:
        logger.warning(
            "Skipping collection event with no collection_id",
            extra={"detail_type": detail_type},
        )
        return False

    detail: Dict[str, Any] = {
        "collectionId": collection_id,
        "collectionName": collection_name,
        "collectionTypeId": collection_type_id,
        "userId": user_id,
        "origin": origin,
        "timestamp": _utc_now_iso(),
    }
    if extra:
        detail.update(extra)

    try:
        response = _get_eventbridge_client().put_events(
            Entries=[
                {
                    "Source": EVENT_SOURCE,
                    "DetailType": detail_type,
                    "Detail": json.dumps(_clean(detail), default=str),
                    "EventBusName": EVENT_BUS_NAME,
                }
            ]
        )
        failed = response.get("FailedEntryCount", 0)
        if failed:
            logger.warning(
                "EventBridge rejected collection event",
                extra={"detail_type": detail_type, "response": response},
            )
            return False
        logger.info(
            "Published collection event",
            extra={
                "detail_type": detail_type,
                "collection_id": collection_id,
                "event_bus": EVENT_BUS_NAME,
            },
        )
        return True
    except Exception as e:  # noqa: BLE001 - never let event publishing break the caller
        logger.warning(
            "Failed to publish collection event",
            extra={
                "detail_type": detail_type,
                "collection_id": collection_id,
                "error": str(e),
            },
        )
        return False


# --- Typed helpers ---------------------------------------------------------


def publish_collection_created(
    collection_id: str,
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    is_public: Optional[bool] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionCreated``."""
    return publish_collection_event(
        CollectionEvent.CREATED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean({"parentId": parent_id, "isPublic": is_public}),
    )


def publish_collection_deleted(
    collection_id: str,
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    items_deleted: Optional[int] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionDeleted``."""
    return publish_collection_event(
        CollectionEvent.DELETED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean({"parentId": parent_id, "itemsDeleted": items_deleted}),
    )


def publish_collection_metadata_updated(
    collection_id: str,
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    updated_fields: Optional[Iterable[str]] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionMetadataUpdated``.

    ``updated_fields`` lists which metadata fields changed (e.g. ``name``,
    ``description``, ``customMetadata``, ``tags``), letting consumers react to
    specific changes.
    """
    fields = list(updated_fields) if updated_fields else None
    return publish_collection_event(
        CollectionEvent.METADATA_UPDATED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean({"updatedFields": fields}),
    )


def publish_collection_assets_added(
    collection_id: str,
    asset_ids: Iterable[Any],
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit a single batched ``CollectionAssetAdded`` referencing every asset id.

    One event per batch (not per asset). No event is published when the
    normalized id list is empty.
    """
    ids = _normalize_ids(asset_ids)
    if not ids:
        return False
    return publish_collection_event(
        CollectionEvent.ASSETS_ADDED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra={"assetIds": ids, "assetCount": len(ids)},
    )


def publish_collection_assets_removed(
    collection_id: str,
    asset_ids: Iterable[Any],
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit a single batched ``CollectionAssetRemoved`` referencing every asset id."""
    ids = _normalize_ids(asset_ids)
    if not ids:
        return False
    return publish_collection_event(
        CollectionEvent.ASSETS_REMOVED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra={"assetIds": ids, "assetCount": len(ids)},
    )


def publish_collection_shared(
    collection_id: str,
    *,
    shared_with_user_id: Optional[str] = None,
    permission: Optional[str] = None,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionShared`` (a share/grant was created)."""
    return publish_collection_event(
        CollectionEvent.SHARED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean(
            {"sharedWithUserId": shared_with_user_id, "permission": permission}
        ),
    )


def publish_collection_share_removed(
    collection_id: str,
    *,
    shared_with_user_id: Optional[str] = None,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionShareRemoved`` (a share/grant was revoked)."""
    return publish_collection_event(
        CollectionEvent.SHARE_REMOVED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean({"sharedWithUserId": shared_with_user_id}),
    )


def publish_collection_child_added(
    parent_collection_id: str,
    child_collection_id: str,
    *,
    collection_name: Optional[str] = None,
    child_collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionChildAdded`` (a child collection was nested under a parent).

    The event is keyed on the parent ``collectionId`` (the collection that
    changed) and carries the child's id/name separately.

    ``collection_name`` is the *parent's* name. Like every other event, it
    populates ``detail.collectionName``, which is what collection-name trigger
    filters match on — without it a name filter can never match a child event.
    """
    return publish_collection_event(
        CollectionEvent.CHILD_ADDED,
        parent_collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean(
            {
                "childCollectionId": child_collection_id,
                "childCollectionName": child_collection_name,
            }
        ),
    )


def publish_collection_child_removed(
    parent_collection_id: str,
    child_collection_id: str,
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionChildRemoved`` (a child collection was detached/deleted).

    ``collection_name`` is the *parent's* name; see
    :func:`publish_collection_child_added` for why it matters.
    """
    return publish_collection_event(
        CollectionEvent.CHILD_REMOVED,
        parent_collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean({"childCollectionId": child_collection_id}),
    )


def publish_collection_thumbnail_updated(
    collection_id: str,
    *,
    thumbnail_type: Optional[str] = None,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionThumbnailUpdated`` (thumbnail set or changed)."""
    return publish_collection_event(
        CollectionEvent.THUMBNAIL_UPDATED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
        extra=_clean({"thumbnailType": thumbnail_type}),
    )


def publish_collection_thumbnail_removed(
    collection_id: str,
    *,
    collection_name: Optional[str] = None,
    collection_type_id: Optional[str] = None,
    user_id: Optional[str] = None,
    origin: str = "collections-api",
) -> bool:
    """Emit ``CollectionThumbnailRemoved`` (thumbnail cleared)."""
    return publish_collection_event(
        CollectionEvent.THUMBNAIL_REMOVED,
        collection_id,
        collection_name=collection_name,
        collection_type_id=collection_type_id,
        user_id=user_id,
        origin=origin,
    )
