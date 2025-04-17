import os
import json
import boto3
import random
import time
from botocore.config import Config
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics

# Configuration variables
MAX_CONCURRENT_EXECUTIONS = 100  # Adjust based on your workload
MAX_API_RETRIES = 4
BASE_BACKOFF = 0.5  # Base delay in seconds
# Use a cache to reduce API calls
EXECUTION_COUNT_CACHE_TTL = 2  # seconds

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
    
    # If cache is valid and for the same state machine, use cached value
    if (execution_count_cache["state_machine_arn"] == state_machine_arn and
        current_time - execution_count_cache["last_updated"] < EXECUTION_COUNT_CACHE_TTL):
        logger.info(f"Using cached execution count: {execution_count_cache['count']}")
        return execution_count_cache["count"]
    
    # Cache is invalid, need to make API call
    try:
        running_count = count_running_executions(state_machine_arn)
        
        # Update cache
        execution_count_cache["count"] = running_count
        execution_count_cache["last_updated"] = current_time
        execution_count_cache["state_machine_arn"] = state_machine_arn
        
        return running_count
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            logger.warning("Throttling when checking execution count, assuming at capacity")
            # If we're being throttled, assume we're at capacity
            return MAX_CONCURRENT_EXECUTIONS
        else:
            # For other errors, re-raise
            raise

def count_running_executions(state_machine_arn):
    """Count the number of currently running executions with exponential backoff"""
    running_count = 0
    next_token = None
    
    for attempt in range(MAX_API_RETRIES):
        try:
            # Prepare request parameters
            params = {
                'stateMachineArn': state_machine_arn,
                'statusFilter': 'RUNNING'
            }
            
            if next_token:
                params['nextToken'] = next_token
                
            # Make the API call
            response = sfn_client.list_executions(**params)
            
            # Add to our count
            running_count += len(response['executions'])
            
            # Check if there are more results to fetch
            if 'nextToken' in response and response['nextToken']:
                next_token = response['nextToken']
            else:
                # No more pages, we're done
                return running_count
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if attempt < MAX_API_RETRIES - 1:
                    # Calculate backoff time with jitter
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    jitter = random.uniform(0, backoff * 0.1)
                    sleep_time = backoff + jitter
                    
                    logger.warning(
                        f"Throttling when listing executions, retrying in {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
                    )
                    
                    time.sleep(sleep_time)
                else:
                    # We've exhausted retries, re-raise
                    logger.error(f"Throttling persisted after {MAX_API_RETRIES} retries")
                    raise
            else:
                # Not a throttling error, re-raise
                raise
    
    # If we get here, we've exhausted retries
    return running_count

def start_execution_with_backoff(state_machine_arn, execution_input):
    """Start a Step Function execution with exponential backoff"""
    for attempt in range(MAX_API_RETRIES):
        try:
            response = sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                input=json.dumps(execution_input),
            )
            return response
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if attempt < MAX_API_RETRIES - 1:
                    # Calculate backoff time with jitter
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    jitter = random.uniform(0, backoff * 0.1)
                    sleep_time = backoff + jitter
                    
                    logger.warning(
                        f"Throttling when starting execution, retrying in {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
                    )
                    
                    time.sleep(sleep_time)
                else:
                    # We've exhausted retries, re-raise
                    logger.error(f"Throttling persisted after {MAX_API_RETRIES} retries")
                    raise
            else:
                # Not a throttling error, re-raise
                raise

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    print(json.dumps(event))
    
    # Track which messages were processed and which failed
    processed_records = []
    failed_message_ids = []
    
    try:
        # Process each record from SQS
        for record in event["Records"]:
            # Parse the message body
            message_body = json.loads(record["body"])
            
            # Extract data
            asset = message_body["Asset"]
            step_function_arn = message_body["StateMachineArn"]
            
            try:
                # Check if we're under the concurrency limit
                current_running = get_running_executions_count(step_function_arn)
                
                if current_running >= MAX_CONCURRENT_EXECUTIONS:
                    logger.info(
                        f"Concurrency limit reached for asset {asset['InventoryID']} "
                        f"({current_running}/{MAX_CONCURRENT_EXECUTIONS} executions running)"
                    )
                    
                    # Add message ID to the failed list so it will be retried
                    failed_message_ids.append(record["messageId"])
                    continue
                
                # Prepare the input for the Step Function
                step_function_input = {
                    "pipeline_id": asset["InventoryID"],
                    "input": asset,
                }
                
                # Start execution with backoff
                response = start_execution_with_backoff(step_function_arn, step_function_input)
                
                logger.info(
                    f"Started execution for asset {asset['InventoryID']}: {response['executionArn']}"
                )
                
                processed_records.append({
                    "inventory_id": asset['InventoryID'],
                    "execution_arn": response['executionArn']
                })
                
                # Update our in-memory cache to avoid unnecessary API calls
                execution_count_cache["count"] += 1
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ThrottlingException':
                    logger.error(
                        f"Throttling exception persisted when processing asset {asset['InventoryID']}"
                    )
                    failed_message_ids.append(record["messageId"])
                else:
                    logger.error(
                        f"Error processing asset {asset['InventoryID']}: {str(e)}"
                    )
                    failed_message_ids.append(record["messageId"])
        
        # Return the result with batchItemFailures for SQS to retry just the failed messages
        return {
            "batchItemFailures": [{"itemIdentifier": message_id} for message_id in failed_message_ids],
            "processed": processed_records
        }

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        # If we have an unhandled exception, all messages will be retried anyway
        raise