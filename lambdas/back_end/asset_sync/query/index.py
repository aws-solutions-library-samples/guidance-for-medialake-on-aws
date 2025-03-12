# lambda/query/handler.py
import os
import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType

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
def load_scan_results(result_key: str) -> List[Dict[str, Any]]:
    """
    Load scan results from S3
    
    Args:
        result_key: S3 object key with scan results
        
    Returns:
        List of scanned objects
    """
    s3 = get_optimized_client('s3')
    result_bucket = os.environ.get('RESULTS_BUCKET_NAME')
    
    # Load results from S3
    response = s3.get_object(
        Bucket=result_bucket,
        Key=result_key
    )
    
    # Parse JSON response
    return json.loads(response['Body'].read().decode('utf-8'))

@tracer.capture_method
def save_query_results(
    job_id: str,
    partition_id: str,
    objects: List[Dict[str, Any]],
    page_number: int = 1
) -> str:
    """
    Save query results to S3
    
    Args:
        job_id: Job ID
        partition_id: Partition ID
        objects: List of objects to process
        page_number: Page number
        
    Returns:
        S3 object key where results are stored
    """
    # If no objects to process, return empty key
    if not objects:
        return ""
    
    s3 = get_optimized_client('s3')
    result_bucket = os.environ.get('RESULTS_BUCKET_NAME')
    
    # Create chunked results (100 objects per chunk)
    chunks = [objects[i:i+100] for i in range(0, len(objects), 100)]
    result_keys = []
    
    # Save each chunk to S3
    for i, chunk in enumerate(chunks):
        # Create S3 key for chunk
        chunk_key = f"job-results/{job_id}/to-process/{partition_id}/page-{page_number}-chunk-{i+1}.json"
        
        # Save chunk to S3
        s3.put_object(
            Bucket=result_bucket,
            Key=chunk_key,
            Body=json.dumps(chunk, cls=DecimalEncoder),
            ContentType="application/json"
        )
        
        result_keys.append({
            'key': chunk_key,
            'count': len(chunk)
        })
    
    # Create S3 key for chunk manifest
    manifest_key = f"job-results/{job_id}/to-process/{partition_id}/page-{page_number}-manifest.json"
    
    # Save manifest to S3
    s3.put_object(
        Bucket=result_bucket,
        Key=manifest_key,
        Body=json.dumps({
            'chunks': result_keys,
            'totalObjects': len(objects)
        }, cls=DecimalEncoder),
        ContentType="application/json"
    )
    
    return manifest_key

@tracer.capture_method
def send_to_processing_queue(
    job_id: str,
    bucket_name: str,
    partition_id: str,
    manifest_key: str,
    total_objects: int
) -> None:
    """
    Send query results to processing queue
    
    Args:
        job_id: Job ID
        bucket_name: S3 bucket name
        partition_id: Partition ID
        manifest_key: S3 object key with chunk manifest
        total_objects: Total number of objects to process
    """
    sqs = get_optimized_client('sqs')
    
    # Create message body
    message_body = {
        'jobId': job_id,
        'bucketName': bucket_name,
        'partitionId': partition_id,
        'operation': 'PROCESS_OBJECTS',
        'manifestKey': manifest_key,
        'objectsCount': total_objects,
        'manifestType': 'CHUNKED'
    }
    
    # Create message attributes
    message_attributes = {
        'jobId': {
            'DataType': 'String',
            'StringValue': job_id
        },
        'partitionId': {
            'DataType': 'String',
            'StringValue': partition_id
        },
        'operation': {
            'DataType': 'String',
            'StringValue': 'PROCESS_OBJECTS'
        }
    }
    
    # Create message group ID for FIFO queue
    # This ensures ordering for each partition
    message_group_id = f"job-{job_id}-partition-{partition_id}"
    
    # Create message deduplication ID
    message_deduplication_id = f"{job_id}-{partition_id}-{manifest_key.split('/')[-1]}"
    
    # Send message to processing queue
    sqs.send_message(
        QueueUrl=os.environ.get('PROCESSING_QUEUE_URL'),
        MessageBody=json.dumps(message_body),
        MessageAttributes=message_attributes,
        MessageGroupId=message_group_id,
        MessageDeduplicationId=message_deduplication_id
    )
    
    logger.info(f"Sent {total_objects} objects to processing queue for job {job_id}, partition {partition_id}")

