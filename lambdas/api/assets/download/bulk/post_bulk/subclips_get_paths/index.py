"""
Bulk Download Subclips Get Paths Lambda

This Lambda function returns the input/output paths for subclips by:
1. Retrieving path for source asset
2. Generating an output path to write the sub-clip out to.
3. Updating the job record with input/output information.

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
from datetime import datetime
from typing import Any, Dict, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-subclips-get-paths")
tracer = Tracer(service="bulk-download-subclips-get-paths")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-subclips-get-paths"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
ASSET_TABLE = os.environ["ASSET_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]

# Initialize DynamoDB tables
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs
asset_table = dynamodb.Table(ASSET_TABLE)


@tracer.capture_method
def get_existing_job_item_key(job_id: str) -> str:
    """
    Get the existing itemKey for a job by querying GSI3.

    Args:
        job_id: The job ID to find

    Returns:
        The itemKey of the existing job record

    Raises:
        ValueError: If job is not found
    """
    try:
        response = user_table.query(
            IndexName="GSI3",
            KeyConditionExpression="gsi3Pk = :gsi3_pk",
            ExpressionAttributeValues={":gsi3_pk": f"JOB#{job_id}"},
            Limit=1,
        )

        if not response.get("Items"):
            raise ValueError(f"Job {job_id} not found")

        return response["Items"][0]["itemKey"]

    except Exception as e:
        logger.error(f"Failed to find existing job record: {str(e)}")
        raise


@tracer.capture_method
def get_asset_details(asset_id: str) -> Tuple[str, str, str]:
    """
    Retrieve asset details from DynamoDB.

    Args:
        asset_id: ID of the asset to retrieve

    Returns:
        Bucket: the name of the s3 bucket
        File Path: the path to the file in S3 (includes the filename)
        File Name: the name of the file

    Raises:
        Exception: If asset retrieval fails
    """
    try:
        response = asset_table.get_item(
            Key={"InventoryID": asset_id},
            ConsistentRead=True,
        )

        if "Item" not in response:
            raise Exception(f"Asset {asset_id} not found")

        main_rep = (
            response["Item"].get("DigitalSourceAsset", {}).get("MainRepresentation", {})
        )
        storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
        bucket = storage_info.get("Bucket")
        file_path = storage_info.get("ObjectKey", {}).get("FullPath")

        if not file_path or not bucket:
            logger.error(
                f"Could not determine file path or bucket for asset {asset_id}",
                extra={"assetId": asset_id},
            )

        # Get file name from path
        file_name = os.path.basename(file_path)

        return bucket, file_path, file_name

    except ClientError as e:
        logger.error(
            "Failed to retrieve asset details",
            extra={
                "error": str(e),
                "assetId": asset_id,
            },
        )
        raise Exception(f"Failed to retrieve asset details: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for getting input/output paths for sub-clips

    Args:
        event: Event containing job details and sub-clips specs
        context: Lambda context

    Returns:
        Updated job details with sub-clip source and output locations
    """
    try:
        job_id = event.get("jobId")
        user_id = event.get("userId")

        if not job_id:
            raise ValueError("Missing jobId in event")

        if not user_id:
            raise ValueError("Missing userId in event")

        sub_clips = event.get("subClips", [])
        if not sub_clips:
            logger.error("No sub-clips found in event")
            raise ValueError("No sub-clips found in event")

        logger.info(
            "Gathering sub-clip input/output paths for processing",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "subClipFileCount": len(sub_clips),
            },
        )

        bucket: str = ""
        file_path: str = ""
        file_name: str = ""

        # Update sub_clip entries with input/output path details
        for sub_clip in sub_clips:
            bucket, file_path, file_name = get_asset_details(sub_clip["assetId"])

            if not bucket or not file_path or not file_name:
                raise ValueError(
                    f"Missing asset details: Bucket: {bucket}, File Path: {file_path}, File Name: {file_name}"
                )

            # The path to the input source file from which to clip
            sub_clip["sourceLocation"] = f"s3://{bucket}/{file_path.lstrip("/")}"

            # Generate output S3 location through combo of:
            # <assets_bucket>/temp/subClips/<job-id>/source-name_<start-time-dashes>_<end-time-dashes>
            start_time = sub_clip.get("clipBoundary", {}).get("startTime", "")
            end_time = sub_clip.get("clipBoundary", {}).get("endTime", "")

            if not start_time:
                raise ValueError("Missing sub-clip start_time in event")
            if not end_time:
                raise ValueError("Missing sub-clip end_time in event")

            name, extension = os.path.splitext(file_name)

            # Change timecode formats to be compatible with object naming conventions
            formatted_start_time = start_time.replace(":", "-").replace(";", "-")
            formatted_end_time = end_time.replace(":", "-").replace(";", "-")

            # The path for the output sub-clip
            path_no_extension = f"s3://{MEDIA_ASSETS_BUCKET}/temp/subClips/{job_id}/{name}_{formatted_start_time}_{formatted_end_time}"
            sub_clip["outputLocationNoExt"] = path_no_extension
            sub_clip["outputLocation"] = f"{path_no_extension}{extension}"

        # Update dynamo job status in user table
        # Get the existing job's itemKey
        item_key = get_existing_job_item_key(job_id)

        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=("SET #status = :status, " "#updatedAt = :updatedAt"),
            ExpressionAttributeNames={
                "#status": "status",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "GENERATING_SUB_CLIPS",
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "Completed get subclips paths.",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "subClipFileCount": len(sub_clips),
            },
        )

        return event

    except Exception as e:
        logger.error(
            f"Error getting sub-clips paths: {str(e)}",
            exc_info=True,
            extra={"jobId": event.get("jobId")},
        )

        # Update job status to FAILED
        try:
            if "jobId" in event and "userId" in event:
                # Format user_id only if it doesn't already have the USER# prefix
                formatted_user_id = (
                    event["userId"]
                    if event["userId"].startswith("USER#")
                    else f"USER#{event['userId']}"
                )

                # Get the existing job's itemKey
                try:
                    item_key = get_existing_job_item_key(event["jobId"])

                    user_table.update_item(
                        Key={"userId": formatted_user_id, "itemKey": item_key},
                        UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                        ExpressionAttributeNames={
                            "#status": "status",
                            "#error": "error",
                            "#updatedAt": "updatedAt",
                        },
                        ExpressionAttributeValues={
                            ":status": "FAILED",
                            ":error": f"Failed to process large files: {str(e)}",
                            ":updatedAt": datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as query_error:
                    logger.error(
                        f"Failed to find job record for error update: {str(query_error)}"
                    )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"userId": event.get("userId"), "jobId": event.get("jobId")},
            )

        metrics.add_metric(
            name="SubClipsGetPathsErrors", unit=MetricUnit.Count, value=1
        )

        # Re-raise the exception to be handled by Step Functions
        raise
