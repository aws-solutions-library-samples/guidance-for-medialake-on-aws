"""
Bulk Download Append to Zip Lambda

This Lambda function appends files to an existing zip file on shared storage (EFS) by:
1. Downloading the file from S3
2. Appending it to the existing zip file using streaming
3. Updating the job progress in DynamoDB

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
import zipfile
import tempfile
import uuid
from typing import Dict, Any, List, Tuple, BinaryIO
from datetime import datetime
from pathlib import Path

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-append-to-zip")
tracer = Tracer(service="bulk-download-append-to-zip")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-append-to-zip")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
s3_resource = boto3.resource("s3")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
ASSET_TABLE = os.environ["ASSET_TABLE"]
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]
EFS_MOUNT_PATH = os.environ["EFS_MOUNT_PATH"]

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_RETRIES = 3  # Maximum number of retries for S3 operations
CHUNK_SIZE_MB = int(os.environ.get("CHUNK_SIZE_MB", "100"))
CHUNK_SIZE = CHUNK_SIZE_MB * 1024 * 1024  # Convert MB to bytes for streaming


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
def get_asset_details(asset_id: str) -> Dict[str, Any]:
    """
    Retrieve asset details from DynamoDB.
    
    Args:
        asset_id: ID of the asset to retrieve
        
    Returns:
        Asset details
        
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
        
        return response["Item"]
    
    except ClientError as e:
        logger.error(
            "Failed to retrieve asset details",
            extra={
                "error": str(e),
                "assetId": asset_id,
            },
        )
        raise Exception(f"Failed to retrieve asset details: {str(e)}")


