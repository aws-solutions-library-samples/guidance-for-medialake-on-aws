import json
import os
import time
from decimal import Decimal
from functools import wraps
from typing import List, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from boto3.dynamodb.types import TypeDeserializer
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
from requests_aws4auth import AWS4Auth

logger = Logger(service="ddb-to-os-index")
tracer = Tracer()
metrics = Metrics(namespace="MediaLake/AssetIndexing", service="ddb-to-os-index")

# OpenSearch configuration
REGION = os.environ["OS_DOMAIN_REGION"]
HOST = os.environ["OPENSEARCH_ENDPOINT"].split("://")[-1]
INDEX = os.environ["OPENSEARCH_INDEX"]
SQS_URL = os.environ["SQS_URL"]

# Bulk processing configuration
BULK_BATCH_SIZE = int(os.environ.get("BULK_BATCH_SIZE", "500"))
MAX_BULK_SIZE_MB = int(os.environ.get("MAX_BULK_SIZE_MB", "5"))

# Circuit breaker configuration
ERROR_THRESHOLD = float(os.environ.get("ERROR_THRESHOLD", "0.3"))
CIRCUIT_TIMEOUT = int(os.environ.get("CIRCUIT_TIMEOUT", "60"))

# Verbose logging configuration
VERBOSE_LOGGING = False

deserializer = TypeDeserializer()


class CircuitBreaker:
    """
    Circuit breaker to prevent overwhelming OpenSearch when it's under pressure.
    Opens circuit when error rate exceeds threshold, preventing further requests.
    """

    def __init__(
        self, error_threshold: float = ERROR_THRESHOLD, timeout: int = CIRCUIT_TIMEOUT
    ):
        self.error_threshold = error_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
        if self.state == "HALF_OPEN" and self.success_count >= 3:
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker closed - system recovered")

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        total_requests = self.success_count + self.failure_count
        if total_requests >= 10:
            error_rate = self.failure_count / total_requests
            if error_rate >= self.error_threshold and self.state == "CLOSED":
                self.state = "OPEN"
                logger.warning(
                    f"Circuit breaker opened - error rate {error_rate:.2%}",
                    extra={"failures": self.failure_count, "total": total_requests},
                )

    def can_proceed(self) -> bool:
        """Check if requests can proceed."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "HALF_OPEN"
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker half-open - testing recovery")
                return True
            return False

        return True  # HALF_OPEN state


circuit_breaker = CircuitBreaker()


def retry_with_backoff(max_retries=5, base_delay=2, max_delay=60):
    """
    Decorator that implements retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds between retries (default: 2s)
        max_delay: Maximum delay in seconds between retries (default: 60s)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    if not circuit_breaker.can_proceed():
                        logger.warning("Circuit breaker open - skipping operation")
                        raise Exception("Circuit breaker is open")

                    result = func(*args, **kwargs)
                    circuit_breaker.record_success()
                    return result

                except Exception as e:
                    last_exception = e
                    circuit_breaker.record_failure()

                    if attempt == max_retries:
                        logger.error(
                            f"All {max_retries + 1} retry attempts failed for function {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "total_attempts": max_retries + 1,
                                "final_error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        raise e

                    delay = min(base_delay * (2**attempt), max_delay)

                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal objects from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


# Initialize AWS credentials and clients
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "es",
    session_token=credentials.token,
)
sqs = boto3.client("sqs")
opensearch_client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
    max_retries=3,
    retry_on_timeout=True,
)


