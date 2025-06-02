"""
Bulk Download Final Merge Lambda

This Lambda function merges the results of the batch merge Map state by:
1. Downloading the merged batch zip files from S3
2. Merging them into a single final zip file
3. Uploading the final zip file to S3
4. Generating a presigned URL for the final zip file
5. Updating the job record with the download URL
"""

import json
import os
import io
import time
import shutil
import zipfile
import tempfile
import uuid
import subprocess
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from botocore.config import Config

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-final-merge")
tracer = Tracer(service="bulk-download-final-merge")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-final-merge")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
# Configure S3 client with Signature Version 4 for KMS encryption support
s3 = boto3.client("s3", config=Config(signature_version='s3v4'))
s3_resource = boto3.resource("s3", config=Config(signature_version='s3v4'))

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]
FILE_MERGE_TIMEOUT = int(os.environ.get("FILE_MERGE_TIMEOUT", "120"))  # 2 minute timeout per file merge

# Constants
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds
FINAL_ZIP_PREFIX = "temp/zip/final"
MAX_ZIP_ENTRIES = 65000  # Slightly below the 65,535 limit for safety


@tracer.capture_method
def get_job_details(job_id: str) -> Dict[str, Any]:
    """
    Retrieve job details from DynamoDB.
    
    Args:
        job_id: ID of the job to retrieve
        
    Returns:
        Job details
        
    Raises:
        Exception: If job retrieval fails
    """
    try:
        bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
        response = bulk_download_table.get_item(
            Key={"jobId": job_id},
            ConsistentRead=True,
        )
        
        if "Item" not in response:
            raise Exception(f"Job {job_id} not found")
        
        return response["Item"]
    
    except ClientError as e:
        logger.error(
            "Failed to retrieve job details",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to retrieve job details: {str(e)}")


@tracer.capture_method
def download_s3_zip(s3_path: str, local_path: str) -> bool:
    """
    Download a zip file from S3 to local storage.
    
    Args:
        s3_path: S3 path in the format s3://bucket/key
        local_path: Local path to save the file
        
    Returns:
        True if download was successful, False otherwise
    """
    try:
        # Parse S3 path
        parsed = urlparse(s3_path)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        
        # Download file
        s3.download_file(bucket, key, local_path)
        return True
    
    except Exception as e:
        logger.error(
            "Failed to download zip from S3",
            extra={
                "error": str(e),
                "s3Path": s3_path,
                "localPath": local_path,
            },
        )
        return False


@tracer.capture_method
def upload_to_s3_with_expiration(local_path: str, job_id: str) -> str:
    """
    Upload a file to S3 with a 7-day expiration policy.
    
    Args:
        local_path: Local path of the file to upload
        job_id: Job ID for naming
        
    Returns:
        S3 key of the uploaded file
    """
    try:
        # Generate a unique key
        file_name = os.path.basename(local_path)
        s3_key = f"{FINAL_ZIP_PREFIX}/{job_id}/{file_name}"
        
        # Upload file
        s3.upload_file(
            local_path,
            MEDIA_ASSETS_BUCKET,
            s3_key,
            ExtraArgs={
                'Metadata': {
                    'job-id': job_id,
                    'expiration': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                }
            }
        )
        
        return s3_key
    
    except Exception as e:
        logger.error(
            "Failed to upload file to S3",
            extra={
                "error": str(e),
                "localPath": local_path,
                "jobId": job_id,
            },
        )
        raise


@tracer.capture_method
def generate_presigned_url(bucket: str, key: str) -> str:
    """
    Generate a presigned URL for an S3 object.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        Presigned URL
    """
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': f'attachment; filename="{os.path.basename(key)}"',
            },
            ExpiresIn=MAX_PRESIGNED_URL_EXPIRATION,
        )
        
        return url
    
    except Exception as e:
        logger.error(
            "Failed to generate presigned URL",
            extra={
                "error": str(e),
                "bucket": bucket,
                "key": key,
            },
        )
        raise


