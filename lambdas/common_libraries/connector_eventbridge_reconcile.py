"""Utilities for detecting and cleaning up orphaned MediaLake connector rules.

Motivating incident (BUG-22, QA passes 2 and 3, 2026-08-22 → 2026-08-23):

On ``ml-uat-small-438465153766-us-east-1`` there were three enabled
EventBridge rules whose names match the ``medialake-{bucket}-s3-events*``
pattern used by the S3 connector-create path. Two of the three
(``…-0eza`` and ``…-9ncp``) targeted SQS FIFO queues that no longer
existed — because the queues themselves had never been created, or had
been rolled back partway through a failed connector-create attempt.
Each such orphan rule fires on every S3 object event on that bucket
and generates a permanent ``FailedInvocations`` metric that never
self-heals: EventBridge has no idea the SQS target is missing until it
tries to send, and CloudTrail's ``lookup-events`` API does not index
EventBridge rules, so these orphans are effectively invisible to
normal observability.

The connector-DELETE path already handles rule cleanup correctly (the
QA pass-3 controlled create→delete test verified that a deliberate
delete leaves no rule or queue behind). The orphans came from
create-failure paths where the reverse-walk cleanup was incomplete —
either the Lambda timed out before it ran, the ``created_resources``
list never got the rule appended, or the ``delete_rule`` call in the
cleanup loop raised.

This module holds two things the connector-create failure handler and
the ad-hoc reconcile utility both need:

1. :func:`is_rule_orphaned` — decides whether a given rule points at
   nothing but non-existent SQS queues. Rules with any live target are
   left alone (defensive: an in-flight create might have queued but
   not yet returned).

2. :func:`sweep_orphan_rules_for_bucket` — walks every
   ``medialake-{bucket}-s3-events*`` rule for the supplied bucket and
   deletes the orphaned ones, returning what it found for logging.
   The connector-create failure handler calls this after its
   reverse-walk cleanup; the reconcile Lambda calls it per-bucket.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

from botocore.exceptions import ClientError

# Deterministic prefix that ``setup_eventbridge_notifications`` writes to every
# rule it creates. Also documented in
# ``lambdas/api/connectors/rp_connectorId/del_connectorId/index.py`` — keep
# these three definitions in lockstep.
RULE_NAME_PREFIX = "medialake"
RULE_NAME_INFIX = "s3-events"

# ``ListRules`` in EventBridge only supports a single ``NamePrefix`` — the
# connector suffix means we can't filter on the full rule name, so the
# ``sweep`` helper filters client-side after the ``ListRules`` call.


@dataclass
class OrphanRuleSweepResult:
    """Return value of :func:`sweep_orphan_rules_for_bucket`.

    - ``deleted`` — rules that were successfully deleted.
    - ``skipped_live`` — rules skipped because at least one target queue
      still exists (so the rule is presumed in-use).
    - ``skipped_error`` — rules skipped because ``describe_rule`` /
      ``list_targets_by_rule`` / ``get_queue_url`` raised anything other
      than the specific "not found" errors we treat as evidence of
      orphaning. Callers should log these and re-run.
    """

    deleted: List[str] = field(default_factory=list)
    skipped_live: List[str] = field(default_factory=list)
    skipped_error: List[dict] = field(default_factory=list)

    @property
    def total_examined(self) -> int:
        return len(self.deleted) + len(self.skipped_live) + len(self.skipped_error)


def _matches_medialake_rule_pattern(rule_name: str, bucket: str) -> bool:
    """True if ``rule_name`` was created by ``setup_eventbridge_notifications``
    for the given bucket.

    The naming convention in ``post_s3/index.py`` is
    ``medialake-{bucket}-s3-events-{suffix}``, with a length ceiling that
    truncates the ``medialake-{bucket}-s3-events`` prefix at 59 chars
    before appending the ``-{suffix}``. Match both untruncated and
    truncated variants for safety.
    """
    full_prefix = f"{RULE_NAME_PREFIX}-{bucket}-{RULE_NAME_INFIX}"
    # 59-char truncation matches the delete handler's ``truncated_prefix``.
    truncated_prefix = full_prefix[:59]
    return rule_name.startswith(full_prefix) or rule_name.startswith(truncated_prefix)


def _sqs_url_from_arn(sqs_client: Any, queue_arn: str) -> Optional[str]:
    """Return the queue URL for an ARN, or ``None`` if the queue does not
    exist. Any other error is re-raised so the caller can decide.
    """
    try:
        queue_name = queue_arn.rsplit(":", 1)[-1]
    except Exception:
        return None
    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        return response.get("QueueUrl")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in (
            "AWS.SimpleQueueService.NonExistentQueue",
            "QueueDoesNotExist",
            "NonExistentQueue",
        ):
            return None
        raise


def is_rule_orphaned(
    eventbridge_client: Any,
    sqs_client: Any,
    rule_name: str,
    *,
    logger: Optional[Any] = None,
) -> bool:
    """True if every SQS target of ``rule_name`` points at a queue that no
    longer exists.

    Rules with no SQS targets at all are treated as orphaned — the
    intended shape produced by ``setup_eventbridge_notifications`` has
    exactly one SQS target, and a shape without any is either a partial
    failure or a manual edit that should not fire silently.

    A rule with even one live SQS target is NOT orphaned; we err
    conservative because that rule is presumably in use by a working
    connector.
    """
    try:
        targets_response = eventbridge_client.list_targets_by_rule(Rule=rule_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("ResourceNotFoundException", "ValidationException"):
            # Rule is already gone — treat as orphaned (nothing to do).
            return True
        raise

    targets: List[dict] = targets_response.get("Targets", []) or []

    if not targets:
        return True

    sqs_targets = [t for t in targets if ":sqs:" in (t.get("Arn") or "")]

    if not sqs_targets:
        # Rule has targets but none are SQS — outside the connector shape.
        # Do NOT delete: this might be a hand-authored rule the operator
        # added to the same name space intentionally.
        if logger is not None:
            logger.info(
                "rule has non-SQS targets — leaving alone",
                extra={"rule_name": rule_name, "target_count": len(targets)},
            )
        return False

    for target in sqs_targets:
        target_arn = target.get("Arn") or ""
        queue_url = _sqs_url_from_arn(sqs_client, target_arn)
        if queue_url is not None:
            # At least one target queue is live.
            return False
    return True


def _delete_rule_best_effort(
    eventbridge_client: Any, rule_name: str, *, logger: Optional[Any] = None
) -> bool:
    """Delete a rule and its targets, tolerating ``ResourceNotFoundException``.

    Mirrors ``rp_connectorId/del_connectorId``'s helper of the same name so
    the create-failure sweep and the DELETE path behave identically.
    """
    try:
        targets = eventbridge_client.list_targets_by_rule(Rule=rule_name).get(
            "Targets", []
        )
        if targets:
            eventbridge_client.remove_targets(
                Rule=rule_name, Ids=[t["Id"] for t in targets]
            )
        eventbridge_client.delete_rule(Name=rule_name)
        if logger is not None:
            logger.info(
                "deleted orphan EventBridge rule", extra={"rule_name": rule_name}
            )
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("ResourceNotFoundException", "ValidationException"):
            if logger is not None:
                logger.info(
                    "orphan rule already gone",
                    extra={"rule_name": rule_name, "error_code": code},
                )
            return True
        if logger is not None:
            logger.warning(
                "failed to delete orphan rule",
                extra={"rule_name": rule_name, "error_code": code, "error": str(exc)},
            )
        return False


def _iter_medialake_rules(eventbridge_client: Any, bucket: str) -> Iterable[str]:
    """Yield rule names matching the ``medialake-{bucket}-s3-events*`` shape."""
    full_prefix = f"{RULE_NAME_PREFIX}-{bucket}-{RULE_NAME_INFIX}"
    truncated_prefix = full_prefix[:59]
    seen: set[str] = set()
    for prefix in (
        (full_prefix, truncated_prefix)
        if truncated_prefix != full_prefix
        else (full_prefix,)
    ):
        paginator = eventbridge_client.get_paginator("list_rules")
        for page in paginator.paginate(NamePrefix=prefix):
            for rule in page.get("Rules", []) or []:
                name = rule.get("Name")
                if not name or name in seen:
                    continue
                if _matches_medialake_rule_pattern(name, bucket):
                    seen.add(name)
                    yield name


def _rule_targets_bucket(eventbridge_client: Any, rule_name: str, bucket: str) -> bool:
    """Confirm that ``rule_name``'s ``EventPattern`` targets ``bucket``.

    Belt-and-suspenders defence: the name-prefix filter narrows candidates
    but we cross-check the event pattern before deleting. Prevents an
    edge case where a rule is named after bucket A but rewritten to
    target bucket B by hand.
    """
    try:
        response = eventbridge_client.describe_rule(Name=rule_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("ResourceNotFoundException", "ValidationException"):
            return False
        raise
    pattern_json = response.get("EventPattern")
    if not pattern_json:
        return False
    try:
        pattern = json.loads(pattern_json)
    except (TypeError, ValueError):
        return False
    return bucket in pattern.get("detail", {}).get("bucket", {}).get("name", []) or []


def sweep_orphan_rules_for_bucket(
    eventbridge_client: Any,
    sqs_client: Any,
    bucket: str,
    *,
    dry_run: bool = False,
    logger: Optional[Any] = None,
) -> OrphanRuleSweepResult:
    """Walk every ``medialake-{bucket}-s3-events*`` rule and delete orphans.

    A rule qualifies as an orphan iff:
      1. its name matches the connector-create naming pattern for ``bucket``,
      2. its event pattern actually targets ``bucket`` (belt-and-suspenders),
      3. every SQS target it declares points at a queue that no longer
         exists (or the rule has no targets at all).

    ``dry_run=True`` returns what would be deleted without touching AWS.
    Handy for the reconcile Lambda's "report first" mode.
    """
    result = OrphanRuleSweepResult()
    for rule_name in _iter_medialake_rules(eventbridge_client, bucket):
        try:
            if not _rule_targets_bucket(eventbridge_client, rule_name, bucket):
                # Name matched but pattern doesn't reference this bucket —
                # leave alone. Same defensive stance as the DELETE handler.
                if logger is not None:
                    logger.info(
                        "rule name matches but event pattern doesn't target bucket — skipping",
                        extra={"rule_name": rule_name, "bucket": bucket},
                    )
                result.skipped_live.append(rule_name)
                continue
            if not is_rule_orphaned(
                eventbridge_client, sqs_client, rule_name, logger=logger
            ):
                result.skipped_live.append(rule_name)
                continue
            if dry_run:
                result.deleted.append(rule_name)
                continue
            if _delete_rule_best_effort(eventbridge_client, rule_name, logger=logger):
                result.deleted.append(rule_name)
            else:
                result.skipped_error.append(
                    {"rule_name": rule_name, "reason": "delete_failed"}
                )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            result.skipped_error.append(
                {"rule_name": rule_name, "reason": "client_error", "code": code}
            )
            if logger is not None:
                logger.warning(
                    "sweep skipped rule due to ClientError",
                    extra={
                        "rule_name": rule_name,
                        "error_code": code,
                        "error": str(exc),
                    },
                )
        except Exception as exc:  # noqa: BLE001 — best-effort sweep must not crash
            result.skipped_error.append(
                {"rule_name": rule_name, "reason": "unexpected", "error": str(exc)}
            )
            if logger is not None:
                logger.warning(
                    "sweep skipped rule due to unexpected error",
                    extra={"rule_name": rule_name, "error": str(exc)},
                )
    return result
