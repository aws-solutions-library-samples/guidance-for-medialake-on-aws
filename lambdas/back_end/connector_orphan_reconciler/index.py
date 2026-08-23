"""Ad-hoc reconciler for orphaned MediaLake connector EventBridge rules.

Motivating incident (BUG-22): on ``ml-uat-small-…`` there were three enabled
``medialake-<bucket>-s3-events*`` rules whose SQS target queues had never
been created — the residue of two aborted connector-CREATE attempts. They
kept firing on every S3 object event, forever failing invocation, and
never self-heal. The connector-CREATE and connector-DELETE handlers now
sweep those orphans as part of their normal control flow (see
``lambdas/common_libraries/connector_eventbridge_reconcile.py``), but
existing orphans on already-deployed environments need a one-shot cleanup.

This Lambda handler is that one-shot. It takes a bucket (or list of
buckets) and a ``dry_run`` flag, and invokes the same shared sweep helper
that runs inside the create/delete Lambdas.

Invoke ad-hoc via the AWS CLI:

    aws lambda invoke \\
      --function-name medialake_connector_orphan_reconciler_<env> \\
      --payload '{"buckets": ["ml-uat-small-438465153766-us-east-1"], "dry_run": true}' \\
      --cli-binary-format raw-in-base64-out out.json

Set ``dry_run: false`` (or omit the field — default is ``false``) to
actually delete. Response body contains per-bucket sweep results plus a
summary.

Invocation payload shape:

    {
      "buckets": ["bucket-a", "bucket-b"],   # OR single "bucket": "…"
      "dry_run": true,                       # optional, default false
      "region": "us-east-1"                  # optional, defaults to AWS_REGION
    }

If ``buckets`` and ``bucket`` are both absent the handler reads every
connector out of the connectors table and reconciles each unique
bucket it finds — useful for a scheduled sweep of the whole account.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from connector_eventbridge_reconcile import (
    OrphanRuleSweepResult,
    sweep_orphan_rules_for_bucket,
)

logger = Logger(service="connector-orphan-reconciler")

DEFAULT_REGION = os.environ.get("AWS_REGION") or os.environ.get("REGION", "us-east-1")
CONNECTOR_TABLE_NAME = os.environ.get("MEDIALAKE_CONNECTOR_TABLE_NAME") or ""


def _sweep_result_to_dict(result: OrphanRuleSweepResult) -> Dict[str, Any]:
    return {
        "deleted": result.deleted,
        "skipped_live": result.skipped_live,
        "skipped_error": result.skipped_error,
        "total_examined": result.total_examined,
    }


def _list_buckets_from_connectors_table() -> List[str]:
    """Return every unique bucket name referenced by an s3-integration connector.

    Only meaningful when ``MEDIALAKE_CONNECTOR_TABLE_NAME`` is configured.
    Scans the whole table because the reconciler runs interactively rather
    than on a hot path; a Scan on a few hundred connectors is fine.
    """
    if not CONNECTOR_TABLE_NAME:
        logger.warning(
            "connector table env var not set; cannot enumerate buckets — "
            "supply 'bucket' or 'buckets' in the payload instead."
        )
        return []
    table = boto3.resource("dynamodb").Table(CONNECTOR_TABLE_NAME)
    buckets: set[str] = set()
    scan_kwargs: Dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []) or []:
            bucket = None
            configuration = item.get("configuration")
            if isinstance(configuration, dict):
                bucket = configuration.get("bucket") or configuration.get("bucketName")
            bucket = bucket or item.get("storageIdentifier")
            if bucket:
                buckets.add(bucket)
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return sorted(buckets)


@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], _context: LambdaContext) -> Dict[str, Any]:
    """Sweep orphan connector rules for one bucket, a list, or every known bucket.

    Returns a report dict — the CLI wrapper prints this from the ``out.json``
    file. Errors on individual buckets are captured in the report rather than
    raised, so a single misconfigured bucket doesn't abort the sweep for the
    rest.
    """
    dry_run = bool(event.get("dry_run", False))
    region = event.get("region") or DEFAULT_REGION
    explicit_buckets = event.get("buckets")
    if not explicit_buckets and event.get("bucket"):
        explicit_buckets = [event["bucket"]]

    if explicit_buckets:
        buckets = list(explicit_buckets)
        source = "payload"
    else:
        buckets = _list_buckets_from_connectors_table()
        source = "connectors_table"

    if not buckets:
        return {
            "status": "noop",
            "reason": "no buckets to reconcile — payload missing bucket(s) "
            "and connectors table returned zero entries",
            "region": region,
            "dry_run": dry_run,
        }

    eventbridge = boto3.client("events", region_name=region)
    sqs = boto3.client("sqs", region_name=region)

    per_bucket: Dict[str, Any] = {}
    grand_total_deleted = 0
    grand_total_examined = 0

    for bucket in buckets:
        try:
            result = sweep_orphan_rules_for_bucket(
                eventbridge, sqs, bucket, dry_run=dry_run, logger=logger
            )
            per_bucket[bucket] = _sweep_result_to_dict(result)
            grand_total_deleted += len(result.deleted)
            grand_total_examined += result.total_examined
            logger.info(
                "bucket sweep complete",
                extra={
                    "bucket": bucket,
                    "deleted": result.deleted,
                    "skipped_live_count": len(result.skipped_live),
                    "skipped_error_count": len(result.skipped_error),
                    "dry_run": dry_run,
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            per_bucket[bucket] = {"error": str(exc), "error_code": code}
            logger.warning(
                "bucket sweep failed",
                extra={"bucket": bucket, "error_code": code, "error": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001 — best-effort reconciler
            per_bucket[bucket] = {"error": str(exc)}
            logger.warning(
                "bucket sweep failed unexpectedly",
                extra={"bucket": bucket, "error": str(exc)},
            )

    return {
        "status": "ok",
        "dry_run": dry_run,
        "region": region,
        "bucket_source": source,
        "buckets_reconciled": len(buckets),
        "total_orphans": grand_total_deleted,
        "total_rules_examined": grand_total_examined,
        "results": per_bucket,
    }
