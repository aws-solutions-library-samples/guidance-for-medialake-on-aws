# lambda/processor/handler.py
import os
import json
import boto3
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Union
from concurrent.futures import ThreadPoolExecutor

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError

# Import common utilities
import sys
sys.path.append('/opt/python')
from common import (
    AssetProcessor, JobStatus, PartitionStatus, ErrorType, logger, tracer, metrics,
    get_optimized_client, get_optimized_s3_client, MAX_THREADS, DecimalEncoder
)

# Initialize batch processor
processor = BatchProcessor(event_type=EventType.SQS)

@tracer.capture_method
def load_manifest(manifest_key: str) -> Dict[str, Any]:
    """
    Load chunk manifest from S3
    
    Args:
        manifest_key: S3 object key with chunk manifest
        
    Returns:
        Manifest dict
    """
    s3 = get_optimized_client('s3')
    result_bucket = os.environ.get('RESULTS_BUCKET_NAME')
    
    # Load manifest from S3
    response = s3.get_object(
        Bucket=result_bucket,
        Key=manifest_key
    )
    
    # Parse JSON response
    return json.loads(response['Body'].read().decode('utf-8'))

@tracer.capture_method
def load_chunk(chunk_key: str) -> List[Dict[str, Any]]:
    """
    Load objects chunk from S3
    
    Args:
        chunk_key: S3 object key with objects chunk
        
    Returns:
        List of objects
    """
    s3 = get_optimized_client('s3')
    result_bucket = os.environ.get('RESULTS_BUCKET_NAME')
    
    # Load chunk from S3
    response = s3.get_object(
        Bucket=result_bucket,
        Key=chunk_key
    )
    
    # Parse JSON response
    return json.loads(response['Body'].read().decode('utf-8'))

@tracer.capture_method
def generate_presigned_url(bucket_name: str, object_key: str, expiration: int = 3600) -> str:
    """
    Generate presigned URL for S3 object
    
    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key
        expiration: URL expiration in seconds
        
    Returns:
        Presigned URL
    """
    s3 = get_optimized_s3_client(bucket_name)
    
    # Generate presigned URL
    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': bucket_name,
            'Key': object_key
        },
        ExpiresIn=expiration
    )
    
    return url

@tracer.capture_method
def process_object(
    obj: Dict[str, Any],
    bucket_name: str,
    job_id: str,
    partition_id: str
) -> Dict[str, Any]:
    """
    Process a single object
    
    Args:
        obj: Object to process
        bucket_name: S3 bucket name
        job_id: Job ID
        partition_id: Partition ID
        
    Returns:
        Processing result
    """
    s3 = get_optimized_s3_client(bucket_name)
    object_key = obj['key']
    
    try:
        # Get existing tags
        try:
            tags_response = s3.get_object_tagging(
                Bucket=bucket_name,
                Key=object_key
            )
            existing_tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}
        except Exception as e:
            logger.warning(f"Error fetching tags for {object_key}: {str(e)}")
            existing_tags = {}
        
        # Prepare new tags
        new_tags = existing_tags.copy()
        
        # If object doesn't have AssetID, generate one
        if not obj.get('assetId'):
            obj['assetId'] = f"asset-{str(uuid.uuid4())}"
            new_tags['AssetID'] = obj['assetId']
        
        # If object doesn't have InventoryID, generate one
        if not obj.get('inventoryId'):
            obj['inventoryId'] = f"inventory-{str(uuid.uuid4())}"
            new_tags['InventoryID'] = obj['inventoryId']
        
        # Set job ID tag for tracking
        new_tags['JobID'] = job_id
        new_tags['ProcessedAt'] = datetime.utcnow().isoformat()
        
        # Only update tags if they changed
        if new_tags != existing_tags:
            # Update object tags
            tag_set = [{'Key': k, 'Value': v} for k, v in new_tags.items()]
            s3.put_object_tagging(
                Bucket=bucket_name,
                Key=object_key,
                Tagging={'TagSet': tag_set}
            )
        
        # Trigger S3:ObjectCreated event by copying object to itself
        # This is the key part that simulates a new object creation
        copy_source = {'Bucket': bucket_name, 'Key': object_key}
        
        # Generate tag string for copy operation
        tag_string = "&".join([f"{k}={v}" for k, v in new_tags.items()])
        
        # Copy object to itself
        s3.copy_object(
            Bucket=bucket_name,
            CopySource=copy_source,
            Key=object_key,
            TaggingDirective='REPLACE',
            Tagging=tag_string
        )
        
        # Return success result
        return {
            'status': 'success',
            'key': object_key,
            'assetId': obj['assetId'],
            'inventoryId': obj['inventoryId']
        }
        
    except Exception as e:
        # Log error
        error_id = str(uuid.uuid4())
        AssetProcessor.log_error(
            AssetProcessor.format_error(
                error_id=error_id,
                object_key=object_key,
                error_type=ErrorType.PROCESS_ERROR,
                error_message=str(e),
                retry_count=0,
                job_id=job_id,
                bucket_name=bucket_name
            )
        )
        
        # Return error result
        return {
            'status': 'error',
            'key': object_key,
            'error': str(e),
            'errorId': error_id
        }

