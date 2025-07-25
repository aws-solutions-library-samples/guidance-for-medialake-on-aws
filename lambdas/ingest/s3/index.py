import concurrent.futures
import json
import os
import resource
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the refactored AssetProcessor
from .asset_processor import create_asset_processor

# Import from extracted modules
from .config import (
    AWS_REGION,
    DO_NOT_INGEST_DUPLICATES,
    S3_CONFIG,
    VECTOR_BUCKET_NAME,
    configure_logging_level,
)
from .s3_utils import extract_s3_details_from_event
from .utils import get_memory_usage, is_relevant_event, json_serialize

# Re-use boto3's session credentials
_session = boto3.Session()
_credentials = _session.get_credentials()

# Global clients - initialized once for Lambda container reuse
s3_client = None
dynamodb_resource = None
dynamodb_client = None
eventbridge_client = None
s3_vector_client = None

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configure logging based on environment
logger.setLevel(configure_logging_level())

# Log configuration at startup
logger.info(
    f"Lambda configuration - DO_NOT_INGEST_DUPLICATES: {DO_NOT_INGEST_DUPLICATES}"
)
logger.info(
    "Note: Files with same hash AND same object key will always be skipped regardless of DO_NOT_INGEST_DUPLICATES setting"
)


def initialize_global_clients():
    """Initialize global AWS clients for container reuse"""
    global s3_client, dynamodb_resource, dynamodb_client, eventbridge_client, s3_vector_client

    if s3_client is None:
        s3_client = boto3.client("s3", config=S3_CONFIG)
        logger.info("Initialized global S3 client")

    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb")
        logger.info("Initialized global DynamoDB resource")

    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")
        logger.info("Initialized global DynamoDB client")

    if eventbridge_client is None:
        eventbridge_client = boto3.client("events")
        logger.info("Initialized global EventBridge client")

    if s3_vector_client is None and VECTOR_BUCKET_NAME:
        try:
            s3_vector_client = boto3.client("s3vectors", region_name=AWS_REGION)
            logger.info("Initialized global S3 Vector Store client")
        except Exception as e:
            logger.warning(f"Failed to initialize S3 Vector Store client: {e}")
            s3_vector_client = None


