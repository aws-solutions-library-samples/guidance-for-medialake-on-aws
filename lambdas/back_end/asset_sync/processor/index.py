import hashlib
import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote_plus

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.config import Config
from botocore.exceptions import ClientError
from common import AssetProcessor, JobStatus, get_optimized_s3_client

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configure boto3 clients with connection pooling and keep-alive for better performance
BOTO3_CONFIG = Config(
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    retries={"max_attempts": 3, "mode": "adaptive"},
    max_pool_connections=50,
    parameter_validation=False,  # Skip parameter validation for better performance
)

# Initialize clients at module level for reuse across invocations
sqs_client = boto3.client("sqs", config=BOTO3_CONFIG)
dynamodb_client = boto3.client("dynamodb", config=BOTO3_CONFIG)
dynamodb_resource = boto3.resource("dynamodb", config=BOTO3_CONFIG)

# S3 client cache - since bucket names can vary, we'll cache them
_s3_client_cache = {}


def get_cached_s3_client(bucket_name: str):
    """
    Get a cached S3 client for the specific bucket.
    Creates and caches clients as needed.
    """
    if bucket_name not in _s3_client_cache:
        logger.info(f"Creating new S3 client for bucket: {bucket_name}")
        _s3_client_cache[bucket_name] = get_optimized_s3_client(bucket_name)
    return _s3_client_cache[bucket_name]


# Define retry constants with environment variable configuration
MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "15"))
BASE_BACKOFF_TIME = float(os.environ.get("BASE_BACKOFF_TIME", "0.1"))
MAX_BACKOFF_TIME = float(os.environ.get("MAX_BACKOFF_TIME", "30.0"))


def sanitize_for_sqs(text: str, max_length: int = 128) -> str:
    """
    Sanitize text for SQS fields like MessageDeduplicationId and MessageGroupId.

    AWS SQS requirements:
    - MessageDeduplicationId: alphanumeric (a-z, A-Z, 0-9), hyphens (-), and underscores (_) only
    - MessageGroupId: alphanumeric (a-z, A-Z, 0-9), hyphens (-), and underscores (_) only
    - Max length: 128 characters

    Args:
        text: Text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text that meets SQS requirements
    """
    if not text:
        return str(uuid.uuid4())  # Fallback to UUID if empty

    # First, URL decode if needed
    try:
        decoded_text = unquote_plus(text)
    except Exception:
        decoded_text = text

    # Replace any character that's not alphanumeric, hyphen, or underscore with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "_", decoded_text)

    # Remove consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Ensure it's not empty after sanitization
    if not sanitized:
        sanitized = str(uuid.uuid4()).replace("-", "_")

    # Truncate if too long, but if we need to truncate, use a hash instead to maintain uniqueness
    if len(sanitized) > max_length:
        # Use MD5 hash to ensure uniqueness while staying within length limits
        hash_suffix = hashlib.md5(text.encode()).hexdigest()[:8]  # nosec B324
        # Take as much of the sanitized string as possible, leaving room for hash
        prefix_length = max_length - len(hash_suffix) - 1  # -1 for separator
        if prefix_length > 0:
            sanitized = sanitized[:prefix_length] + "_" + hash_suffix
        else:
            sanitized = hash_suffix

    return sanitized