@tracer.capture_method
def process_record(record: Dict[str, Any]) -> None:
    """
    Process a single SQS record
    
    Args:
        record: SQS record
    """
    # Parse message body
    body = json.loads(record['body'])
    job_id = body.get('jobId')
    bucket_name = body.get('bucketName')
    partition_id = body.get('partitionId')
    operation = body.get('operation')
    
    # Only process PROCESS_OBJECTS operations
    if operation != 'PROCESS_OBJECTS':
        logger.warning(f"Skipping non-process operation: {operation}")
        return
    
    # Get manifest information
    manifest_key = body.get('manifestKey')
    manifest_type = body.get('manifestType', 'CHUNKED')
    
    # Update partition status
    AssetProcessor.update_partition_status(
        job_id,
        partition_id,
        PartitionStatus.PROCESSING,
        f"Processing objects from manifest {manifest_key}"
    )
    
    try:
        # Load manifest
        manifest = load_manifest(manifest_key)
        chunks = manifest.get('chunks', [])
        total_objects = manifest.get('totalObjects', 0)
        
        logger.info(f"Processing {total_objects} objects in {len(chunks)} chunks for job {job_id}, partition {partition_id}")
        
        # Process each chunk
        results = {
            'successful': 0,
            'failed': 0
        }
        
        for chunk_info in chunks:
            chunk_key = chunk_info.get('key')
            chunk_count = chunk_info.get('count', 0)
            
            try:
                # Load chunk objects
                objects = load_chunk(chunk_key)
                
                # Process objects in parallel
                with ThreadPoolExecutor(max_workers=min(MAX_THREADS, len(objects))) as executor:
                    futures = [
                        executor.submit(
                            process_object, obj, bucket_name, job_id, partition_id
                        ) for obj in objects
                    ]
                    
                    # Collect results
                    for future in futures:
                        result = future.result()
                        
                        if result.get('status') == 'success':
                            results['successful'] += 1
                        else:
                            results['failed'] += 1
                
            except Exception as e:
                # Log chunk processing error
                error_id = str(uuid.uuid4())
                AssetProcessor.log_error(
                    AssetProcessor.format_error(
                        error_id=error_id,
                        object_key=f"chunk-{chunk_key}",
                        error_type=ErrorType.PROCESS_ERROR,
                        error_message=str(e),
                        retry_count=0,
                        job_id=job_id,
                        bucket_name=bucket_name
                    )
                )
                
                # Count all objects in chunk as failed
                results['failed'] += chunk_count
        
        # Update partition stats
        AssetProcessor.increment_partition_counter(
            job_id, partition_id, 'objectsProcessed', results['successful']
        )
        
        # Update job stats
        AssetProcessor.increment_job_counter(
            job_id, 'totalObjectsProcessed', results['successful']
        )
        
        if results['failed'] > 0:
            AssetProcessor.increment_job_counter(job_id, 'errors', results['failed'])
            AssetProcessor.increment_partition_counter(
                job_id, partition_id, 'errors', results['failed']
            )
        
        # If all chunks are processed, update partition status
        if results['successful'] + results['failed'] >= total_objects:
            # Check if all partition pages are complete
            # This would require additional tracking, simplified for now
            AssetProcessor.update_partition_status(
                job_id,
                partition_id,
                PartitionStatus.COMPLETED,
                f"Processed {results['successful']} objects ({results['failed']} errors)"
            )
        
        # Record metrics
        metrics.add_metric(name="ObjectsProcessed",