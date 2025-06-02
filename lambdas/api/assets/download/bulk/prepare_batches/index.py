"""
Bulk Download Prepare Batches Lambda

This Lambda function prepares batches of zip files for parallel processing by:
1. Extracting file paths from the smallZipFiles and largeZipFiles arrays
2. Organizing them into batches of a configurable size
3. Returning the batches for processing by the merge_batch Lambda

This function is designed to be used in a Step Functions workflow.
"""

import json
import os
import boto3
from typing import Dict, Any, List
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-prepare-batches")
tracer = Tracer(service="bulk-download-prepare-batches")
metrics = Metrics(namespace="BulkDownloadService", service="bulk-download-prepare-batches")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
BULK_DOWNLOAD_TABLE = os.environ["BULK_DOWNLOAD_TABLE"]
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))  # Default to 5 files per batch

# Initialize DynamoDB table
bulk_download_table = dynamodb.Table(BULK_DOWNLOAD_TABLE)


@tracer.capture_method
def extract_zip_paths(event: Dict[str, Any]) -> List[str]:
    """
    Extract zip file paths from the smallZipFiles and largeZipFiles arrays.
    
    Args:
        event: Event containing job details and file information
        
    Returns:
        List of zip file paths
    """
    all_zip_paths = []
    
    # Extract small zip file paths
    small_zip_files = event.get("smallZipFiles", [])
    for item in small_zip_files:
        if isinstance(item, dict) and "smallZipFiles" in item:
            small_paths = item.get("smallZipFiles", [])
            logger.info(f"Found {len(small_paths)} small zip paths in item", extra={"item": str(item)})
            all_zip_paths.extend(small_paths)
    
    # Extract large zip file paths
    large_zip_files = event.get("largeZipFiles", [])
    for item in large_zip_files:
        if isinstance(item, dict) and "chunkZipPath" in item:
            chunk_path = item.get("chunkZipPath")
            logger.info(f"Found large zip path: {chunk_path}")
            all_zip_paths.append(chunk_path)
    
    logger.info(
        f"Extracted {len(all_zip_paths)} total zip paths",
        extra={
            "smallZipCount": len(small_zip_files),
            "largeZipCount": len(large_zip_files),
            "totalPaths": len(all_zip_paths),
            "samplePaths": str(all_zip_paths[:5]) if all_zip_paths else "None"
        }
    )
    
    logger.info(
        f"Extracted {len(all_zip_paths)} zip file paths",
        extra={
            "jobId": event.get("jobId"),
            "smallZipCount": len(small_zip_files),
            "largeZipCount": len(large_zip_files),
        },
    )
    
    return all_zip_paths


@tracer.capture_method
def create_batches(zip_paths: List[str], batch_size: int) -> List[List[str]]:
    """
    Create batches of zip file paths.
    
    Args:
        zip_paths: List of zip file paths
        batch_size: Number of files per batch
        
    Returns:
        List of batches, where each batch is a list of zip file paths
    """
    return [zip_paths[i:i + batch_size] for i in range(0, len(zip_paths), batch_size)]


@tracer.capture_method
def create_balanced_batches(zip_paths: List[str], batch_size: int) -> List[List[str]]:
    """
    Create balanced batches of zip file paths, ensuring each batch has a mix of small and large files if possible.
    
    Args:
        zip_paths: List of zip file paths
        batch_size: Number of files per batch
        
    Returns:
        List of batches, where each batch is a list of zip file paths
    """
    # Separate small and large files
    small_files = [p for p in zip_paths if "/zips/" in p]  # Heuristic to identify small files
    large_files = [p for p in zip_paths if "s3://" in p]   # Heuristic to identify large files
    
    logger.info(
        f"Creating balanced batches",
        extra={
            "smallFileCount": len(small_files),
            "largeFileCount": len(large_files),
            "batchSize": batch_size,
        }
    )
    
    # If we only have one type of files, use the simple batching
    if not small_files or not large_files:
        return create_batches(zip_paths, batch_size)
    
    # Create balanced batches
    batches = []
    current_batch = []
    
    # Add large files first (one per batch if possible)
    for large_file in large_files:
        if len(current_batch) >= batch_size:
            batches.append(current_batch)
            current_batch = []
        current_batch.append(large_file)
    
    # Add small files to fill the batches
    for small_file in small_files:
        if len(current_batch) >= batch_size:
            batches.append(current_batch)
            current_batch = []
        current_batch.append(small_file)
    
    # Add the last batch if it's not empty
    if current_batch:
        batches.append(current_batch)
    
    logger.info(
        f"Created {len(batches)} balanced batches",
        extra={
            "batchCount": len(batches),
            "firstBatchSize": len(batches[0]) if batches else 0,
            "lastBatchSize": len(batches[-1]) if batches else 0,
        }
    )
    
    return batches


