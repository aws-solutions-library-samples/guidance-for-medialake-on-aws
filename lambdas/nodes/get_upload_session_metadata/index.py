"""Get Upload Session Metadata — read-only pipeline node.

Resolves an upload session and emits its status, counts, the branchable
``filesProcessed`` / ``formSubmissionComplete`` signals, and the batch's
user-entered portal form fields (``userMetadata``) so downstream nodes can branch
on what the uploader submitted (e.g. ``data.uploadSession.userMetadata.<slug>``).

Session id resolution (first match wins):
    1. ``SESSION_ID`` env override — a pinned node parameter.
    2. ``sessionId`` found anywhere in the payload — e.g. an "Upload Batch
       Completed" event detail, or a value set by an upstream node.
    3. ``ml-batch-id`` found anywhere in the payload — the asset's S3
       user-metadata, stamped at upload time (same key the barrier node reads).

Read-only: this node NEVER mutates the upload-sessions table (no status,
count, or metadata writes), so it cannot trigger or interfere with the
OPEN -> terminal transition or the UploadBatchCompleted emission.

Degrades gracefully: when the id cannot be resolved, the table is
unconfigured, or the session is missing/expired (sessions have a TTL), it
returns a ``uploadSession`` block with ``found: false`` rather than failing
the pipeline. Upstream payload data is preserved and assets pass through the
middleware unchanged.
"""

import os
import sys
from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

try:
    from lambda_middleware import lambda_middleware
except ImportError:
    # Local/test fallback: a no-op decorator so the module imports without the
    # common-libraries layer present.
    def lambda_middleware(**_kwargs):
        def decorator(fn):
            return fn

        return decorator


# Upload session store — vendored into the Lambda package at deploy time.
# The canonical module lives at lambdas/shared/upload_session/session_store.py;
# a byte-for-byte copy is vendored here (guarded by
# tests/unit/test_vendored_session_store_sync.py) so the import resolves at the
# bundle root in the deployed Lambda.
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

logger = Logger(service="get-upload-session-metadata-node")
tracer = Tracer(service="get-upload-session-metadata-node")

UPLOAD_SESSIONS_TABLE_NAME = os.environ.get("UPLOAD_SESSIONS_TABLE_NAME", "")

_ML_BATCH_ID_KEY = "ml-batch-id"
_SESSION_ID_KEY = "sessionid"

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
# Session id resolution
# ---------------------------------------------------------------------------


def _find_value_for_key(obj: Any, target_key_lower: str) -> Optional[str]:
    """Recursively return the first non-empty string value whose key (lowercased)
    equals ``target_key_lower``.

    Mirrors the case-insensitive recursive search used by the barrier node
    (``mark_upload_complete._find_batch_id``) so an id is found wherever it sits
    in a nested pipeline payload (dicts and lists).
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key.lower() == target_key_lower and value:
                return str(value)
            found = _find_value_for_key(value, target_key_lower)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_value_for_key(item, target_key_lower)
            if found is not None:
                return found
    return None


def _resolve_session_id(payload: Any) -> Optional[str]:
    """Resolve the session id to look up (see module docstring for priority)."""
    override = os.environ.get("SESSION_ID", "").strip()
    if override:
        return override

    session_id = _find_value_for_key(payload, _SESSION_ID_KEY)
    if session_id:
        return session_id

    return _find_value_for_key(payload, _ML_BATCH_ID_KEY)


# ---------------------------------------------------------------------------
# Session view shaping
# ---------------------------------------------------------------------------


def _not_found_view(session_id: Optional[str]) -> Dict[str, Any]:
    """A uniform ``found: false`` view so downstream nodes can branch safely."""
    return {
        "found": False,
        "sessionId": session_id,
        "status": None,
        "filesProcessed": False,
        "formSubmissionComplete": False,
        "userMetadata": {},
    }


def _coerce_user_metadata(raw: Any) -> Dict[str, str]:
    """Coerce the stored userMetadata Map to a flat {str: str} dict."""
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _to_int(value: Any) -> int:
    """Best-effort int coercion (DynamoDB numbers arrive as Decimal)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_session_view(session_id: Optional[str]) -> Dict[str, Any]:
    """Read the session META item and shape it for downstream nodes.

    Never raises: returns a ``found: false`` view when the id is missing, the
    table is unconfigured, or the session does not exist / has expired.
    """
    if not session_id:
        logger.info("No upload session id resolved from payload")
        return _not_found_view(None)

    if not UPLOAD_SESSIONS_TABLE_NAME:
        logger.warning("UPLOAD_SESSIONS_TABLE_NAME not set; cannot read session")
        return _not_found_view(session_id)

    item = _get_session_store().get_session(session_id)
    if not item:
        logger.info("Upload session not found", extra={"session_id": session_id})
        return _not_found_view(session_id)

    status = item.get("status")
    expected_count = _to_int(item.get("expectedCount", 0))
    completed_count = _to_int(item.get("completedCount", 0))
    failed_count = _to_int(item.get("failedCount", 0))
    # Live view of the two branchable signals, computed from the current
    # counters/marker so it is accurate at any lifecycle point (and equals
    # derive_signals(status) once the session is terminal):
    #   filesProcessed         - every uploaded file succeeded
    #   formSubmissionComplete - the user clicked Submit
    files_processed = (
        expected_count > 0 and failed_count == 0 and completed_count >= expected_count
    )
    form_submission_complete = bool(item.get("finalizeRequestedAt"))
    return {
        "found": True,
        "sessionId": item.get("sessionId", session_id),
        "status": status,
        "filesProcessed": files_processed,
        "formSubmissionComplete": form_submission_complete,
        "portalId": item.get("portalId"),
        "automationTag": item.get("automationTag"),
        "expectedCount": expected_count,
        "completedCount": completed_count,
        "failedCount": failed_count,
        "createdAt": item.get("createdAt"),
        "completedAt": item.get("completedAt"),
        "userMetadata": _coerce_user_metadata(item.get("userMetadata")),
    }


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Resolve the upload session and merge its metadata into the payload data.

    The returned dict becomes the next node's ``payload.data`` (assets pass
    through the middleware unchanged). Upstream ``data`` keys are preserved and
    the resolved session is added under ``uploadSession``.
    """
    payload = event.get("payload", {}) or {}
    data = payload.get("data", {})

    session_id = _resolve_session_id(payload)
    session_view = _build_session_view(session_id)

    # Preserve upstream data (when it is a dict) and add the session view.
    merged: Dict[str, Any] = dict(data) if isinstance(data, dict) else {}
    # Keep non-dict upstream data (e.g. a Map scalar) addressable rather than
    # silently dropping it.
    if not isinstance(data, dict) and data not in (None, {}, [], ""):
        merged["data"] = data
    merged["uploadSession"] = session_view

    logger.info(
        "Resolved upload session metadata",
        extra={
            "session_id": session_id,
            "found": session_view.get("found"),
            "status": session_view.get("status"),
            "user_metadata_keys": sorted(session_view.get("userMetadata", {}).keys()),
        },
    )
    return merged
