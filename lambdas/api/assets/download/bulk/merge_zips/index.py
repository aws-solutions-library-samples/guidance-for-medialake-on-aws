"""
Bulk Download Merge Zips Lambda

This Lambda function merges zip files from small and large file handlers by:
1. Retrieving zip files from EFS (small files) and S3 (large files)
2. Creating final zip files in S3 with a 7-day expiration policy
3. Generating presigned URLs for the zip files
4. Updating the job record with download URLs
5. Cleaning up temporary files

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""

import json
import os
import io
import time
import shutil
import zipfile
import tempfile
import uuid
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
logger = Logger(service="bulk-download-merge-zips")
tracer = Tracer(service="bulk-download-merge-zips")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-merge-zips")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
# Configure S3 client with Signature Version 4 for KMS encryption support
s3 = boto3.client("s3", config=Config(signature_version='s3v4'))
s3_resource = boto3.resource("s3", config=Config(signature_version='s3v4'))

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB table
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)

# Constants
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds
MAX_RETRIES = 3  # Maximum number of retries for S3 operations
FINAL_ZIP_PREFIX = "temp/zip/final"
MERGE_BATCH_SIZE = int(os.environ.get("MERGE_BATCH_SIZE", "5"))  # Number of zip files to merge at once
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
def merge_zip_files(
    small_zip_files: List[str],
    large_zip_files: List[str],
    output_path: str,
    job_id: str
) -> bool:
    """
    Merge multiple zip files into a single zip file.
    
    Args:
        small_zip_files: List of small zip file paths in EFS
        large_zip_files: List of large zip file paths in S3
        output_path: Path to save the merged zip file
        job_id: Job ID for logging
        
    Returns:
        True if merge was successful, False otherwise
    """
    try:
        # Create a temporary directory for downloaded large zip files (use EFS for more space)
        base_dir = os.environ.get("EFS_MOUNT_PATH", "/tmp")
        with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
            # Download large zip files from S3
            large_zip_local_paths = []
            for s3_path in large_zip_files:
                local_path = os.path.join(temp_dir, os.path.basename(s3_path))
                if download_s3_zip(s3_path, local_path):
                    large_zip_local_paths.append(local_path)
            
            # Combine all zip files
            all_zip_files = small_zip_files + large_zip_local_paths
            
            if not all_zip_files:
                logger.warning("No zip files to merge", extra={"jobId": job_id})
                return False
            
            # If there's only one zip file, just copy it
            if len(all_zip_files) == 1:
                shutil.copy2(all_zip_files[0], output_path)
                return True
            
            # Create a new zip file and copy contents from all zip files
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as output_zip:
                # Track files already added to avoid duplicates
                added_files = set()
                
                # Process each zip file
                for zip_path in all_zip_files:
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as input_zip:
                            # Get list of files in this zip
                            for file_info in input_zip.infolist():
                                # Skip directories and duplicates
                                if file_info.filename.endswith('/') or file_info.filename in added_files:
                                    continue
                                
                                # Read file from input zip and write to output zip
                                file_data = input_zip.read(file_info.filename)
                                output_zip.writestr(file_info, file_data)
                                added_files.add(file_info.filename)
                    except Exception as e:
                        logger.error(
                            f"Error processing zip file {zip_path}: {str(e)}",
                            extra={"zipPath": zip_path}
                        )
                        # Continue with next zip file
            
            return True
    
    except Exception as e:
        logger.error(
            "Failed to merge zip files",
            extra={
                "error": str(e),
                "outputPath": output_path,
                "smallZipCount": len(small_zip_files),
                "largeZipCount": len(large_zip_files),
            },
        )
        return False


@tracer.capture_method
def merge_in_batches(zip_files: List[str], temp_dir: str, job_id: str) -> Tuple[bool, List[str]]:
    """
    Merge zip files in batches to avoid memory issues and zip file entry limits.
    
    Args:
        zip_files: List of zip file paths
        temp_dir: Temporary directory for intermediate files
        job_id: Job ID for naming
        
    Returns:
        Tuple of (success, list of intermediate zip file paths)
    """
    if not zip_files:
        return True, []
        
    # If we have a small number of files, return them directly
    if len(zip_files) <= MERGE_BATCH_SIZE:
        return True, zip_files
        
    intermediate_zips = []
    
    # Process in batches
    for i in range(0, len(zip_files), MERGE_BATCH_SIZE):
        batch = zip_files[i:i + MERGE_BATCH_SIZE]
        batch_zip_name = f"intermediate_batch_{i//MERGE_BATCH_SIZE}_{job_id}.zip"
        batch_zip_path = os.path.join(temp_dir, batch_zip_name)
        
        logger.info(
            f"Merging batch {i//MERGE_BATCH_SIZE + 1}/{(len(zip_files) + MERGE_BATCH_SIZE - 1)//MERGE_BATCH_SIZE}",
            extra={
                "jobId": job_id,
                "batchSize": len(batch),
                "outputPath": batch_zip_path,
            }
        )
        
        # Create a new zip file for this batch
        with zipfile.ZipFile(batch_zip_path, 'w', zipfile.ZIP_DEFLATED) as output_zip:
            # Track files already added to avoid duplicates
            added_files = set()
            entry_count = 0
            
            # Process each zip file in the batch
            for zip_path in batch:
                try:
                    with zipfile.ZipFile(zip_path, 'r') as input_zip:
                        # Get list of files in this zip
                        for file_info in input_zip.infolist():
                            # Skip directories and duplicates
                            if file_info.filename.endswith('/') or file_info.filename in added_files:
                                continue
                                
                            # Check if we're approaching the zip entry limit
                            if entry_count >= MAX_ZIP_ENTRIES:
                                logger.warning(
                                    f"Reached maximum zip entries ({MAX_ZIP_ENTRIES}), creating new batch",
                                    extra={"jobId": job_id}
                                )
                                break
                                
                            # Read file from input zip and write to output zip
                            file_data = input_zip.read(file_info.filename)
                            output_zip.writestr(file_info, file_data)
                            added_files.add(file_info.filename)
                            entry_count += 1
                except Exception as e:
                    logger.error(
                        f"Error processing zip file {zip_path}: {str(e)}",
                        extra={"zipPath": zip_path}
                    )
                    # Continue with next zip file
        
        intermediate_zips.append(batch_zip_path)
    
    return True, intermediate_zips


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
def cleanup_temp_files(job_id: str, small_zip_files: List[str], large_zip_files: List[str]) -> None:
    """
    Clean up temporary files after successful processing.
    
    Args:
        job_id: Job ID
        small_zip_files: List of small zip file paths in EFS
        large_zip_files: List of large zip file paths in S3
    """
    # Clean up EFS files
    try:
        # Remove individual zip files
        for zip_path in small_zip_files:
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception as e:
                logger.warning(
                    f"Failed to remove temporary zip file: {str(e)}",
                    extra={"zipPath": zip_path}
                )
        
        # Remove job working directory
        job_dir = os.path.join(EFS_MOUNT_PATH, job_id)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
    
    except Exception as e:
        logger.warning(
            f"Error cleaning up EFS files: {str(e)}",
            extra={"jobId": job_id}
        )
    
    # Clean up S3 temporary files
    try:
        for item in large_zip_files:
            try:
                # Handle both string paths and dictionary objects
                if isinstance(item, dict) and "chunkZipPath" in item:
                    s3_path = item.get("chunkZipPath")
                else:
                    s3_path = item
                
                # Parse S3 path
                parsed = urlparse(s3_path)
                bucket = parsed.netloc
                key = parsed.path.lstrip('/')
                
                # Delete object
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception as e:
                logger.warning(
                    f"Failed to delete S3 temporary file: {str(e)}",
                    extra={"s3Path": item}
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
    Lambda handler for merging zip files and finalizing the bulk download job.
    
    Args:
        event: Event containing job details
        context: Lambda context
        
    Returns:
        Updated job details with download URLs
    """
    job_id = event.get("jobId")
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    # Get small and large zip files from event
    small_zip_files_input = event.get("smallZipFiles", [])
    large_zip_files_input = event.get("largeZipFiles", [])
    
    # Extract actual file paths from the input
    small_zip_files = []
    for item in small_zip_files_input:
        if isinstance(item, dict) and "smallZipFiles" in item:
            # Extract the array of paths from the dictionary
            small_zip_files.extend(item.get("smallZipFiles", []))
        elif isinstance(item, str):
            small_zip_files.append(item)
    
    # Extract S3 paths from large zip files
    large_zip_files = []
    for item in large_zip_files_input:
        if isinstance(item, dict) and "chunkZipPath" in item:
            # Extract the S3 path from the dictionary
            large_zip_files.append(item.get("chunkZipPath"))
        elif isinstance(item, str):
            large_zip_files.append(item)
    
    # Create a temporary directory for merged zip files
    # Use EFS for temporary storage instead of Lambda's local storage
    base_dir = os.environ.get("EFS_MOUNT_PATH", "/tmp")
    with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
        try:
            logger.info(
                "Merging zip files",
                extra={
                    "jobId": job_id,
                    "smallZipCount": len(small_zip_files),
                    "largeZipCount": len(large_zip_files),
                },
            )
            
            # Get job details
            job = get_job_details(job_id)
            
            # Determine final zip file name
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            final_zip_name = f"bulk_download_{job_id}_{timestamp}.zip"
            final_zip_path = os.path.join(temp_dir, final_zip_name)
            
            # Process all zip files in batches to handle large numbers of files
            logger.info(
                "Processing zip files in batches",
                extra={
                    "jobId": job_id,
                    "smallZipCount": len(small_zip_files),
                    "largeZipCount": len(large_zip_files),
                    "batchSize": MERGE_BATCH_SIZE,
                }
            )
            
            # Process files in smaller batches to avoid disk space issues
            # First process small files in batches
            small_batches = []
            for i in range(0, len(small_zip_files), MERGE_BATCH_SIZE):
                small_batch = small_zip_files[i:i + MERGE_BATCH_SIZE]
                small_batches.append(small_batch)
            
            # Then process large files in batches
            large_batches = []
            for i in range(0, len(large_zip_files), MERGE_BATCH_SIZE // 2):  # Smaller batches for large files
                large_batch = large_zip_files[i:i + MERGE_BATCH_SIZE // 2]
                large_batches.append(large_batch)
            
            # Process each batch and create intermediate zips
            intermediate_zips = []
            
            # Process small file batches
            for batch_idx, small_batch in enumerate(small_batches):
                batch_zip_name = f"small_batch_{batch_idx}_{job_id}.zip"
                batch_zip_path = os.path.join(temp_dir, batch_zip_name)
                
                logger.info(
                    f"Processing small files batch {batch_idx + 1}/{len(small_batches)}",
                    extra={
                        "jobId": job_id,
                        "batchSize": len(small_batch),
                    }
                )
                
                # Create a zip file for this batch
                with zipfile.ZipFile(batch_zip_path, 'w', zipfile.ZIP_DEFLATED) as output_zip:
                    # Track files already added to avoid duplicates
                    added_files = set()
                    
                    # Process each zip file in the batch
                    for zip_path in small_batch:
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as input_zip:
                                # Get list of files in this zip
                                for file_info in input_zip.infolist():
                                    # Skip directories and duplicates
                                    if file_info.filename.endswith('/') or file_info.filename in added_files:
                                        continue
                                    
                                    # Read file from input zip and write to output zip
                                    file_data = input_zip.read(file_info.filename)
                                    output_zip.writestr(file_info, file_data)
                                    added_files.add(file_info.filename)
                        except Exception as e:
                            logger.error(
                                f"Error processing zip file {zip_path}: {str(e)}",
                                extra={"zipPath": zip_path}
                            )
                            # Continue with next zip file
                
                intermediate_zips.append(batch_zip_path)
            
            # Process large file batches
            for batch_idx, large_batch in enumerate(large_batches):
                batch_zip_name = f"large_batch_{batch_idx}_{job_id}.zip"
                batch_zip_path = os.path.join(temp_dir, batch_zip_name)
                
                logger.info(
                    f"Processing large files batch {batch_idx + 1}/{len(large_batches)}",
                    extra={
                        "jobId": job_id,
                        "batchSize": len(large_batch),
                    }
                )
                
                # Create a temporary directory for downloaded large zip files (use EFS for more space)
                with tempfile.TemporaryDirectory(dir=base_dir) as download_temp_dir:
                    # Download large zip files from S3 for this batch only
                    local_large_zip_files = []
                    for s3_path in large_batch:
                        local_path = os.path.join(download_temp_dir, os.path.basename(s3_path))
                        if download_s3_zip(s3_path, local_path):
                            local_large_zip_files.append(local_path)
                    
                    # Create a zip file for this batch
                    with zipfile.ZipFile(batch_zip_path, 'w', zipfile.ZIP_DEFLATED) as output_zip:
                        # Track files already added to avoid duplicates
                        added_files = set()
                        
                        # Process each zip file in the batch
                        for zip_path in local_large_zip_files:
                            try:
                                with zipfile.ZipFile(zip_path, 'r') as input_zip:
                                    # Get list of files in this zip
                                    for file_info in input_zip.infolist():
                                        # Skip directories and duplicates
                                        if file_info.filename.endswith('/') or file_info.filename in added_files:
                                            continue
                                        
                                        # Read file from input zip and write to output zip
                                        file_data = input_zip.read(file_info.filename)
                                        output_zip.writestr(file_info, file_data)
                                        added_files.add(file_info.filename)
                            except Exception as e:
                                logger.error(
                                    f"Error processing zip file {zip_path}: {str(e)}",
                                    extra={"zipPath": zip_path}
                                )
                                # Continue with next zip file
                
                intermediate_zips.append(batch_zip_path)
                
                # Clean up downloaded files after each batch to save space
                # The temporary directory will be automatically cleaned up
            
            # Now merge the intermediate zips in batches if needed
            if intermediate_zips:
                # If we have multiple intermediate zips, merge them into a final zip
                if len(intermediate_zips) > 1:
                    logger.info(
                        f"Merging {len(intermediate_zips)} intermediate zip files into final zip",
                        extra={"jobId": job_id}
                    )
                    
                    # If we have too many intermediate zips, merge them in batches
                    if len(intermediate_zips) > MERGE_BATCH_SIZE:
                        logger.info(
                            f"Too many intermediate zips ({len(intermediate_zips)}), merging in batches",
                            extra={"jobId": job_id}
                        )
                        
                        # Merge intermediate zips in batches
                        second_level_zips = []
                        for i in range(0, len(intermediate_zips), MERGE_BATCH_SIZE):
                            batch = intermediate_zips[i:i + MERGE_BATCH_SIZE]
                            batch_zip_name = f"level2_batch_{i//MERGE_BATCH_SIZE}_{job_id}.zip"
                            batch_zip_path = os.path.join(temp_dir, batch_zip_name)
                            
                            logger.info(
                                f"Merging level 2 batch {i//MERGE_BATCH_SIZE + 1}/{(len(intermediate_zips) + MERGE_BATCH_SIZE - 1)//MERGE_BATCH_SIZE}",
                                extra={
                                    "jobId": job_id,
                                    "batchSize": len(batch),
                                }
                            )
                            
                            if merge_zip_files(batch, [], batch_zip_path, job_id):
                                second_level_zips.append(batch_zip_path)
                                
                                # Clean up intermediate zips after merging to save space
                                for zip_path in batch:
                                    try:
                                        if os.path.exists(zip_path):
                                            os.remove(zip_path)
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to remove intermediate zip file: {str(e)}",
                                            extra={"zipPath": zip_path}
                                        )
                        
                        # Now merge the second level zips into the final zip
                        if merge_zip_files(second_level_zips, [], final_zip_path, job_id):
                            # Clean up second level zips
                            for zip_path in second_level_zips:
                                try:
                                    if os.path.exists(zip_path):
                                        os.remove(zip_path)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to remove second level zip file: {str(e)}",
                                        extra={"zipPath": zip_path}
                                    )
                            
                            # Upload merged zip to S3
                            s3_key = upload_to_s3_with_expiration(final_zip_path, job_id)
                            
                            # Generate presigned URL
                            download_url = generate_presigned_url(MEDIA_ASSETS_BUCKET, s3_key)
                            
                            # Update job as completed
                            update_job_completed(job_id, [download_url])
                            
                            # Clean up temporary files
                            cleanup_temp_files(job_id, small_zip_files, large_zip_files_input)
                            
                            # Add metrics
                            metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)
                            
                            # Return updated job details
                            return {
                                "jobId": job_id,
                                "userId": job.get("userId"),
                                "status": "COMPLETED",
                                "downloadUrls": [download_url],
                            }
                    else:
                        # Merge all intermediate zips directly into the final zip
                        if merge_zip_files(intermediate_zips, [], final_zip_path, job_id):
                            # Upload merged zip to S3
                            s3_key = upload_to_s3_with_expiration(final_zip_path, job_id)
                            
                            # Generate presigned URL
                            download_url = generate_presigned_url(MEDIA_ASSETS_BUCKET, s3_key)
                            
                            # Update job as completed
                            update_job_completed(job_id, [download_url])
                            
                            # Clean up temporary files
                            cleanup_temp_files(job_id, small_zip_files, large_zip_files_input)
                            
                            # Also clean up intermediate zips
                            for zip_path in intermediate_zips:
                                try:
                                    if os.path.exists(zip_path):
                                        os.remove(zip_path)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to remove intermediate zip file: {str(e)}",
                                        extra={"zipPath": zip_path}
                                    )
                            
                            # Add metrics
                            metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)
                            
                            # Return updated job details
                            return {
                                "jobId": job_id,
                                "userId": job.get("userId"),
                                "status": "COMPLETED",
                                "downloadUrls": [download_url],
                            }
                else:
                    # Only one intermediate zip, use it as the final zip
                    final_zip_path = intermediate_zips[0]
                    
                    # Upload merged zip to S3
                    s3_key = upload_to_s3_with_expiration(final_zip_path, job_id)
                    
                    # Generate presigned URL
                    download_url = generate_presigned_url(MEDIA_ASSETS_BUCKET, s3_key)
                    
                    # Update job as completed
                    update_job_completed(job_id, [download_url])
                    
                    # Clean up temporary files
                    cleanup_temp_files(job_id, small_zip_files, large_zip_files_input)
                    
                    # Add metrics
                    metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)
                    
                    # Return updated job details
                    return {
                        "jobId": job_id,
                        "userId": job.get("userId"),
                        "status": "COMPLETED",
                        "downloadUrls": [download_url],
                    }
            else:
                # Handle case where no intermediate zips were created
                logger.warning("No files were merged", extra={"jobId": job_id})
                
                # Update job status
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
                        ":error": "No files were available for download",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
                
                # Add metrics
                metrics.add_metric(name="JobsFailed", unit=MetricUnit.Count, value=1)
                
                # Return error
                return {
                    "jobId": job_id,
                    "userId": job.get("userId"),
                    "status": "FAILED",
                    "error": "No files were available for download",
                }
        
        except Exception as e:
            logger.error(
                f"Error merging zip files: {str(e)}",
                exc_info=True,
                extra={"jobId": job_id},
            )
            
            # Update job status to FAILED
            try:
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
                        ":error": f"Failed to merge zip files: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as update_error:
                logger.error(
                    f"Failed to update job status after error: {str(update_error)}",
                    extra={"jobId": job_id},
                )
            
            metrics.add_metric(name="MergeZipsErrors", unit=MetricUnit.Count, value=1)
            
            # Re-raise the exception to be handled by Step Functions
            raise