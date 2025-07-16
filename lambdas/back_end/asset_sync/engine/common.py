import enum
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

# Logging setup
from aws_lambda_powertools import Logger
from botocore.config import Config

logger = Logger()

# Constants
MAX_THREADS = 40  # Maximum number of threads for parallel operations
MAX_RETRY_ATTEMPTS = 5  # Maximum number of retry attempts for operations


class JobStatus(enum.Enum):
    """Enum for job status values"""

    INITIALIZING = "INITIALIZING"
    DISCOVERING = "DISCOVERING"
    SCANNING = "SCANNING"
    SCANNED = "SCANNED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PartitionStatus(enum.Enum):
    """Enum for partition status values"""

    PENDING = "PENDING"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ErrorType(enum.Enum):
    """Enum for error types"""

    S3_ACCESS_ERROR = "S3_ACCESS_ERROR"
    TAG_FETCH_ERROR = "TAG_FETCH_ERROR"
    PROCESS_ERROR = "PROCESS_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB"""

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super(DecimalEncoder, self).default(o)


def get_optimized_client(service_name):
    """Get optimized boto3 client with retries and connection pooling"""
    config = Config(
        retries={"max_attempts": 10, "mode": "adaptive"}, max_pool_connections=40
    )
    return boto3.client(service_name, config=config)


def get_optimized_s3_client(bucket_name=None):
    """Get optimized S3 client with correct region for bucket"""
    region = None
    if bucket_name:
        try:
            s3_client = boto3.client("s3")
            location = s3_client.get_bucket_location(Bucket=bucket_name)
            region = location.get("LocationConstraint")

            # Handle special case for us-east-1
            if region is None:
                region = "us-east-1"
        except Exception:
            # Fall back to default client
            pass

    config = Config(
        retries={"max_attempts": 10, "mode": "adaptive"},
        max_pool_connections=40,
        region_name=region,
    )

    return boto3.client("s3", config=config)