def dynamodb_item_to_dict(item):
    """
    Convert a DynamoDB record (e.g., NewImage from a Streams event)
    into a normal Python dict.
    """
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def prepare_bulk_actions(records: List[dict]) -> Tuple[List[dict], dict, List[dict]]:
    """
    Prepare bulk actions from DynamoDB stream records.

    Returns:
        Tuple of (bulk_actions, action_to_record_map, failed_records)
        action_to_record_map: dict mapping document_id to original record
    """
    bulk_actions = []
    action_to_record_map = {}
    failed_records = []

    for idx, record in enumerate(records):
        try:
            event_name = record.get("eventName")

            if VERBOSE_LOGGING:
                logger.info(
                    f"Processing record {idx + 1}/{len(records)}",
                    extra={"event_name": event_name, "record_index": idx},
                )

            if event_name == "REMOVE":
                document_id = record["dynamodb"]["OldImage"]["InventoryID"]["S"]
                bulk_actions.append(
                    {
                        "_op_type": "delete",
                        "_index": INDEX,
                        "_id": document_id,
                    }
                )
                action_to_record_map[document_id] = record

                if VERBOSE_LOGGING:
                    logger.info(
                        f"Prepared DELETE action for document {document_id}",
                        extra={"document_id": document_id, "operation": "delete"},
                    )

            elif event_name == "INSERT":
                new_image = record["dynamodb"].get("NewImage")
                if not new_image:
                    logger.warning("INSERT event without NewImage; skipping")
                    continue

                document = dynamodb_item_to_dict(new_image)
                document_id = document["InventoryID"]

                bulk_actions.append(
                    {
                        "_op_type": "index",
                        "_index": INDEX,
                        "_id": document_id,
                        "_source": document,
                    }
                )
                action_to_record_map[document_id] = record

                if VERBOSE_LOGGING:
                    logger.info(
                        f"Prepared INDEX action for document {document_id}",
                        extra={"document_id": document_id, "operation": "index"},
                    )

            elif event_name == "MODIFY":
                new_image = record["dynamodb"].get("NewImage")
                if not new_image:
                    logger.warning("MODIFY event without NewImage; skipping")
                    continue

                document = dynamodb_item_to_dict(new_image)
                document_id = document["InventoryID"]

                bulk_actions.append(
                    {
                        "_op_type": "update",
                        "_index": INDEX,
                        "_id": document_id,
                        "doc": document,
                        "doc_as_upsert": True,
                    }
                )
                action_to_record_map[document_id] = record

                if VERBOSE_LOGGING:
                    logger.info(
                        f"Prepared UPDATE action for document {document_id}",
                        extra={"document_id": document_id, "operation": "update"},
                    )

        except Exception as e:
            logger.error(
                f"Failed to prepare bulk action for record",
                extra={"error": str(e), "event_name": event_name, "record_index": idx},
            )
            failed_records.append(record)

    if VERBOSE_LOGGING:
        logger.info(
            f"Bulk action preparation complete",
            extra={
                "total_records": len(records),
                "actions_prepared": len(bulk_actions),
                "failed_preparations": len(failed_records),
                "mapping_size": len(action_to_record_map),
            },
        )

    return bulk_actions, action_to_record_map, failed_records


def estimate_bulk_size(actions: List[dict]) -> int:
    """Estimate the size of bulk actions in bytes."""
    return len(json.dumps(actions, cls=DecimalEncoder).encode("utf-8"))


def chunk_bulk_actions(actions: List[dict]) -> List[List[dict]]:
    """
    Split bulk actions into chunks based on size and count limits.

    Returns:
        List of action chunks
    """
    chunks = []
    current_chunk = []
    current_size = 0
    max_size_bytes = MAX_BULK_SIZE_MB * 1024 * 1024

    for action in actions:
        action_size = len(json.dumps(action, cls=DecimalEncoder).encode("utf-8"))

        if (
            len(current_chunk) >= BULK_BATCH_SIZE
            or current_size + action_size > max_size_bytes
        ):
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0

        current_chunk.append(action)
        current_size += action_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