# Process records in parallel with improved logging
def process_records_in_parallel(processor, records: List[Dict], max_workers: int = 5):
    """Process records in parallel using a ThreadPoolExecutor"""
    # Add logging for initial record count
    logger.info(f"Starting parallel processing with {len(records)} records")

    # Debug log the first record structure
    if records and len(records) > 0:
        logger.info(f"First record structure: {json_serialize(records[0])}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        skipped_records = 0

        for i, record in enumerate(records):
            try:
                # Extract S3 details using the helper function
                bucket, key, event_name, version_id = extract_s3_details_from_event(
                    record
                )

                if bucket and key:
                    # Debug log for keys containing special characters
                    if "+" in key or "%" in key:
                        logger.info(f"Key with special characters: {key}")

                    logger.info(
                        f"Submitting task for bucket: {bucket}, key: {key}, event: {event_name}, version: {version_id}"
                    )
                    futures.append(
                        executor.submit(
                            process_s3_event,
                            processor,
                            bucket,
                            key,
                            event_name,
                            version_id,
                        )
                    )
                else:
                    logger.warning(f"Could not extract bucket/key from record {i}")
                    skipped_records += 1
            except Exception as e:
                logger.exception(
                    f"Error preparing record {i} for parallel processing: {e}"
                )
                skipped_records += 1

        # Log summary of submitted tasks
        logger.info(
            f"Submitted {len(futures)} tasks for parallel processing, skipped {skipped_records} records"
        )

        if not futures:
            logger.warning(
                "No tasks were submitted for processing! Check record format."
            )
            # Safe serialization for the sample record
            if len(records) > 0:
                sample_record = records[0]
                if isinstance(sample_record, dict):
                    # Fix: Avoid using __name__ attribute for str type
                    sample_str = json_serialize(
                        {
                            k: (
                                type(v).__name__
                                if hasattr(type(v), "__name__")
                                else str(type(v))
                            )
                            for k, v in sample_record.items()
                        }
                    )
                else:
                    # Fix: Avoid using __name__ attribute for str type
                    sample_str = (
                        type(sample_record).__name__
                        if hasattr(type(sample_record), "__name__")
                        else str(type(sample_record))
                    )
            else:
                sample_str = "empty"

            event_format_data = {
                "type": (
                    type(records).__name__
                    if hasattr(type(records), "__name__")
                    else str(type(records))
                ),
                "length": len(records) if hasattr(records, "__len__") else "unknown",
                "sample_structure": sample_str,
            }
            logger.info(f"Full event format: {json_serialize(event_format_data)}")
            return

        # Wait for all to complete
        completed_futures = concurrent.futures.wait(futures)

        # Process results and count successes/failures
        success_count = 0
        error_count = 0
        for future in completed_futures.done:
            try:
                future.result()
                success_count += 1
            except Exception as e:
                error_count += 1
                # Log the actual exception
                logger.exception(f"Task execution failed: {str(e)}")

        logger.info(
            f"Parallel processing complete: {success_count} succeeded, {error_count} failed, {skipped_records} skipped"
        )

        # Add metrics
        metrics.add_metric(
            name="RecordsProcessedSuccessfully",
            unit=MetricUnit.Count,
            value=success_count,
        )
        metrics.add_metric(
            name="RecordsSkipped", unit=MetricUnit.Count, value=skipped_records
        )
        if error_count > 0:
            metrics.add_metric(
                name="RecordsProcessedWithErrors",
                unit=MetricUnit.Count,
                value=error_count,
            )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict, context: LambdaContext) -> Dict:
    """Handle S3 events via SQS from either direct S3 notifications or EventBridge Pipes"""
    # Add overall Lambda metrics
    metrics.add_metric(name="Invocations", unit=MetricUnit.Count, value=1)

    # Initialize memory usage metrics
    initial_memory = get_memory_usage()

    # Thorough event investigation logging
    logger.info(f"Received event type: {type(event).__name__}")
    if isinstance(event, dict):
        logger.info(f"Event keys: {list(event.keys())}")
        if "Records" in event:
            logger.info(f"Records count: {len(event['Records'])}")
            if event["Records"]:
                logger.info(f"First record type: {type(event['Records'][0]).__name__}")
                if isinstance(event["Records"][0], dict):
                    logger.info(
                        f"First record keys: {list(event['Records'][0].keys())}"
                    )
                    # Check if it's an SQS event
                    if (
                        "eventSource" in event["Records"][0]
                        and event["Records"][0]["eventSource"] == "aws:sqs"
                    ):
                        logger.info("Detected SQS event source")

    # Initialize global clients
    initialize_global_clients()

    # Create processor using the new factory function
    processor = create_asset_processor(
        s3_client=s3_client,
        dynamodb_resource=dynamodb_resource,
        eventbridge_client=eventbridge_client,
        s3_vector_client=s3_vector_client,
    )

    # Log environment variables at debug level
    logger.debug(
        f"Environment variables: ASSETS_TABLE={os.environ.get('ASSETS_TABLE')}, "
        f"EVENT_BUS_NAME={os.environ.get('EVENT_BUS_NAME')}"
    )

    # Check DynamoDB table exists
    try:
        table_info = dynamodb_client.describe_table(
            TableName=os.environ["ASSETS_TABLE"]
        )
        logger.debug(
            f"DynamoDB table info available - Table Status: {dynamodb_client.describe_table(TableName=os.environ['ASSETS_TABLE']).get('Table', {}).get('TableStatus')}"
        )
    except Exception as e:
        logger.error(f"Error accessing DynamoDB table: {str(e)}")
        metrics.add_metric(name="DynamoDBAccessErrors", unit=MetricUnit.Count, value=1)

    try:
        # Quick filter for empty event
        if not event:
            logger.warning("Empty event received")
            # Add comprehensive event structure logging to diagnose issues
            logger.info(f"Event type: {type(event).__name__}")
            if isinstance(event, dict):
                logger.info(f"Event keys: {list(event.keys())}")
                if "Records" in event:
                    logger.info(f"Records count: {len(event['Records'])}")
                    if event["Records"]:
                        logger.info(
                            f"First record keys: {list(event['Records'][0].keys())}"
                        )
                        if "s3" in event["Records"][0]:
                            logger.info(
                                f"S3 structure: {json_serialize(event['Records'][0]['s3'])}"
                            )
            elif isinstance(event, list):
                logger.info(f"List event length: {len(event)}")
                if event:
                    logger.info(f"First item type: {type(event[0]).__name__}")
                    if isinstance(event[0], dict):
                        logger.info(f"First item keys: {list(event[0].keys())}")
            return {"statusCode": 200, "body": "No records to process"}

        # Check if it's a test event
        if isinstance(event, dict) and event.get("Event") == "s3:TestEvent":
            logger.info("Received S3 test event - skipping processing")
            return {"statusCode": 200, "body": "Test event received"}

        # Count records for metrics
        total_records = 0

        # Enhanced event detection - determine event type with less nesting
        if isinstance(event, list):
            # Direct list of records - process in parallel
            logger.info(f"Processing {len(event)} records directly")
            total_records = len(event)
            process_records_in_parallel(processor, event)

        elif isinstance(event, dict) and "Records" in event:
            # Standard S3 event format
            logger.info(
                f"Processing standard S3 event with {len(event['Records'])} records"
            )
            total_records = len(event["Records"])

            # Process records in parallel
            s3_records = []
            for record in event["Records"]:
                if (
                    "body" in record
                    and "eventSource" in record
                    and record["eventSource"] == "aws:sqs"
                ):
                    # This is an SQS message, parse the body
                    try:
                        body = json.loads(record["body"])
                        if "Records" in body and isinstance(body["Records"], list):
                            # Extract S3 records from SQS message body
                            for s3_record in body["Records"]:
                                # Validate that this is a proper S3 record
                                if "s3" in s3_record and "eventSource" in s3_record:
                                    valid_sources = [
                                        "aws:s3",
                                        "medialake.AssetSyncProcessor",
                                    ]
                                    if s3_record.get("eventSource") in valid_sources:
                                        s3_records.append(s3_record)
                                        logger.info(
                                            f"Extracted S3 record from SQS: {s3_record.get('eventSource')} - {s3_record['s3']['bucket']['name']}/{s3_record['s3']['object']['key']}"
                                        )
                        else:
                            logger.warning(
                                f"SQS message body does not contain Records array"
                            )
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SQS message body: {str(e)}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing SQS message: {str(e)}")
                        continue
                elif "s3" in record:
                    # Direct S3 record (not from SQS)
                    s3_records.append(record)
                else:
                    logger.warning(
                        f"Unrecognized record format: {json_serialize(record)}"
                    )

            # Process the collected records in parallel
            if s3_records:
                logger.info(f"Processing {len(s3_records)} S3 records in parallel")
                process_records_in_parallel(processor, s3_records)

        elif isinstance(event, dict) and "detail-type" in event:
            # EventBridge event format - single event
            logger.info("Processing EventBridge event")
            total_records = 1

            if event.get("source") != "aws.s3":
                logger.warning(f"Unexpected event source: {event.get('source')}")
                return {"statusCode": 200, "body": "Event ignored - not from S3"}

            detail = event.get("detail", {})

            # Extract bucket and key with enhanced robustness
            bucket = None
            key = None
            version_id = None

            # Check all possible locations for bucket
            if isinstance(detail.get("bucket"), dict):
                bucket = detail["bucket"].get("name")
            elif isinstance(detail.get("bucket"), str):
                bucket = detail["bucket"]

            # Check all possible locations for key
            if isinstance(detail.get("object"), dict):
                key = detail["object"].get("key")
                version_id = detail["object"].get("version-id") or detail["object"].get(
                    "versionId"
                )
            elif isinstance(detail.get("object"), str):
                key = detail["object"]
            elif "key" in detail:
                key = detail["key"]

            # Map EventBridge detail-type to S3 event name
            detail_type = event.get("detail-type", "")
            event_type_mapping = {
                "Object Created": "ObjectCreated:",
                "Object Deleted": "ObjectRemoved:",
                "Object Restored": "ObjectRestore:",
                "Object Tagged": "ObjectTagging:",
                "PutObject": "ObjectCreated:Put",
                "CompleteMultipartUpload": "ObjectCreated:CompleteMultipartUpload",
                "DeleteObject": "ObjectRemoved:Delete",
                "CopyObject": "ObjectCreated:Copy",  # Add mapping for CopyObject events
            }

            event_name = event_type_mapping.get(detail_type, "")

            # If we have valid bucket and key, process the event
            if bucket and key:
                logger.info(
                    f"Processing EventBridge event for {bucket}/{key} with event type: {event_name}, version: {version_id}"
                )
                process_s3_event(processor, bucket, key, event_name, version_id)
            else:
                logger.warning(
                    f"Missing bucket or key in EventBridge event: {json_serialize(detail)}"
                )

        # Calculate memory usage metrics
        final_memory = get_memory_usage()
        memory_used = final_memory - initial_memory

        metrics.add_metric(
            name="MemoryUsedMB", unit=MetricUnit.Megabytes, value=memory_used
        )
        metrics.add_metric(
            name="RecordsProcessed", unit=MetricUnit.Count, value=total_records
        )
        logger.info(
            f"Finished processing {total_records} records, memory used: {memory_used}MB"
        )

        return {
            "statusCode": 200,
            "body": f"Processed {total_records} records successfully",
        }

    except Exception:
        logger.exception("Error in handler")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        raise


