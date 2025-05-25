"""
Bulk Download Upload Part Lambda

This Lambda function uploads a part of a file for a multipart upload:
1. Reads the specified part from the local file
2. Uploads the part to S3
3. Returns the ETag of the uploaded part

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
- Metrics and monitoring
"""

import os
import json
import time
from typing import Dict, Any
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from botocore.config import Config

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-upload-part")
tracer = Tracer(service="bulk-download-upload-part")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-upload-part")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
# Configure S3 client with Signature Version 4 for KMS encryption support
s3 = boto3.client("s3", config=Config(signature_version='s3v4'))
sfn = boto3.client('stepfunctions')

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")

# Initialize DynamoDB table
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)


@tracer.capture_method
def update_job_progress(job_id: str, part_number: int, total_parts: int) -> None:
    """
    Update the job progress in DynamoDB.
    
    Args:
        job_id: Job ID
        part_number: Current part number
        total_parts: Total number of parts
    """
    try:
        # Calculate progress (50% for initialization + 50% for uploading parts)
        progress = 50 + int((part_number / total_parts) * 50)
        
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #progress = :progress, #updatedAt = :updatedAt",
            ExpressionAttributeNames={
                "#progress": "progress",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":progress": progress,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        logger.info(
            "Updated job progress",
            extra={
                "jobId": job_id,
                "progress": progress,
                "partNumber": part_number,
                "totalParts": total_parts,
            },
        )
    
    except ClientError as e:
        logger.warning(
            "Failed to update job progress",
            extra={
                "error": str(e),
                "jobId": job_id,
                "partNumber": part_number,
            },
        )
        # Don't raise an exception here, as this is not critical


@tracer.capture_method
def upload_part(
    bucket: str, key: str, upload_id: str, part_number: int, body: bytes
) -> Dict[str, Any]:
    """
    Upload a part to S3.
    
    Args:
        bucket: S3 bucket name
        key: S3 key
        upload_id: Upload ID
        part_number: Part number
        body: Part data
        
    Returns:
        Dictionary containing the ETag of the uploaded part
    """
    try:
        response = s3.upload_part(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=body,
        )
        
        logger.info(
            "Uploaded part",
            extra={
                "bucket": bucket,
                "key": key,
                "uploadId": upload_id,
                "partNumber": part_number,
                "size": len(body),
                "etag": response["ETag"],
            },
        )
        
        return {
            "PartNumber": part_number,
            "ETag": response["ETag"],
        }
    
    except Exception as e:
        logger.error(
            "Failed to upload part",
            extra={
                "error": str(e),
                "bucket": bucket,
                "key": key,
                "uploadId": upload_id,
                "partNumber": part_number,
            },
        )
        raise


@tracer.capture_method
def read_part_from_file(file_path: str, start_byte: int, end_byte: int) -> bytes:
    """
    Read a part from a file.
    
    Args:
        file_path: Path to the file
        start_byte: Start byte
        end_byte: End byte
        
    Returns:
        Part data
    """
    try:
        with open(file_path, "rb") as f:
            f.seek(start_byte)
            data = f.read(end_byte - start_byte + 1)
        
        logger.info(
            "Read part from file",
            extra={
                "filePath": file_path,
                "startByte": start_byte,
                "endByte": end_byte,
                "size": len(data),
            },
        )
        
        return data
    
    except Exception as e:
        logger.error(
            "Failed to read part from file",
            extra={
                "error": str(e),
                "filePath": file_path,
                "startByte": start_byte,
                "endByte": end_byte,
            },
        )
        raise


@tracer.capture_method
def send_task_success(task_token: str, output: Dict[str, Any]) -> None:
    """
    Send a task success to Step Functions.
    
    Args:
        task_token: Task token
        output: Output data
    """
    try:
        sfn.send_task_success(
            taskToken=task_token,
            output=json.dumps(output),
        )
        
        logger.info(
            "Sent task success",
            extra={
                "taskToken": task_token[:10] + "...",  # Log only part of the token for security
            },
        )
    
    except Exception as e:
        # Check if the error is due to task timeout
        if "TaskTimedOut" in str(e) or "does not exist anymore" in str(e):
            logger.warning(
                "Task token has expired, but part upload was successful",
                extra={
                    "error": str(e),
                    "taskToken": task_token[:10] + "...",
                    "output": output,
                },
            )
            # Don't raise the exception for timeout errors since the upload was successful
            return
        
        logger.error(
            "Failed to send task success",
            extra={
                "error": str(e),
                "taskToken": task_token[:10] + "...",
            },
        )
        raise


@tracer.capture_method
def send_task_failure(task_token: str, error: str, cause: str) -> None:
    """
    Send a task failure to Step Functions.
    
    Args:
        task_token: Task token
        error: Error type
        cause: Error cause
    """
    try:
        sfn.send_task_failure(
            taskToken=task_token,
            error=error,
            cause=cause,
        )
        
        logger.info(
            "Sent task failure",
            extra={
                "taskToken": task_token[:10] + "...",
                "error": error,
                "cause": cause,
            },
        )
    
    except Exception as e:
        # Check if the error is due to task timeout
        if "TaskTimedOut" in str(e) or "does not exist anymore" in str(e):
            logger.warning(
                "Task token has expired, cannot send failure",
                extra={
                    "error": str(e),
                    "taskToken": task_token[:10] + "...",
                    "originalError": error,
                    "originalCause": cause,
                },
            )
            # Don't raise the exception for timeout errors
            return
        
        logger.error(
            "Failed to send task failure",
            extra={
                "error": str(e),
                "taskToken": task_token[:10] + "...",
            },
        )
        raise


@tracer.capture_method
def get_parts_from_manifest(manifest_key: str, start_part: int, end_part: int) -> list:
    """
    Get parts from the manifest file.
    
    Args:
        manifest_key: S3 key of the manifest file
        start_part: Start part number (1-based)
        end_part: End part number (1-based)
        
    Returns:
        List of parts
    """
    try:
        response = s3.get_object(
            Bucket=MEDIA_ASSETS_BUCKET,
            Key=manifest_key,
        )
        
        manifest = json.loads(response["Body"].read().decode("utf-8"))
        
        # Filter parts by part number
        filtered_parts = [
            part for part in manifest 
            if part["partNumber"] >= start_part and part["partNumber"] <= end_part
        ]
        
        logger.info(
            "Got parts from manifest",
            extra={
                "manifestKey": manifest_key,
                "startPart": start_part,
                "endPart": end_part,
                "numParts": len(filtered_parts),
            },
        )
        
        return filtered_parts
    
    except Exception as e:
        logger.error(
            "Failed to get parts from manifest",
            extra={
                "error": str(e),
                "manifestKey": manifest_key,
                "startPart": start_part,
                "endPart": end_part,
            },
        )
        raise


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for uploading a part.
    
    Args:
        event: Event containing part details
        context: Lambda context
        
    Returns:
        Dictionary containing the ETag of the uploaded part
    """
    # Check if this is an SQS event
    if "Records" in event and len(event["Records"]) > 0:
        # Process each SQS message
        for record in event["Records"]:
            try:
                # Parse the message body
                message_body = json.loads(record["body"])
                
                # Extract the task token and part details
                task_token = message_body.get("taskToken")
                part_info = message_body.get("part", {})
                
                if not task_token or not part_info:
                    logger.error(
                        "Missing task token or part info in SQS message",
                        extra={"messageId": record["messageId"]},
                    )
                    continue
                
                # Process the part
                try:
                    # Extract part details
                    job_id = part_info.get("jobId")
                    upload_id = part_info.get("uploadId")
                    s3_key = part_info.get("s3Key")
                    part_number = part_info.get("partNumber")
                    start_byte = part_info.get("startByte")
                    end_byte = part_info.get("endByte")
                    local_path = part_info.get("localPath")
                    
                    if not all([
                        job_id is not None,
                        upload_id is not None,
                        s3_key is not None,
                        part_number is not None,
                        start_byte is not None,
                        end_byte is not None,
                        local_path is not None
                    ]):
                        raise ValueError("Missing required parameters in part info")
                    
                    # Read the part from the file
                    part_data = read_part_from_file(local_path, start_byte, end_byte)
                    
                    # Upload the part to S3
                    result = upload_part(
                        MEDIA_ASSETS_BUCKET, s3_key, upload_id, part_number, part_data
                    )
                    
                    # Send task success to Step Functions
                    send_task_success(task_token, result)
                    
                    # Add metrics
                    metrics.add_metric(name="PartsUploaded", unit=MetricUnit.Count, value=1)
                
                except Exception as e:
                    logger.error(
                        f"Error processing part: {str(e)}",
                        exc_info=True,
                        extra={"messageId": record["messageId"]},
                    )
                    
                    # Send task failure to Step Functions
                    send_task_failure(
                        task_token,
                        "PartUploadError",
                        f"Failed to upload part: {str(e)}",
                    )
                    
                    # Add metrics
                    metrics.add_metric(name="PartUploadErrors", unit=MetricUnit.Count, value=1)
            
            except Exception as e:
                logger.error(
                    f"Error processing SQS message: {str(e)}",
                    exc_info=True,
                    extra={"messageId": record["messageId"]},
                )
        
        # Return success for SQS processing
        return {"status": "success"}
    
    # If not an SQS event, process as a direct invocation
    try:
        # Extract parameters from the event
        job_id = event.get("jobId")
        upload_id = event.get("uploadId")
        s3_key = event.get("s3Key")
        manifest_key = event.get("manifestKey")
        start_part = event.get("startPart")
        end_part = event.get("endPart")
        
        if not all([job_id, upload_id, s3_key, manifest_key, start_part, end_part]):
            raise ValueError("Missing required parameters in event")
        
        # Get parts from the manifest
        parts = get_parts_from_manifest(manifest_key, start_part, end_part)
        
        # Process each part
        results = []
        for part in parts:
            # Extract part details
            part_number = part["partNumber"]
            start_byte = part["startByte"]
            end_byte = part["endByte"]
            local_path = part["localPath"]
            
            # Read the part from the file
            part_data = read_part_from_file(local_path, start_byte, end_byte)
            
            # Upload the part to S3
            result = upload_part(
                MEDIA_ASSETS_BUCKET, s3_key, upload_id, part_number, part_data
            )
            
            # Add the result to the list
            results.append(result)
            
            # Update job progress
            update_job_progress(job_id, part_number, len(parts))
        
        # Add metrics
        metrics.add_metric(name="PartsUploaded", unit=MetricUnit.Count, value=len(results))
        
        return {
            "jobId": job_id,
            "uploadId": upload_id,
            "s3Key": s3_key,
            "parts": results,
        }
    
    except Exception as e:
        logger.error(
            f"Error uploading part: {str(e)}",
            exc_info=True,
        )
        
        # Add metrics
        metrics.add_metric(name="PartUploadErrors", unit=MetricUnit.Count, value=1)
        
        # Re-raise the exception to be handled by Step Functions
        raise