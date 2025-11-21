import json
import os
import re
from decimal import Decimal

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
transcribe_client = boto3.client("transcribe")


def _strip_decimals(obj):
    """Convert Decimal objects to int/float for JSON serialization"""
    if isinstance(obj, list):
        return [_strip_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """
    Parse S3 URI to extract bucket and key

    Args:
        uri: S3 URI in format https://s3.region.amazonaws.com/bucket/key

    Returns:
        Tuple of (bucket, key)
    """
    pattern = (
        r"^https:\/\/s3\.(?:[a-z0-9-]{4,})\.amazonaws\.com\/([a-z0-9-\.]{1,})\/(.*)$"
    )
    match = re.match(pattern, uri)
    if not match:
        raise ValueError(f"Invalid S3 URI format: {uri}")
    return match.group(1), match.group(2)


def read_transcript_from_s3(bucket: str, key: str) -> str:
    """
    Read and extract transcript text from S3

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Transcript text (empty string if no speech detected)
    """
    try:
        logger.info(f"Reading transcript from s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = json.loads(response["Body"].read().decode("utf-8"))

        # Extract transcript text from AWS Transcribe output format
        transcripts = content.get("results", {}).get("transcripts", [])
        if transcripts and len(transcripts) > 0:
            transcript_text = transcripts[0].get("transcript", "").strip()
            logger.info(f"Extracted transcript: {len(transcript_text)} characters")
            return transcript_text

        logger.warning("No transcripts found in results")
        return ""

    except ClientError as e:
        logger.error(f"S3 error reading transcript: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error parsing transcript: {e}", exc_info=True)
        raise


def validate_transcript(transcript: str) -> tuple[bool, str | None]:
    """
    Validate transcript content

    Args:
        transcript: Transcript text to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not transcript or transcript.strip() == "":
        logger.warning("Transcript validation failed: empty or whitespace-only")
        return False, "No speech detected in audio/video content"

    logger.info(
        f"Transcript validation passed: {len(transcript)} characters, {len(transcript.split())} words"
    )
    return True, None


def extract_job_name(event: dict) -> str:
    """Extract transcription job name from event"""
    # Try from metadata first
    metadata = event.get("metadata", {})
    job_name = metadata.get("transcriptionJobName")
    if job_name:
        return job_name

    # Try from externalJobId
    job_name = metadata.get("externalJobId")
    if job_name:
        return job_name

    # Try from payload
    payload = event.get("payload", {})
    data = payload.get("data", {})
    body = data.get("body", {})

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass

    job_name = body.get("transcriptionJobName") or body.get("externalJobId")
    if job_name:
        return job_name

    raise ValueError("transcriptionJobName not found in event")


def extract_inventory_id(event: dict) -> str:
    """Extract inventory_id from event payload"""
    # Try from payload.assets
    payload = event.get("payload", {})
    assets = payload.get("assets", [])
    if isinstance(assets, list) and assets:
        inventory_id = assets[0].get("InventoryID")
        if inventory_id:
            return inventory_id

    # Try from payload.data.body
    data = payload.get("data", {})
    body = data.get("body", {})
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass

    inventory_id = body.get("inventory_id")
    if inventory_id:
        return inventory_id

    raise ValueError("inventory_id not found in event payload")


def update_asset_table(
    inventory_id: str, transcript_uri: str, transcript_text: str, transcript_valid: bool
) -> dict:
    """
    Update DynamoDB asset table with transcription results

    Args:
        inventory_id: Asset inventory ID
        transcript_uri: S3 URI of transcript JSON
        transcript_text: Extracted transcript text
        transcript_valid: Whether transcript passed validation

    Returns:
        Updated DynamoDB item
    """
    table_name = os.getenv("MEDIALAKE_ASSET_TABLE")
    if not table_name:
        logger.warning("MEDIALAKE_ASSET_TABLE not set, skipping DynamoDB update")
        return {}

    table = dynamodb.Table(table_name)

    update_expression = "SET TranscriptionS3Uri = :uri, TranscriptValid = :valid"
    expression_values = {":uri": transcript_uri, ":valid": transcript_valid}

    # Only store transcript text if not empty
    if transcript_text and transcript_text.strip():
        update_expression += ", TranscriptText = :text"
        expression_values[":text"] = transcript_text

    logger.info(f"Updating asset {inventory_id} in DynamoDB")
    table.update_item(
        Key={"InventoryID": inventory_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
    )

    item = table.get_item(Key={"InventoryID": inventory_id}).get("Item", {})
    return _strip_decimals(item)


def build_response(
    job: dict,
    transcript_text: str,
    inventory_id: str,
    transcript_valid: bool,
    validation_error: str | None = None,
    updated_asset: dict | None = None,
) -> dict:
    """
    Build standardized response for pipeline

    Args:
        job: Transcription job details from AWS Transcribe
        transcript_text: Extracted transcript text
        inventory_id: Asset inventory ID
        transcript_valid: Whether transcript passed validation
        validation_error: Validation error message if any
        updated_asset: Updated DynamoDB item if available

    Returns:
        Formatted response dict for pipeline
    """
    job_name = job.get("TranscriptionJobName", "")
    status = job.get("TranscriptionJobStatus", "")
    language = job.get("LanguageCode", "")

    # Build base response
    response = {
        "statusCode": 200,
        "inventory_id": inventory_id,
        "status": status,
        "transcript_text": transcript_text,
        "transcript_valid": transcript_valid,
        "transcription": {
            "job_name": job_name,
            "transcript": transcript_text,
            "detected_language": language,
            "is_empty": len(transcript_text.strip()) == 0,
            "length": len(transcript_text),
            "word_count": len(transcript_text.split()) if transcript_text else 0,
        },
    }

    # Add validation error if present
    if validation_error:
        response["validation_error"] = validation_error
        response["transcription"]["validation_error"] = validation_error

    # Map AWS Transcribe status to pipeline status
    status_mapping = {
        "COMPLETED": "Completed",
        "IN_PROGRESS": "inProgress",
        "QUEUED": "Started",
        "PROCESSING": "inProgress",
        "FAILED": "Failed",
    }
    response["externalJobStatus"] = status_mapping.get(status, "Started")

    # Set job result
    if status == "COMPLETED":
        # Keep externalJobStatus as "Completed" even if transcript is empty
        # The Choice node will check transcript_valid field separately
        if transcript_valid:
            response["externalJobResult"] = "Success"
        else:
            response["externalJobResult"] = "Failed"
    elif status == "FAILED":
        response["externalJobResult"] = "Failed"
    else:
        response["externalJobResult"] = "Running"

    response["externalJobId"] = job_name

    # Add updated asset if available
    if updated_asset:
        response["updatedAsset"] = updated_asset

    logger.info(
        f"Built response: status={status}, valid={transcript_valid}, length={len(transcript_text)}"
    )
    return response


@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """
    Check transcription job status and validate transcript

    This Lambda:
    1. Gets transcription job status from AWS Transcribe
    2. If completed, downloads and validates transcript from S3
    3. Updates DynamoDB with results
    4. Returns formatted response for pipeline with validation status
    """
    logger.info("Received event", extra={"event": event})

    try:
        # Extract required data from event
        job_name = extract_job_name(event)
        inventory_id = extract_inventory_id(event)

        logger.info(
            f"Processing transcription job: {job_name} for asset: {inventory_id}"
        )

        # Get job status from AWS Transcribe
        job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_details = job["TranscriptionJob"]
        status = job_details.get("TranscriptionJobStatus")

        logger.info(f"Job status: {status}")

        # Initialize response variables
        transcript_text = ""
        transcript_valid = False
        validation_error = None
        updated_asset = None

        # Process completed jobs
        if status == "COMPLETED":
            transcript_info = job_details.get("Transcript", {})
            transcript_uri = transcript_info.get("TranscriptFileUri", "")

            if transcript_uri:
                # Download and extract transcript from S3
                bucket, key = parse_s3_uri(transcript_uri)
                transcript_text = read_transcript_from_s3(bucket, key)

                # Validate transcript - raise exception if empty
                transcript_valid, validation_error = validate_transcript(
                    transcript_text
                )

                if not transcript_valid:
                    error_msg = (
                        validation_error or "No speech detected in audio/video content"
                    )
                    logger.error(f"Empty transcript detected: {error_msg}")
                    raise RuntimeError(error_msg)

                # Convert HTTPS URL to S3 URI format for storage
                s3_uri = f"s3://{bucket}/{key}"

                # Update DynamoDB
                updated_asset = update_asset_table(
                    inventory_id=inventory_id,
                    transcript_uri=s3_uri,
                    transcript_text=transcript_text,
                    transcript_valid=transcript_valid,
                )
            else:
                logger.warning("No transcript URI in completed job")
                validation_error = "Transcription completed but no transcript URI found"

        # Build and return response
        response = build_response(
            job=job_details,
            transcript_text=transcript_text,
            inventory_id=inventory_id,
            transcript_valid=transcript_valid,
            validation_error=validation_error,
            updated_asset=updated_asset,
        )

        logger.info("Successfully processed transcription status")
        return response

    except Exception as e:
        logger.error(f"Error processing transcription status: {e}", exc_info=True)
        raise
