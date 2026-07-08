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


def _pk_portal(portal_id: str) -> str:
    """Build partition key for a portal-scoped item (e.g. batch-token mappings)."""
    return f"PORTAL#{portal_id}"


def _sk_batch_token(batch_token: str) -> str:
    """Sort key for a client batch-token -> session mapping."""
    return f"BATCHTOKEN#{batch_token}"


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


@dataclass(frozen=True)
class ReleaseResult:
    """Result of a release_key operation.

    Possible states:
    - success=True, already_released=False: key guard removed, expectedCount decremented
    - success=True, already_released=True:  guard was already gone, no-op (idempotent)
    - success=False, not_open=True:         session is not OPEN (terminal or missing)
    """

    success: bool
    already_released: bool
    not_open: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Terminal session statuses (two-signal 2x2 model)
# ---------------------------------------------------------------------------
#
# A session is created OPEN and reaches exactly one terminal status. Each
# terminal status encodes the two independent signals a downstream pipeline
# branches on:
#
#   * filesProcessed          - every uploaded file reached a terminal pipeline
#                               state AND none failed
#                               (``completedCount >= expectedCount`` and
#                               ``failedCount == 0``).
#   * formSubmissionComplete  - the user clicked Submit (the ``finalizeRequestedAt``
#                               marker is present).
#
#   SUBMITTED_PROCESSED       filesProcessed=true,  formSubmissionComplete=true
#   SUBMITTED_UNPROCESSED     filesProcessed=false, formSubmissionComplete=true
#                             (submitted, but some files failed or never finished)
#   UNSUBMITTED_PROCESSED     filesProcessed=true,  formSubmissionComplete=false
#                             (all uploaded files succeeded, user never submitted)
#   UNSUBMITTED_UNPROCESSED   filesProcessed=false, formSubmissionComplete=false
#                             (never submitted and files never all succeeded)
#
# Only the first three EMIT an ``Upload Batch Completed`` event.
# UNSUBMITTED_UNPROCESSED is silent (nothing actionable happened).

STATUS_OPEN = "OPEN"
STATUS_SUBMITTED_PROCESSED = "SUBMITTED_PROCESSED"
STATUS_SUBMITTED_UNPROCESSED = "SUBMITTED_UNPROCESSED"
STATUS_UNSUBMITTED_PROCESSED = "UNSUBMITTED_PROCESSED"
STATUS_UNSUBMITTED_UNPROCESSED = "UNSUBMITTED_UNPROCESSED"

#: Terminal statuses that publish an ``Upload Batch Completed`` pipeline event.
#: UNSUBMITTED_UNPROCESSED (the silent false/false corner) is excluded.
EMITTING_TERMINAL_STATUSES = frozenset(
    {
        STATUS_SUBMITTED_PROCESSED,
        STATUS_SUBMITTED_UNPROCESSED,
        STATUS_UNSUBMITTED_PROCESSED,
    }
)

#: Statuses for which ``filesProcessed`` is true.
_FILES_PROCESSED_STATUSES = frozenset(
    {STATUS_SUBMITTED_PROCESSED, STATUS_UNSUBMITTED_PROCESSED}
)

#: Statuses for which ``formSubmissionComplete`` is true.
_FORM_SUBMITTED_STATUSES = frozenset(
    {STATUS_SUBMITTED_PROCESSED, STATUS_SUBMITTED_UNPROCESSED}
)