def retry_with_backoff(
    func: Callable,
    *args,
    exception_class=ClientError,
    max_attempts=MAX_RETRY_ATTEMPTS,
    base_delay=BASE_BACKOFF_TIME,
    max_delay=MAX_BACKOFF_TIME,
    throttling_errors=(
        "ThrottlingException",
        "ProvisionedThroughputExceededException",
        "RequestThrottled",
    ),
    **kwargs,
) -> Any:
    """
    Execute a function with exponential backoff and jitter for retries.
    Specifically handles DynamoDB throttling exceptions.

    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        exception_class: Exception class to catch and retry on
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay time in seconds
        max_delay: Maximum delay time in seconds
        throttling_errors: Error codes that indicate throttling
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result from the function call

    Raises:
        The last exception if all retries fail
    """
    attempt = 0
    last_exception = None
    metrics_count = 0

    while attempt < max_attempts:
        try:
            return func(*args, **kwargs)
        except exception_class as e:
            # Check if this is a throttling error
            if hasattr(e, "response") and "Error" in e.response:
                error_code = e.response["Error"].get("Code")
                if error_code not in throttling_errors:
                    # Not a throttling error, reraise
                    raise
            else:
                # Not a ClientError with error code, reraise
                raise

            attempt += 1
            metrics_count += 1
            last_exception = e

            if attempt >= max_attempts:
                logger.error(f"Max retry attempts ({max_attempts}) exceeded: {str(e)}")
                break

            # Calculate delay with exponential backoff and jitter
            delay = min(max_delay, base_delay * (2**attempt))
            jitter = random.uniform(0, 1)
            delay = delay + (delay * 0.2 * jitter)  # Add up to 20% jitter

            # Determine service name for better logging
            service_name = "DynamoDB"  # Default
            if hasattr(e, "response") and "Error" in e.response:
                error_code = e.response["Error"].get("Code")
                if error_code == "RequestThrottled":
                    service_name = "SQS"

            logger.warning(
                f"{service_name} throttling error on attempt {attempt}/{max_attempts}. "
                f"Retrying in {delay:.2f}s: {str(e)}"
            )

            # Record metric for throttling based on service
            service_name = "DynamoDB"  # Default
            if hasattr(e, "response") and "Error" in e.response:
                error_code = e.response["Error"].get("Code")
                if error_code == "RequestThrottled":
                    service_name = "SQS"

            metrics.add_metric(
                name=f"{service_name}ThrottlingRetries",
                unit=MetricUnit.Count,
                value=metrics_count,
            )

            # Sleep with backoff
            time.sleep(delay)

    # If we get here, we've exhausted our retries
    if last_exception:
        raise last_exception

    # This should never happen
    raise Exception("Unexpected error in retry mechanism")


# Patch AssetProcessor methods with retry
original_increment_job_counter = AssetProcessor.increment_job_counter
original_update_job_status = AssetProcessor.update_job_status
original_update_job_metadata = AssetProcessor.update_job_metadata
original_log_error = AssetProcessor.log_error


@staticmethod
def patched_increment_job_counter(
    job_id: str, counter_name: str, increment_by: int = 1
) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(
        original_increment_job_counter, job_id, counter_name, increment_by
    )


@staticmethod
def patched_update_job_status(
    job_id: str, status: JobStatus, message: str = None
) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(original_update_job_status, job_id, status, message)


@staticmethod
def patched_update_job_metadata(job_id: str, metadata: Dict[str, Any]) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(original_update_job_metadata, job_id, metadata)


@staticmethod
def patched_log_error(error_data: Dict[str, Any]) -> bool:
    """Patched method with retry for DynamoDB throttling"""
    return retry_with_backoff(original_log_error, error_data)


# Apply patches
AssetProcessor.increment_job_counter = patched_increment_job_counter
AssetProcessor.update_job_status = patched_update_job_status
AssetProcessor.update_job_metadata = patched_update_job_metadata
AssetProcessor.log_error = patched_log_error


