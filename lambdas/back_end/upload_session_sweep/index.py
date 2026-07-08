"""Upload Session Reconciliation Sweep Lambda.

Triggered on a CloudWatch Events schedule (hourly). Queries GSI1 to find all
OPEN sessions (GSI1_PK="STATUS#OPEN") and evaluates each against the timeout
thresholds. The submit marker (`finalizeRequestedAt`) is set ONLY by an explicit
user Submit — the sweep never fabricates it:

1. Max-age force-resolve: If `now - createdAt > MAX_SESSION_AGE_HOURS`, call
   `store.reconcile_max_age(session_id)`, which resolves to the matching corner
   of the 2x2 model (submitted/not x all-succeeded/not).
2. Grace force-complete: If the submit marker IS set AND
   `now - finalizeRequestedAt > COMPLETION_GRACE_HOURS` AND some files never
   reached a terminal state (`resolvedCount < expectedCount`), force-complete as
   SUBMITTED_UNPROCESSED via `store.reconcile_grace(session_id)` (fires with the
   with-errors signal).
3. Idle unsubmitted-processed: If there is NO submit marker AND
   `now - lastHeartbeatAt > IDLE_TIMEOUT_HOURS`, call
   `store.reconcile_idle_unsubmitted(session_id)`. That transitions to
   UNSUBMITTED_PROCESSED (fires filesProcessed=true / formSubmissionComplete=false)
   ONLY when every uploaded file succeeded; a never-submitted session with a
   failed or still-processing file is a no-op and stays OPEN until it either
   succeeds or hits max age (→ silent UNSUBMITTED_UNPROCESSED).
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key

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

logger = Logger(service="upload_session_sweep")

# Environment variables
UPLOAD_SESSIONS_TABLE_NAME = os.environ.get("UPLOAD_SESSIONS_TABLE_NAME", "")
IDLE_TIMEOUT_HOURS = int(os.environ.get("IDLE_TIMEOUT_HOURS", "4"))
COMPLETION_GRACE_HOURS = int(os.environ.get("COMPLETION_GRACE_HOURS", "8"))
MAX_SESSION_AGE_HOURS = int(os.environ.get("MAX_SESSION_AGE_HOURS", "48"))

# AWS resources
dynamodb = boto3.resource("dynamodb")

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
# ISO-8601 parsing helper
# ---------------------------------------------------------------------------


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO-8601 UTC timestamp string (ending in 'Z') to a datetime.

    Returns None if the value is empty or cannot be parsed.
    """
    if not value:
        return None
    try:
        # Handle both "2024-01-01T00:00:00Z" and "2024-01-01T00:00:00+00:00"
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Reconciliation logic per session
# ---------------------------------------------------------------------------


def _reconcile_session(store: SessionStore, item: dict, now: datetime) -> None:
    """Evaluate a single OPEN session against the timeout thresholds.

    Checks are evaluated in priority order:
    1. Max-age force-resolve (most aggressive — overrides everything)
    2. Grace force-complete (submitted but not all files resolved past grace)
    3. Idle unsubmitted-processed (never submitted and idle too long)

    Parameters
    ----------
    store : SessionStore
        The session store instance to call reconciliation methods on.
    item : dict
        The DynamoDB item from the GSI1 query (full projection).
    now : datetime
        The current UTC time.
    """
    session_id = item.get("sessionId", "")
    if not session_id:
        return

    created_at = _parse_iso(item.get("createdAt", ""))
    last_heartbeat_at = _parse_iso(item.get("lastHeartbeatAt", ""))
    finalize_requested_at = _parse_iso(item.get("finalizeRequestedAt", ""))
    expected_count = int(item.get("expectedCount", 0))
    # resolvedCount = completedCount + failedCount (files that reached a terminal
    # pipeline state). Falls back to completedCount for robustness if the
    # attribute is somehow absent.
    resolved_count = int(item.get("resolvedCount", item.get("completedCount", 0)))

    # Check 1: Max-age force-resolve.
    # If now - createdAt > MAX_SESSION_AGE_HOURS, resolve regardless of state.
    if created_at and (now - created_at) > timedelta(hours=MAX_SESSION_AGE_HOURS):
        logger.info(
            "Session exceeded max age, force-resolving",
            extra={
                "session_id": session_id,
                "created_at": item.get("createdAt", ""),
                "max_age_hours": MAX_SESSION_AGE_HOURS,
            },
        )
        store.reconcile_max_age(session_id)
        return

    # Check 2: Grace force-complete (submitted path).
    # If finalizeRequestedAt IS set AND now - finalizeRequestedAt > grace AND
    # some files never reached a terminal state, force-complete with errors.
    if finalize_requested_at is not None:
        if (now - finalize_requested_at) > timedelta(
            hours=COMPLETION_GRACE_HOURS
        ) and resolved_count < expected_count:
            logger.info(
                "Submitted session exceeded grace period, force-completing with errors",
                extra={
                    "session_id": session_id,
                    "finalize_requested_at": item.get("finalizeRequestedAt", ""),
                    "grace_hours": COMPLETION_GRACE_HOURS,
                    "resolved_count": resolved_count,
                    "expected_count": expected_count,
                },
            )
            store.reconcile_grace(session_id)
        return

    # Check 3: Idle unsubmitted-processed (never-submitted path).
    # If now - lastHeartbeatAt > IDLE_TIMEOUT_HOURS and there is NO submit marker,
    # attempt the never-submitted-but-all-processed transition. reconcile_idle_
    # unsubmitted is a no-op unless every uploaded file succeeded (it guards on
    # completedCount >= expectedCount AND failedCount == 0 AND expectedCount > 0),
    # so a session with a failed or still-processing file simply stays OPEN until
    # it succeeds or hits max age.
    if last_heartbeat_at and (now - last_heartbeat_at) > timedelta(
        hours=IDLE_TIMEOUT_HOURS
    ):
        logger.info(
            "Session idle beyond threshold and never submitted, attempting unsubmitted-processed",
            extra={
                "session_id": session_id,
                "last_heartbeat_at": item.get("lastHeartbeatAt", ""),
                "idle_hours": IDLE_TIMEOUT_HOURS,
            },
        )
        store.reconcile_idle_unsubmitted(session_id)


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event, context):
    """Reconciliation sweep entry point.

    Queries all OPEN sessions from GSI1, paginates through results, and evaluates
    each session against idle, grace, and max-age thresholds.

    Returns a summary dict with the count of processed sessions.
    """
    now = datetime.now(timezone.utc)
    store = _get_session_store()

    # Query all OPEN sessions from GSI1
    table = dynamodb.Table(UPLOAD_SESSIONS_TABLE_NAME)
    query_kwargs = {
        "IndexName": "GSI1",
        "KeyConditionExpression": Key("GSI1_PK").eq("STATUS#OPEN"),
    }

    processed = 0
    while True:
        response = table.query(**query_kwargs)
        items = response.get("Items", [])

        for item in items:
            _reconcile_session(store, item, now)
            processed += 1

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    logger.info(
        "Reconciliation sweep complete",
        extra={"processed_sessions": processed},
    )

    return {"processed": processed}
