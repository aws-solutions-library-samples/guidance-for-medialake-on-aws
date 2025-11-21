import os
import re

import boto3
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()

transcribe_client = boto3.client("transcribe")
s3_client = boto3.client("s3")


def clean_asset_id(input_string: str) -> str:
    """Extract UUID from asset ID"""
    parts = input_string.split(":")
    uuid_part = parts[-1]
    if uuid_part == "master":
        uuid_part = parts[-2]
    return f"asset:uuid:{uuid_part}"


def sanitize_job_name(name: str) -> str:
    """Sanitize job name to fit AWS Transcribe requirements"""
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return sanitized[:200]


def extract_media_info(event: dict) -> dict:
    """Extract media file information from event (from proxy representation)"""
    payload = event.get("payload", {})
    assets = payload.get("assets", [])

    if not assets or len(assets) == 0:
        raise ValueError("No assets found in event payload")

    asset = assets[0]
    inventory_id = asset.get("InventoryID", "")

    # Find proxy representation
    proxy_rep = None
    for rep in asset.get("DerivedRepresentations", []):
        if rep.get("Purpose") == "proxy":
            proxy_rep = rep
            break

    if not proxy_rep:
        raise ValueError("No proxy representation found in asset")

    # Get storage info from proxy representation
    storage_info = proxy_rep.get("StorageInfo", {})
    primary_location = storage_info.get("PrimaryLocation", {})

    bucket = primary_location.get("Bucket", "")
    object_key = primary_location.get("ObjectKey", {})
    full_path = object_key.get("FullPath", "")

    if not bucket or not full_path:
        raise ValueError(f"Invalid storage info: bucket={bucket}, path={full_path}")

    # Extract directory path (everything before the last slash)
    s3_path = ""
    if "/" in full_path:
        s3_path = full_path.rsplit("/", 1)[0]

    media_uri = f"s3://{bucket}/{full_path}"

    # Determine media format from file extension
    file_ext = full_path.split(".")[-1].lower()
    format_mapping = {
        "mp3": "mp3",
        "mp4": "mp4",
        "wav": "wav",
        "flac": "flac",
        "m4a": "mp4",
        "webm": "webm",
        "ogg": "ogg",
        "amr": "amr",
    }
    media_format = format_mapping.get(file_ext, "mp4")

    logger.info(
        f"Extracted media info - bucket: {bucket}, key: {full_path}, path: {s3_path}, format: {media_format}"
    )

    return {
        "inventory_id": inventory_id,
        "media_uri": media_uri,
        "media_format": media_format,
        "bucket": bucket,
        "object_key": full_path,
        "s3_path": s3_path,
    }


def build_transcription_request(event: dict, media_info: dict) -> dict:
    """
    Build AWS Transcribe request parameters

    Args:
        event: Lambda event
        media_info: Extracted media information

    Returns:
        Dict with Transcribe API parameters
    """
    inventory_id = media_info["inventory_id"]

    # Generate job name from inventory_id
    job_name = f"transcribe-{inventory_id}-{os.urandom(4).hex()}"
    job_name = sanitize_job_name(job_name)

    # Get output bucket from environment
    output_bucket = os.environ.get("MEDIA_ASSETS_BUCKET_NAME")
    if not output_bucket:
        raise ValueError("MEDIA_ASSETS_BUCKET_NAME environment variable not set")

    # Get Transcribe service role ARN for S3 access
    transcribe_role_arn = os.environ.get("TRANSCRIBE_SERVICE_ROLE_ROLE_ARN")
    if not transcribe_role_arn:
        raise ValueError(
            "TRANSCRIBE_SERVICE_ROLE_ROLE_ARN environment variable not set"
        )

    # Build OutputKey - include job name to make it unique per video
    output_key = f"{media_info['s3_path']}/transcription/{job_name}"

    # Build transcription job parameters (matching original api_template format)
    request = {
        "TranscriptionJobName": job_name,
        "Media": {"MediaFileUri": media_info["media_uri"]},
        "MediaFormat": media_info["media_format"],
        "IdentifyLanguage": True,  # Auto-detect language
        "OutputBucketName": output_bucket,
        "OutputKey": output_key,
        "Subtitles": {"Formats": ["vtt"]},
        "JobExecutionSettings": {
            "AllowDeferredExecution": True,
            "DataAccessRoleArn": transcribe_role_arn,
        },
    }

    logger.info(
        f"Built transcription request for job: {job_name}, output: s3://{output_bucket}/{output_key}"
    )
    return request


def build_response(job_response: dict, inventory_id: str) -> dict:
    """
    Build response from Transcribe API response

    Args:
        job_response: Response from start_transcription_job
        inventory_id: Asset inventory ID

    Returns:
        Formatted response for pipeline
    """
    job = job_response.get("TranscriptionJob", {})
    job_name = job.get("TranscriptionJobName", "")
    status = job.get("TranscriptionJobStatus", "")

    # Map status to pipeline format
    status_mapping = {
        "QUEUED": "Started",
        "IN_PROGRESS": "inProgress",
        "COMPLETED": "Completed",
        "FAILED": "Failed",
    }

    response = {
        "statusCode": 200,
        "inventory_id": inventory_id,
        "status": status,
        "transcriptionJobName": job_name,
        "externalJobId": job_name,
        "externalJobStatus": status_mapping.get(status, "Started"),
        "externalJobResult": "Running",
        "metadata": {"service": "transcribe", "jobName": job_name, "status": status},
    }

    logger.info(f"Built response for job: {job_name}, status: {status}")
    return response


@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """
    Start AWS Transcribe transcription job

    This Lambda:
    1. Extracts media file information from event
    2. Builds Transcribe API request
    3. Starts transcription job
    4. Returns job information for pipeline
    """
    logger.info("Received event", extra={"event": event})

    try:
        # Extract media information
        media_info = extract_media_info(event)
        logger.info(f"Extracted media info: {media_info}")

        # Build transcription request
        job_settings = build_transcription_request(event, media_info)
        logger.info(
            "Created job settings",
            extra={
                "TranscriptionJobName": job_settings["TranscriptionJobName"],
                "MediaFileUri": job_settings["Media"]["MediaFileUri"],
                "MediaFormat": job_settings["MediaFormat"],
                "OutputBucketName": job_settings["OutputBucketName"],
            },
        )

        # Start transcription job
        job_response = transcribe_client.start_transcription_job(**job_settings)
        logger.info("Successfully started transcription job")

        # Build and return response
        result = build_response(job_response, media_info["inventory_id"])
        logger.info("Successfully created response")

        return result

    except Exception as e:
        logger.error(f"Error starting transcription job: {e}", exc_info=True)
        raise
