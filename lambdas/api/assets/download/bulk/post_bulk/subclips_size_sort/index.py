"""
Bulk Download Subclips Size Sort Lambda

This Lambda function sort sub-clips by size for packaging by:
1. Calling HeadObject in S3 to get the size of each output sub-clip
2. Putting it into either the largeFiles or smallFiles array for download packaging

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import os
from datetime import datetime
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-subclips-size-sort")
tracer = Tracer(service="bulk-download-subclips-size-sort")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-subclips-size-sort"
)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# Get environment variables
USER_TABLE_NAME = os.environ[
    "USER_TABLE_NAME"
]  # User table now stores bulk download jobs
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
SMALL_FILE_THRESHOLD_MB = int(os.environ.get("SMALL_FILE_THRESHOLD_MB", "1024"))  # MB

# Initialize DynamoDB tables
user_table = dynamodb.Table(USER_TABLE_NAME)  # User table for bulk download jobs


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


# Run HeadObject on the path provided and return the ContentLength
@tracer.capture_method
def get_s3_object_size(bucket: str, key: str) -> int:
    """
    Get the size of an S3 object.

    Args:
        bucket: Name of the S3 bucket
        key: Path to the S3 object

    Returns:
        Size of the S3 object in bytes

    Raises:
        Exception: If HeadObject fails
    """
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        return response["ContentLength"]
    except ClientError as e:
        logger.error(f"Failed to get S3 object size: {str(e)}")
        raise


@tracer.capture_method
def find_dict_by_value(dict_list: list[Dict], key: str, value: Any) -> Dict:
    """Find dict in list where "key" equals "value"

    Args:
        dict_list: A list of Dicts to search
        key: The Key you want to match values to
        value: The value you're looking to find in a Dict

    Returns:
        Dict: The dict that contains the specified value for the specified key
    """
    for d in dict_list:
        if d.get(key) == value:
            return d
    return {}


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def combined_file_totals(
    event: Dict[str, Any], clip_bytes: int, small_clips: int, large_clips: int
) -> Dict[str, int]:
    """Whole-file totals from assess_scale plus the encoded sub-clips.

    Returns the values to store on the job record and pass downstream:
    totalSize (bytes the user will download), smallFilesCount (zipped files)
    and largeFilesCount (individual presigned files).
    """
    return {
        "totalSize": _as_int(event.get("totalSize")) + clip_bytes,
        "smallFilesCount": _as_int(event.get("smallFilesCount")) + small_clips,
        "largeFilesCount": _as_int(event.get("largeFilesCount")) + large_clips,
    }


@tracer.capture_method
def split_s3_uri(s3_uri: str) -> Tuple[str, str]:
    """
    Split an S3 URI into its constituent parts

    Args:
        s3_uri: the S3 uri to parse

    Returns:
        A Tuple containing the Bucket and Key Name
    """
    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for sorting completed sub-clips by size.

    Args:
        event: Event containing job details and sub-clips file locations
        context: Lambda context

    Returns:
        Updated job details with sub-clips sorted into smallFiles and largeFiles arrays
    """
    try:
        processed_sub_clips: list = event.get("processedSubClips", [])
        sub_clips_configs: list = event.get("subClips", [])
        job_id = event.get("jobId")
        user_id = event.get("userId")

        # Basic input validation
        if not processed_sub_clips:
            raise ValueError("No processed subclips found in event")
        if not sub_clips_configs:
            raise ValueError("No subclips found in event")
        if not job_id:
            raise ValueError("Missing jobId in event")
        if not user_id:
            raise ValueError("Missing userId in event")
        if not event.get("smallFiles"):
            event["smallFiles"] = []
        if not event.get("largeFiles"):
            event["largeFiles"] = []

        logger.info(
            "Sorting subClips by size for download packaging",
            extra={
                "userId": user_id,
                "jobId": job_id,
                "subClipFileCount": len(processed_sub_clips),
            },
        )

        # Sort subclips into large/small file arrays
        clip_bytes = 0
        small_clip_count = 0
        large_clip_count = 0
        for sub_clip in processed_sub_clips:
            # The MediaConvert task does not provide the output file extension as part of the destination
            # value in the task output, so we'll need to get it from the original config inputs.
            matching_sub_clip_config = find_dict_by_value(
                sub_clips_configs,
                "outputLocationNoExt",
                sub_clip.get("outputLocation", ""),
            )
            if not matching_sub_clip_config:
                raise ValueError(f"Matching subclip config not found for {sub_clip}")

            output_location: str = matching_sub_clip_config.get("outputLocation", "")

            # Check if output path is S3 URI:
            if not output_location.startswith("s3://") and len(output_location) > 5:
                raise ValueError(f"Invalid outputLocation: {output_location}")

            # Get the size of the sub-clip
            bucket, key = split_s3_uri(output_location)
            size_bytes = get_s3_object_size(bucket, key)
            clip_bytes += size_bytes

            # If it qualifies as a small file, add to smallFiles for zipping
            if size_bytes <= SMALL_FILE_THRESHOLD_MB * 1024 * 1024:
                small_clip_count += 1
                event["smallFiles"].append(
                    {
                        "jobId": job_id,
                        "userId": user_id,
                        "outputLocation": output_location,
                        "assetId": "S3_URI_ASSET_LOCATION",
                        "type": "S3_URI",
                        "options": {},
                    }
                )
            else:
                large_clip_count += 1
                event["largeFiles"].append(
                    {
                        "jobId": job_id,
                        "userId": user_id,
                        "outputLocation": output_location,
                        "assetId": "S3_URI_ASSET_LOCATION",
                        "type": "S3_URI",
                        "options": {},
                    }
                )

        # Remove subclips and processedSubClips fields from task output,
        # we won't need them now that sub-clip processing is done.
        event.pop("subClips", None)
        event.pop("processedSubClips", None)

        # assess_scale counted only whole files (a clip's size is unknown until
        # it is encoded). Now that every clip exists, report the job's real
        # download: clips counted as zipped or large files, and their output
        # bytes added to the whole-file total. Absolute values (not ADD), so a
        # retried invocation cannot double-count.
        totals = combined_file_totals(
            event, clip_bytes, small_clip_count, large_clip_count
        )
        event.update(totals)

        logger.info(
            "Updating Dynamo Job Status",
            extra={"jobId": job_id, **totals},
        )

        # Update dynamo job status in user table
        # Get the existing job's itemKey
        item_key = get_existing_job_item_key(job_id)

        # Format user_id only if it doesn't already have the USER# prefix
        formatted_user_id = (
            user_id if user_id.startswith("USER#") else f"USER#{user_id}"
        )

        user_table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=(
                "SET #status = :status, #updatedAt = :updatedAt, "
                "#totalSize = :totalSize, #smallFilesCount = :smallFilesCount, "
                "#largeFilesCount = :largeFilesCount"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#updatedAt": "updatedAt",
                "#totalSize": "totalSize",
                "#smallFilesCount": "smallFilesCount",
                "#largeFilesCount": "largeFilesCount",
            },
            ExpressionAttributeValues={
                ":status": "SUB_CLIPPING_COMPLETE",
                ":updatedAt": datetime.utcnow().isoformat(),
                ":totalSize": totals["totalSize"],
                ":smallFilesCount": totals["smallFilesCount"],
                ":largeFilesCount": totals["largeFilesCount"],
            },
        )

        logger.info(
            "Completed subclips size sort",
            extra={
                "userId": user_id,
                "jobId": job_id,
            },
        )

        return event

    except Exception as e:
        logger.error(
            f"Error sorting sub-clips by size: {str(e)}",
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
            name="SubClipsSizeSortErrors", unit=MetricUnit.Count, value=1
        )

        # Re-raise the exception to be handled by Step Functions
        raise