def derive_signals(status: Optional[str]) -> "tuple[str, str]":
    """Map a terminal status to the ``(filesProcessed, formSubmissionComplete)`` pair.

    Returns the two signals as the STRINGS ``"true"`` / ``"false"`` (not JSON
    booleans) because they ride the EventBridge event detail and are matched by
    the trigger node's string-interpolated event pattern — the same convention
    the portal form fields (``userMetadata``) already use. A non-terminal or
    unknown status yields ``("false", "false")``.
    """
    files_processed = "true" if status in _FILES_PROCESSED_STATUSES else "false"
    form_submission_complete = "true" if status in _FORM_SUBMITTED_STATUSES else "false"
    return files_processed, form_submission_complete


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
            # resolvedCount = completedCount + failedCount, maintained as its own
            # attribute because DynamoDB condition expressions cannot evaluate the
            # arithmetic sum ``completedCount + failedCount >= expectedCount``. The
            # join and reconciliation conditions compare this attribute directly.
            "resolvedCount": 0,
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
    # get_or_create_session_by_token
    # ------------------------------------------------------------------

    def get_or_create_session_by_token(
        self,
        portal_id: str,
        automation_tag: str,
        max_files: int,
        retention_days: int,
        batch_token: str,
    ) -> str:
        """Idempotently resolve a single session for a client batch token.

        A multi-file upload issues several concurrent ``POST /upload`` calls.
        Without a shared key, every call that arrives before the first session
        exists would mint its own session and the batch would fragment across
        many sessions. This method maps a client-supplied ``batchToken`` to
        exactly ONE session so all concurrent callers converge on the same
        sessionId (server-side dedupe; defense-in-depth with the client
        single-flight).

        Race-safe ordering (create-session-then-claim-token):
        1. Fast path — if the token already maps to a session, reuse it.
        2. Otherwise create a fresh session META item (existing create_session).
        3. Claim the token with a conditional put (attribute_not_exists(SK)):
           - on success, the freshly created session wins;
           - on ConditionalCheckFailedException, another caller already claimed
             the token, so re-read and return the winner's sessionId.

        Creating the session BEFORE claiming the token guarantees the token
        never points at a not-yet-created session META. Sessions created by the
        losing callers are harmless: they hold zero registered keys and expire
        via the same TTL / reconciliation sweep as any empty session.

        Parameters
        ----------
        portal_id : str
            The authenticated portalId (token mappings are namespaced per portal).
        automation_tag : str
            The portal's automationTag value (forwarded to create_session).
        max_files : int
            The portal's maxFilesPerSession cap (forwarded to create_session).
        retention_days : int
            Session retention period in days (TTL basis, shared with create_session).
        batch_token : str
            The client-supplied per-batch token that disambiguates the session.

        Returns
        -------
        str
            The sessionId that all callers sharing this (portal_id, batch_token)
            resolve to.
        """
        token_key = {
            "PK": _pk_portal(portal_id),
            "SK": _sk_batch_token(batch_token),
        }

        # 1. Fast path: the token already maps to a session — reuse it.
        existing = self._table.get_item(Key=token_key, ConsistentRead=True).get("Item")
        if existing and existing.get("sessionId"):
            return existing["sessionId"]

        # 2. Create a fresh session META (same automationTag/TTL conventions).
        record = self.create_session(
            portal_id=portal_id,
            automation_tag=automation_tag,
            max_files=max_files,
            retention_days=retention_days,
        )
        new_id = record["sessionId"]

        # 3. Claim the token idempotently. The conditional put guarantees only
        #    one concurrent caller wins the mapping; the rest re-read the winner.
        now_dt = self._clock()
        ttl = int(now_dt.timestamp()) + (retention_days * 86400)
        try:
            self._table.put_item(
                Item={**token_key, "sessionId": new_id, "ttl": ttl},
                ConditionExpression="attribute_not_exists(SK)",
            )
            return new_id
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            winner = self._table.get_item(Key=token_key, ConsistentRead=True).get(
                "Item"
            )
            return winner["sessionId"] if winner and winner.get("sessionId") else new_id

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
    # release_key
    # ------------------------------------------------------------------

    def release_key(self, session_id: str, s3_key: str) -> ReleaseResult:
        """Release a previously-registered key whose upload failed or was aborted.

        Mirrors ``register_key`` in reverse: deletes the ``KEY#{s3Key}`` guard
        and decrements ``expectedCount`` so a failed client upload no longer
        inflates the join's denominator. Called from the uploader's
        upload-error / multipart-abort paths — independent of submit — so the
        running ``expectedCount`` stays accurate even when the user never
        submits (the abandoned path relies on it).

        Idempotent via the guard: a dropped/retried call cannot double-decrement
        because the second delete finds no guard.

        Uses transact_write_items with two operations:
        1. Delete the ``KEY#{s3Key}`` guard (ConditionExpression
           attribute_exists(SK)).
        2. Update META: ``ADD expectedCount :neg_one``, refresh heartbeat,
           conditioned on ``status = OPEN AND expectedCount > 0``.

        On success, attempts the terminal transition: dropping ``expectedCount``
        can satisfy ``completedCount >= expectedCount`` and complete a submitted
        session cleanly (``SUBMITTED_PROCESSED``) instead of waiting out the
        grace period for ``SUBMITTED_UNPROCESSED``.

        Returns
        -------
        ReleaseResult
            success / already_released / not_open.
        """
        now = utc_now_z(self._clock)
        pk = _pk(session_id)
        try:
            self._client.transact_write_items(
                TransactItems=[
                    {
                        "Delete": {
                            "TableName": self._table_name,
                            "Key": {
                                "PK": {"S": pk},
                                "SK": {"S": _sk_key(s3_key)},
                            },
                            "ConditionExpression": "attribute_exists(SK)",
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
                                "ADD expectedCount :neg_one "
                                "SET lastHeartbeatAt = :now, GSI1_SK = :now"
                            ),
                            "ConditionExpression": (
                                "#st = :open AND expectedCount > :zero"
                            ),
                            "ExpressionAttributeNames": {"#st": "status"},
                            "ExpressionAttributeValues": {
                                ":neg_one": {"N": "-1"},
                                ":now": {"S": now},
                                ":open": {"S": "OPEN"},
                                ":zero": {"N": "0"},
                            },
                        }
                    },
                ]
            )
        except self._client.exceptions.TransactionCanceledException as exc:
            reasons = exc.response.get("CancellationReasons", [])
            return self._classify_release_cancellation(reasons)

        # Decrement won — the smaller denominator may now satisfy the join.
        self.try_terminal_transition(session_id)
        return ReleaseResult(success=True, already_released=False)

    def _classify_release_cancellation(self, reasons: list) -> ReleaseResult:
        """Classify a transact_write_items cancellation for release_key.

        Parameters
        ----------
        reasons : list
            CancellationReasons from the TransactionCanceledException response.

        Returns
        -------
        ReleaseResult
        """
        key_reason = reasons[0] if len(reasons) > 0 else {}
        meta_reason = reasons[1] if len(reasons) > 1 else {}

        key_failed = key_reason.get("Code") == "ConditionalCheckFailed"
        meta_failed = meta_reason.get("Code") == "ConditionalCheckFailed"

        # Guard already gone → key was never counted or already released (no-op).
        if key_failed:
            return ReleaseResult(success=True, already_released=True)

        # Only META failed → session not OPEN (terminal) or expectedCount == 0.
        if meta_failed and not key_failed:
            return ReleaseResult(
                success=False,
                already_released=False,
                not_open=True,
                error="Session not OPEN or expectedCount already zero",
            )

        return ReleaseResult(
            success=False,
            already_released=False,
            error="Unexpected transaction cancellation",
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
    # submit
    # ------------------------------------------------------------------

    def submit(
        self,
        session_id: str,
        user_metadata: Optional[dict] = None,
        uploaded_keys: Optional[list] = None,
        declared_count: Optional[int] = None,
    ) -> FinalizeResult:
        """Record an explicit user SUBMIT on an OPEN session.

        Submit — not upload completion — is the authoritative signal that the
        user is done. It is one half of the two-signal join in
        ``try_terminal_transition`` (the other half being
        ``completedCount >= expectedCount``, driven by asset processing). The
        order of the two signals does not matter: whichever arrives last wins
        the transition.

        This method, in a single conditional write (status = OPEN):
        1. Trues up ``expectedCount`` to the count of files that actually
           uploaded (see below) so the join's denominator matches reality.
        2. Overwrites ``userMetadata`` with the final form snapshot — the
           authoritative set of conditions downstream pipelines branch on.
           Unlike the old per-file capture, the submit snapshot always wins so
           fields edited AFTER the upload page are captured.
        3. Sets the submit marker (``finalizeRequestedAt``, idempotent via
           if_not_exists) that ``try_terminal_transition`` requires.
        4. Attempts the terminal transition.

        expectedCount true-up (do-both denominator):
        - The running ``expectedCount`` is maintained in real time by
          ``register_key`` (+1) / ``release_key`` (-1), so it stays accurate
          even when submit is never hit (the abandoned path relies on it).
        - When *uploaded_keys* is provided, submit additionally trues up to
          ``min(len(uploaded_keys), currentExpected)`` — honoring the client's
          report of what actually succeeded while never expecting MORE than the
          server registered. This is the backstop for a dropped
          ``release_key`` call.
        - When only *declared_count* is provided (legacy), it is likewise
          trued up to ``min(declared_count, currentExpected)``.
        - When neither is provided, the running count is left unchanged.

        Parameters
        ----------
        session_id : str
            The session being submitted.
        user_metadata : dict, optional
            The resolved, server-trusted final form snapshot (``{slug: value}``).
            Overwrites any previously captured ``userMetadata``.
        uploaded_keys : list, optional
            The S3 keys the client reports as successfully uploaded. Used to
            true up ``expectedCount``.
        declared_count : int, optional
            Legacy fallback total file count when *uploaded_keys* is absent.

        Returns
        -------
        FinalizeResult
            Indicates whether the session completed (both signals satisfied),
            is still open (awaiting processing), or the write failed (the
            session was not OPEN — retryable / already terminal).
        """
        item = self.get_session(session_id)
        if not item:
            return FinalizeResult(completed=False, still_open=True, write_failed=True)

        current_expected = int(item.get("expectedCount", 0) or 0)

        # Authoritative expectedCount true-up. The running expectedCount is kept
        # accurate in real time by register_key (+1) / release_key (-1); submit
        # additionally trues it up to what the client reports actually uploaded,
        # but NEVER higher than the server-registered count (the cross-check
        # backstop for a dropped release_key call).
        reported = None
        if uploaded_keys is not None:
            reported = len(uploaded_keys)
        elif declared_count is not None:
            reported = declared_count
        if reported is not None:
            target_expected = min(max(reported, 0), current_expected)
        else:
            target_expected = current_expected

        now = utc_now_z(self._clock)

        set_clauses = [
            "expectedCount = :exp",
            "lastHeartbeatAt = :now",
            "finalizeRequestedAt = if_not_exists(finalizeRequestedAt, :now)",
        ]
        values = {
            ":open": "OPEN",
            ":exp": target_expected,
            ":now": now,
        }
        # Authoritative overwrite of the form snapshot (submit wins).
        if user_metadata:
            set_clauses.append("userMetadata = :m")
            values[":m"] = dict(user_metadata)

        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression="SET " + ", ".join(set_clauses),
                ConditionExpression="#st = :open",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues=values,
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            # Not OPEN (already terminal or missing) — leave as-is, retryable.
            return FinalizeResult(completed=False, still_open=True, write_failed=True)

        portal_id = item.get("portalId")
        self._emit_metric("UploadSessionSubmitted", portal_id=portal_id)

        # Attempt the join — completes now iff processing already finished.
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
                            "UpdateExpression": "ADD completedCount :one, resolvedCount :one",
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
    # mark_asset_failed
    # ------------------------------------------------------------------

    def mark_asset_failed(
        self, session_id: str, asset_id: str, portal_id: Optional[str] = None
    ) -> MarkResult:
        """Mark an asset as FAILED for an OPEN session (idempotent).

        The companion to :meth:`mark_asset_complete`, called from the
        ``mark_asset_failed`` node placed on a pipeline's error/catch branch. A
        genuine in-pipeline processing failure (transcode error, corrupt-but-
        valid file, a node timeout, ...) increments ``failedCount`` so the join
        can resolve PROMPTLY instead of blocking on the grace timeout, while
        still surfacing the batch as "submitted, with errors"
        (SUBMITTED_UNPROCESSED / ``filesProcessed=false``).

        Uses transact_write_items with two operations:
        1. Put an ``ASSET#{assetId}`` guard item (``attribute_not_exists(SK)``).
           This is the SAME guard key ``mark_asset_complete`` uses, so an asset
           is counted EXACTLY ONCE across both signals — whichever terminal
           result (complete or fail) lands first wins, and the other is an
           idempotent no-op. This is what keeps Step Functions retries (which
           run BEFORE the catch branch) from prematurely marking failure, and
           prevents a late straggler from double-counting.
        2. Update the META item: ``ADD failedCount :one, resolvedCount :one``,
           conditioned on ``status = OPEN``.

        On a first-time mark, attempts the terminal transition.

        Note on validation/upload rejections: a file rejected for MIME/type/size
        never reaches a pipeline (it is blocked at file selection and again at
        the presigned-URL step, BEFORE ``register_key``), so it never enters
        ``expectedCount`` and MUST NOT be routed here — it is not a failure. This
        node is exclusively for files that were accepted, uploaded, and then
        errored during processing.

        Parameters
        ----------
        session_id : str
            The session to mark the asset failure against.
        asset_id : str
            The asset id that failed processing.
        portal_id : str, optional
            The portalId for metric emission dimension.

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
                            "UpdateExpression": "ADD failedCount :one, resolvedCount :one",
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

        # First-time mark succeeded — attempt terminal transition. A failure can
        # complete the join for a submitted session (resolvedCount catches up to
        # expectedCount), resolving it as SUBMITTED_UNPROCESSED without waiting
        # out the grace period.
        self._emit_metric("UploadAssetMarkedFailed", portal_id=portal_id)
        self.try_terminal_transition(session_id, portal_id=portal_id)
        return MarkResult(marked=True, already_counted=False)

    # ------------------------------------------------------------------
    # reconcile_idle_unsubmitted
    # ------------------------------------------------------------------

    def reconcile_idle_unsubmitted(self, session_id: str) -> bool:
        """Emit the never-submitted-but-all-files-processed outcome (T/F).

        Called by the reconciliation sweep when a session has been idle past the
        Idle Timeout AND carries NO submit marker AND every uploaded file
        succeeded (``completedCount >= expectedCount``, ``failedCount == 0``, and
        at least one file was uploaded). Transitions OPEN ->
        UNSUBMITTED_PROCESSED so the stream processor emits
        ``filesProcessed=true`` / ``formSubmissionComplete=false`` — letting a
        pipeline act on assets that arrived even though the user never submitted
        the form.

        Never fires when the user submitted (that path completes via the join or
        the grace sweep), when any file failed or is still processing (that stays
        OPEN until it succeeds or hits max age -> UNSUBMITTED_UNPROCESSED, which
        is silent), or when the session is empty (``expectedCount == 0`` ->
        nothing happened).

        The write is conditioned on
        ``status = OPEN AND attribute_not_exists(finalizeRequestedAt) AND
        completedCount >= expectedCount AND failedCount = 0 AND expectedCount > 0``
        so a concurrent Submit can never be clobbered — if the marker appears
        first, this condition fails and the session completes via the join.

        Parameters
        ----------
        session_id : str
            The session to transition.

        Returns
        -------
        bool
            True if this actor transitioned the session, False if the condition
            was not met (already terminal, missing, submitted, incomplete,
            failed, or empty).
        """
        portal_id = None
        item = self.get_session(session_id)
        if item:
            portal_id = item.get("portalId")

        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :up, completedAt = :now REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression=(
                    "#st = :open AND attribute_not_exists(finalizeRequestedAt) "
                    "AND completedCount >= expectedCount AND failedCount = :zero "
                    "AND expectedCount > :zero"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":up": STATUS_UNSUBMITTED_PROCESSED,
                    ":now": now,
                    ":zero": 0,
                },
            )
            self._emit_metric("UploadSessionUnsubmittedProcessed", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # reconcile_grace
    # ------------------------------------------------------------------

    def reconcile_grace(self, session_id: str) -> bool:
        """Force-complete a SUBMITTED session that exceeded the Completion Grace Period.

        Called by the reconciliation sweep when the session IS submitted
        (``finalizeRequestedAt`` present) AND
        ``now - finalizeRequestedAt > Completion_Grace_Period`` AND some files
        never reached a terminal state (``resolvedCount < expectedCount``).

        Force-completes as SUBMITTED_UNPROCESSED (``filesProcessed=false`` /
        ``formSubmissionComplete=true``) — the "submitted, with errors" outcome.
        Records ``failedCount = expectedCount - completedCount`` (counting the
        stuck-and-never-resolved files as failed for reporting) and drops the
        session out of the GSI1 index. Conditioned on
        ``status = OPEN AND attribute_exists(finalizeRequestedAt)`` so it only
        ever resolves a genuinely submitted session.

        Parameters
        ----------
        session_id : str
            The session to force-complete.

        Returns
        -------
        bool
            True if the force-complete succeeded, False on condition failure.
        """
        # Step 1: read the META item
        item = self.get_session(session_id)
        if not item:
            return False

        expected_count = int(item.get("expectedCount", 0))
        completed_count = int(item.get("completedCount", 0))
        portal_id = item.get("portalId")

        # Step 2: compute failedCount (stuck files counted as failed)
        failed_count = max(expected_count - completed_count, 0)

        # Step 3: force-complete conditional update
        now = utc_now_z(self._clock)
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :su, completedAt = :now, failedCount = :failed "
                    "REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression=(
                    "#st = :open AND attribute_exists(finalizeRequestedAt)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":su": STATUS_SUBMITTED_UNPROCESSED,
                    ":now": now,
                    ":failed": failed_count,
                    ":open": "OPEN",
                },
            )
            self._emit_metric("UploadSessionSubmittedUnprocessed", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # reconcile_max_age
    # ------------------------------------------------------------------

    def reconcile_max_age(self, session_id: str) -> bool:
        """Force-resolve a session that exceeded the Maximum Session Age.

        The hard-cap backstop, applied regardless of how far the session got.
        The terminal status is the matching corner of the 2x2 model, chosen by
        (submit marker present?) x (all uploaded files succeeded?):

            marker    + all succeeded        -> SUBMITTED_PROCESSED     (fires)
            marker    + some failed/stuck    -> SUBMITTED_UNPROCESSED   (fires)
            no marker + all succeeded (>0)   -> UNSUBMITTED_PROCESSED   (fires)
            no marker + some failed/stuck    -> UNSUBMITTED_UNPROCESSED (silent)
                      or empty session

        To stay race-safe against a concurrent Submit or a late asset signal,
        each corner is attempted as its own conditional write; the specific
        "processed" corners are tried BEFORE the catch-all "unprocessed"
        fallbacks so whichever matches current state wins and the rest fail on
        the ``status = OPEN`` guard.

        Parameters
        ----------
        session_id : str
            The session to force-resolve.

        Returns
        -------
        bool
            True if this actor resolved the session, False if it had already
            transitioned.
        """
        item = self.get_session(session_id)
        if not item:
            return False

        expected_count = int(item.get("expectedCount", 0) or 0)
        completed_count = int(item.get("completedCount", 0) or 0)
        portal_id = item.get("portalId")
        failed_count = max(expected_count - completed_count, 0)
        now = utc_now_z(self._clock)

        def _attempt(
            new_status: str, condition: str, extra_values: dict, write_failed: bool
        ) -> bool:
            set_clause = "#st = :status, completedAt = :now"
            values = {":status": new_status, ":now": now, **extra_values}
            if write_failed:
                set_clause += ", failedCount = :failed"
                values[":failed"] = failed_count
            try:
                self._table.update_item(
                    Key={"PK": _pk(session_id), "SK": _sk_meta()},
                    UpdateExpression=f"SET {set_clause} REMOVE GSI1_PK, GSI1_SK",
                    ConditionExpression=condition,
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues=values,
                )
                return True
            except self._table.meta.client.exceptions.ConditionalCheckFailedException:
                return False

        # Corner 1: submitted + all files succeeded -> SUBMITTED_PROCESSED.
        if _attempt(
            STATUS_SUBMITTED_PROCESSED,
            (
                "#st = :open AND attribute_exists(finalizeRequestedAt) "
                "AND completedCount >= expectedCount AND failedCount = :zero"
            ),
            {":open": "OPEN", ":zero": 0},
            write_failed=False,
        ):
            self._emit_metric("UploadSessionSubmittedProcessed", portal_id=portal_id)
            return True

        # Corner 2: never submitted + all files succeeded (>0) -> UNSUBMITTED_PROCESSED.
        if _attempt(
            STATUS_UNSUBMITTED_PROCESSED,
            (
                "#st = :open AND attribute_not_exists(finalizeRequestedAt) "
                "AND completedCount >= expectedCount AND failedCount = :zero "
                "AND expectedCount > :zero"
            ),
            {":open": "OPEN", ":zero": 0},
            write_failed=False,
        ):
            self._emit_metric("UploadSessionUnsubmittedProcessed", portal_id=portal_id)
            return True

        # Corner 3: submitted + some failed/stuck -> SUBMITTED_UNPROCESSED (fires).
        if _attempt(
            STATUS_SUBMITTED_UNPROCESSED,
            "#st = :open AND attribute_exists(finalizeRequestedAt)",
            {":open": "OPEN"},
            write_failed=True,
        ):
            self._emit_metric("UploadSessionSubmittedUnprocessed", portal_id=portal_id)
            return True

        # Corner 4: never submitted + some failed/stuck or empty ->
        # UNSUBMITTED_UNPROCESSED (silent).
        if _attempt(
            STATUS_UNSUBMITTED_UNPROCESSED,
            "#st = :open AND attribute_not_exists(finalizeRequestedAt)",
            {":open": "OPEN"},
            write_failed=True,
        ):
            self._emit_metric(
                "UploadSessionUnsubmittedUnprocessed", portal_id=portal_id
            )
            return True

        return False

    # ------------------------------------------------------------------
    # try_terminal_transition
    # ------------------------------------------------------------------

    def try_terminal_transition(
        self, session_id: str, portal_id: Optional[str] = None
    ) -> bool:
        """Attempt the conditional OPEN -> submitted-terminal transition.

        The submit-side half of the two-signal join: fires only for a SUBMITTED
        session (``finalizeRequestedAt`` present) once every uploaded file has
        reached a terminal state (``resolvedCount >= expectedCount``, where
        ``resolvedCount = completedCount + failedCount``). The resulting status
        depends on whether any file failed:

          - failedCount == 0  -> SUBMITTED_PROCESSED    (filesProcessed=true)
          - failedCount  > 0  -> SUBMITTED_UNPROCESSED  (filesProcessed=false)

        ``resolvedCount`` is compared instead of ``completedCount + failedCount``
        because DynamoDB condition expressions cannot evaluate arithmetic sums;
        it is maintained as its own counter by ``mark_asset_complete`` and
        ``mark_asset_failed``.

        Idempotent and race-safe: both attempts are conditioned on
        ``status = OPEN``, so whichever of the submit / asset signals arrives
        last wins the single transition and repeated calls are no-ops.

        Parameters
        ----------
        session_id : str
            The session to attempt completion on.
        portal_id : str, optional
            The portalId for metric emission dimension.

        Returns
        -------
        bool
            True if this actor won the transition, False if the conditions were
            not met (not submitted, files still pending, or already terminal).
        """
        now = utc_now_z(self._clock)

        # Attempt 1: all files succeeded -> SUBMITTED_PROCESSED (true/true).
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :sp, completedAt = :now REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression=(
                    "#st = :open AND attribute_exists(finalizeRequestedAt) "
                    "AND resolvedCount >= expectedCount AND failedCount = :zero"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":sp": STATUS_SUBMITTED_PROCESSED,
                    ":now": now,
                    ":zero": 0,
                },
            )
            self._emit_metric("UploadSessionSubmittedProcessed", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            pass

        # Attempt 2: all files resolved but some failed -> SUBMITTED_UNPROCESSED
        # (false/true). This lets a genuine processing failure complete the join
        # PROMPTLY as "submitted, with errors" instead of waiting out the grace
        # period.
        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression=(
                    "SET #st = :su, completedAt = :now REMOVE GSI1_PK, GSI1_SK"
                ),
                ConditionExpression=(
                    "#st = :open AND attribute_exists(finalizeRequestedAt) "
                    "AND resolvedCount >= expectedCount AND failedCount > :zero"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":open": "OPEN",
                    ":su": STATUS_SUBMITTED_UNPROCESSED,
                    ":now": now,
                    ":zero": 0,
                },
            )
            self._emit_metric("UploadSessionSubmittedUnprocessed", portal_id=portal_id)
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    # ------------------------------------------------------------------
    # set_batch_metadata
    # ------------------------------------------------------------------

    def set_batch_metadata(self, session_id: str, user_metadata: dict) -> None:
        """Overwrite the batch's user-entered metadata snapshot on the META item.

        Portal forms are batch-uniform (one set of answers applied to every file)
        and may be edited AFTER the upload page, so the AUTHORITATIVE snapshot is
        the one captured at SUBMIT. This writes ``userMetadata`` as a last-write-
        wins ``{slug: stringValue}`` Map — the submit snapshot always wins, which
        is what downstream pipelines branch on. No-op when *user_metadata* is
        empty. Best-effort: a write failure never breaks the submit path.

        Note: ``submit()`` writes ``userMetadata`` atomically with the submit
        marker; this standalone helper exists for callers that capture metadata
        outside the submit write.
        """
        if not user_metadata:
            return

        try:
            self._table.update_item(
                Key={"PK": _pk(session_id), "SK": _sk_meta()},
                UpdateExpression="SET userMetadata = :m",
                ExpressionAttributeValues={":m": dict(user_metadata)},
            )
        except Exception:
            # Best-effort: never break the submit path on a metadata-capture failure.
            pass
