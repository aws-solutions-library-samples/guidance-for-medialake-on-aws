import json
import os
import random
import time

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.config import Config
from botocore.exceptions import ClientError

# Configuration variables
# MAX_CONCURRENT_EXECUTIONS can be configured per pipeline via environment variable
# Default to 10 to prevent MediaConvert API throttling
MAX_CONCURRENT_EXECUTIONS = int(os.environ.get("MAX_CONCURRENT_EXECUTIONS", "10"))
MAX_API_RETRIES = 20
BASE_BACKOFF = 0.5  # seconds
EXECUTION_COUNT_CACHE_TTL = 20  # seconds

# Default State Machine ARN for EventBridge-style messages
DEFAULT_STATE_MACHINE_ARN = os.environ["DEFAULT_STATE_MACHINE_ARN"]

# Source used by every collection lifecycle event (see
# common_libraries/collection_events.py). Collection events carry asset *ids*
# rather than asset records, so they are expanded before starting executions.
COLLECTION_EVENT_SOURCE = "custom.collection.processor"

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PipelineTrigger")

# Clients with retry config
retry_config = Config(retries={"max_attempts": MAX_API_RETRIES, "mode": "standard"})
sfn_client = boto3.client("stepfunctions", config=retry_config)
sqs_client = boto3.client("sqs")

# In-memory execution count cache
execution_count_cache = {"count": 0, "last_updated": 0, "state_machine_arn": None}


def get_running_executions_count(state_machine_arn):
    """Cached list_executions('RUNNING') count."""
    now = time.time()
    if (
        execution_count_cache["state_machine_arn"] == state_machine_arn
        and now - execution_count_cache["last_updated"] < EXECUTION_COUNT_CACHE_TTL
    ):
        logger.info(f"Using cached execution count: {execution_count_cache['count']}")
        return execution_count_cache["count"]

    try:
        count = _count_running_executions(state_machine_arn)
        execution_count_cache.update(
            {
                "count": count,
                "last_updated": now,
                "state_machine_arn": state_machine_arn,
            }
        )
        return count

    except ClientError as e:
        if e.response["Error"]["Code"] == "ThrottlingException":
            logger.warning("Throttled, assuming at max capacity")
            return MAX_CONCURRENT_EXECUTIONS
        raise


def _count_running_executions(state_machine_arn):
    """List and count RUNNING executions with backoff."""
    total = 0
    token = None
    for attempt in range(MAX_API_RETRIES):
        try:
            params = {"stateMachineArn": state_machine_arn, "statusFilter": "RUNNING"}
            if token:
                params["nextToken"] = token
            resp = sfn_client.list_executions(**params)
            total += len(resp.get("executions", []))
            token = resp.get("nextToken")
            if not token:
                return total

        except ClientError as e:
            if (
                e.response["Error"]["Code"] == "ThrottlingException"
                and attempt < MAX_API_RETRIES - 1
            ):
                backoff = BASE_BACKOFF * (2**attempt)
                jitter = random.uniform(0, backoff * 0.1)
                sleep = backoff + jitter
                logger.warning(
                    f"Throttled listing executions, retry {attempt+1} in {sleep:.2f}s"
                )
                time.sleep(sleep)
            else:
                raise
    return total


def _sanitize_execution_name(raw: str) -> str:
    """Coerce a string into a legal Step Functions execution name (<=80 chars)."""
    cleaned = "".join(c if (c.isalnum() or c in "-_") else "-" for c in raw)
    return cleaned[:80].strip("-") or "collection-event"


def _expand_execution_inputs(body):
    """Turn one queued message into the execution inputs to start.

    Non-collection events keep today's behaviour exactly: the matched event is
    passed straight through as the state machine input.

    Collection events are different. They deliberately carry only asset *ids*
    (``detail.assetIds``) plus collection metadata, so passing the raw event
    through would leave ``lambda_middleware`` treating the collection metadata
    itself as the asset (its plain-EventBridge branch sets
    ``payload.assets = [event["detail"]]``), and any asset-processing node would
    fail on the missing ``DigitalSourceAsset``.

    Instead each asset id is expanded into the *same* shape the manual/bin
    trigger uses (``lambdas/api/pipelines/trigger_pipeline``)::

        {"item": {"inventory_id": "asset:uuid:...", "params": {}}}

    ``lambda_middleware`` already recognises ``item.inventory_id``: it fetches
    the full record from the asset table and populates ``payload.assets``. So
    collection-triggered pipelines reuse the existing hydration path and any
    pipeline that works from the bin works from a collection trigger unchanged —
    no hydration node and no conditional branch required.

    One execution is started per asset (mirroring the bin's per-asset model), so
    a bulk add fans out correctly. Execution names are derived from the event id
    so an SQS redelivery is idempotent rather than duplicating work.

    Returns:
        List of ``(execution_input, execution_name_or_None)`` tuples.
    """
    if not isinstance(body, dict):
        return [(body, None)]

    detail = body.get("detail")
    if body.get("source") != COLLECTION_EVENT_SOURCE or not isinstance(detail, dict):
        return [(body, None)]

    asset_ids = [a for a in (detail.get("assetIds") or []) if a]
    if not asset_ids:
        # Collection events that aren't about assets (CollectionCreated,
        # CollectionDeleted, ...) have nothing to expand — pass them through so
        # non-asset pipelines still see the raw event.
        return [(body, None)]

    collection_context = {
        "collectionId": detail.get("collectionId"),
        "collectionName": detail.get("collectionName"),
        "collectionTypeId": detail.get("collectionTypeId"),
    }
    event_id = str(body.get("id") or "")

    expanded = []
    for index, asset_id in enumerate(asset_ids):
        execution_input = {
            "item": {"inventory_id": asset_id, "params": {}},
            "trigger_type": "collection_event",
            "detail_type": body.get("detail-type"),
            "collection": collection_context,
            "timestamp": detail.get("timestamp"),
        }
        name = (
            _sanitize_execution_name(f"{event_id}-{index}")
            if event_id
            else None  # let Step Functions generate one
        )
        expanded.append((execution_input, name))
    return expanded