@tracer.capture_method
def update_job_completed(job_id: str, download_urls: List[str]) -> None:
    """
    Update the job record with download URLs and mark as completed.
    
    Args:
        job_id: ID of the job to update
        download_urls: List of presigned download URLs
        
    Raises:
        Exception: If job update fails
    """
    try:
        # Calculate expiration time (7 days from now)
        expiration_time = datetime.utcnow() + timedelta(days=7)
        
        bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=(
                "SET #status = :status, "
                "#downloadUrls = :downloadUrls, "
                "#expiresAt = :expiresAt, "
                "#progress = :progress, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#downloadUrls": "downloadUrls",
                "#expiresAt": "expiresAt",
                "#progress": "progress",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "COMPLETED",
                ":downloadUrls": download_urls,
                ":expiresAt": int(expiration_time.timestamp()),
                ":progress": 100,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        logger.info(
            "Updated job as completed",
            extra={
                "jobId": job_id,
                "urlCount": len(download_urls),
                "expiresAt": expiration_time.isoformat(),
            },
        )
    
    except ClientError as e:
        logger.error(
            "Failed to update job as completed",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job as completed: {str(e)}")


@tracer.capture_method
def merge_zip_files(zip_files: List[str], output_path: str, job_id: str) -> bool:
    """
    Merge multiple zip files into a single zip file.
    
    Args:
        zip_files: List of zip file paths
        output_path: Path to save the merged zip file
        job_id: Job ID for logging
        
    Returns:
        True if merge was successful, False otherwise
    """
    try:
        # If there's only one zip file, just copy it
        if len(zip_files) == 1:
            shutil.copy2(zip_files[0], output_path)
            return True
        
        # Use the zipmerge binary from the Lambda layer
        zipmerge_path = "/opt/bin/zipmerge"
        
        # Ensure zipmerge binary exists
        if not os.path.exists(zipmerge_path):
            logger.error(
                "Zipmerge binary not found",
                extra={"zipmerge_path": zipmerge_path}
            )
            return False
        
        # Create a valid empty zip file as the base
        with zipfile.ZipFile(output_path, 'w') as _:
            pass
        
        # Process each zip file one at a time
        for i, zip_path in enumerate(zip_files):
            # Build the zipmerge command to merge just this one file
            cmd = [zipmerge_path, output_path, zip_path]
            
            # Log the command
            logger.info(
                f"Running zipmerge command for file {i+1}/{len(zip_files)}",
                extra={
                    "jobId": job_id,
                    "command": " ".join(cmd),
                    "zipFile": zip_path,
                }
            )
            
            # Run the zipmerge command with timeout
            start_time = time.time()
            try:
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=FILE_MERGE_TIMEOUT,  # Add timeout to prevent hanging
                )
                end_time = time.time()
                timed_out = False
            except subprocess.TimeoutExpired as e:
                end_time = time.time()
                timed_out = True
                logger.warning(
                    f"Zipmerge timed out after {FILE_MERGE_TIMEOUT} seconds for file {i+1}/{len(zip_files)}",
                    extra={
                        "jobId": job_id,
                        "zipFile": zip_path,
                        "timeout": FILE_MERGE_TIMEOUT,
                    }
                )
                # Skip this file and continue with the next one
                continue
            
            # Check if the command was successful (only if not timed out)
            if not timed_out and process.returncode == 0:
                logger.info(
                    f"Zipmerge completed successfully in {end_time - start_time:.2f} seconds for file {i+1}/{len(zip_files)}",
                    extra={
                        "jobId": job_id,
                        "zipFile": zip_path,
                        "currentSize": os.path.getsize(output_path),
                    }
                )
                
                # Delete the source zip file after successful merge to save space
                try:
                    os.remove(zip_path)
                    logger.info(f"Deleted source zip file after merge: {zip_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to delete source zip file: {str(e)}",
                        extra={"zipPath": zip_path}
                    )
            elif not timed_out:  # Only log error if not timed out (timeout is already logged)
                logger.error(
                    f"Zipmerge failed with return code {process.returncode} for file {i+1}/{len(zip_files)}",
                    extra={
                        "jobId": job_id,
                        "zipFile": zip_path,
                        "stdout": process.stdout.decode('utf-8', errors='replace'),
                        "stderr": process.stderr.decode('utf-8', errors='replace'),
                    }
                )
                # Continue with next file instead of failing completely
        
        # Check if the final zip file exists and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(
                f"Merge completed successfully",
                extra={
                    "jobId": job_id,
                    "zipCount": len(zip_files),
                    "finalSize": os.path.getsize(output_path),
                }
            )
            return True
        else:
            logger.error(
                "Merge failed - output file is empty or missing",
                extra={
                    "jobId": job_id,
                    "outputPath": output_path,
                }
            )
            return False
    
    except Exception as e:
        logger.error(
            "Failed to merge zip files",
            extra={
                "error": str(e),
                "outputPath": output_path,
                "zipCount": len(zip_files),
            },
        )
        return False