@tracer.capture_method
def update_job_status(job_id: str, batch_count: int) -> None:
    """
    Update the job status in DynamoDB.
    
    Args:
        job_id: ID of the job to update
        batch_count: Number of batches created
    """
    try:
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=(
                "SET #status = :status, "
                "#batchCount = :batchCount, "
                "#updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#batchCount": "batchCount",
                "#updatedAt": "updatedAt",
            },
            ExpressionAttributeValues={
                ":status": "PROCESSING_BATCHES",
                ":batchCount": batch_count,
                ":updatedAt": datetime.utcnow().isoformat(),
            },
        )
    except ClientError as e:
        logger.error(
            "Failed to update job status",
            extra={
                "error": str(e),
                "jobId": job_id,
            },
        )
        raise


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for preparing batches of zip files.
    
    Args:
        event: Event containing job details and file information
        context: Lambda context
        
    Returns:
        Dictionary containing job details and batches of zip file paths
    """
    job_id = event.get("jobId")
    user_id = event.get("userId")
    
    if not job_id:
        raise ValueError("Missing jobId in event")
    
    try:
        # Extract zip file paths
        all_zip_paths = extract_zip_paths(event)
        
        if not all_zip_paths:
            logger.warning("No zip files to process", extra={"jobId": job_id})
            return {
                "jobId": job_id,
                "userId": user_id,
                "status": "EMPTY",
                "zipBatches": [],
            }
        
        # Log the total number of files
        logger.info(
            f"Processing {len(all_zip_paths)} total files",
            extra={
                "jobId": job_id,
                "smallFileCount": len([p for p in all_zip_paths if "/zips/" in p]),  # Heuristic to identify small files
                "largeFileCount": len([p for p in all_zip_paths if "s3://" in p]),   # Heuristic to identify large files
            }
        )
        
        # Create balanced batches of zip files
        # Ensure each batch has a mix of small and large files if possible
        raw_batches = create_balanced_batches(all_zip_paths, BATCH_SIZE)
        
        # Enrich each batch with job context
        enriched_batches = []
        for batch_index, batch in enumerate(raw_batches):
            enriched_batch = {
                "jobId": job_id,
                "userId": user_id,
                "batchId": str(batch_index),
                "zipFiles": batch,
                "options": event.get("options", {})
            }
            enriched_batches.append(enriched_batch)
        
        # Update job status
        update_job_status(job_id, len(enriched_batches))
        
        # Add metrics
        metrics.add_metric(name="BatchesCreated", unit=MetricUnit.Count, value=len(enriched_batches))
        metrics.add_metric(name="TotalFiles", unit=MetricUnit.Count, value=len(all_zip_paths))
        
        logger.info(
            f"Created {len(enriched_batches)} batches of zip files",
            extra={
                "jobId": job_id,
                "totalFiles": len(all_zip_paths),
                "batchSize": BATCH_SIZE,
            },
        )
        
        return {
            "jobId": job_id,
            "userId": user_id,
            "status": "PROCESSING_BATCHES",
            "zipBatches": enriched_batches,
            "options": event.get("options", {}),
        }
    
    except Exception as e:
        logger.error(
            f"Error preparing batches: {str(e)}",
            exc_info=True,
            extra={"jobId": job_id},
        )
        
        # Add metrics
        metrics.add_metric(name="BatchPreparationErrors", unit=MetricUnit.Count, value=1)
        
        return {
            "jobId": job_id,
            "userId": user_id,
            "status": "FAILED",
            "error": str(e),
        }