class AssetSyncProcessor:
    """Processes objects for synchronization with the Asset Management system via S3 batch operations"""

    def __init__(self, job_id: str, bucket_name: str):
        """
        Initialize the Asset Sync Processor

        Args:
            job_id: Unique job identifier
            bucket_name: S3 bucket name
        """
        self.job_id = job_id
        self.bucket_name = bucket_name
        # Use cached S3 client instead of creating new one
        self.s3_client = get_cached_s3_client(bucket_name)

    def process_s3_batch_operation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single task from S3 batch operations

        Args:
            task: Task information from S3 batch operations

        Returns:
            Result of processing
        """
        logger.info(f"Processing S3 batch operation task: {json.dumps(task)}")

        # Extract the S3 key
        try:
            key = task.get("s3Key")
            if not key:
                logger.error("No S3 key found in task")
                return {
                    "resultCode": "PermanentFailure",
                    "resultString": "No S3 key found in task",
                }

            # Get object tags
            tags = self._get_object_tags(key)

            # Prepare object for processing
            obj = {
                "key": key,
                "assetId": tags.get("AssetID"),
                "inventoryId": tags.get("InventoryID"),
                "lastModified": datetime.now(timezone.utc).isoformat(),
                "size": 0,  # We don't need the size for processing
            }

            # Filter and process the object
            objects_to_process = self._filter_objects_to_process([obj])

            if not objects_to_process:
                logger.info(f"Object {key} doesn't need processing")
                return {
                    "resultCode": "Succeeded",
                    "resultString": "Object already processed",
                }

            # Process the object
            result = self._process_object(objects_to_process[0])

            if result.get("status") == "success":
                # Update job counters
                AssetProcessor.increment_job_counter(
                    self.job_id, "totalObjectsScanned", 1
                )
                AssetProcessor.increment_job_counter(
                    self.job_id, "totalObjectsToProcess", 1
                )
                AssetProcessor.increment_job_counter(
                    self.job_id, "totalObjectsProcessed", 1
                )

                return {
                    "resultCode": "Succeeded",
                    "resultString": f"Successfully processed object: {key}",
                }
            else:
                # Update error counters
                AssetProcessor.increment_job_counter(
                    self.job_id, "totalObjectsScanned", 1
                )
                AssetProcessor.increment_job_counter(
                    self.job_id, "totalObjectsToProcess", 1
                )
                AssetProcessor.increment_job_counter(self.job_id, "errors", 1)

                return {
                    "resultCode": "PermanentFailure",
                    "resultString": f"Failed to process object: {key}. Error: {result.get('error')}",
                }

        except Exception as e:
            logger.error(
                f"Error processing S3 batch operation task: {str(e)}", exc_info=True
            )

            # Update error counters
            AssetProcessor.increment_job_counter(self.job_id, "errors", 1)

            return {
                "resultCode": "PermanentFailure",
                "resultString": f"Exception: {str(e)}",
            }

    def _get_object_tags(self, object_key: str) -> Dict[str, str]:
        """Get tags for an S3 object"""
        try:
            # URL decode the object key to handle encoded characters like spaces
            decoded_key = unquote_plus(object_key)

            response = self.s3_client.get_object_tagging(
                Bucket=self.bucket_name, Key=decoded_key
            )

            return {tag["Key"]: tag["Value"] for tag in response.get("TagSet", [])}
        except Exception as e:
            logger.warning(
                f"Error getting tags for object {object_key} (decoded: {unquote_plus(object_key)}): {str(e)}"
            )
            return {}

    def _get_ingest_queue_url(self) -> Optional[str]:
        """
        Get the SQS queue URL for ingesting events from the job metadata

        Returns:
            SQS queue URL or None if not found
        """
        try:
            # Get job details which should contain the queue URL
            job_details = AssetProcessor.get_job_details(self.job_id)
            if not job_details:
                logger.error(f"Job {self.job_id} not found when looking up queue URL")
                return None

            # Check job metadata for queue URL (set by engine lambda)
            metadata = job_details.get("metadata", {})
            queue_url = metadata.get("ingestQueueUrl")

            if queue_url:
                logger.info(f"Found ingest queue URL in job metadata: {queue_url}")
                return queue_url

            logger.error(
                f"No ingest queue URL found in job metadata for job {self.job_id}"
            )
            return None

        except Exception as e:
            logger.error(f"Error getting ingest queue URL: {str(e)}", exc_info=True)
            return None

    def _filter_objects_to_process(
        self, objects: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter objects that need processing

        Processing logic:
        1. If neither asset ID nor inventory ID exists - process object (PUT)
        2. If asset ID doesn't exist but inventory ID exists - process object (COPY)
        3. If asset ID exists - skip object (already processed)
        """
        logger.info(f"Filtering {len(objects)} objects for processing")

        if not objects:
            return []

        # Extract IDs for batch checking
        asset_ids = [obj.get("assetId") for obj in objects if obj.get("assetId")]
        inventory_ids = [
            obj.get("inventoryId") for obj in objects if obj.get("inventoryId")
        ]

        try:
            # Batch check existence with retry
            existing = retry_with_backoff(
                AssetProcessor.batch_check_asset_exists, asset_ids, inventory_ids
            )
            existing_asset_ids = existing["asset_ids"]
            existing_inventory_ids = existing["inventory_ids"]

            # Filter objects that need processing
            objects_to_process = []

            for obj in objects:
                asset_id = obj.get("assetId")
                inventory_id = obj.get("inventoryId")

                # Determine processing action based on ID existence
                if asset_id and asset_id in existing_asset_ids:
                    # Asset ID exists - skip processing
                    continue
                elif inventory_id and inventory_id in existing_inventory_ids:
                    # Inventory ID exists but asset ID doesn't - S3 copy
                    obj["processingAction"] = "COPY"
                    objects_to_process.append(obj)
                else:
                    # Neither ID exists - full processing
                    obj["processingAction"] = "PUT"
                    objects_to_process.append(obj)

            return objects_to_process

        except Exception as e:
            logger.error(f"Error filtering objects: {str(e)}", exc_info=True)
            raise

    def _process_object(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single object by sending a simulated S3 event to SQS

        Args:
            obj: Object to process

        Returns:
            Processing result
        """
        # URL decode the object key
        object_key = unquote_plus(obj["key"])
        obj.get("processingAction", "PUT")

        try:
            # Get existing tags
            try:
                tags_response = self.s3_client.get_object_tagging(
                    Bucket=self.bucket_name, Key=object_key
                )
                existing_tags = {
                    tag["Key"]: tag["Value"] for tag in tags_response.get("TagSet", [])
                }
            except Exception as e:
                logger.warning(f"Error fetching tags for {object_key}: {str(e)}")

            # Get the ingest SQS queue URL dynamically based on the job configuration
            ingest_queue_url = self._get_ingest_queue_url()

            if not ingest_queue_url:
                logger.error("No ingest queue URL found for this job/bucket")
                raise ValueError("No ingest queue URL found for this job/bucket")

            logger.info(
                f"Sending simulated S3 event for object {object_key} to SQS queue {ingest_queue_url}"
            )

            # Create simulated S3 event message that matches real S3 SQS notifications
            # This mimics the structure of S3 event notifications sent to SQS
            s3_event_message = {
                "Records": [
                    {
                        "eventVersion": "2.1",
                        "eventSource": "medialake.AssetSyncProcessor",
                        "eventTime": datetime.now(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "eventName": "ObjectCreated:Put",
                        "userIdentity": {"principalId": "AssetSyncProcessor"},
                        "requestParameters": {"sourceIPAddress": "127.0.0.1"},
                        "responseElements": {
                            "x-amz-request-id": str(uuid.uuid4()),
                            "x-amz-id-2": str(uuid.uuid4()),
                        },
                        "s3": {
                            "s3SchemaVersion": "1.0",
                            "configurationId": "AssetSyncProcessor",
                            "bucket": {
                                "name": self.bucket_name,
                                "ownerIdentity": {"principalId": "AssetSyncProcessor"},
                                "arn": f"arn:aws:s3:::{self.bucket_name}",
                            },
                            "object": {
                                "key": object_key,
                                "size": obj.get("size", 0),
                                "eTag": obj.get("etag", ""),
                                "sequencer": hex(int(time.time() * 1000000))[2:]
                                .upper()
                                .zfill(16),
                            },
                        },
                    }
                ]
            }

            # Check if this is a FIFO queue (ends with .fifo)
            is_fifo_queue = ingest_queue_url.endswith(".fifo")

            # Prepare message parameters
            message_params = {
                "QueueUrl": ingest_queue_url,
                "MessageBody": json.dumps(s3_event_message),
                "MessageAttributes": {
                    "source": {
                        "StringValue": "medialake.AssetSyncProcessor",
                        "DataType": "String",
                    },
                    "eventType": {
                        "StringValue": "ObjectCreated:Put",
                        "DataType": "String",
                    },
                },
            }

            # Add FIFO-specific parameters if needed
            if is_fifo_queue:
                # Use job ID as MessageGroupId to ensure processing order per job
                # Sanitize job ID for SQS field requirements
                sanitized_job_id = sanitize_for_sqs(self.job_id)
                message_params["MessageGroupId"] = sanitized_job_id

                # Use object key + timestamp for deduplication to prevent duplicates
                dedup_base = f"{object_key}-{int(time.time() * 1000000)}"
                # Sanitize the deduplication ID for SQS requirements
                sanitized_dedup_id = sanitize_for_sqs(dedup_base)
                message_params["MessageDeduplicationId"] = sanitized_dedup_id

                logger.info(
                    f"Sending to FIFO queue with MessageGroupId: {sanitized_job_id}, MessageDeduplicationId: {sanitized_dedup_id}"
                )

            # Send message to SQS with retry logic for throttling - use module-level client
            response = retry_with_backoff(sqs_client.send_message, **message_params)

            # Check if message was sent successfully
            if not response.get("MessageId"):
                error_msg = f"Failed to send SQS message: {response}"
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.info(
                f"Successfully sent simulated S3 event for object {object_key} to SQS. MessageId: {response['MessageId']}"
            )

            # Record successful object processing metric
            metrics.add_metric(
                name="SingleObjectProcessingSuccess", unit=MetricUnit.Count, value=1
            )
            metrics.add_dimension(name="JobId", value=self.job_id)

            # Return success result
            return {
                "status": "success",
                "key": object_key,
                "action": "SIMULATED_SQS_MESSAGE",
            }

        except Exception as e:
            # Check if this is an SQS throttling error that exhausted retries
            is_sqs_throttling = False
            if isinstance(e, ClientError):
                is_sqs_throttling = (
                    hasattr(e, "response")
                    and "Error" in e.response
                    and e.response["Error"].get("Code") == "RequestThrottled"
                )

            if is_sqs_throttling:
                # Record specific metric for SQS throttling failures
                metrics.add_metric(
                    name="SQSThrottlingFailures", unit=MetricUnit.Count, value=1
                )
                metrics.add_dimension(name="JobId", value=self.job_id)
                logger.error(
                    f"SQS throttling exhausted all retries for object {object_key}"
                )

            # Log error locally instead of using AssetProcessor.log_error
            error_id = str(uuid.uuid4())
            logger.error(
                f"Error processing object {object_key}: {str(e)}",
                extra={
                    "errorId": error_id,
                    "objectKey": object_key,
                    "jobId": self.job_id,
                    "bucketName": self.bucket_name,
                    "errorType": (
                        "SQS_THROTTLING_ERROR" if is_sqs_throttling else "PROCESS_ERROR"
                    ),
                },
                exc_info=True,
            )

            # Record failed object processing metric
            metrics.add_metric(
                name="SingleObjectProcessingFailure", unit=MetricUnit.Count, value=1
            )
            metrics.add_dimension(name="JobId", value=self.job_id)

            # Return error result
            return {
                "status": "error",
                "key": object_key,
                "error": str(e),
                "errorId": error_id,
            }


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    """Lambda handler for Asset Sync Processor - S3 Batch Operations only"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # This lambda only handles S3 batch operations
        if "tasks" in event or "task" in event or "job" in event:
            # This is an S3 batch operations event
            logger.info("Processing S3 batch operations event")

            # Get the invocation details
            invocation_schema_version = event.get("invocationSchemaVersion", "1.0")
            invocation_id = event.get("invocationId", "unknown")

            # S3 batch operations sends the task directly or in an array
            tasks = event.get("tasks", [])
            if "task" in event:
                tasks = [event["task"]]

            # Extract the INTERNAL job ID from userArguments
            job_id = None
            if "job" in event and isinstance(event["job"], dict):
                # Get userArguments which contains our application's job ID
                user_args = event["job"].get("userArguments", {})
                if isinstance(user_args, dict):
                    job_id = user_args.get("jobId")

                # If we didn't find it in userArguments, log that for debugging
                if not job_id:
                    logger.warning(f"No jobId found in userArguments: {user_args}")
                    # Fallback to using S3 batch job ID
                    s3_batch_job_id = event["job"].get("id")
                    if s3_batch_job_id:
                        logger.info(
                            f"Using S3 batch job ID as fallback: {s3_batch_job_id}"
                        )
                        job_id = f"s3batch-{s3_batch_job_id}"

            # Log the extracted information for debugging
            logger.info(f"Batch operation details: jobId={job_id}, tasks={len(tasks)}")

            if not job_id:
                logger.error("No job ID found in userArguments")
                return {
                    "invocationSchemaVersion": invocation_schema_version,
                    "treatMissingKeysAs": "PermanentFailure",
                    "invocationId": invocation_id,
                    "results": [
                        {
                            "taskId": task.get("taskId", "unknown"),
                            "resultCode": "PermanentFailure",
                            "resultString": "No job ID found in userArguments",
                        }
                        for task in tasks
                    ],
                }

            # Extract bucket name from the tasks
            bucket_name = None
            if tasks:
                # First, try to get from s3BucketArn
                if "s3BucketArn" in tasks[0]:
                    bucket_arn = tasks[0]["s3BucketArn"]
                    bucket_name = bucket_arn.split(":")[-1]
                # Otherwise, try s3Bucket directly
                elif "s3Bucket" in tasks[0]:
                    bucket_name = tasks[0]["s3Bucket"]

                logger.info(f"Extracted bucket name: {bucket_name}")

            if not bucket_name:
                # Get the job details from DynamoDB to find the bucket name
                job_details = retry_with_backoff(AssetProcessor.get_job_details, job_id)
                if not job_details:
                    logger.error(f"Job {job_id} not found")
                    return {
                        "invocationSchemaVersion": invocation_schema_version,
                        "treatMissingKeysAs": "PermanentFailure",
                        "invocationId": invocation_id,
                        "results": [
                            {
                                "taskId": task.get("taskId", "unknown"),
                                "resultCode": "PermanentFailure",
                                "resultString": f"Job {job_id} not found",
                            }
                            for task in tasks
                        ],
                    }
                # Extract bucket name from job details
                bucket_name = job_details.get("bucketName")

            # Initialize the processor
            processor = AssetSyncProcessor(job_id, bucket_name)

            # Process tasks and collect results
            results = []
            for task in tasks:
                try:
                    task_id = task.get("taskId", "unknown")
                    logger.info(f"Processing task {task_id}")

                    result = processor.process_s3_batch_operation(task)

                    # Record batch operation processing success/failure
                    if result.get("resultCode") == "Succeeded":
                        metrics.add_metric(
                            name="BatchOperationSuccesses",
                            unit=MetricUnit.Count,
                            value=1,
                        )
                    else:
                        metrics.add_metric(
                            name="BatchOperationErrors", unit=MetricUnit.Count, value=1
                        )

                    results.append(
                        {
                            "taskId": task_id,
                            "resultCode": result.get("resultCode", "PermanentFailure"),
                            "resultString": result.get("resultString", "Unknown error"),
                        }
                    )
                except Exception as e:
                    logger.error(f"Error processing task: {str(e)}", exc_info=True)

                    # Record batch operation processing errors
                    metrics.add_metric(
                        name="BatchOperationErrors", unit=MetricUnit.Count, value=1
                    )

                    results.append(
                        {
                            "taskId": task.get("taskId", "unknown"),
                            "resultCode": "PermanentFailure",
                            "resultString": f"Exception: {str(e)}",
                        }
                    )

            # Return the results
            return {
                "invocationSchemaVersion": invocation_schema_version,
                "treatMissingKeysAs": "PermanentFailure",
                "invocationId": invocation_id,
                "results": results,
            }

        else:
            logger.error(
                "Unrecognized event format - expected S3 batch operations event"
            )
            return {"error": "This lambda only handles S3 batch operations events"}

    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}", exc_info=True)
        return {"error": f"Error in lambda handler: {str(e)}"}
