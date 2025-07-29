import json
import os
import random
import time

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.config import Config
from botocore.exceptions import ClientError

# Configuration variables
MAX_CONCURRENT_EXECUTIONS = 1000
MAX_API_RETRIES = 20
BASE_BACKOFF = 0.5  # seconds
EXECUTION_COUNT_CACHE_TTL = 20  # seconds

# Default State Machine ARN for EventBridge-style messages
DEFAULT_STATE_MACHINE_ARN = os.environ["DEFAULT_STATE_MACHINE_ARN"]

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


def start_execution_with_backoff(state_machine_arn, execution_input):
    """Start execution with exponential backoff on ThrottlingException."""
    for attempt in range(MAX_API_RETRIES):
        try:
            return sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                input=json.dumps(execution_input),
            )
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
                "Concurrency limit reached (%d/%d) for %s",
                running,
                MAX_CONCURRENT_EXECUTIONS,
                inventory_id,
            )
            failures.append(record["messageId"])
            continue
        try:
            resp = start_execution_with_backoff(state_machine_arn, body)
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
