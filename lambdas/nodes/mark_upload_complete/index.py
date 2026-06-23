"""Mark Upload Processing Complete — barrier pipeline node.

Reads `ml-batch-id` from the asset's nested S3 user-metadata, extracts the
asset identifier, and marks the asset as complete against its upload session.
When both identifiers are present and the session table is configured, calls
`mark_asset_complete` (which itself calls `try_terminal_transition`).

Always passes the payload through unchanged (R5.6).
No-op when `ml-batch-id` is absent (R5.5) or UPLOAD_SESSIONS_TABLE_NAME is unset.
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

logger = Logger(service="mark-upload-complete-node")

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
    """Recursively locate a case-insensitive `ml-batch-id` value in nested structures.

    Mirrors the recursive search pattern of
    `lambdas/ingest/s3/index.py::_find_portal_user_metadata` but targets a
    single key (`ml-batch-id`) rather than looking for a marker key to
    identify the metadata dict.

    Walks all dict values recursively; when a key (lowercased) equals
    "ml-batch-id", returns the corresponding value.

    Parameters
    ----------
    metadata : Any
        The payload or a nested portion thereof to search.

    Returns
    -------
    str or None
        The value of `ml-batch-id` if found, otherwise None.
    """
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if isinstance(key, str) and key.lower() == _ML_BATCH_ID_KEY:
                # Found it — return the value as a string
                return str(value) if value is not None else None
            # Recurse into the value
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
    """Recursively locate a case-insensitive, non-empty `InventoryID` value.

    Mirrors the recursive traversal of `_find_batch_id`: walks all dict values
    and list items, returning the first non-empty value whose key (lowercased)
    equals "inventoryid". An empty/falsy value does not match and the search
    continues, preserving the legacy "empty InventoryID falls through" behaviour.

    Parameters
    ----------
    payload : Any
        The payload or a nested portion thereof to search.

    Returns
    -------
    str or None
        The first non-empty `InventoryID` found, otherwise None.
    """
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
    """Recursively locate the `ID`/`id` of a `DigitalSourceAsset` map.

    Mirrors the recursive traversal of `_find_batch_id`: walks all dict values
    and list items, and when a key (lowercased) equals "digitalsourceasset" and
    its value is a dict, returns that map's `ID` (preferred) or `id`.

    Parameters
    ----------
    payload : Any
        The payload or a nested portion thereof to search.

    Returns
    -------
    str or None
        The first `DigitalSourceAsset` map's `ID`/`id`, otherwise None.
    """
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

    Real AssetCreated pipeline payloads nest the asset identity under
    `payload["detail"]` (e.g. `payload["detail"]["InventoryID"]` and
    `payload["detail"]["DigitalSourceAsset"]["ID"]`), so a top-level-only lookup
    misses it. This searches RECURSIVELY through nested dicts/lists — mirroring
    `_find_batch_id` — so the id is found wherever it sits. The legacy top-level
    checks remain a subset of this traversal.

    Preference order (each searched recursively, case-insensitive key match):
    1. `InventoryID` — the ingest identity (preferred). Returns the first
       non-empty value found anywhere in the payload.
    2. A `DigitalSourceAsset` map's `ID`/`id` — fallback when no `InventoryID`
       exists anywhere.

    Returns the resolved identifier, or None when neither is present.

    Parameters
    ----------
    payload : dict
        The pipeline node payload.

    Returns
    -------
    str or None
        The asset identifier, or None if not found.
    """
    # Prefer InventoryID found anywhere in the (possibly nested) payload.
    inventory_id = _find_inventory_id(payload)
    if inventory_id:
        return inventory_id

    # Fall back to a DigitalSourceAsset map's ID/id found anywhere.
    return _find_digital_source_asset_id(payload)


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the Mark Upload Processing Complete pipeline node.

    Expected event shape (from Step Functions task):
    {
        "payload": { ... }  # upstream pipeline payload (passed through unchanged)
    }

    Always returns `payload` unchanged (R5.6).
    """
    payload = event.get("payload", {})

    # No-op when table is not configured
    if not UPLOAD_SESSIONS_TABLE_NAME:
        logger.debug("UPLOAD_SESSIONS_TABLE_NAME not set, skipping")
        return payload

    # Extract batch id from nested metadata
    batch_id = _find_batch_id(payload)
    if not batch_id:
        logger.debug("No ml-batch-id found in payload, passing through")
        return payload

    # Extract asset id
    asset_id = _extract_asset_id(payload)
    if not asset_id:
        logger.info(
            "ml-batch-id found but no asset id available, passing through",
            extra={"batch_id": batch_id},
        )
        return payload

    # Mark the asset complete and attempt terminal transition
    logger.info(
        "Marking asset complete",
        extra={"batch_id": batch_id, "asset_id": asset_id},
    )
    store = _get_session_store()
    result = store.mark_asset_complete(session_id=batch_id, asset_id=asset_id)

    if result.marked:
        logger.info(
            "Asset newly marked complete",
            extra={"batch_id": batch_id, "asset_id": asset_id},
        )
    elif result.already_counted:
        logger.debug(
            "Asset already counted",
            extra={"batch_id": batch_id, "asset_id": asset_id},
        )
    else:
        logger.warning(
            "Asset mark failed (session may not be OPEN)",
            extra={"batch_id": batch_id, "asset_id": asset_id},
        )

    # Always return the payload unchanged (R5.6)
    return payload
