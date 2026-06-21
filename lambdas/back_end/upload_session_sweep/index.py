"""Upload Session Reconciliation Sweep Lambda.

Triggered on a CloudWatch Events schedule (every X minutes). Queries GSI1 to
find all OPEN sessions (GSI1_PK="STATUS#OPEN") and evaluates each against three
reconciliation thresholds:

1. Idle auto-finalize (R3.7): If `now - lastHeartbeatAt > IDLE_FINALIZE_MINUTES`
   AND `finalizeRequestedAt` is NOT set, apply the finalize marker via
   `store.reconcile_idle(session_id)`.
2. Grace force-complete (R8.1): If `finalizeRequestedAt` IS set AND
   `now - finalizeRequestedAt > COMPLETION_GRACE_MINUTES` AND
   `completedCount < expectedCount`, force-complete via
   `store.reconcile_grace(session_id)`.
3. Max-age force-complete (R8.2): If `now - createdAt > MAX_SESSION_AGE_HOURS`,
   force-complete via `store.reconcile_max_age(session_id)`.

Requirements: 3.7, 8.1, 8.2
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
IDLE_FINALIZE_MINUTES = int(os.environ.get("IDLE_FINALIZE_MINUTES", "60"))
COMPLETION_GRACE_MINUTES = int(os.environ.get("COMPLETION_GRACE_MINUTES", "30"))
MAX_SESSION_AGE_HOURS = int(os.environ.get("MAX_SESSION_AGE_HOURS", "24"))

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
    """Evaluate a single OPEN session against reconciliation thresholds.

    Checks are evaluated in priority order:
    1. Max-age force-complete (most aggressive — overrides everything)
    2. Grace force-complete (finalized but incomplete past grace period)
    3. Idle auto-finalize (not yet finalized and idle too long)

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
    completed_count = int(item.get("completedCount", 0))

    # Check 1: Max-age force-complete (R8.2)
    # If now - createdAt > MAX_SESSION_AGE_HOURS, force-complete regardless of
    # finalize state.
    if created_at and (now - created_at) > timedelta(hours=MAX_SESSION_AGE_HOURS):
        logger.info(
            "Session exceeded max age, force-completing",
            extra={
                "session_id": session_id,
                "created_at": item.get("createdAt", ""),
                "max_age_hours": MAX_SESSION_AGE_HOURS,
            },
        )
        store.reconcile_max_age(session_id)
        return

    # Check 2: Grace force-complete (R8.1)
    # If finalizeRequestedAt IS set AND now - finalizeRequestedAt > COMPLETION_GRACE_MINUTES
    # AND completedCount < expectedCount, force-complete.
    if finalize_requested_at is not None:
        if (now - finalize_requested_at) > timedelta(
            minutes=COMPLETION_GRACE_MINUTES
        ) and completed_count < expected_count:
            logger.info(
                "Finalized session exceeded grace period, force-completing",
                extra={
                    "session_id": session_id,
                    "finalize_requested_at": item.get("finalizeRequestedAt", ""),
                    "grace_minutes": COMPLETION_GRACE_MINUTES,
                    "completed_count": completed_count,
                    "expected_count": expected_count,
                },
            )
            store.reconcile_grace(session_id)
        return

    # Check 3: Idle auto-finalize (R3.7)
    # If now - lastHeartbeatAt > IDLE_FINALIZE_MINUTES AND finalizeRequestedAt is NOT set,
    # apply the finalize marker.
    if last_heartbeat_at and (now - last_heartbeat_at) > timedelta(
        minutes=IDLE_FINALIZE_MINUTES
    ):
        logger.info(
            "Session idle beyond threshold, auto-finalizing",
            extra={
                "session_id": session_id,
                "last_heartbeat_at": item.get("lastHeartbeatAt", ""),
                "idle_minutes": IDLE_FINALIZE_MINUTES,
            },
        )
        store.reconcile_idle(session_id)


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
