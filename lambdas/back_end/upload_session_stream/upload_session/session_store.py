"""Upload Session Service — DynamoDB-backed session lifecycle management.

This module encapsulates all conditional/transactional writes for the upload-session
DynamoDB table. It is vendored into each Lambda that needs it (portal_public, the
mark_upload_complete node, the stream processor, and the reconciliation sweep).

Table schema (single-table design):
    PK: SESSION#{sessionId}
    SK: META | KEY#{s3Key} | ASSET#{assetId}
    GSI1: GSI1_PK (STATUS#OPEN) / GSI1_SK (lastHeartbeatAt)
"""

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import boto3
from aws_lambda_powertools.metrics import MetricUnit

# ---------------------------------------------------------------------------
# Injectable clock
# ---------------------------------------------------------------------------

Clock = Callable[[], datetime]
"""A callable that returns the current UTC datetime. Inject for testing."""


def _default_clock() -> datetime:
    """Production clock — returns current UTC time."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Shared UTC helper
# ---------------------------------------------------------------------------


def utc_now_z(clock: Optional[Clock] = None) -> str:
    """Return current time as ISO-8601 UTC string ending in 'Z'.

    Example: "2024-01-01T00:00:00Z"
    """
    dt = (clock or _default_clock)()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------


def _pk(session_id: str) -> str:
    """Build partition key for a session."""
    return f"SESSION#{session_id}"


def _sk_meta() -> str:
    """Sort key for the session META item."""
    return "META"


def _sk_key(s3_key: str) -> str:
    """Sort key for a registered S3 object key guard."""
    return f"KEY#{s3_key}"


def _sk_asset(asset_id: str) -> str:
    """Sort key for an asset completion guard."""
    return f"ASSET#{asset_id}"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegisterResult:
    """Result of a register_key operation.

    Possible states:
    - success=True, already_counted=False: key newly registered, expectedCount incremented
    - success=True, already_counted=True:  key was already counted, no-op (idempotent)
    - success=False, not_open=True:        session is not OPEN (terminal or missing)
    - success=False, cap_exceeded=True:    registration would exceed maxFilesPerSession
    """

    success: bool
    already_counted: bool
    not_open: bool = False
    cap_exceeded: bool = False
    error: Optional[str] = None


@dataclass(frozen=True)
class FinalizeResult:
    """Result of a finalize operation."""

    completed: bool
    still_open: bool
    write_failed: bool


@dataclass(frozen=True)
class MarkResult:
    """Result of a mark_asset_complete operation."""

    marked: bool
    already_counted: bool


# ---------------------------------------------------------------------------
# Session Store
# ---------------------------------------------------------------------------


class SessionStore:
    """DynamoDB-backed upload session store.

    Parameters
    ----------
    table_name : str, optional
        DynamoDB table name. Defaults to env var UPLOAD_SESSIONS_TABLE_NAME.
    clock : Clock, optional
        Injectable clock for testing. Defaults to real UTC clock.
    dynamodb_resource : optional
        A boto3 DynamoDB resource. Defaults to boto3.resource("dynamodb").
    dynamodb_client : optional
        A boto3 DynamoDB low-level client. Used for transact_write_items.
        Defaults to boto3.client("dynamodb").
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        clock: Optional[Clock] = None,
        dynamodb_resource=None,
        dynamodb_client=None,
        metrics=None,
    ):
        self._table_name = table_name or os.environ.get(
            "UPLOAD_SESSIONS_TABLE_NAME", ""
        )
        self._clock = clock or _default_clock
        self._dynamodb = dynamodb_resource or boto3.resource("dynamodb")
        self._table = self._dynamodb.Table(self._table_name)
        self._client = dynamodb_client or boto3.client("dynamodb")
        self._metrics = metrics

    # ------------------------------------------------------------------
    # Metrics helper
    # ------------------------------------------------------------------

    def _emit_metric(self, name: str, portal_id: Optional[str] = None) -> None:
        """Emit a CloudWatch count metric if metrics instance is available.

        Parameters
        ----------
        name : str
            The metric name (e.g. "UploadSessionCreated").
        portal_id : str, optional
            The portalId dimension value. When provided, adds a portalId dimension.
        """
        if self._metrics is None:
            return
        if portal_id:
            self._metrics.add_dimension(name="portalId", value=portal_id)
        self._metrics.add_metric(name=name, unit=MetricUnit.Count, value=1)

    # ------------------------------------------------------------------
    # create_session
    # ------------------------------------------------------------------

    def create_session(
        self,
        portal_id: str,
        automation_tag: str,
        max_files: int,
        retention_days: int,
    ) -> dict:
        """Create a new upload session.

        Uses put_item with ConditionExpression="attribute_not_exists(PK)" to
        guarantee uniqueness. The sessionId is a v4 UUID (R9.2).

        Parameters
        ----------
        portal_id : str
            The authenticated portalId from the Portal_Authorizer context.
        automation_tag : str
            The portal's automationTag value. Resolved to portalId when empty.
        max_files : int
            The portal's maxFilesPerSession cap (snapshot at creation time).
        retention_days : int
            Session retention period in days for TTL calculation.

        Returns
        -------
        dict
            The created session item attributes.
        """
        session_id = str(uuid.uuid4())
        now = utc_now_z(self._clock)
        now_dt = self._clock()
        ttl = int(now_dt.timestamp()) + (retention_days * 86400)

        # Resolve automationTag: use portal tag when non-empty, else portalId (R7.5/7.6)
        resolved_tag = (
            automation_tag if (automation_tag and automation_tag.strip()) else portal_id
        )

        item = {
            "PK": _pk(session_id),
            "SK": _sk_meta(),
            "sessionId": session_id,
            "portalId": portal_id,
            "automationTag": resolved_tag,
            "status": "OPEN",
            "expectedCount": 0,
            "completedCount": 0,
            "failedCount": 0,
            "maxFilesPerSession": max_files,
            "createdAt": now,
            "lastHeartbeatAt": now,
            "ttl": ttl,
            "GSI1_PK": "STATUS#OPEN",
            "GSI1_SK": now,
        }

        self._table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )

        self._emit_metric("UploadSessionCreated", portal_id=portal_id)

        return item

    # ------------------------------------------------------------------
    # register_key
    # ------------------------------------------------------------------

    def register_key(
        self,
        session_id: str,
        s3_key: str,
        max_files: int,
        portal_id: Optional[str] = None,
    ) -> RegisterResult:
        """Register a distinct S3 object key against an OPEN session.

        Uses transact_write_items with two operations:
        1. Put a KEY#{s3Key} guard item (attribute_not_exists(SK)) for idempotency.
        2. Update the META item: ADD expectedCount :one, SET lastHeartbeatAt/GSI1_SK,
           conditioned on status = OPEN AND expectedCount < maxFilesPerSession.

        Inspects CancellationReasons on TransactionCanceledException:
        - Key guard failure (index 0) → already counted, no-op success (R1.3)
        - META failure (index 1) → re-read to distinguish not-OPEN vs cap-exceeded

        Parameters
        ----------
        session_id : str
            The session to register the key against.
        s3_key : str
            The S3 object key being registered.
        max_files : int
            The portal's maxFilesPerSession cap.

        Returns
        -------
        RegisterResult
            Indicates success, already_counted, not_open, or cap_exceeded.
        """
        now = utc_now_z(self._clock)
        pk = _pk(session_id)

        try:
            self._client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self._table_name,
                            "Item": {
                                "PK": {"S": pk},
                                "SK": {"S": _sk_key(s3_key)},
                            },
                            "ConditionExpression": "attribute_not_exists(SK)",
                        }
                    },
                    {
                        "Update": {
                            "TableName": self._table_name,
                            "Key": {
                                "PK": {"S": pk},
                                "SK": {"S": _sk_meta()},
                            },
                            "UpdateExpression": (
                                "ADD expectedCount :one "
                                "SET lastHeartbeatAt = :now, GSI1_SK = :now"
                            ),
                            "ConditionExpression": (
                                "#st = :open AND expectedCount < :max_files"
                            ),
                            "ExpressionAttributeNames": {"#st": "status"},
                            "ExpressionAttributeValues": {
                                ":one": {"N": "1"},
                                ":now": {"S": now},
                                ":open": {"S": "OPEN"},
                                ":max_files": {"N": str(max_files)},
                            },
                        }
                    },
                ]
            )
            self._emit_metric("UploadSessionExtended", portal_id=portal_id)
            return RegisterResult(success=True, already_counted=False)

        except self._client.exceptions.TransactionCanceledException as exc:
            reasons = exc.response.get("CancellationReasons", [])
            return self._classify_register_cancellation(reasons, session_id)

    def _classify_register_cancellation(
        self, reasons: list, session_id: str
    ) -> RegisterResult:
        """Classify a transact_write_items cancellation for register_key.

        Parameters
        ----------
        reasons : list
            CancellationReasons from the TransactionCanceledException response.
        session_id : str
            The session id for potential re-read.

        Returns
        -------
        RegisterResult
        """
        key_reason = reasons[0] if len(reasons) > 0 else {}
        meta_reason = reasons[1] if len(reasons) > 1 else {}

        key_failed = key_reason.get("Code") == "ConditionalCheckFailed"
        meta_failed = meta_reason.get("Code") == "ConditionalCheckFailed"

        # Case 1: key guard failed → key already counted (idempotent no-op)
        if key_failed and not meta_failed:
            return RegisterResult(success=True, already_counted=True)

        # Case 2: both failed → also already counted (the META condition cannot
        # be evaluated independently when the transaction is cancelled due to key)
        if key_failed and meta_failed:
            return RegisterResult(success=True, already_counted=True)

        # Case 3: only META failed → session is not OPEN or cap exceeded
        if meta_failed and not key_failed:
            return self._distinguish_meta_failure(session_id)

        # Unexpected cancellation
        return RegisterResult(
            success=False,
            already_counted=False,
            error="Unexpected transaction cancellation",
        )

    def _distinguish_meta_failure(self, session_id: str) -> RegisterResult:
        """Re-read the META item to distinguish not-OPEN from cap-exceeded.

        When the META update condition fails, the session may either be in a
        non-OPEN status or the expectedCount has reached maxFilesPerSession.
        A re-read of the item determines which case applies.

        Parameters
        ----------
        session_id : str
            The session to inspect.

        Returns
        -------
        RegisterResult
        """
        try:
            response = self._table.get_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                ConsistentRead=True,
            )
        except Exception:
            return RegisterResult(
                success=False,
                already_counted=False,
                error="Failed to read session for failure classification",
            )

        item = response.get("Item")
        if not item:
            return RegisterResult(
                success=False,
                already_counted=False,
                not_open=True,
                error="Session not found",
            )

        status = item.get("status", "")
        if status != "OPEN":
            return RegisterResult(
                success=False,
                already_counted=False,
                not_open=True,
                error=f"Session status is {status}",
            )

        # Status is OPEN, so the failure must be the cap condition
        return RegisterResult(
            success=False,
            already_counted=False,
            cap_exceeded=True,
            error="Registration would exceed maxFilesPerSession",
        )

    # ------------------------------------------------------------------
    # heartbeat
    # ------------------------------------------------------------------

    def heartbeat(self, session_id: str, min_interval_seconds: int) -> bool:
        """Send a heartbeat to an OPEN session, rate-limited.

        Updates `lastHeartbeatAt` and `GSI1_SK` only if the session is OPEN and
        the previous heartbeat was recorded more than `min_interval_seconds` ago.

        Parameters
        ----------
        session_id : str
            The session to heartbeat.
        min_interval_seconds : int
            Minimum seconds between accepted heartbeats (heartbeat_min_interval_seconds).

        Returns
        -------
        bool
            True if the heartbeat was accepted, False if rate-limited.
        """
        now_dt = self._clock()
        now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        min_next_dt = now_dt - timedelta(seconds=min_interval_seconds)
        min_next = min_next_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression="SET lastHeartbeatAt = :now, GSI1_SK = :now",
                ConditionExpression="#st = :open AND lastHeartbeatAt < :min_next",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":now": now,
                    ":min_next": min_next,
                },
            )
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # get_session
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve the META item for a session.

        Parameters
        ----------
        session_id : str
            The session to retrieve.

        Returns
        -------
        dict or None
            The session META item, or None if not found.
        """
        response = self._table.get_item(
            Key={"PK": _pk(session_id), "SK": _sk_meta()},
            ConsistentRead=True,
        )
        return response.get("Item")

    # ------------------------------------------------------------------
    # finalize
    # ------------------------------------------------------------------

    def finalize(self, session_id: str, declared_count: int) -> FinalizeResult:
        """Finalize an OPEN session: set the authoritative expectedCount and marker.

        Steps:
        1. Read the META item to get the stored `maxFilesPerSession`.
        2. Compute `capped = min(declared_count, maxFilesPerSession)`.
        3. Conditional update: SET expectedCount, lastHeartbeatAt, and the
           finalize marker (idempotent via if_not_exists), conditioned on
           status = OPEN.
        4. On success, attempt the terminal transition.
        5. On ConditionalCheckFailedException, leave the session OPEN and
           return a retryable result (R3.6).

        Parameters
        ----------
        session_id : str
            The session to finalize.
        declared_count : int
            The client-declared total file count.

        Returns
        -------
        FinalizeResult
            Indicates whether the session completed, is still open, or
            the write failed (retryable).
        """
        # Step 1: read META to get the stored maxFilesPerSession
        item = self.get_session(session_id)
        if not item:
            return FinalizeResult(completed=False, still_open=True, write_failed=True)

        max_files = int(item.get("maxFilesPerSession", declared_count))

        # Step 2: compute capped expectedCount
        capped = min(declared_count, max_files)

        # Step 3: conditional update with finalize marker
        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET expectedCount = :capped, "
                    "lastHeartbeatAt = :now, "
                    "finalizeRequestedAt = if_not_exists(finalizeRequestedAt, :now)"
                ),
                ConditionExpression="#st = :open",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":capped": capped,
                    ":now": now,
                },
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            # Write failed — session is not OPEN; leave OPEN and return retryable (R3.6)
            return FinalizeResult(completed=False, still_open=True, write_failed=True)

        # Emit metric for successful finalization
        portal_id = item.get("portalId")
        self._emit_metric("UploadSessionFinalized", portal_id=portal_id)

        # Step 4: attempt terminal transition
        transitioned = self.try_terminal_transition(session_id, portal_id=portal_id)
        return FinalizeResult(
            completed=transitioned,
            still_open=not transitioned,
            write_failed=False,
        )

    # ------------------------------------------------------------------
    # mark_asset_complete
    # ------------------------------------------------------------------

    def mark_asset_complete(
        self, session_id: str, asset_id: str, portal_id: Optional[str] = None
    ) -> MarkResult:
        """Mark an asset as complete for an OPEN session (idempotent).

        Uses transact_write_items with two operations:
        1. Put an ASSET#{assetId} guard item (attribute_not_exists(SK)) for idempotency.
        2. Update the META item: ADD completedCount :one, conditioned on status = OPEN.

        On success, calls try_terminal_transition to attempt OPEN → COMPLETE.

        Inspects CancellationReasons on TransactionCanceledException:
        - ASSET put failed (index 0) → already counted, no-op (R5.3)
        - META update failed (index 1) → session not OPEN
        - Both failed → already counted

        Parameters
        ----------
        session_id : str
            The session to mark the asset against.
        asset_id : str
            The asset id being marked complete.

        Returns
        -------
        MarkResult
            Indicates whether the asset was newly marked or already counted.
        """
        pk = _pk(session_id)

        try:
            self._client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self._table_name,
                            "Item": {
                                "PK": {"S": pk},
                                "SK": {"S": _sk_asset(asset_id)},
                            },
                            "ConditionExpression": "attribute_not_exists(SK)",
                        }
                    },
                    {
                        "Update": {
                            "TableName": self._table_name,
                            "Key": {
                                "PK": {"S": pk},
                                "SK": {"S": _sk_meta()},
                            },
                            "UpdateExpression": "ADD completedCount :one",
                            "ConditionExpression": "#st = :open",
                            "ExpressionAttributeNames": {"#st": "status"},
                            "ExpressionAttributeValues": {
                                ":one": {"N": "1"},
                                ":open": {"S": "OPEN"},
                            },
                        }
                    },
                ]
            )
        except self._client.exceptions.TransactionCanceledException as exc:
            reasons = exc.response.get("CancellationReasons", [])
            return self._classify_mark_cancellation(reasons)

        # First-time mark succeeded — attempt terminal transition
        self._emit_metric("UploadAssetMarkedComplete", portal_id=portal_id)
        self.try_terminal_transition(session_id, portal_id=portal_id)
        return MarkResult(marked=True, already_counted=False)

    def _classify_mark_cancellation(self, reasons: list) -> MarkResult:
        """Classify a transact_write_items cancellation for mark_asset_complete.

        Parameters
        ----------
        reasons : list
            CancellationReasons from the TransactionCanceledException response.

        Returns
        -------
        MarkResult
        """
        asset_reason = reasons[0] if len(reasons) > 0 else {}
        meta_reason = reasons[1] if len(reasons) > 1 else {}

        asset_failed = asset_reason.get("Code") == "ConditionalCheckFailed"
        meta_failed = meta_reason.get("Code") == "ConditionalCheckFailed"

        # Case 1: ASSET guard failed → already counted (idempotent no-op, R5.3)
        if asset_failed:
            return MarkResult(marked=False, already_counted=True)

        # Case 2: only META failed → session not OPEN
        if meta_failed and not asset_failed:
            return MarkResult(marked=False, already_counted=False)

        # Unexpected cancellation — treat as not marked
        return MarkResult(marked=False, already_counted=False)

    # ------------------------------------------------------------------
    # reconcile_idle
    # ------------------------------------------------------------------

    def reconcile_idle(self, session_id: str) -> bool:
        """Apply the finalize marker to an idle OPEN session and attempt completion.

        Called by the reconciliation sweep when `now - lastHeartbeatAt` exceeds the
        Idle_Finalize_Threshold and the session does NOT yet have a finalizeRequestedAt
        attribute.

        Steps:
        1. Read the META item to get the current `expectedCount`.
        2. Apply the finalize marker: SET expectedCount (re-affirm current),
           lastHeartbeatAt = now, finalizeRequestedAt = if_not_exists(finalizeRequestedAt, now),
           conditioned on status = OPEN.
        3. Call try_terminal_transition (may complete immediately if all assets are done).
        4. Return True if the marker was applied, False on condition failure.

        Parameters
        ----------
        session_id : str
            The session to reconcile.

        Returns
        -------
        bool
            True if the finalize marker was applied (or already present), False if
            the session is no longer OPEN.
        """
        # Step 1: read the META item
        item = self.get_session(session_id)
        if not item:
            return False

        current_expected = int(item.get("expectedCount", 0))

        # Step 2: conditional update with finalize marker
        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET expectedCount = :expected, "
                    "lastHeartbeatAt = :now, "
                    "finalizeRequestedAt = if_not_exists(finalizeRequestedAt, :now)"
                ),
                ConditionExpression="#st = :open",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":expected": current_expected,
                    ":now": now,
                },
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

        # Step 3: attempt terminal transition
        self.try_terminal_transition(session_id, portal_id=item.get("portalId"))
        return True

    # ------------------------------------------------------------------
    # reconcile_grace
    # ------------------------------------------------------------------

    def reconcile_grace(self, session_id: str) -> bool:
        """Force-complete a finalized session that exceeded the Completion_Grace_Period.

        Called by the reconciliation sweep when the session IS finalized AND
        `now - finalizeRequestedAt > Completion_Grace_Period` AND
        `completedCount < expectedCount`.

        Steps:
        1. Read the META item to get expectedCount and completedCount.
        2. Compute failedCount = expectedCount - completedCount.
        3. Force-complete: SET status = COMPLETE_WITH_ERRORS, completedAt = now,
           failedCount = computed value, REMOVE GSI1_PK and GSI1_SK,
           conditioned on status = OPEN.
        4. Return True if the force-complete succeeded, False on condition failure.

        Parameters
        ----------
        session_id : str
            The session to force-complete.

        Returns
        -------
        bool
            True if the force-complete succeeded, False if the session already
            transitioned.
        """
        # Step 1: read the META item
        item = self.get_session(session_id)
        if not item:
            return False

        expected_count = int(item.get("expectedCount", 0))
        completed_count = int(item.get("completedCount", 0))
        portal_id = item.get("portalId")

        # Step 2: compute failedCount
        failed_count = expected_count - completed_count

        # Step 3: force-complete conditional update
        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :cwe, completedAt = :now, failedCount = :failed "
                    "REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression="#st = :open",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":cwe": "COMPLETE_WITH_ERRORS",
                    ":now": now,
                    ":failed": failed_count,
                    ":open": "OPEN",
                },
            )
            self._emit_metric("UploadSessionCompletedWithErrors", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # reconcile_max_age
    # ------------------------------------------------------------------

    def reconcile_max_age(self, session_id: str) -> bool:
        """Force-complete a session that exceeded the Maximum_Session_Age.

        Called by the reconciliation sweep when `now - createdAt > Maximum_Session_Age`
        regardless of finalize state.

        Steps:
        1. Read the META item to get expectedCount and completedCount.
        2. Compute failedCount = expectedCount - completedCount.
        3. Force-complete: SET status = COMPLETE_WITH_ERRORS, completedAt = now,
           failedCount = computed value, REMOVE GSI1_PK and GSI1_SK,
           conditioned on status = OPEN.
        4. Return True if the force-complete succeeded, False on condition failure.

        Parameters
        ----------
        session_id : str
            The session to force-complete.

        Returns
        -------
        bool
            True if the force-complete succeeded, False if the session already
            transitioned.
        """
        # Step 1: read the META item
        item = self.get_session(session_id)
        if not item:
            return False

        expected_count = int(item.get("expectedCount", 0))
        completed_count = int(item.get("completedCount", 0))
        portal_id = item.get("portalId")

        # Step 2: compute failedCount
        failed_count = expected_count - completed_count

        # Step 3: force-complete conditional update
        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :cwe, completedAt = :now, failedCount = :failed "
                    "REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression="#st = :open",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":cwe": "COMPLETE_WITH_ERRORS",
                    ":now": now,
                    ":failed": failed_count,
                    ":open": "OPEN",
                },
            )
            self._emit_metric("UploadSessionCompletedWithErrors", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # try_terminal_transition
    # ------------------------------------------------------------------

    def try_terminal_transition(
        self, session_id: str, portal_id: Optional[str] = None
    ) -> bool:
        """Attempt the conditional OPEN -> COMPLETE transition.

        Succeeds only when all three conditions hold:
        - status is OPEN
        - finalizeRequestedAt exists (the finalize marker is set)
        - completedCount >= expectedCount

        On success, sets status to COMPLETE, records completedAt, and removes
        the GSI1 attributes so the session drops out of the reconciliation index.

        Parameters
        ----------
        session_id : str
            The session to attempt completion on.
        portal_id : str, optional
            The portalId for metric emission dimension.

        Returns
        -------
        bool
            True if this actor won the transition (session is now COMPLETE),
            False if the conditions were not met.
        """
        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :complete, completedAt = :now " "REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression=(
                    "#st = :open AND attribute_exists(finalizeRequestedAt) "
                    "AND completedCount >= expectedCount"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":complete": "COMPLETE",
                    ":now": now,
                },
            )
            self._emit_metric("UploadSessionCompleted", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # set_batch_metadata
    # ------------------------------------------------------------------

    def set_batch_metadata(self, session_id: str, user_metadata: dict) -> None:
        """Capture the batch's user-entered metadata onto the session META item, once.

        Portal forms are batch-uniform (filled once, applied to every file), so we
        record the first non-empty user-metadata map and never overwrite it. Stored
        as a `userMetadata` Map of {slug: stringValue}. No-op when user_metadata is
        empty. Best-effort: a conditional failure (already set) is swallowed.
        """
        if not user_metadata:
            return

        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression="SET userMetadata = if_not_exists(userMetadata, :m)",
                ExpressionAttributeValues={":m": dict(user_metadata)},
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            # First capture wins; nothing to do if userMetadata is already set.
            pass
        except Exception:
            # Best-effort: never break the upload path on a metadata-capture failure.
            pass