class AssetProcessor:
    """Utility class for asset processing operations"""

    @staticmethod
    def update_job_status(job_id, status, status_message=None):
        """Update job status in DynamoDB"""
        if not job_id:
            raise ValueError("job_id is required")

        if "JOB_TABLE_NAME" not in os.environ:
            raise ValueError("JOB_TABLE_NAME environment variable is not set")

        dynamodb = boto3.resource("dynamodb")
        job_table = dynamodb.Table(os.environ["JOB_TABLE_NAME"])

        update_expr = "SET #status = :status, lastUpdated = :timestamp"
        expr_values = {
            ":status": status.value if isinstance(status, enum.Enum) else status,
            ":timestamp": datetime.now(timezone.utc).isoformat(),
        }
        expr_names = {"#status": "status"}

        if status_message:
            update_expr += ", statusMessage = :message"
            expr_values[":message"] = status_message

        job_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )

    @staticmethod
    def increment_job_counter(job_id, counter_name, value=1):
        """Increment a counter in job stats"""
        if not job_id or not counter_name:
            raise ValueError("job_id and counter_name are required")

        if "JOB_TABLE_NAME" not in os.environ:
            raise ValueError("JOB_TABLE_NAME environment variable is not set")

        dynamodb = boto3.resource("dynamodb")
        job_table = dynamodb.Table(os.environ["JOB_TABLE_NAME"])

        update_expr = "ADD stats.#counter :inc SET lastUpdated = :timestamp"
        expr_values = {
            ":inc": value,
            ":timestamp": datetime.now(timezone.utc).isoformat(),
        }
        expr_names = {"#counter": counter_name}

        job_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )

    @staticmethod
    def update_job_metadata(job_id, metadata):
        """Update job metadata in DynamoDB"""
        if not job_id:
            raise ValueError("job_id is required")

        if "JOB_TABLE_NAME" not in os.environ:
            raise ValueError("JOB_TABLE_NAME environment variable is not set")

        dynamodb = boto3.resource("dynamodb")
        job_table = dynamodb.Table(os.environ["JOB_TABLE_NAME"])

        # First check if the job exists
        response = job_table.get_item(Key={"jobId": job_id})
        job = response.get("Item")

        if not job:
            raise ValueError(f"Job {job_id} not found")

        # If metadata doesn't exist, create it first
        if "metadata" not in job:
            job_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression="SET metadata = :empty_map, lastUpdated = :timestamp",
                ExpressionAttributeValues={
                    ":empty_map": {},
                    ":timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        # Now update the metadata fields
        update_expr = "SET lastUpdated = :timestamp"
        expr_values = {":timestamp": datetime.now(timezone.utc).isoformat()}

        # Build update expression for metadata fields
        for i, (key, value) in enumerate(metadata.items()):
            update_expr += f", metadata.#key{i} = :value{i}"
            expr_values[f":value{i}"] = value

        # Build expression attribute names
        expr_names = {}
        for i, key in enumerate(metadata.keys()):
            expr_names[f"#key{i}"] = key

        job_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )

    @staticmethod
    def get_job_details(job_id):
        """Get job details from DynamoDB"""
        if not job_id:
            raise ValueError("job_id is required")

        if "JOB_TABLE_NAME" not in os.environ:
            raise ValueError("JOB_TABLE_NAME environment variable is not set")

        dynamodb = boto3.resource("dynamodb")
        job_table = dynamodb.Table(os.environ["JOB_TABLE_NAME"])

        response = job_table.get_item(Key={"jobId": job_id})
        return response.get("Item")

    @staticmethod
    def get_job_by_batch_id(batch_job_id):
        """
        Get job details by S3 Batch Operations job ID

        Args:
            batch_job_id: S3 Batch Operations job ID

        Returns:
            Job details dict or None if not found
        """
        if not batch_job_id:
            raise ValueError("batch_job_id is required")

        if "JOB_TABLE_NAME" not in os.environ:
            raise ValueError("JOB_TABLE_NAME environment variable is not set")

        try:
            dynamodb = boto3.resource("dynamodb")
            job_table = dynamodb.Table(os.environ["JOB_TABLE_NAME"])

            # Scan the table to find a job with the matching batch job ID in metadata
            response = job_table.scan(
                FilterExpression="metadata.batchJobId = :batch_job_id",
                ExpressionAttributeValues={":batch_job_id": batch_job_id},
            )

            # Return the first matching job
            items = response.get("Items", [])
            if items:
                logger.info(
                    f"Found job for batch ID {batch_job_id}: {items[0].get('jobId')}"
                )
                return items[0]
            else:
                logger.warning(f"No job found for batch ID: {batch_job_id}")
                return None

        except Exception as e:
            logger.error(f"Error looking up job by batch ID {batch_job_id}: {str(e)}")
            return None

    @staticmethod
    def format_error(
        error_id,
        object_key,
        error_type,
        error_message,
        retry_count,
        job_id,
        bucket_name,
    ):
        """Format error details in a standard way"""
        return {
            "errorId": error_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bucketName": bucket_name,
            "objectKey": object_key,
            "errorType": (
                error_type.value if isinstance(error_type, enum.Enum) else error_type
            ),
            "errorMessage": error_message,
            "retryCount": retry_count,
            "jobId": job_id,
        }

    @staticmethod
    def log_error(error_details):
        """Log an error to the error table"""
        if "ERROR_TABLE_NAME" not in os.environ:
            logger.warning(
                "ERROR_TABLE_NAME environment variable is not set, skipping error logging"
            )
            return error_details.get("errorId", str(uuid.uuid4()))

        try:
            dynamodb = boto3.resource("dynamodb")
            error_table = dynamodb.Table(os.environ["ERROR_TABLE_NAME"])

            error_table.put_item(Item=error_details)
            logger.info(f"Logged error {error_details.get('errorId')} to error table")
            return error_details.get("errorId")
        except Exception as e:
            logger.error(f"Failed to log error to table: {str(e)}")
            return error_details.get("errorId", str(uuid.uuid4()))

    @staticmethod
    def batch_check_asset_exists(asset_ids, inventory_ids):
        """
        Check if assets exist in the asset table

        Args:
            asset_ids: List of asset IDs to check
            inventory_ids: List of inventory IDs to check

        Returns:
            Dict with sets of existing asset IDs and inventory IDs
        """
        existing_asset_ids = set()
        existing_inventory_ids = set()

        try:
            if not asset_ids and not inventory_ids:
                logger.info("No IDs to check")
                return {
                    "asset_ids": existing_asset_ids,
                    "inventory_ids": existing_inventory_ids,
                }

            if "ASSETS_TABLE_NAME" not in os.environ:
                logger.error("ASSETS_TABLE_NAME environment variable is not set")
                return {
                    "asset_ids": existing_asset_ids,
                    "inventory_ids": existing_inventory_ids,
                }

            dynamodb = boto3.resource("dynamodb")
            assets_table = dynamodb.Table(os.environ["ASSETS_TABLE_NAME"])

            # Check for asset IDs using the AssetIDIndex
            if asset_ids:
                # Process in batches to avoid DynamoDB limits
                for asset_id in set(asset_ids):
                    try:
                        response = assets_table.query(
                            IndexName="AssetIDIndex",
                            KeyConditionExpression="#dsaid = :asset_id",
                            ExpressionAttributeNames={
                                "#dsaid": "DigitalSourceAsset.ID"
                            },
                            ExpressionAttributeValues={":asset_id": asset_id},
                            Limit=1,
                        )

                        if response.get("Items"):
                            existing_asset_ids.add(asset_id)
                    except Exception as e:
                        logger.warning(f"Error checking asset ID {asset_id}: {str(e)}")

            # Check for inventory IDs using direct get_item calls
            if inventory_ids:
                for inventory_id in set(inventory_ids):
                    try:
                        response = assets_table.get_item(
                            Key={"InventoryID": inventory_id}
                        )

                        if "Item" in response:
                            existing_inventory_ids.add(inventory_id)
                    except Exception as e:
                        logger.warning(
                            f"Error checking inventory ID {inventory_id}: {str(e)}"
                        )

            return {
                "asset_ids": existing_asset_ids,
                "inventory_ids": existing_inventory_ids,
            }
        except Exception as e:
            logger.error(f"Error in batch_check_asset_exists: {str(e)}")
            return {
                "asset_ids": existing_asset_ids,
                "inventory_ids": existing_inventory_ids,
            }