def start_execution_with_backoff(
    state_machine_arn, execution_input, execution_name=None
):
    """Start execution with exponential backoff on ThrottlingException."""
    for attempt in range(MAX_API_RETRIES):
        try:
            params = {
                "stateMachineArn": state_machine_arn,
                "input": json.dumps(execution_input),
            }
            if execution_name:
                params["name"] = execution_name
            return sfn_client.start_execution(**params)
        except ClientError as e:
            if (
                e.response["Error"]["Code"] == "ThrottlingException"
                and attempt < MAX_API_RETRIES - 1
            ):
                backoff = BASE_BACKOFF * (2**attempt)
                jitter = random.uniform(0, backoff * 0.1)
                sleep = backoff + jitter
                logger.warning(
                    f"Throttled starting execution, retry {attempt+1} in {sleep:.2f}s"
                )
                time.sleep(sleep)
            else:
                logger.error(f"Failed to start execution: {e}")
                raise
    raise RuntimeError(
        f"Failed to start execution after {MAX_API_RETRIES} retries "
        f"due to persistent throttling"
    )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    logger.debug(f"Received event: {json.dumps(event)}")
    processed = []
    failures = []

    for record in event.get("Records", []):
        body = json.loads(record["body"])

        state_machine_arn = DEFAULT_STATE_MACHINE_ARN

        # Concurrency check
        running = get_running_executions_count(state_machine_arn)
        if running >= MAX_CONCURRENT_EXECUTIONS:
            logger.info(
                "Concurrency limit reached (%d/%d), message will be retried",
                running,
                MAX_CONCURRENT_EXECUTIONS,
            )
            failures.append(record["messageId"])
            continue

        # Gradual ramp-up: Add startup delay to prevent initial burst race condition
        # When count is low (0-5), add progressive delay to allow executions to register
        # This prevents multiple Lambda containers from all seeing "0 running" simultaneously
        if running < 5:
            delay_seconds = (
                5 - running
            ) * 0.5  # 2.5s at 0, 2s at 1, 1.5s at 2, 1s at 3, 0.5s at 4
            logger.info(
                f"Gradual ramp-up: waiting {delay_seconds}s before starting (current: {running}/{MAX_CONCURRENT_EXECUTIONS})"
            )
            time.sleep(delay_seconds)

            # Re-check after delay to ensure we're still under limit
            # Force fresh count by bypassing cache
            running = _count_running_executions(state_machine_arn)
            if running >= MAX_CONCURRENT_EXECUTIONS:
                logger.info(
                    f"Concurrency limit reached after ramp-up delay ({running}/{MAX_CONCURRENT_EXECUTIONS}), message will be retried"
                )
                failures.append(record["messageId"])
                continue

        try:
            # One queued event can fan out to several executions (a collection
            # add carrying multiple assetIds); everything else stays 1:1.
            expanded = _expand_execution_inputs(body)
            fanned_out = len(expanded) > 1
            for execution_input, execution_name in expanded:
                # The guard above only covered the first execution. A fan-out
                # starts many from a single message, so the limit has to be
                # re-checked per execution — otherwise a bulk collection add
                # walks straight past MAX_CONCURRENT_EXECUTIONS and re-introduces
                # the MediaConvert throttling this guard exists to prevent.
                # The optimistic cache bump below keeps this from adding an API
                # call per asset.
                if fanned_out:
                    running = get_running_executions_count(state_machine_arn)
                    if running >= MAX_CONCURRENT_EXECUTIONS:
                        logger.info(
                            "Concurrency limit reached mid fan-out (%d/%d), "
                            "message will be retried; executions already started "
                            "are skipped on redelivery by their deterministic names",
                            running,
                            MAX_CONCURRENT_EXECUTIONS,
                        )
                        failures.append(record["messageId"])
                        break
                try:
                    resp = start_execution_with_backoff(
                        state_machine_arn, execution_input, execution_name
                    )
                except ClientError as inner:
                    if inner.response["Error"]["Code"] == "ExecutionAlreadyExists":
                        # Deterministic names make SQS redelivery a no-op rather
                        # than a duplicate run.
                        logger.info(
                            "Execution %s already exists, skipping duplicate",
                            execution_name,
                        )
                        continue
                    raise
                logger.info("Started %s ", resp["executionArn"])
                processed.append({"execution_arn": resp["executionArn"]})
                # optimistic cache bump
                execution_count_cache["count"] += 1

        except ClientError as e:
            logger.error("Failed processing %s:", e)
            failures.append(record["messageId"])

    return {
        "batchItemFailures": [{"itemIdentifier": mid} for mid in failures],
        "processed": processed,
    }
