"""Mark Asset Failed — barrier pipeline node (error/catch branch).

The companion to ``mark_upload_complete``. Placed on a pipeline's error/catch
branch, it reads ``ml-batch-id`` from the asset's nested S3 user-metadata,
extracts the asset identifier, and records the asset as FAILED against its
upload session via ``mark_asset_failed`` (which itself calls
``try_terminal_transition``).

Recording a genuine processing failure lets the two-signal join resolve
PROMPTLY as "submitted, with errors" (SUBMITTED_UNPROCESSED) instead of blocking
on the grace-period timeout, and it lets a never-submitted session with a failed
file settle to the silent corner rather than a false "all processed" result.

Always passes the payload through unchanged.
No-op when ``ml-batch-id`` is absent or ``UPLOAD_SESSIONS_TABLE_NAME`` is unset.

IMPORTANT: only files that were accepted, uploaded, and then errored DURING
processing should reach this node. Files rejected for MIME/type/size are blocked
before upload (at file selection and again at the presigned-URL step, before
``register_key``), never enter ``expectedCount``, and must never be routed here.
"""

import os
import sys
from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger

# Upload session store — vendored into the Lambda package at deploy time.
# The shared module lives at lambdas/shared/upload_session/session_store.py;
# in the Lambda runtime it's available on sys.path directly.
try:
    from upload_session.session_store import SessionStore
except ImportError:
    # Fallback for local development / testing: add the shared dir to path.
    _SHARED_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    )
    if _SHARED_DIR not in sys.path:
        sys.path.insert(0, _SHARED_DIR)
    from upload_session.session_store import SessionStore

logger = Logger(service="mark-asset-failed-node")

UPLOAD_SESSIONS_TABLE_NAME = os.environ.get("UPLOAD_SESSIONS_TABLE_NAME", "")

# ---------------------------------------------------------------------------
# Lazy-init singleton SessionStore
# ---------------------------------------------------------------------------

_session_store: Optional[SessionStore] = None


def _get_session_store() -> SessionStore:
    """Get or create the singleton SessionStore instance."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore(table_name=UPLOAD_SESSIONS_TABLE_NAME)
    return _session_store


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

_ML_BATCH_ID_KEY = "ml-batch-id"
_INVENTORY_ID_KEY = "inventoryid"
_DIGITAL_SOURCE_ASSET_KEY = "digitalsourceasset"


def _find_batch_id(metadata: Any) -> Optional[str]:
    """Recursively locate a case-insensitive ``ml-batch-id`` value.

    Mirrors ``mark_upload_complete._find_batch_id``: walks all dict values and
    list items and returns the value whose key (lowercased) equals
    ``ml-batch-id``, wherever it sits in the (possibly nested) payload.
    """
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if isinstance(key, str) and key.lower() == _ML_BATCH_ID_KEY:
                return str(value) if value is not None else None
            found = _find_batch_id(value)
            if found is not None:
                return found
    elif isinstance(metadata, list):
        for item in metadata:
            found = _find_batch_id(item)
            if found is not None:
                return found
    return None


def _find_inventory_id(payload: Any) -> Optional[str]:
    """Recursively locate a case-insensitive, non-empty ``InventoryID`` value."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and key.lower() == _INVENTORY_ID_KEY and value:
                return str(value)
            found = _find_inventory_id(value)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_inventory_id(item)
            if found is not None:
                return found
    return None


def _find_digital_source_asset_id(payload: Any) -> Optional[str]:
    """Recursively locate the ``ID``/``id`` of a ``DigitalSourceAsset`` map."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if (
                isinstance(key, str)
                and key.lower() == _DIGITAL_SOURCE_ASSET_KEY
                and isinstance(value, dict)
            ):
                dsa_id = value.get("ID") or value.get("id")
                if dsa_id:
                    return str(dsa_id)
            found = _find_digital_source_asset_id(value)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_digital_source_asset_id(item)
            if found is not None:
                return found
    return None


def _extract_asset_id(payload: Dict[str, Any]) -> Optional[str]:
    """Extract the asset identifier from the pipeline payload.

    Preference order (each searched recursively, case-insensitive key match):
    1. ``InventoryID`` — the ingest identity (preferred).
    2. A ``DigitalSourceAsset`` map's ``ID``/``id`` — fallback.

    Uses the SAME resolution as ``mark_upload_complete`` so a given asset maps
    to the same identifier for both the complete and failed signals — which is
    what makes the shared ``ASSET#{assetId}`` guard count it exactly once.
    """
    inventory_id = _find_inventory_id(payload)
    if inventory_id:
        return inventory_id
    return _find_digital_source_asset_id(payload)


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the Mark Asset Failed pipeline node.

    Expected event shape (from a Step Functions catch/error task):
    {
        "payload": { ... }  # upstream pipeline payload (passed through unchanged)
    }

    Always returns ``payload`` unchanged.
    """
    payload = event.get("payload", {})

    # No-op when table is not configured
    if not UPLOAD_SESSIONS_TABLE_NAME:
        logger.debug("UPLOAD_SESSIONS_TABLE_NAME not set, skipping")
        return payload

    batch_id = _find_batch_id(payload)
    if not batch_id:
        logger.debug("No ml-batch-id found in payload, passing through")
        return payload

    asset_id = _extract_asset_id(payload)
    if not asset_id:
        logger.info(
            "ml-batch-id found but no asset id available, passing through",
            extra={"batch_id": batch_id},
        )
        return payload

    logger.info(
        "Marking asset failed",
        extra={"batch_id": batch_id, "asset_id": asset_id},
    )
    store = _get_session_store()
    result = store.mark_asset_failed(session_id=batch_id, asset_id=asset_id)

    if result.marked:
        logger.info(
            "Asset newly marked failed",
            extra={"batch_id": batch_id, "asset_id": asset_id},
        )
    elif result.already_counted:
        logger.debug(
            "Asset already counted (completed or failed)",
            extra={"batch_id": batch_id, "asset_id": asset_id},
        )
    else:
        logger.warning(
            "Asset mark-failed did not apply (session may not be OPEN)",
            extra={"batch_id": batch_id, "asset_id": asset_id},
        )

    # Always return the payload unchanged
    return payload