@retry_with_backoff(max_retries=15, base_delay=3, max_delay=60)
def execute_bulk_operation(
    actions: List[dict], action_to_record_map: dict
) -> Tuple[int, List[dict]]:
    """
    Execute bulk operation on OpenSearch with retry logic for 429 errors.

    Args:
        actions: List of bulk actions to execute
        action_to_record_map: Mapping of document_id to original DynamoDB record

    Returns:
        Tuple of (success_count, failed_records)
    """
    if not actions:
        return 0, []

    logger.info(f"Executing bulk operation with {len(actions)} actions")

    if VERBOSE_LOGGING:
        logger.info(
            "Bulk operation details",
            extra={
                "action_count": len(actions),
                "mapping_size": len(action_to_record_map),
                "action_types": {
                    "index": len([a for a in actions if a.get("_op_type") == "index"]),
                    "update": len(
                        [a for a in actions if a.get("_op_type") == "update"]
                    ),
                    "delete": len(
                        [a for a in actions if a.get("_op_type") == "delete"]
                    ),
                },
            },
        )

    success, failed = bulk(
        opensearch_client,
        actions,
        stats_only=False,
        raise_on_error=False,
        raise_on_exception=False,
    )

    failed_records = []
    has_429_errors = False

    if failed:
        if VERBOSE_LOGGING:
            logger.info(f"Processing {len(failed)} failed items from bulk operation")

        for idx, item in enumerate(failed):
            error_info = item.get("index", item.get("update", item.get("delete", {})))
            status = error_info.get("status", 0)
            item_id = error_info.get("_id", "unknown")

            if status == 429:
                has_429_errors = True
                logger.warning(
                    "Bulk operation item failed with 429 - Too Many Requests",
                    extra={"item_id": item_id, "status": status},
                )
            else:
                logger.error(
                    "Bulk operation item failed",
                    extra={
                        "error": error_info.get("error"),
                        "status": status,
                        "item_id": item_id,
                    },
                )

            # Map failed action back to original record
            if item_id in action_to_record_map:
                failed_records.append(action_to_record_map[item_id])
                if VERBOSE_LOGGING:
                    logger.info(
                        f"Mapped failed action to original record",
                        extra={
                            "item_id": item_id,
                            "status": status,
                            "failed_item_index": idx,
                        },
                    )
            else:
                logger.warning(
                    f"Failed to map document_id {item_id} back to original record"
                )

    if VERBOSE_LOGGING:
        logger.info(
            "Bulk operation results",
            extra={
                "success_count": success,
                "failed_count": len(failed),
                "failed_records_mapped": len(failed_records),
                "has_429_errors": has_429_errors,
            },
        )

    # If we got 429 errors, raise exception to trigger retry with backoff
    if has_429_errors:
        raise Exception(
            f"OpenSearch returned 429 errors for {len([f for f in failed if (f.get('index', f.get('update', f.get('delete', {}))).get('status') == 429)])} items"
        )

    metrics.add_metric(name="BulkOperationSuccess", unit="Count", value=success)
    metrics.add_metric(name="BulkOperationFailed", unit="Count", value=len(failed))

    return success, failed_records