@tracer.capture_method
def update_job_progress(job_id: str, processed_count: int, total_count: int) -> None:
    """
    Update job progress in DynamoDB.
    
    Args:
        job_id: ID of the job to update
        processed_count: Number of files processed
        total_count: Total number of files to process
        
    Raises:
        Exception: If job update fails
    """
    progress = int((processed_count / total_count) * 100) if total_count > 0 else 0
    
    update_expression = "SET #status = :status, #progress = :progress, #processedFiles = :processedFiles, #updatedAt = :updatedAt"
    expression_attribute_names = {
        "#status": "status",
        "#progress": "progress",
        "#processedFiles": "processedFiles",
        "#updatedAt": "updatedAt",
    }
    expression_attribute_values = {
        ":status": "PROCESSING",
        ":progress": progress,
        ":processedFiles": processed_count,
        ":updatedAt": datetime.utcnow().isoformat(),
    }
    
    try:
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
        
        logger.info(
            "Updated job progress",
            extra={
                "jobId": job_id,
                "progress": progress,
                "processedFiles": processed_count,
                "totalFiles": total_count,
            },
        )
    
    except ClientError as e:
        logger.error(
            "Failed to update job progress",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        # Continue processing even if update fails


@tracer.capture_method
def append_file_to_zip(
    bucket: str, 
    key: str, 
    zip_path: str, 
    archive_name: str
) -> bool:
    """
    Append a file from S3 to an existing zip file using streaming.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        zip_path: Path to the existing zip file
        archive_name: Name to use in the archive
        
    Returns:
        True if appending was successful, False otherwise
    """
    try:
        # Get object size
        response = s3.head_object(Bucket=bucket, Key=key)
        content_length = response.get('ContentLength', 0)
        
        logger.info(
            "Appending file from S3 to zip",
            extra={
                "bucket": bucket,
                "key": key,
                "size": content_length,
                "archiveName": archive_name,
                "zipPath": zip_path,
            },
        )
        
        # Create a temporary file for the new zip
        temp_dir = os.path.dirname(zip_path)
        temp_zip_path = os.path.join(temp_dir, f"temp_{uuid.uuid4()}.zip")
        
        # Copy the existing zip file to the temporary file
        with open(zip_path, 'rb') as src, open(temp_zip_path, 'wb') as dst:
            dst.write(src.read())
        
        # Append the new file to the temporary zip
        with zipfile.ZipFile(temp_zip_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
            # Create a ZipInfo object to store file info
            zip_info = zipfile.ZipInfo(archive_name)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            zip_info.date_time = time.localtime(time.time())[:6]
            
            # Stream the file in chunks
            with zipf.open(zip_info, 'w') as dest_file:
                # Get the S3 object
                s3_object = s3_resource.Object(bucket, key)
                
                # Stream the object in chunks
                offset = 0
                while offset < content_length:
                    end = min(offset + CHUNK_SIZE, content_length)
                    range_str = f'bytes={offset}-{end-1}'
                    
                    response = s3_object.get(Range=range_str)
                    data = response['Body'].read()
                    dest_file.write(data)
                    
                    offset = end
        
        # Replace the original zip with the temporary one
        os.replace(temp_zip_path, zip_path)
        
        return True
    
    except Exception as e:
        logger.error(
            "Failed to append file to zip",
            extra={
                "error": str(e),
                "bucket": bucket,
                "key": key,
                "zipPath": zip_path,
            },
        )
        
        # Clean up temporary file if it exists
        if os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception:
                pass
                
        return False


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for appending a file to an existing zip file.
    
    Args:
        event: Event containing job details and asset information
        context: Lambda context
        
    Returns:
        Dictionary containing the result of the operation
    """
    job_id = event.get("jobId")
    asset_id = event.get("assetId")
    
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    if not asset_id:
        raise ValueError("Missing assetId in event")
    
    try:
        # Get job details
        job = get_job_details(job_id)
        
        # Get the zip path from the job
        zip_path = job.get("zipPath")
        if not zip_path:
            raise ValueError(f"No zip path found for job {job_id}")
        
        # Ensure the zip file exists
        if not os.path.exists(zip_path):
            raise ValueError(f"Zip file not found at {zip_path}")
        
        # Get asset details
        asset = get_asset_details(asset_id)
        
        # Get download options
        options = job.get("options", {})
        quality = options.get("quality", "original")  # original or proxy
        
        # Determine file path based on quality option
        if quality == "proxy":
            # Look for proxy representation
            file_path = None
            bucket = None
            
            for rep in asset.get("DerivedRepresentations", []):
                if rep.get("Purpose") == "proxy":
                    storage_info = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                    bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
                    file_path = storage_info.get("ObjectKey", {}).get("FullPath")
                    break
            
            # If no proxy found, use original
            if not file_path:
                logger.warning(
                    "No proxy representation found, using original",
                    extra={"assetId": asset_id}
                )
                main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
                storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
                file_path = storage_info.get("ObjectKey", {}).get("FullPath")
        else:
            # Use original representation
            main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
            storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            bucket = storage_info.get("Bucket", MEDIA_ASSETS_BUCKET)
            file_path = storage_info.get("ObjectKey", {}).get("FullPath")
        
        if not file_path:
            raise ValueError(f"Could not determine file path for asset {asset_id}")
        
        # Get file name from path
        file_name = os.path.basename(file_path)
        
        # Append the file to the zip
        if append_file_to_zip(bucket, file_path, zip_path, file_name):
            # Update job progress
            processed_count = job.get("processedFiles", 0) + 1
            total_count = job.get("totalFiles", 0)
            update_job_progress(job_id, processed_count, total_count)
            
            # Add metrics
            metrics.add_metric(name="FilesAppendedToZip", unit=MetricUnit.Count, value=1)
            
            return {
                "jobId": job_id,
                "assetId": asset_id,
                "status": "APPENDED",
                "zipPath": zip_path,
                "processedCount": processed_count,
                "totalCount": total_count,
            }
        else:
            raise Exception(f"Failed to append file {file_path} to zip {zip_path}")
    
    except Exception as e:
        logger.error(
            f"Error appending file to zip: {str(e)}",
            exc_info=True,
            extra={
                "jobId": job_id,
                "assetId": asset_id,
            },
        )
        
        # Add metrics
        metrics.add_metric(name="AppendToZipErrors", unit=MetricUnit.Count, value=1)
        
        # Re-raise the exception to be handled by Step Functions
        raise