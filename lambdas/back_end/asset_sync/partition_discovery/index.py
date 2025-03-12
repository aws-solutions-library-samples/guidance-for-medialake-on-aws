# lambda/partition_discovery/handler.py
import os
import json
import boto3
import uuid
import math
from datetime import datetime, timedelta
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
    get_optimized_client, get_optimized_s3_client, DecimalEncoder
)

# Initialize batch processor
processor = BatchProcessor(event_type=EventType.SQS)

@tracer.capture_method
def analyze_bucket_structure(bucket_name: str, sample_size: int = 1000) -> Dict[str, Any]:
    """
    Analyze bucket structure to determine the best partitioning strategy
    
    Args:
        bucket_name: S3 bucket name
        sample_size: Number of objects to sample
        
    Returns:
        Dict with bucket analysis results
    """
    s3 = get_optimized_s3_client(bucket_name)
    
    try:
        # Get bucket information
        bucket_info = s3.head_bucket(Bucket=bucket_name)
        
        # Try to list some objects to determine structure
        sample_response = s3.list_objects_v2(
            Bucket=bucket_name, 
            MaxKeys=sample_size
        )
        
        sample_count = len(sample_response.get('Contents', []))
        
        # Look for common prefixes at different levels
        prefix_response = s3.list_objects_v2(
            Bucket=bucket_name, 
            Delimiter='/',
            MaxKeys=sample_size
        )
        
        top_level_prefixes = [
            prefix.get('Prefix') for prefix in 
            prefix_response.get('CommonPrefixes', [])
        ]
        
        # Analyze key patterns
        key_patterns = []
        date_patterns = 0
        has_nested_structure = False
        
        for obj in sample_response.get('Contents', []):
            key = obj.get('Key', '')
            parts = key.split('/')
            
            # Check for date patterns in keys (YYYY, YYYY-MM, YYYY/MM, etc.)
            # This is a simplistic check - could be enhanced for more patterns
            for part in parts:
                if (
                    (len(part) == 4 and part.isdigit()) or  # YYYY
                    (len(part) == 7 and part[4] == '-' and part[:4].isdigit() and part[5:].isdigit()) or  # YYYY-MM
                    (len(part) == 10 and part[4] == '-' and part[7] == '-' and part[:4].isdigit())  # YYYY-MM-DD
                ):
                    date_patterns += 1
                    break
            
            # Check if key has path structure
            if '/' in key:
                has_nested_structure = True
                
                # Extract key pattern up to second level
                if len(parts) > 2:
                    pattern = '/'.join(parts[:2]) + '/'
                    if pattern not in key_patterns:
                        key_patterns.append(pattern)
        
        # Determine estimated total objects
        is_truncated = sample_response.get('IsTruncated', False)
        estimated_total = sample_count
        
        if is_truncated and sample_count == sample_size:
            # If we hit the sample size limit, the bucket is likely large
            # We can't easily determine actual size without listing everything,
            # so we'll make a conservative estimate
            estimated_total = sample_count * 10  # Conservative multiplier
        
        return {
            'sampleCount': sample_count,
            'topLevelPrefixes': top_level_prefixes,
            'datePatternRatio': date_patterns / max(1, sample_count),
            'hasNestedStructure': has_nested_structure,
            'keyPatterns': key_patterns[:50],  # Limit to avoid excessive partitions
            'estimatedTotal': estimated_total,
            'isTruncated': is_truncated
        }
        
    except Exception as e:
        logger.error(f"Error analyzing bucket structure: {str(e)}")
        raise