def send_to_dlq(records: List[dict], reason: str):
    """Send failed records to DLQ."""
    for record in records:
        try:
            event_name = record.get("eventName")

            if event_name == "REMOVE":
                document = dynamodb_item_to_dict(record["dynamodb"]["OldImage"])
                message_type = "Delete the Index"
            elif event_name in ["INSERT", "MODIFY"]:
                document = dynamodb_item_to_dict(record["dynamodb"]["NewImage"])
                message_type = (
                    "Insert the Index" if event_name == "INSERT" else "Modify the Index"
                )
            else:
                continue

            sqs.send_message(
                QueueUrl=SQS_URL,
                MessageBody=json.dumps(document, cls=DecimalEncoder),
                MessageAttributes={
                    "MessageType": {"DataType": "String", "StringValue": message_type},
                    "FailureReason": {"DataType": "String", "StringValue": reason},
                    "EventName": {"DataType": "String", "StringValue": event_name},
                },
            )

            metrics.add_metric(name="DLQMessagesSent", unit="Count", value=1)

        except Exception as e:
            logger.error(
                f"Failed to send record to DLQ",
                extra={"error": str(e), "record": record},
            )


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    logger.info("Lambda invoked", extra={"aws_request_id": context.aws_request_id})

    records = event.get("Records", [])
    total_records = len(records)

    logger.info(f"Processing {total_records} records from DynamoDB stream")
    metrics.add_metric(name="RecordsReceived", unit="Count", value=total_records)

    try:
        if VERBOSE_LOGGING:
            logger.info(
                "Starting bulk action preparation",
                extra={"total_records": total_records},
            )

        # Prepare bulk actions with mapping
        bulk_actions, action_to_record_map, failed_prep = prepare_bulk_actions(records)

        if failed_prep:
            logger.warning(f"Failed to prepare {len(failed_prep)} records")
            if VERBOSE_LOGGING:
                logger.info(
                    "Sending failed preparation records to DLQ",
                    extra={"failed_prep_count": len(failed_prep)},
                )
            send_to_dlq(failed_prep, "Failed to prepare bulk action")

        if not bulk_actions:
            logger.info("No bulk actions to process")
            return {"statusCode": 200, "body": json.dumps("No actions to process")}

        # Split into chunks if needed
        action_chunks = chunk_bulk_actions(bulk_actions)
        logger.info(
            f"Split {len(bulk_actions)} actions into {len(action_chunks)} chunks"
        )

        if VERBOSE_LOGGING:
            logger.info(
                "Chunk details",
                extra={
                    "total_actions": len(bulk_actions),
                    "chunk_count": len(action_chunks),
                    "chunk_sizes": [len(chunk) for chunk in action_chunks],
                },
            )

        total_success = 0
        total_failed = 0

        # Process each chunk
        for i, chunk in enumerate(action_chunks):
            try:
                logger.info(
                    f"Processing chunk {i+1}/{len(action_chunks)} with {len(chunk)} actions"
                )

                success_count, failed_records = execute_bulk_operation(
                    chunk, action_to_record_map
                )
                total_success += success_count
                total_failed += len(failed_records)

                if failed_records:
                    logger.warning(f"Chunk {i+1} had {len(failed_records)} failures")
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Sending {len(failed_records)} failed records from chunk {i+1} to DLQ",
                            extra={
                                "chunk_number": i + 1,
                                "failed_count": len(failed_records),
                            },
                        )
                    send_to_dlq(failed_records, "Bulk operation failed")
                elif VERBOSE_LOGGING:
                    logger.info(f"Chunk {i+1} completed successfully with no failures")

            except Exception as e:
                logger.error(
                    f"Failed to process chunk {i+1}",
                    extra={"error": str(e), "chunk_size": len(chunk)},
                )
                # Map chunk actions back to original records
                chunk_failed_records = []
                for action in chunk:
                    doc_id = action.get("_id")
                    if doc_id and doc_id in action_to_record_map:
                        chunk_failed_records.append(action_to_record_map[doc_id])
                        if VERBOSE_LOGGING:
                            logger.info(
                                f"Mapped failed chunk action to record",
                                extra={"document_id": doc_id, "chunk": i + 1},
                            )
                    else:
                        logger.warning(
                            f"Could not map action with id {doc_id} to original record"
                        )

                if chunk_failed_records:
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Sending {len(chunk_failed_records)} chunk failure records to DLQ",
                            extra={
                                "chunk": i + 1,
                                "failed_count": len(chunk_failed_records),
                            },
                        )
                    send_to_dlq(
                        chunk_failed_records, f"Chunk processing failed: {str(e)}"
                    )
                total_failed += len(chunk)

        logger.info(
            f"Bulk processing completed",
            extra={
                "total_records": total_records,
                "success": total_success,
                "failed": total_failed,
                "chunks": len(action_chunks),
            },
        )

        metrics.add_metric(
            name="RecordsProcessedSuccess", unit="Count", value=total_success
        )
        metrics.add_metric(
            name="RecordsProcessedFailed", unit="Count", value=total_failed
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Processing completed",
                    "total_records": total_records,
                    "success": total_success,
                    "failed": total_failed,
                }
            ),
        }

    except Exception as e:
        logger.exception("Unhandled exception processing stream")
        metrics.add_metric(name="UnhandledErrors", unit="Count", value=1)

        # Send all records to DLQ as fallback
        send_to_dlq(records, f"Unhandled exception: {str(e)}")

        return {"statusCode": 500, "body": json.dumps(f"Error processing stream: {e}")}
