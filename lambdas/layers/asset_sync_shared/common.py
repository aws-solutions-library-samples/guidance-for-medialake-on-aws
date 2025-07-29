### lambda/shared/python/common.py ###
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class JobStatus:
    """Job status constants"""

    INITIALIZING = "INITIALIZING"
    SCANNING = "SCANNING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ErrorType:
    """Error type constants"""

    S3_ACCESS_ERROR = "S3_ACCESS_ERROR"
    TAG_FETCH_ERROR = "TAG_FETCH_ERROR"
    DYNAMO_QUERY_ERROR = "DYNAMO_QUERY_ERROR"
    SQS_SEND_ERROR = "SQS_SEND_ERROR"
    PROCESS_ERROR = "PROCESS_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class AssetProcessor:
    """Utility methods for asset processing"""

    @staticmethod
    def format_error(
        error_id: str,
        object_key: str,
        error_type: str,
        error_message: str,
        retry_count: int,
        job_id: str,
        bucket_name: str,
    ) -> Dict[str, Any]:
        """Format error details in a standard way"""
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
        }

    @staticmethod
    def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split a list into chunks of specified size"""
        return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]

    @staticmethod
    def log_error(error_details: Dict[str, Any]) -> None:
        """Log error in standardized format"""
        logger.error(json.dumps(error_details))

    @staticmethod
    def update_job_status(
        job_id: str,
        status: str,
        message: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update job status in the job table"""
        try:
            dynamodb = boto3.resource("dynamodb")
            job_table = dynamodb.Table(os.environ.get("JOB_TABLE_NAME"))

            update_expression = "SET #status = :status, lastUpdated = :lastUpdated"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": status,
                ":lastUpdated": datetime.utcnow().isoformat(),
            }

            if message:
                update_expression += ", statusMessage = :message"
                expression_attribute_values[":message"] = message

            if stats:
                update_expression += ", stats = :stats"
                expression_attribute_values[":stats"] = stats

            job_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )
        except Exception as e:
            logger.error(f"Failed to update job status: {str(e)}")

    @staticmethod
    def get_job_details(job_id: str) -> Dict[str, Any]:
        """Get job details from the job table"""
        try:
            dynamodb = boto3.resource("dynamodb")
            job_table = dynamodb.Table(os.environ.get("JOB_TABLE_NAME"))

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
        """Increment a counter in the job stats"""
        try:
            dynamodb = boto3.resource("dynamodb")
            job_table = dynamodb.Table(os.environ.get("JOB_TABLE_NAME"))

            job_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=f"ADD stats.{counter_name} :inc",
                ExpressionAttributeValues={":inc": increment},
            )
        except Exception as e:
            logger.error(f"Failed to increment job counter: {str(e)}")

    @staticmethod
    def check_asset_exists(
        asset_id: Optional[str] = None, inventory_id: Optional[str] = None
    ) -> bool:
        """Check if an asset exists with the given asset ID or inventory ID"""
        try:
            dynamodb = boto3.resource("dynamodb")
            assets_table = dynamodb.Table(os.environ.get("ASSETS_TABLE_NAME"))

            if asset_id:
                response = assets_table.get_item(Key={"assetId": asset_id})
                return "Item" in response
            elif inventory_id:
                response = assets_table.query(
                    IndexName="inventoryId-index",
                    KeyConditionExpression="inventoryId = :invId",
                    ExpressionAttributeValues={":invId": inventory_id},
                )
                return len(response.get("Items", [])) > 0
            return False
        except Exception as e:
            logger.error(f"Failed to check asset existence: {str(e)}")
            return False
