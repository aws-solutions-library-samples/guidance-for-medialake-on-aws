"""
Bulk Download Handle Individual Lambda

This Lambda function handles files individually by:
1. Retrieving asset details from DynamoDB
2. Generating presigned URLs for each file
3. Updating the job record with the download URLs

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling and retries
- Metrics and monitoring
"""
import unicodedata
import json
import os
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from botocore.config import Config

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-handle-individual")
tracer = Tracer(service="bulk-download-handle-individual")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-handle-individual")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3", config=Config(signature_version='s3v4'))

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
ASSET_TABLE = os.environ["ASSET_TABLE"]

# Initialize DynamoDB tables
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)
asset_table = dynamodb.Table(ASSET_TABLE)

# Constants
MAX_PRESIGNED_URL_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds
MAX_RETRIES = 3  # Maximum number of retries for operations


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
def generate_presigned_url(bucket: str, key: str, filename: str) -> str:
    """
    Generate a presigned URL for an S3 object.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        filename: Original filename for content disposition
        
    Returns:
        Presigned URL
    """
    try:
        raw = os.path.basename(filename)
        # Normalize to NFKD, drop anything that can't be ASCII-encoded:
        safe = (
            unicodedata
                .normalize('NFKD', raw)
                .encode('ascii', 'ignore')
                .decode('ascii')
            )
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': f'attachment; filename="{safe}"',
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
def process_files(job_id: str, files: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Process files and generate presigned URLs for each.
    
    Args:
        job_id: ID of the job
        files: List of file asset IDs
        options: Download options
        
    Returns:
        List of dictionaries containing URL and filename
    """
    download_files = []
    quality = options.get("quality", "original")  # original or proxy
    
    for file in files:
        asset_id = file.get("assetId")
        
        try:
            # Get asset details
            asset = get_asset_details(asset_id)
            
            # Determine file path based on quality option
            file_path = None
            bucket = None
            
            if quality == "proxy":
                # Look for proxy representation
                for rep in asset.get("DerivedRepresentations", []):
                    if rep.get("Purpose") == "proxy":
                        storage_info = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                        bucket = storage_info.get("Bucket")
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
                    bucket = storage_info.get("Bucket")
                    file_path = storage_info.get("ObjectKey", {}).get("FullPath")
            else:
                # Use original representation
                main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
                storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                bucket = storage_info.get("Bucket")
                file_path = storage_info.get("ObjectKey", {}).get("FullPath")
            
            if not file_path or not bucket:
                logger.error(
                    f"Could not determine file path or bucket for asset {asset_id}",
                    extra={"assetId": asset_id}
                )
                continue
            
            # Get file name from path
            file_name = os.path.basename(file_path)
            
            # Generate presigned URL
            download_url = generate_presigned_url(bucket, file_path, file_name)
            download_files.append({
                "url": download_url,
                "filename": file_name,
                "assetId": asset_id
            })
            
            logger.info(
                "Generated presigned URL for file",
                extra={
                    "assetId": asset_id,
                    "fileName": file_name,
                    "jobId": job_id,
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to process file {asset_id}: {str(e)}",
                extra={
                    "assetId": asset_id,
                    "jobId": job_id,
                }
            )
            # Continue processing other files even if one fails
            continue
    
    return download_files


@tracer.capture_method
def update_job_with_file_urls(job_id: str, file_data: List[Dict[str, str]]) -> None:
    """
    Update the job record with file URLs in downloadUrls structure.
    
    Args:
        job_id: ID of the job to update
        file_data: List of dictionaries containing URL and filename for files
        
    Raises:
        Exception: If job update fails
    """
    try:
        # Calculate expiration time (7 days from now)
        expiration_time = datetime.utcnow() + timedelta(days=7)
        
        # Store file data in downloadUrls.files structure for mixed jobs
        structured_urls = {
            "files": file_data
        }
        
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=(
                "SET #downloadUrls = :downloadUrls, "
                "#expiresAt = :expiresAt, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#downloadUrls": "downloadUrls",
                "#expiresAt": "expiresAt",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":downloadUrls": structured_urls,
                ":expiresAt": int(expiration_time.timestamp()),
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
        
        logger.info(
            "Updated job with file URLs in downloadUrls structure",
            extra={
                "jobId": job_id,
                "urlCount": len(file_data),
                "expiresAt": expiration_time.isoformat(),
            },
        )
    
    except ClientError as e:
        logger.error(
            "Failed to update job with file URLs",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise Exception(f"Failed to update job with file URLs: {str(e)}")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for generating presigned URLs for files.
    
    Args:
        event: Event containing job details and files
        context: Lambda context
        
    Returns:
        Updated job details with file URLs
    """
    try:
        # Get job ID from event
        job_id = event.get("jobId")
        if not job_id:
            raise ValueError("Missing jobId in event")
        
        # Get job details for options and job type
        job = get_job_details(job_id)
        options = job.get("options", {})
        job_type = job.get("jobType", "")
        
        # Handle both single file and individual file jobs
        files = []
        
        if job_type in ["SINGLE_FILE", "LARGE_INDIVIDUAL"]:
            # For individual file jobs, get assets from foundAssets
            asset_ids = job.get("foundAssets", [])
            if not asset_ids:
                logger.info("No assets found for individual file job", extra={"jobId": job_id})
                return {
                    "jobId": job_id,
                    "largeFileUrls": [],
                }
            
            # Convert assets to files format
            for asset_id in asset_ids:
                files.append({
                    "assetId": asset_id,
                    "options": options
                })
            
            logger.info(
                "Processing individual file job",
                extra={
                    "jobId": job_id,
                    "jobType": job_type,
                    "assetCount": len(asset_ids),
                }
            )
        else:
            # For mixed jobs, get files from event (this should only be for MIXED job type now)
            files = event.get("largeFiles", [])
            if not files:
                logger.info("No files to process", extra={"jobId": job_id})
                return {
                    "jobId": job_id,
                    "largeFileUrls": [],
                }
            
            logger.info(
                "Processing files for mixed job",
                extra={
                    "jobId": job_id,
                    "fileCount": len(files),
                }
            )
        
        # Process files and generate presigned URLs with metadata
        file_data = process_files(job_id, files, options)
        
        # If this is a LARGE_INDIVIDUAL or SINGLE_FILE job (individual downloads), complete the job
        if job_type in ["LARGE_INDIVIDUAL", "SINGLE_FILE"]:
            # Calculate expiration time (7 days from now)
            expiration_time = datetime.utcnow() + timedelta(days=7)
            
            # Store structured format in database for LARGE_INDIVIDUAL jobs
            structured_urls = {
                "files": file_data
            }
            
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
                    ":downloadUrls": structured_urls,
                    ":expiresAt": int(expiration_time.timestamp()),
                    ":progress": 100,
                    ":updatedAt": datetime.utcnow().isoformat(),
                },
            )
            
            logger.info(
                f"Completed {job_type} job with individual file URLs",
                extra={
                    "jobId": job_id,
                    "jobType": job_type,
                    "urlCount": len(file_data),
                    "expiresAt": expiration_time.isoformat(),
                },
            )
        else:
            # For mixed jobs, just update with file URLs (small files will be handled separately)
            update_job_with_file_urls(job_id, file_data)
        
        # Add metrics
        metrics.add_metric(name="FilesProcessed", unit=MetricUnit.Count, value=len(file_data))
        
        # Return updated job details with structured format
        response = {
            "jobId": job_id,
            "largeFileUrls": [item["url"] for item in file_data],  # Keep for internal workflow compatibility
            "status": "COMPLETED" if job_type in ["LARGE_INDIVIDUAL", "SINGLE_FILE"] else "PROCESSING",
        }
        
        # Add structured downloadUrls for individual download jobs
        if job_type in ["LARGE_INDIVIDUAL", "SINGLE_FILE"]:
            response["downloadUrls"] = {
                "files": file_data
            }
        
        return response
    
    except Exception as e:
        logger.error(
            f"Error processing files: {str(e)}",
            exc_info=True,
            extra={"jobId": event.get("jobId")},
        )
        
        # Update job status to FAILED
        try:
            if "jobId" in event:
                bulk_download_table.update_item(
                    Key={"jobId": event["jobId"]},
                    UpdateExpression="SET #status = :status, #error = :error, #updatedAt = :updatedAt",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                        "#updatedAt": "updatedAt",
                    },
                    ExpressionAttributeValues={
                        ":status": "FAILED",
                        ":error": f"Failed to process files: {str(e)}",
                        ":updatedAt": datetime.utcnow().isoformat(),
                    },
                )
        except Exception as update_error:
            logger.error(
                f"Failed to update job status after error: {str(update_error)}",
                extra={"jobId": event.get("jobId")},
            )
        
        metrics.add_metric(name="FileProcessingErrors", unit=MetricUnit.Count, value=1)
        
        # Re-raise the exception to be handled by Step Functions
        raise