def process_s3_event(
    processor,
    bucket: str,
    key: str,
    event_name: str,
    version_id: str = None,
):
    """Process a single S3 event with improved performance"""
    # Skip processing if event type not relevant (quick filtering)
    if not is_relevant_event(event_name):
        logger.info(f"Skipping irrelevant event type: {event_name} for {bucket}/{key}")
        return

    logger.info(
        f"Processing {event_name} event for asset: {bucket}/{key}, version: {version_id}"
    )

    # Record start time for duration tracking
    start_time = datetime.now()

    try:
        if event_name.startswith("ObjectRemoved:"):
            # Handle deletion - only delete from DynamoDB, don't try to delete the S3 object again
            logger.info(
                f"Processing deletion event for {bucket}/{key}, version: {version_id}"
            )
            processor.delete_asset(
                bucket, key, is_delete_event=True, version_id=version_id
            )
            metrics.add_metric(name="DeletedAssets", unit=MetricUnit.Count, value=1)
            logger.info(f"Asset deletion processed: {key}")
        else:
            # Handle creation/modification/copy events - process all ObjectCreated events the same way
            logger.info(f"Processing ObjectCreated event for {bucket}/{key}")

            # Store original key for fallback in error handling
            original_event_key = key

            # Verify object exists in S3 before processing
            try:
                # Try to get tags to identify asset early for logging
                try:
                    tag_response = processor.s3.get_object_tagging(
                        Bucket=bucket, Key=key
                    )
                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in tag_response.get("TagSet", [])
                    }

                    if "AssetID" in tags and "InventoryID" in tags:
                        # Add asset context for early logging
                        logger.append_keys(
                            assetID=tags["AssetID"], inventoryID=tags["InventoryID"]
                        )
                        logger.info(
                            f"Processing existing tagged asset: {tags['AssetID']}"
                        )
                except Exception:
                    # Continue without tags, not critical
                    pass

                processor.s3.head_object(Bucket=bucket, Key=key)
            except Exception as s3_error:
                logger.error(
                    f"S3 object verification failed for {bucket}/{key}: {str(s3_error)}"
                )
                # Log exact key for debugging to see if there are encoding issues
                logger.error(
                    f"Failed key details - length: {len(key)}, contains '+': {'+' in key}, raw key: {repr(key)}"
                )

                # Try alternative key encodings to help diagnose the issue
                alternative_found = False
                try:
                    # Try with '+' decoded as literal '+' (no space replacement)
                    alt_key = urllib.parse.unquote(key)
                    if alt_key != key:
                        logger.info(
                            f"Trying alternative key without space replacement: {repr(alt_key)}"
                        )
                        processor.s3.head_object(Bucket=bucket, Key=alt_key)
                        logger.warning(
                            f"Object found with alternative key encoding. Using: {repr(alt_key)}"
                        )
                        key = alt_key
                        alternative_found = True
                except Exception as alt_error:
                    logger.debug(
                        f"Alternative key without space replacement failed: {str(alt_error)}"
                    )

                if not alternative_found:
                    try:
                        # Try with original key from event (before any decoding)
                        logger.info(
                            f"Trying original undecoded key: {repr(original_event_key)}"
                        )
                        processor.s3.head_object(Bucket=bucket, Key=original_event_key)
                        logger.warning(
                            f"Object found with original key. Using: {repr(original_event_key)}"
                        )
                        key = original_event_key
                        alternative_found = True
                    except Exception as orig_error:
                        logger.debug(f"Original key also failed: {str(orig_error)}")

                if not alternative_found:
                    logger.error(
                        f"All key variations failed. Object may not exist or there's a different encoding issue."
                    )
                    raise s3_error

            # Process all ObjectCreated events (including Copy) the same way
            result = processor.process_asset(bucket, key)
            if result:
                # Add asset information to context for logging
                logger.append_keys(
                    assetID=result["DigitalSourceAsset"]["ID"],
                    inventoryID=result["InventoryID"],
                )
                metrics.add_metric(
                    name="ProcessedAssets", unit=MetricUnit.Count, value=1
                )
                metrics.add_metric(
                    name="CreationEvents", unit=MetricUnit.Count, value=1
                )
                logger.info(
                    f"Asset processed successfully: {result['DigitalSourceAsset']['ID']}"
                )
            else:
                logger.info(f"Asset already processed or skipped: {key}")

        # Track processing duration
        duration = (datetime.now() - start_time).total_seconds()
        metrics.add_metric(
            name="EventProcessingTime", unit=MetricUnit.Seconds, value=duration
        )

    except Exception as e:
        logger.exception(f"Error in process_s3_event for {bucket}/{key}: {str(e)}")
        # Log key details for troubleshooting
        logger.error(
            f"Key details - length: {len(key)}, contains '+': {'+' in key}, raw key: {repr(key)}"
        )
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        # Track error duration too
        duration = (datetime.now() - start_time).total_seconds()
        metrics.add_metric(
            name="FailedEventProcessingTime", unit=MetricUnit.Seconds, value=duration
        )
        raise


# Helper function to get memory usage
def get_memory_usage() -> float:
    """Get current memory usage in MB"""
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except (ImportError, AttributeError):
        # If resource module not available (e.g., on Windows), return 0
        return 0


def extract_s3_details_from_event(
    event_record: Dict,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extract S3 bucket, key, event type, and version ID from various event structures
    Returns: (bucket, key, event_name, version_id)
    """
    # Direct S3 event structure
    if "s3" in event_record:
        if "bucket" in event_record["s3"] and "object" in event_record["s3"]:
            bucket = event_record["s3"]["bucket"]["name"]
            # Decode S3 key properly - handle both URL encoding and '+' as spaces
            raw_key = event_record["s3"]["object"]["key"]
            key = urllib.parse.unquote(raw_key).replace("+", " ")
            event_name = event_record.get("eventName", "ObjectCreated:")
            version_id = event_record["s3"]["object"].get("versionId")
            # Log the source for debugging
            event_source = event_record.get("eventSource", "unknown")
            logger.info(
                f"Processing direct S3 record from {event_source}: {bucket}/{key}, version: {version_id}"
            )
            logger.info(f"Key transformation: '{raw_key}' -> '{key}'")
            return bucket, key, event_name, version_id

    # SQS message with EventBridge payload
    if (
        "body" in event_record
        and "eventSource" in event_record
        and event_record["eventSource"] == "aws:sqs"
    ):
        try:
            body = json.loads(event_record["body"])

            # Check if this is an S3 event (might be in Records array)
            if (
                "Records" in body
                and isinstance(body["Records"], list)
                and len(body["Records"]) > 0
            ):
                for record in body["Records"]:
                    # Accept both real S3 events and simulated events from AssetSyncProcessor
                    valid_sources = ["aws:s3", "medialake.AssetSyncProcessor"]
                    if record.get("eventSource") in valid_sources and "s3" in record:
                        bucket = record["s3"]["bucket"]["name"]
                        # Decode S3 key properly - handle both URL encoding and '+' as spaces
                        raw_key = record["s3"]["object"]["key"]
                        key = urllib.parse.unquote(raw_key).replace("+", " ")
                        event_name = record.get("eventName", "ObjectCreated:")
                        version_id = record["s3"]["object"].get("versionId")
                        # Log the extracted details for debugging
                        logger.info(
                            f"Extracted from SQS S3 record (source: {record.get('eventSource')}): bucket={bucket}, key={key}, event={event_name}, version={version_id}"
                        )
                        logger.info(f"Key transformation: '{raw_key}' -> '{key}'")
                        return bucket, key, event_name, version_id

            # Check if this is an S3 event from EventBridge
            if body.get("source") == "aws.s3" and "detail" in body:
                detail = body["detail"]

                # Extract bucket
                bucket = None
                if "bucket" in detail:
                    if isinstance(detail["bucket"], dict):
                        bucket = detail["bucket"].get("name")
                    elif isinstance(detail["bucket"], str):
                        bucket = detail["bucket"]

                # Extract key
                key = None
                if "object" in detail:
                    if isinstance(detail["object"], dict):
                        key = detail["object"].get("key")
                    elif isinstance(detail["object"], str):
                        key = detail["object"]

                # Extract version ID
                version_id = None
                if "object" in detail and isinstance(detail["object"], dict):
                    version_id = detail["object"].get("version-id") or detail[
                        "object"
                    ].get("versionId")

                # Apply URL decoding to the key if it exists - handle both URL encoding and '+' as spaces
                if key:
                    raw_key = key
                    key = urllib.parse.unquote(key).replace("+", " ")
                    if raw_key != key:
                        logger.info(
                            f"EventBridge key transformation: '{raw_key}' -> '{key}'"
                        )

                # Determine event type
                event_name = "ObjectCreated:"
                if body.get("detail-type") == "Object Deleted":
                    event_name = "ObjectRemoved:"

                return bucket, key, event_name, version_id
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SQS message body: {str(e)}")

    # Log unrecognized event structure to help diagnose issues
    logger.warning(f"Unrecognized event structure: {json_serialize(event_record)}")

    return None, None, None, None
