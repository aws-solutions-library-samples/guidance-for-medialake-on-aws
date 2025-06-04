"""
Bulk Download Merge Batch Lambda

This Lambda function merges a batch of zip files by:
1. Downloading zip files from S3
2. Merging them into a single zip file
3. Uploading the merged zip file to S3
4. Returning the S3 path of the merged zip file

This function is designed to be used in a Map state in Step Functions.
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
logger = Logger(service="bulk-download-merge-batch")
tracer = Tracer(service="bulk-download-merge-batch")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-merge-batch")

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
MAX_ZIP_ENTRIES = 65000  # Slightly below the 65,535 limit for safety
TEMP_ZIP_PREFIX = "temp/zip/batches"


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
def upload_to_s3(local_path: str, job_id: str, batch_id: str) -> str:
    """
    Upload a file to S3.
    
    Args:
        local_path: Local path of the file to upload
        job_id: Job ID for naming
        batch_id: Batch ID for naming
        
    Returns:
        S3 path of the uploaded file
    """
    try:
        # Generate a unique key
        file_name = os.path.basename(local_path)
        s3_key = f"{TEMP_ZIP_PREFIX}/{job_id}/batch_{batch_id}_{file_name}"
        
        # Upload file
        s3.upload_file(
            local_path,
            MEDIA_ASSETS_BUCKET,
            s3_key,
            ExtraArgs={
                'Metadata': {
                    'job-id': job_id,
                    'batch-id': batch_id,
                }
            }
        )
        
        return f"s3://{MEDIA_ASSETS_BUCKET}/{s3_key}"
    
    except Exception as e:
        logger.error(
            "Failed to upload file to S3",
            extra={
                "error": str(e),
                "localPath": local_path,
                "jobId": job_id,
                "batchId": batch_id,
            },
        )
        raise


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


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for merging a batch of zip files.
    
    Args:
        event: Event containing job details and batch information
        context: Lambda context
        
    Returns:
        Dictionary containing the S3 path of the merged zip file
    """
    job_id = event.get("jobId")
    batch_id = event.get("batchId")
    zip_files = event.get("zipFiles", [])
    
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    if not batch_id:
        raise ValueError("Missing batchId in event")
    
    if not zip_files:
        logger.warning("No zip files to merge", extra={"jobId": job_id, "batchId": batch_id})
        return {
            "jobId": job_id,
            "batchId": batch_id,
            "status": "EMPTY",
            "mergedZipPath": None,
        }
    
    # Use EFS for temporary storage
    base_dir = os.environ.get("EFS_MOUNT_PATH", "/tmp")
    with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
        try:
            logger.info(
                "Merging zip files",
                extra={
                    "jobId": job_id,
                    "batchId": batch_id,
                    "zipCount": len(zip_files),
                },
            )
            
            # Process both S3 and local EFS paths
            local_zip_files = []
            
            # Log the types of files we're processing
            s3_paths = [p for p in zip_files if p.startswith("s3://")]
            local_paths = [p for p in zip_files if not p.startswith("s3://")]
            
            logger.info(
                f"Processing {len(s3_paths)} S3 paths and {len(local_paths)} local paths",
                extra={
                    "jobId": job_id,
                    "batchId": batch_id,
                    "s3Count": len(s3_paths),
                    "localCount": len(local_paths),
                }
            )
            
            # Handle S3 paths - download to temp directory
            for s3_path in s3_paths:
                local_path = os.path.join(temp_dir, os.path.basename(s3_path))
                if download_s3_zip(s3_path, local_path):
                    local_zip_files.append(local_path)
            
            # Handle local EFS paths - copy to temp directory if needed
            for local_path in local_paths:
                if os.path.exists(local_path):
                    # If the file is already in the temp directory, use it directly
                    if os.path.dirname(local_path) == temp_dir:
                        local_zip_files.append(local_path)
                    else:
                        # Otherwise, copy it to the temp directory
                        temp_path = os.path.join(temp_dir, os.path.basename(local_path))
                        try:
                            shutil.copy2(local_path, temp_path)
                            local_zip_files.append(temp_path)
                        except Exception as e:
                            logger.error(
                                f"Failed to copy local file: {str(e)}",
                                extra={"localPath": local_path, "tempPath": temp_path}
                            )
                else:
                    logger.warning(f"Local file does not exist: {local_path}")
            
            if not local_zip_files:
                logger.warning(
                    "Failed to process any zip files",
                    extra={"jobId": job_id, "batchId": batch_id}
                )
                return {
                    "jobId": job_id,
                    "batchId": batch_id,
                    "status": "FAILED",
                    "error": "Failed to process any zip files",
                }
            
            # Merge zip files
            merged_zip_name = f"merged_batch_{batch_id}_{job_id}.zip"
            merged_zip_path = os.path.join(temp_dir, merged_zip_name)
            
            if merge_zip_files(local_zip_files, merged_zip_path, job_id):
                # Upload merged zip to S3
                s3_path = upload_to_s3(merged_zip_path, job_id, batch_id)
                
                # Add metrics
                metrics.add_metric(name="BatchesMerged", unit=MetricUnit.Count, value=1)
                
                return {
                    "jobId": job_id,
                    "batchId": batch_id,
                    "status": "COMPLETED",
                    "mergedZipPath": s3_path,
                }
            else:
                logger.error(
                    "Failed to merge zip files",
                    extra={"jobId": job_id, "batchId": batch_id}
                )
                return {
                    "jobId": job_id,
                    "batchId": batch_id,
                    "status": "FAILED",
                    "error": "Failed to merge zip files",
                }
        
        except Exception as e:
            logger.error(
                f"Error merging zip files: {str(e)}",
                exc_info=True,
                extra={"jobId": job_id, "batchId": batch_id},
            )
            
            # Add metrics
            metrics.add_metric(name="BatchMergeErrors", unit=MetricUnit.Count, value=1)
            
            return {
                "jobId": job_id,
                "batchId": batch_id,
                "status": "FAILED",
                "error": str(e),
            }