@tracer.capture_method
def create_partitions(
    job_id: str,
    bucket_name: str,
    max_partitions: int = 10,
    bucket_analysis: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Create partitions for parallel processing based on bucket analysis
    
    Args:
        job_id: Job ID
        bucket_name: S3 bucket name
        max_partitions: Maximum number of partitions to create
        bucket_analysis: Optional pre-computed bucket analysis
        
    Returns:
        List of created partitions
    """
    if not bucket_analysis:
        bucket_analysis = analyze_bucket_structure(bucket_name)
    
    partitions = []
    partition_table = boto3.resource('dynamodb').Table(os.environ['PARTITION_TABLE_NAME'])
    s3 = get_optimized_s3_client(bucket_name)
    
    # Update job status
    AssetProcessor.update_job_status(
        job_id, 
        JobStatus.DISCOVERING, 
        f"Creating partitions for bucket {bucket_name}"
    )
    
    # Strategy 1: If we have top-level prefixes and they're not too many, use them as partitions
    if (
        bucket_analysis['topLevelPrefixes'] and 
        1 <= len(bucket_analysis['topLevelPrefixes']) <= max_partitions
    ):
        logger.info(f"Using {len(bucket_analysis['topLevelPrefixes'])} top-level prefixes as partitions for job {job_id}")
        
        for prefix in bucket_analysis['topLevelPrefixes']:
            partition_id = f"prefix-{str(uuid.uuid4())}"
            
            # Create partition record
            partition = {
                'jobId': job_id,
                'partitionId': partition_id,
                'type': 'PREFIX',
                'prefix': prefix,
                'status': PartitionStatus.PENDING.value,
                'createTime': datetime.utcnow().isoformat(),
                'lastUpdated': datetime.utcnow().isoformat(),
                'stats': {
                    'objectsScanned': 0,
                    'objectsToProcess': 0,
                    'objectsProcessed': 0,
                    'errors': 0
                }
            }
            
            # Save partition to DynamoDB
            partition_table.put_item(Item=partition)
            
            partitions.append({
                'partitionId': partition_id,
                'prefix': prefix,
                'type': 'PREFIX'
            })
    
    # Strategy 2: If we have a date-based structure, partition by date patterns
    elif bucket_analysis['datePatternRatio'] > 0.5 and bucket_analysis['keyPatterns']:
        # Use date patterns for partitioning
        logger.info(f"Using date-based partitioning for job {job_id}")
        
        # Limit to max_partitions
        patterns = bucket_analysis['keyPatterns'][:max_partitions]
        
        for pattern in patterns:
            partition_id = f"date-{str(uuid.uuid4())}"
            
            # Create partition record
            partition = {
                'jobId': job_id,
                'partitionId': partition_id,
                'type': 'DATE_PATTERN',
                'prefix': pattern,
                'status': PartitionStatus.PENDING.value,
                'createTime': datetime.utcnow().isoformat(),
                'lastUpdated': datetime.utcnow().isoformat(),
                'stats': {
                    'objectsScanned': 0,
                    'objectsToProcess': 0,
                    'objectsProcessed': 0,
                    'errors': 0
                }
            }
            
            # Save partition to DynamoDB
            partition_table.put_item(Item=partition)
            
            partitions.append({
                'partitionId': partition_id,
                'prefix': pattern,
                'type': 'DATE_PATTERN'
            })
    
    # Strategy 3: If we have nested structure but no clear patterns, use key ranges
    elif bucket_analysis['hasNestedStructure'] and bucket_analysis['sampleCount'] > 0:
        # Create key range partitions
        logger.info(f"Using key range partitioning for job {job_id}")
        
        # Calculate number of partitions based on estimated objects
        estimated_objects = bucket_analysis['estimatedTotal']
        partition_count = min(max(int(estimated_objects / 10000), 1), max_partitions)
        
        # Get a sorted sample of keys
        sample_response = s3.list_objects_v2(
            Bucket=bucket_name, 
            MaxKeys=1000
        )
        
        keys = [obj['Key'] for obj in sample_response.get('Contents', [])]
        keys.sort()
        
        # Create partition boundaries based on key distribution
        if len(keys) > 1 and partition_count > 1:
            step_size = max(1, len(keys) // partition_count)
            boundaries = [keys[i] for i in range(0, len(keys), step_size)]
            
            # Ensure we don't exceed our max partition count
            boundaries = boundaries[:max_partitions]
            
            # Create partitions
            for i in range(len(boundaries)):
                partition_id = f"range-{str(uuid.uuid4())}"
                start_key = boundaries[i]
                end_key = boundaries[i+1] if i < len(boundaries) - 1 else None
                
                # Create partition record
                partition = {
                    'jobId': job_id,
                    'partitionId': partition_id,
                    'type': 'KEY_RANGE',
                    'startKey': start_key,
                    'endKey': end_key,
                    'status': PartitionStatus.PENDING.value,
                    'createTime': datetime.utcnow().isoformat(),
                    'lastUpdated': datetime.utcnow().isoformat(),
                    'stats': {
                        'objectsScanned': 0,
                        'objectsToProcess': 0,
                        'objectsProcessed': 0,
                        'errors': 0
                    }
                }
                
                # Save partition to DynamoDB
                partition_table.put_item(Item=partition)
                
                partitions.append({
                    'partitionId': partition_id,
                    'startKey': start_key,
                    'endKey': end_key,
                    'type': 'KEY_RANGE'
                })
        else:
            # Too few objects or partitions, use a single partition
            partition_id = f"full-{str(uuid.uuid4())}"
            
            # Create partition record
            partition = {
                'jobId': job_id,
                'partitionId': partition_id,
                'type': 'FULL_BUCKET',
                'status': PartitionStatus.PENDING.value,
                'createTime': datetime.utcnow().isoformat(),
                'lastUpdated': datetime.utcnow().isoformat(),
                'stats': {
                    'objectsScanned': 0,
                    'objectsToProcess': 0,
                    'objectsProcessed': 0,
                    'errors': 0
                }
            }
            
            # Save partition to DynamoDB
            partition_table.put_item(Item=partition)
            
            partitions.append({
                'partitionId': partition_id,
                'type': 'FULL_BUCKET'
            })
    
    # Strategy 4: Fallback - use alphabet-based partitioning
    elif bucket_analysis['sampleCount'] > 0:
        # Create alphabetical range partitions
        logger.info(f"Using alphabetical partitioning for job {job_id}")
        
        # Calculate partition count based on sample size
        partition_count = min(max(int(bucket_analysis['sampleCount'] / 1000), 1), max_partitions)
        
        # Create partition boundaries (simplified alphabet partitioning)
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        step_size = max(1, len(alphabet) // partition_count)
        boundaries = [alphabet[i] for i in range(0, len(alphabet), step_size)]
        
        # Ensure we don't exceed our max partition count
        boundaries = boundaries[:max_partitions]
        
        for i in range(len(boundaries)):
            partition_id = f"alpha-{str(uuid.uuid4())}"
            start_char = boundaries[i]
            end_char = boundaries[i+1] if i < len(boundaries) - 1 else None
            
            # Create partition record
            partition = {
                'jobId': job_id,
                'partitionId': partition_id,
                'type': 'ALPHABETICAL',
                'startChar': start_char,
                'endChar': end_char,
                'status': PartitionStatus.PENDING.value,
                'createTime': datetime.utcnow().isoformat(),
                'lastUpdated': datetime.utcnow().isoformat(),
                'stats': {
                    'objectsScanned': 0,
                    'objectsToProcess': 0,
                    'objectsProcessed': 0,
                    'errors': 0
                }
            }
            
            # Save partition to DynamoDB
            partition_table.put_item(Item=partition)
            
            partitions.append({
                'partitionId': partition_id,
                'startChar': start_char,
                'endChar': end_char,
                'type': 'ALPHABETICAL'
            })
    
    else:
        # Empty bucket - create a dummy partition
        partition_id = f"empty-{str(uuid.uuid4())}"
        
        # Create partition record
        partition = {
            'jobId': job_id,
            'partitionId': partition_id,
            'type': 'EMPTY',
            'status': PartitionStatus.COMPLETED.value,  # Mark as complete since there's nothing to do
            'createTime': datetime.utcnow().isoformat(),
            'lastUpdated': datetime.utcnow().isoformat(),
            'stats': {
                'objectsScanned': 0,
                'objectsToProcess': 0,
                'objectsProcessed': 0,
                'errors': 0
            }
        }
        
        # Save partition to DynamoDB
        partition_table.put_item(Item=partition)
        
        partitions.append({
            'partitionId': partition_id,
            'type': 'EMPTY'
        })
    
    # Update job with partition information
    AssetProcessor.update_job_status(
        job_id,
        JobStatus.SCANNING,
        f"Created {len(partitions)} partitions for parallel processing",
        stats={
            'partitionsCreated': len(partitions)
        }
    )
    
    return partitions

@tracer.capture_method
def enqueue_partition_for_processing(
    job_id: str,
    bucket_name: str,
    partition: Dict[str, Any],
    batch_size: int = 1000
) -> None:
    """
    Enqueue a partition for processing
    
    Args:
        job_id: Job ID
        bucket_name: S3 bucket name
        partition: Partition details
        batch_size: Number of objects per batch
    """
    sqs = get_optimized_client('sqs')
    
    # Create message attributes
    message_attributes = {
        'jobId': {
            'DataType': 'String',
            'StringValue': job_id
        },
        'partitionId': {
            'DataType': 'String',
            'StringValue': partition['partitionId']
        },
        'operation': {
            'DataType': 'String',
            'StringValue': 'SCAN_PARTITION'
        }
    }
    
    # Create message body with appropriate parameters based on partition type
    message_body = {
        'jobId': job_id,
        'bucketName': bucket_name,
        'partitionId': partition['partitionId'],
        'operation': 'SCAN_PARTITION',
        'batchSize': batch_size,
        'partitionType': partition.get('type')
    }
    
    # Add type-specific parameters
    if partition.get('type') == 'PREFIX':
        message_body['prefix'] = partition.get('prefix')
    elif partition.get('type') == 'DATE_PATTERN':
        message_body['prefix'] = partition.get('prefix')
    elif partition.get('type') == 'KEY_RANGE':
        message_body['startKey'] = partition.get('startKey')
        message_body['endKey'] = partition.get('endKey')
    elif partition.get('type') == 'ALPHABETICAL':
        message_body['startChar'] = partition.get('startChar')
        message_body['endChar'] = partition.get('endChar')
    
    # Send message to scanner queue
    sqs.send_message(
        QueueUrl=os.environ['SCANNER_QUEUE_URL'],
        MessageBody=json.dumps(message_body),
        MessageAttributes=message_attributes
    )
    
    logger.info(f"Enqueued partition {partition['partitionId']} for job {job_id}")

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
    operation = body.get('operation')
    
    if operation == 'DISCOVER_PARTITIONS':
        # Extract parameters
        max_partitions = min(int(body.get('maxPartitions', 10)), 50)
        batch_size = min(int(body.get('batchSize', 1000)), 10000)
        
        # Create partitions
        partitions = create_partitions(job_id, bucket_name, max_partitions)
        
        # Enqueue each partition for processing
        for partition in partitions:
            enqueue_partition_for_processing(job_id, bucket_name, partition, batch_size)
            
        # Record metrics
        metrics.add_metric(name="PartitionsCreated", unit=MetricUnit.Count, value=len(partitions))
        
        logger.info(f"Created and enqueued {len(partitions)} partitions for job {job_id}")

@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for partition discovery
    
    Args:
        event: SQS event
        context: Lambda context
        
    Returns:
        Dict with processing results
    """
    # Parse SQS event
    batch_item_failures = []
    
    try:
        # Process each record with the batch processor
        with processor(records=event['Records'], handler=process_record) as processed:
            batch_item_failures = processed.partial_response
            
    except Exception as e:
        logger.exception(f"Error in batch processing: {str(e)}")
        # Add all records as failures
        batch_item_failures = [{"itemIdentifier": record["messageId"]} for record in event['Records']]
        
    # Return failures if any
    return {"batchItemFailures": batch_item_failures}