@tracer.capture_method
def cleanup_s3_temp_files(job_id: str, s3_paths: List[str]) -> None:
    """
    Clean up temporary files in S3.
    
    Args:
        job_id: Job ID
        s3_paths: List of S3 paths to delete
    """
    try:
        for s3_path in s3_paths:
            try:
                # Parse S3 path
                parsed = urlparse(s3_path)
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                
                # Delete object
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception as e:
                logger.warning(
                    f"Failed to delete S3 temporary file: {str(e)}",
                    extra={"s3Path": s3_path}
                )
    
    except Exception as e:
        logger.warning(
            f"Error cleaning up S3 files: {str(e)}",
            extra={"jobId": job_id}
        )


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for merging the results of the batch merge Map state.
    
    Args:
        event: Event containing job details and batch merge results
        context: Lambda context
        
    Returns:
        Dictionary containing the download URL for the final zip file
    """
    job_id = event.get("jobId")
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    # Extract merged zip paths from the batch merge results
    batch_results = event.get("batchResults", [])
    merged_zip_paths = []
    
    for result in batch_results:
        if isinstance(result, dict) and result.get("status") == "COMPLETED":
            merged_zip_path = result.get("mergedZipPath")
            if merged_zip_path:
                merged_zip_paths.append(merged_zip_path)
    
    if not merged_zip_paths:
        logger.warning("No merged zip files to process", extra={"jobId": job_id})
        
        # Update job status to FAILED
        bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
            ExpressionAttributeNames={
                "#status": "status",
                "#error": "error",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "FAILED",
                ":error": "No merged zip files to process",
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        return {
            "jobId": job_id,
            "status": "FAILED",
            "error": "No merged zip files to process",
        }
    
    # Use EFS for temporary storage
    base_dir = os.environ.get("EFS_MOUNT_PATH", "/tmp")
    with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
        try:
            logger.info(
                "Merging final zip files",
                extra={
                    "jobId": job_id,
                    "zipCount": len(merged_zip_paths),
                },
            )
            
            # Get job details
            job = get_job_details(job_id)
            
            # Determine final zip file name
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            final_zip_name = f"bulk_download_{job_id}_{timestamp}.zip"
            final_zip_path = os.path.join(temp_dir, final_zip_name)
            
            # Download merged zip files from S3
            local_zip_files = []
            for s3_path in merged_zip_paths:
                local_path = os.path.join(temp_dir, os.path.basename(s3_path))
                if download_s3_zip(s3_path, local_path):
                    local_zip_files.append(local_path)
            
            if not local_zip_files:
                logger.warning(
                    "Failed to download any merged zip files",
                    extra={"jobId": job_id}
                )
                
                # Update job status to FAILED
                bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
                bulk_download_table.update_item(
                    Key={"jobId": job_id},
                    UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                        "#updatedAt": "updatedAt",
                    },
                    ExpressionAttributeValues={
                        ":status": "FAILED",
                        ":error": "Failed to download any merged zip files",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
                
                return {
                    "jobId": job_id,
                    "status": "FAILED",
                    "error": "Failed to download any merged zip files",
                }
            
            # Merge zip files
            if merge_zip_files(local_zip_files, final_zip_path, job_id):
                # Upload merged zip to S3
                s3_key = upload_to_s3_with_expiration(final_zip_path, job_id)
                
                # Generate presigned URL
                download_url = generate_presigned_url(MEDIA_ASSETS_BUCKET, s3_key)
                
                # Update job as completed
                update_job_completed(job_id, [download_url])
                
                # Clean up temporary files in S3
                cleanup_s3_temp_files(job_id, merged_zip_paths)
                
                # Add metrics
                metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)
                
                return {
                    "jobId": job_id,
                    "userId": job.get("userId"),
                    "status": "COMPLETED",
                    "downloadUrls": [download_url],
                }
            else:
                logger.error(
                    "Failed to merge final zip files",
                    extra={"jobId": job_id}
                )
                
                # Update job status to FAILED
                bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
                bulk_download_table.update_item(
                    Key={"jobId": job_id},
                    UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                        "#updatedAt": "updatedAt",
                    },
                    ExpressionAttributeValues={
                        ":status": "FAILED",
                        ":error": "Failed to merge final zip files",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
                
                return {
                    "jobId": job_id,
                    "status": "FAILED",
                    "error": "Failed to merge final zip files",
                }
        
        except Exception as e:
            logger.error(
                f"Error merging final zip files: {str(e)}",
                exc_info=True,
                extra={"jobId": job_id},
            )
            
            # Update job status to FAILED
            try:
                bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
                bulk_download_table.update_item(
                    Key={"jobId": job_id},
                    UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                        "#updatedAt": "updatedAt",
                    },
                    ExpressionAttributeValues={
                        ":status": "FAILED",
                        ":error": f"Failed to merge final zip files: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as update_error:
                logger.error(
                    f"Failed to update job status after error: {str(update_error)}",
                    extra={"jobId": job_id},
                )
            
            # Add metrics
            metrics.add_metric(name="FinalMergeErrors", unit=MetricUnit.Count, value=1)
            
            # Re-raise the exception to be handled by Step Functions
            raise