@tracer.capture_method
def filter_objects_to_process(objects: List[Dict[str, Any]], job_id: str, bucket_name: str) -> List[Dict[str, Any]]:
    """
    Filter objects that need processing
    
    Args:
        objects: List of scanned objects
        job_id: Job ID
        bucket_name: S3 bucket name
        
    Returns:
        List of objects that need processing
    """
    # Extract IDs for batch checking
    asset_ids = [obj['assetId'] for obj in objects if obj.get('assetId')]
    inventory_ids = [obj['inventoryId'] for obj in objects if obj.get('inventoryId')]
    
    # Batch check existence
    existing = AssetProcessor.batch_check_asset_exists(asset_ids, inventory_ids)
    existing_asset_ids = existing['asset_ids']
    existing_inventory_ids = existing['inventory_ids']
    
    # Filter objects that need processing
    objects_to_process = []
    
    for obj in objects:
        # Object needs processing if:
        # 1. It has an AssetID that doesn't exist in the asset table
        # 2. It has an InventoryID that doesn't exist in the asset table
        # 3. It has neither AssetID nor InventoryID
        asset_id = obj.get('assetId')
        inventory_id = obj.get('inventoryId')
        
        if (asset_id and asset_id not in existing_asset_ids) or \
           (inventory_id and inventory_id not in existing_inventory_ids) or \
           (not asset_id and not inventory_id):
            objects_to_process.append(obj)
    
    return objects_to_process

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
    
    # Only process QUERY_OBJECTS operations
    if operation != 'QUERY_OBJECTS':
        logger.warning(f"Skipping non-query operation: {operation}")
        return
    
    # Get scan results
    result_key = body.get('resultKey')
    page_number = body.get('pageNumber', 1)
    objects_count = body.get('objectsCount', 0)
    
    # Update partition status
    AssetProcessor.update_partition_status(
        job_id,
        partition_id,
        PartitionStatus.PROCESSING,
        f"Querying {objects_count} objects from page {page_number}"
    )
    
    try:
        # Load scan results
        scanned_objects = load_scan_results(result_key)
        
        # Filter objects that need processing
        objects_to_process = filter_objects_to_process(scanned_objects, job_id, bucket_name)
        
        # Update partition stats
        AssetProcessor.increment_partition_counter(
            job_id, partition_id, 'objectsToProcess', len(objects_to_process)
        )
        
        # Update job stats
        AssetProcessor.increment_job_counter(
            job_id, 'totalObjectsToProcess', len(objects_to_process)
        )
        
        # If no objects to process, we're done
        if not objects_to_process:
            logger.info(f"No objects to process for job {job_id}, partition {partition_id}, page {page_number}")
            return
        
        # Save query results
        manifest_key = save_query_results(job_id, partition_id, objects_to_process, page_number)
        
        # Send to processing queue
        send_to_processing_queue(
            job_id=job_id,
            bucket_name=bucket_name,
            partition_id=partition_id,
            manifest_key=manifest_key,
            total_objects=len(objects_to_process)
        )
        
        # Record metrics
        metrics.add_metric(name="ObjectsToProcess", unit=MetricUnit.Count, value=len(objects_to_process))
        
        logger.info(f"Found {len(objects_to_process)} objects to process for job {job_id}, partition {partition_id}, page {page_number}")
        
    except Exception as e:
        error_id = str(uuid.uuid4())
        AssetProcessor.log_error(
            AssetProcessor.format_error(
                error_id=error_id,
                object_key=f"partition-{partition_id}-page-{page_number}",
                error_type=ErrorType.DYNAMO_QUERY_ERROR,
                error_message=str(e),
                retry_count=0,
                job_id=job_id,
                bucket_name=bucket_name
            )
        )
        
        # Record error metrics
        metrics.add_metric(name="QueryErrors", unit=MetricUnit.Count, value=1)
        
        # Re-raise to trigger SQS retry mechanism
        raise

@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for query
    
    Args:
        event: SQS event
        context: Lambda context
        
    Returns:
        Dict with processing results
    """
    # Log the entire event to diagnose the issue
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Parse SQS event
    batch_item_failures = []
    
    try:
        # Check if 'Records' exists in the event
        if 'Records' not in event:
            logger.error(f"Event does not contain 'Records' key. Event structure: {json.dumps(event, default=str)}")
            return {"batchItemFailures": []}
            
        # Process each record with the batch processor
        with processor(records=event['Records'], handler=process_record) as processed:
            batch_item_failures = processed.partial_response
            
    except Exception as e:
        logger.exception(f"Error in batch processing: {str(e)}")
        # Add all records as failures if Records exists
        if 'Records' in event:
            batch_item_failures = [{"itemIdentifier": record["messageId"]} for record in event['Records']]
        else:
            logger.error("Cannot create batch_item_failures: 'Records' key missing from event")
            batch_item_failures = []
        
    # Return failures if any
    return {"batchItemFailures": batch_item_failures}