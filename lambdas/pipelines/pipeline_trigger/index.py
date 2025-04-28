import os
import json
import boto3
import random
import time
from botocore.config import Config
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics

# Configuration variables
MAX_CONCURRENT_EXECUTIONS = 1000
MAX_API_RETRIES = 20
BASE_BACKOFF = 0.5  # seconds
EXECUTION_COUNT_CACHE_TTL = 20  # seconds

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PipelineTrigger")

# Initialize clients with retries configuration
retry_config = Config(
    retries={
        "max_attempts": MAX_API_RETRIES,
        "mode": "standard"
    }
)
sfn_client = boto3.client("stepfunctions", config=retry_config)
sqs_client = boto3.client("sqs")

# In-memory cache for execution counts
execution_count_cache = {
    "count": 0,
    "last_updated": 0,
    "state_machine_arn": None
}

def get_running_executions_count(state_machine_arn):
    """
    Get the number of running executions with caching to reduce API calls
    """
    current_time = time.time()

    # Use cache if still fresh for this state machine
    if (execution_count_cache["state_machine_arn"] == state_machine_arn and
        current_time - execution_count_cache["last_updated"] < EXECUTION_COUNT_CACHE_TTL):
        logger.info(f"Using cached execution count: {execution_count_cache['count']}")
        return execution_count_cache["count"]

    # Cache expired, call AWS
    try:
        running_count = count_running_executions(state_machine_arn)
        execution_count_cache.update({
            "count": running_count,
            "last_updated": current_time,
            "state_machine_arn": state_machine_arn
        })
        return running_count

    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            logger.warning("Throttling when checking execution count, assuming at capacity")
            return MAX_CONCURRENT_EXECUTIONS
        else:
            raise

def count_running_executions(state_machine_arn):
    """
    Count the number of currently running executions with exponential backoff
    """
    running_count = 0
    next_token = None

    for attempt in range(MAX_API_RETRIES):
        try:
            params = {
                'stateMachineArn': state_machine_arn,
                'statusFilter': 'RUNNING'
            }
            if next_token:
                params['nextToken'] = next_token

            response = sfn_client.list_executions(**params)
            running_count += len(response.get('executions', []))
            next_token = response.get('nextToken')

            if not next_token:
                return running_count

        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if attempt < MAX_API_RETRIES - 1:
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    jitter = random.uniform(0, backoff * 0.1)
                    sleep_time = backoff + jitter
                    logger.warning(
                        f"Throttling when listing executions, retrying in {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Throttling persisted after {MAX_API_RETRIES} retries")
                    raise
            else:
                raise

    return running_count

def start_execution_with_backoff(state_machine_arn, execution_input):
    """
    Start a Step Function execution with exponential backoff
    """
    for attempt in range(MAX_API_RETRIES):
        try:
            return sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                input=json.dumps(execution_input),
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if attempt < MAX_API_RETRIES - 1:
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    jitter = random.uniform(0, backoff * 0.1)
                    sleep_time = backoff + jitter
                    logger.warning(
                        f"Throttling when starting execution, retrying in {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Throttling persisted after {MAX_API_RETRIES} retries")
                    raise
            else:
                raise

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    print(json.dumps(event))

    processed_records = []
    failed_message_ids = []

    try:
        for record in event.get("Records", []):
            message_body = json.loads(record["body"])
            asset = message_body["Asset"]
            step_function_arn = message_body["StateMachineArn"]

            # Extract InventoryID from nested detail
            inventory_id = asset.get("detail", {}).get("InventoryID")
            if not inventory_id:
                logger.error("Missing InventoryID in asset payload: %s", asset)
                failed_message_ids.append(record["messageId"])
                continue

            try:
                # Check concurrency limit
                current_running = get_running_executions_count(step_function_arn)
                if current_running >= MAX_CONCURRENT_EXECUTIONS:
                    logger.info(
                        f"Concurrency limit reached for asset {inventory_id} "
                        f"({current_running}/{MAX_CONCURRENT_EXECUTIONS})"
                    )
                    failed_message_ids.append(record["messageId"])
                    continue

                # Start the Step Function
                step_function_input = {
                    "pipeline_id": inventory_id,
                    "input": asset
                }
                response = start_execution_with_backoff(step_function_arn, step_function_input)

                logger.info(
                    f"Started execution for asset {inventory_id}: {response['executionArn']}"
                )
                processed_records.append({
                    "inventory_id": inventory_id,
                    "execution_arn": response["executionArn"]
                })

                # Update cache optimistically
                execution_count_cache["count"] += 1

            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code == "ThrottlingException":
                    logger.error(
                        f"Throttling persisted when processing asset {inventory_id}"
                    )
                else:
                    logger.error(
                        f"Error processing asset {inventory_id}: {str(e)}"
                    )
                failed_message_ids.append(record["messageId"])

        return {
            "batchItemFailures": [{"itemIdentifier": mid} for mid in failed_message_ids],
            "processed": processed_records
        }

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise
