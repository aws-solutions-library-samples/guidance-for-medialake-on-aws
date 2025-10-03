# lambda/shared/common.py
import json
import os
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.config import Config

# Initialize Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Constants
DEFAULT_BATCH_SIZE = 1000
MAX_THREADS = 32
MAX_RETRIES = 5
BACKOFF_BASE = 2  # exponential backoff base


# Enums for better type safety
class JobStatus(str, Enum):
    """Job status constants"""

    INITIALIZING = "INITIALIZING"
    DISCOVERING = "DISCOVERING"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PartitionStatus(str, Enum):
    """Partition status constants"""

    PENDING = "PENDING"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ErrorType(str, Enum):
    """Error type constants"""

    S3_ACCESS_ERROR = "S3_ACCESS_ERROR"
    TAG_FETCH_ERROR = "TAG_FETCH_ERROR"
    DYNAMO_QUERY_ERROR = "DYNAMO_QUERY_ERROR"
    SQS_SEND_ERROR = "SQS_SEND_ERROR"
    PROCESS_ERROR = "PROCESS_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


# JSON Encoder for DynamoDB Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super(DecimalEncoder, self).default(o)


# Optimized boto3 clients with connection pooling and retry configuration
def get_optimized_client(service: str, region: Optional[str] = None) -> Any:
    """
    Get boto3 client with optimized configuration for high throughput

    Args:
        service: AWS service name
        region: Optional region override

    Returns:
        Boto3 client
    """
    config = Config(
        max_pool_connections=100,  # Increase connection pool size
        retries={
            "max_attempts": 10,  # More aggressive retries
            "mode": "adaptive",  # Adaptive retry mode
        },
        connect_timeout=5,  # Connect timeout in seconds
        read_timeout=60,  # Read timeout in seconds
    )

    if region:
        return boto3.client(service, region_name=region, config=config)
    else:
        return boto3.client(service, config=config)


def get_optimized_s3_client(bucket_name: str) -> Any:
    """
    Get S3 client for specific bucket, optimized for the bucket's region

    Args:
        bucket_name: S3 bucket name

    Returns:
        Optimized S3 client for the bucket's region
    """
    try:
        s3_global = get_optimized_client("s3")
        location = s3_global.get_bucket_location(Bucket=bucket_name)
        region = location.get("LocationConstraint") or "us-east-1"

        # Create regional client with optimized config
        return get_optimized_client("s3", region)
    except Exception as e:
        logger.warning(f"Could not determine bucket region: {str(e)}")
        return get_optimized_client("s3")


# Cache for DynamoDB clients to avoid creating new ones for each invocation
_dynamodb_clients = {}


def get_dynamodb_client(region: Optional[str] = None) -> Any:
    """
    Get cached DynamoDB client

    Args:
        region: Optional region override

    Returns:
        DynamoDB client
    """
    region_key = region or boto3.session.Session().region_name

    if region_key not in _dynamodb_clients:
        _dynamodb_clients[region_key] = get_optimized_client("dynamodb", region)

    return _dynamodb_clients[region_key]


class AssetProcessor:
    """Utility methods for asset processing"""

    @staticmethod
    def format_error(
        error_id: str,
        object_key: str,
        error_type: ErrorType,
        error_message: str,
        retry_count: int,
        job_id: str,
        bucket_name: str,
    ) -> Dict[str, Any]:
        """
        Format error details in a standard way

        Args:
            error_id: Unique error ID
            object_key: S3 object key
            error_type: Error type
            error_message: Error message
            retry_count: Number of retries
            job_id: Job ID
            bucket_name: S3 bucket name

        Returns:
            Formatted error details
        """
        ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())

        return {
            "errorId": error_id,
            "timestamp": datetime.utcnow().isoformat(),
            "bucketName": bucket_name,
            "objectKey": object_key,
            "errorType": error_type,
            "errorMessage": error_message,
            "retryCount": retry_count,
            "jobId": job_id,
            "stackTrace": traceback.format_exc(),
            "ttl": ttl,
        }

    @staticmethod
    def log_error(error_details: Dict[str, Any]) -> str:
        """
        Log error in standardized format and store in DynamoDB

        Args:
            error_details: Error details dict

        Returns:
            Error ID
        """
        error_id = error_details.get("errorId", str(uuid.uuid4()))

        # Log error
        logger.error(
            f"Error {error_id}: {error_details.get('errorType')} - {error_details.get('errorMessage')}",
            extra=error_details,
        )

        # Record metrics
        metrics.add_metric(name="Errors", unit=MetricUnit.Count, value=1)
        metrics.add_metric(
            name=f"ErrorType.{error_details.get('errorType')}",
            unit=MetricUnit.Count,
            value=1,
        )

        try:
            # Store error in DynamoDB
            get_dynamodb_client()
            table_name = os.environ.get("ERROR_TABLE_NAME")

            if table_name:
                table = boto3.resource("dynamodb").Table(table_name)
                table.put_item(Item=error_details)
        except Exception as e:
            logger.error(f"Failed to store error details: {str(e)}")

        return error_id

    @staticmethod
    def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        Split a list into chunks of specified size

        Args:
            lst: List to chunk
            chunk_size: Size of each chunk

        Returns:
            List of chunks
        """
        return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]

    @staticmethod
    def update_job_status(
        job_id: str,
        status: JobStatus,
        message: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        notify: bool = True,
    ) -> None:
        """
        Update job status in the job table

        Args:
            job_id: Job ID
            status: New job status
            message: Optional status message
            stats: Optional stats to update
            notify: Whether to publish SNS notification
        """
        try:
            get_dynamodb_client()
            job_table = boto3.resource("dynamodb").Table(
                os.environ.get("JOB_TABLE_NAME")
            )

            update_expression = "SET #status = :status, lastUpdated = :lastUpdated"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": status.value,
                ":lastUpdated": datetime.utcnow().isoformat(),
            }

            if message:
                update_expression += ", statusMessage = :message"
                expression_attribute_values[":message"] = message

            if stats:
                # For each stat, add it to the update expression
                for i, (key, value) in enumerate(stats.items()):
                    update_expression += f", stats.{key} = :stat{i}"
                    expression_attribute_values[f":stat{i}"] = value

            # Update job record
            job_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )

            # Send SNS notification if requested
            if notify and os.environ.get("STATUS_TOPIC_ARN"):
                sns = get_optimized_client("sns")
                sns.publish(
                    TopicArn=os.environ.get("STATUS_TOPIC_ARN"),
                    Message=json.dumps(
                        {
                            "jobId": job_id,
                            "status": status.value,
                            "message": message,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        cls=DecimalEncoder,
                    ),
                    MessageAttributes={
                        "jobId": {"DataType": "String", "StringValue": job_id},
                        "status": {"DataType": "String", "StringValue": status.value},
                    },
                )

            # Record metrics
            metrics.add_metadata(key="jobId", value=job_id)
            metrics.add_metadata(key="jobStatus", value=status.value)
        except Exception as e:
            logger.error(f"Failed to update job status: {str(e)}")

    @staticmethod
    def update_partition_status(
        job_id: str,
        partition_id: str,
        status: PartitionStatus,
        message: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update partition status in the partition table

        Args:
            job_id: Job ID
            partition_id: Partition ID
            status: New partition status
            message: Optional status message
            stats: Optional stats to update
        """
        try:
            get_dynamodb_client()
            partition_table = boto3.resource("dynamodb").Table(
                os.environ.get("PARTITION_TABLE_NAME")
            )

            update_expression = "SET #status = :status, lastUpdated = :lastUpdated"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": status.value,
                ":lastUpdated": datetime.utcnow().isoformat(),
            }

            if message:
                update_expression += ", statusMessage = :message"
                expression_attribute_values[":message"] = message

            if stats:
                # For each stat, add it to the update expression
                for i, (key, value) in enumerate(stats.items()):
                    update_expression += f", stats.{key} = :stat{i}"
                    expression_attribute_values[f":stat{i}"] = value

            # Update partition record
            partition_table.update_item(
                Key={"jobId": job_id, "partitionId": partition_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )

            # Record metrics
            metrics.add_metadata(key="jobId", value=job_id)
            metrics.add_metadata(key="partitionId", value=partition_id)
            metrics.add_metadata(key="partitionStatus", value=status.value)
        except Exception as e:
            logger.error(f"Failed to update partition status: {str(e)}")

    @staticmethod
    def get_job_details(job_id: str) -> Dict[str, Any]:
        """
        Get job details from the job table

        Args:
            job_id: Job ID

        Returns:
            Job details dict
        """
        try:
            get_dynamodb_client()
            job_table = boto3.resource("dynamodb").Table(
                os.environ.get("JOB_TABLE_NAME")
            )

            response = job_table.get_item(Key={"jobId": job_id})
            if "Item" in response:
                return response["Item"]
            else:
                logger.error(f"Job not found: {job_id}")
                return {}
        except Exception as e:
            logger.error(f"Failed to get job details: {str(e)}")
            return {}

    @staticmethod
    def increment_job_counter(
        job_id: str, counter_name: str, increment: int = 1
    ) -> None:
        """
        Increment a counter in the job stats

        Args:
            job_id: Job ID
            counter_name: Counter name
            increment: Increment value
        """
        try:
            get_dynamodb_client()
            job_table = boto3.resource("dynamodb").Table(
                os.environ.get("JOB_TABLE_NAME")
            )

            job_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=f"ADD stats.{counter_name} :inc",
                ExpressionAttributeValues={":inc": increment},
            )

            # Record metrics
            metrics.add_metric(
                name=f"JobCounter.{counter_name}",
                unit=MetricUnit.Count,
                value=increment,
            )
        except Exception as e:
            logger.error(f"Failed to increment job counter: {str(e)}")

    @staticmethod
    def increment_partition_counter(
        job_id: str, partition_id: str, counter_name: str, increment: int = 1
    ) -> None:
        """
        Increment a counter in the partition stats

        Args:
            job_id: Job ID
            partition_id: Partition ID
            counter_name: Counter name
            increment: Increment value
        """
        try:
            get_dynamodb_client()
            partition_table = boto3.resource("dynamodb").Table(
                os.environ.get("PARTITION_TABLE_NAME")
            )

            partition_table.update_item(
                Key={"jobId": job_id, "partitionId": partition_id},
                UpdateExpression=f"ADD stats.{counter_name} :inc",
                ExpressionAttributeValues={":inc": increment},
            )

            # Record metrics
            metrics.add_metric(
                name=f"PartitionCounter.{counter_name}",
                unit=MetricUnit.Count,
                value=increment,
            )
        except Exception as e:
            logger.error(f"Failed to increment partition counter: {str(e)}")

    @staticmethod
    def batch_check_asset_exists(
        asset_ids: List[str], inventory_ids: List[str]
    ) -> Dict[str, Set[str]]:
        """
        Batch check if assets exist

        Args:
            asset_ids: List of asset IDs to check
            inventory_ids: List of inventory IDs to check

        Returns:
            Dict with sets of existing IDs
        """
        existing_asset_ids = set()
        existing_inventory_ids = set()

        try:
            if not asset_ids and not inventory_ids:
                return {
                    "asset_ids": existing_asset_ids,
                    "inventory_ids": existing_inventory_ids,
                }

            dynamodb = get_dynamodb_client()
            assets_table_name = os.environ.get("ASSETS_TABLE_NAME")

            # Process asset IDs in batches (max 100 items per batch get)
            if asset_ids:
                asset_id_batches = AssetProcessor.chunk_list(list(set(asset_ids)), 100)

                for batch in asset_id_batches:
                    request_items = {
                        assets_table_name: {"Keys": [{"assetId": id} for id in batch]}
                    }

                    # Use exponential backoff for retries
                    for attempt in range(MAX_RETRIES):
                        try:
                            response = dynamodb.batch_get_item(
                                RequestItems=request_items
                            )
                            for item in response.get("Responses", {}).get(
                                assets_table_name, []
                            ):
                                if "assetId" in item:
                                    existing_asset_ids.add(item["assetId"])

                            # Check for unprocessed items
                            unprocessed = response.get("UnprocessedKeys", {}).get(
                                assets_table_name, None
                            )
                            if not unprocessed:
                                break

                            # Some items were unprocessed, retry with just those
                            request_items = {"UnprocessedKeys": unprocessed}
                            # Exponential backoff
                            time.sleep((BACKOFF_BASE**attempt) / 10.0)

                        except Exception as e:
                            logger.warning(
                                f"Batch get attempt {attempt + 1} failed: {str(e)}"
                            )
                            if attempt < MAX_RETRIES - 1:
                                time.sleep((BACKOFF_BASE**attempt) / 10.0)
                            else:
                                raise

            # Process inventory IDs using GSI
            if inventory_ids:
                assets_table = boto3.resource("dynamodb").Table(assets_table_name)

                # We need to query one at a time for GSI
                def check_inventory_id(id):
                    try:
                        response = assets_table.query(
                            IndexName="inventoryId-index",
                            KeyConditionExpression="inventoryId = :invId",
                            ExpressionAttributeValues={":invId": id},
                            Limit=1,  # We just need to know if it exists
                        )
                        return id if response.get("Items") else None
                    except Exception as e:
                        logger.warning(f"Inventory ID query failed for {id}: {str(e)}")
                        return None

                # Use ThreadPoolExecutor to parallelize queries
                with ThreadPoolExecutor(
                    max_workers=min(MAX_THREADS, len(inventory_ids))
                ) as executor:
                    results = executor.map(check_inventory_id, set(inventory_ids))
                    for result in results:
                        if result:
                            existing_inventory_ids.add(result)

        except Exception as e:
            logger.error(f"Failed to batch check assets: {str(e)}")

        return {
            "asset_ids": existing_asset_ids,
            "inventory_ids": existing_inventory_ids,
        }

    @staticmethod
    def with_retries(func, max_retries=MAX_RETRIES, initial_backoff=0.1):
        """
        Decorator for retrying a function with exponential backoff

        Args:
            func: Function to retry
            max_retries: Maximum number of retries
            initial_backoff: Initial backoff time in seconds

        Returns:
            Wrapped function with retry logic
        """

        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    # Skip waiting on last attempt
                    if attempt < max_retries - 1:
                        wait_time = initial_backoff * (BACKOFF_BASE**attempt)
                        time.sleep(wait_time)
                        logger.warning(
                            f"Retrying {func.__name__} after error: {str(e)}, attempt {attempt + 1}/{max_retries}"
                        )

            # If we get here, all retries failed
            logger.error(f"All {max_retries} retries failed for {func.__name__}")
            raise last_exception

        return wrapper
