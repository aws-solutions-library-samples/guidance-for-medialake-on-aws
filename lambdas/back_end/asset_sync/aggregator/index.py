# lambda/aggregator/handler.py
import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from boto3.dynamodb.conditions import Key, Attr

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SNSEvent, event_source

# Import common utilities
import sys
sys.path.append('/opt/python')
from common import (
    AssetProcessor, JobStatus, PartitionStatus, ErrorType, logger, tracer, metrics,
    get_optimized_client, get_dynamodb_client, DecimalEncoder
)

@tracer.capture_method
def check_active_jobs() -> List[str]:
    """
    Check for active jobs
    
    Returns:
        List of active job IDs
    """
    dynamodb = boto3.resource('dynamodb')
    job_table = dynamodb.Table(os.environ.get('JOB_TABLE_NAME'))
    
    # Query for active jobs (not COMPLETED or FAILED)
    response = job_table.scan(
        FilterExpression=Attr('status').ne(JobStatus.COMPLETED.value) & 
                         Attr('status').ne(JobStatus.FAILED.value),
        ProjectionExpression="jobId"
    )
    
    job_ids = [item['jobId'] for item in response.get('Items', [])]
    
    # Handle pagination for large result sets
    while 'LastEvaluatedKey' in response:
        response = job_table.scan(
            FilterExpression=Attr('status').ne(JobStatus.COMPLETED.value) & 
                            Attr('status').ne(JobStatus.FAILED.value),
            ProjectionExpression="jobId",
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        job_ids.extend([item['jobId'] for item in response.get('Items', [])])
    
    return job_ids

@tracer.capture_method
def check_job_status(job_id: str) -> Dict[str, Any]:
    """
    Check status of a job
    
    Args:
        job_id: Job ID
        
    Returns:
        Job status information
    """
    dynamodb = boto3.resource('dynamodb')
    job_table = dynamodb.Table(os.environ.get('JOB_TABLE_NAME'))
    partition_table = dynamodb.Table(os.environ.get('PARTITION_TABLE_NAME'))
    
    # Get job details
    job_response = job_table.get_item(Key={'jobId': job_id})
    job = job_response.get('Item', {})
    
    if not job:
        logger.warning(f"Job {job_id} not found")
        return {
            'jobId': job_id,
            'status': 'NOT_FOUND'
        }
    
    # Query for partitions by status
    partition_counts = {
        'total': 0,
        'pending': 0,
        'scanning': 0,
        'processing': 0,
        'completed': 0,
        'failed': 0
    }
    
    # Query for all partitions
    partition_response = partition_table.query(
        KeyConditionExpression=Key('jobId').eq(job_id)
    )
    
    # Count partitions by status
    for partition in partition_response.get('Items', []):
        partition_counts['total'] += 1
        status = partition.get('status', '').lower()
        if status in partition_counts:
            partition_counts[status] += 1
    
    # Handle pagination for large result sets
    while 'LastEvaluatedKey' in partition_response:
        partition_response = partition_table.query(
            KeyConditionExpression=Key('jobId').eq(job_id),
            ExclusiveStartKey=partition_response['LastEvaluatedKey']
        )
        
        for partition in partition_response.get('Items', []):
            status = partition.get('status', '').lower()
            if status in partition_counts:
                partition_counts[status] += 1
    
    # Combine job and partition status
    result = {
        'jobId': job_id,
        'status': job.get('status'),
        'partitionCounts': partition_counts,
        'stats': job.get('stats', {}),
        'lastUpdated': job.get('lastUpdated')
    }
    
    return result

@tracer.capture_method
def update_job_status_based_on_partitions(job_id: str, job_status: Dict[str, Any]) -> None:
    """
    Update job status based on partition statuses
    
    Args:
        job_id: Job ID
        job_status: Job status information
    """
    current_status = job_status.get('status')
    partition_counts = job_status.get('partitionCounts', {})
    
    # If job is already completed or failed, nothing to do
    if current_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
        return
    
    # If no partitions, nothing to do
    if partition_counts.get('total', 0) == 0:
        return
    
    # Determine new status based on partition counts
    new_status = None
    status_message = None
    
    # All partitions completed
    if partition_counts.get('completed', 0) == partition_counts.get('total', 0):
        new_status = JobStatus.COMPLETED
        status_message = "All partitions completed successfully"
    
    # Any partition failed and no pending/scanning/processing partitions
    elif (
        partition_counts.get('failed', 0) > 0 and 
        partition_counts.get('pending', 0) == 0 and
        partition_counts.get('scanning', 0) == 0 and
        partition_counts.get('processing', 0) == 0
    ):
        new_status = JobStatus.COMPLETED
        status_message = f"Job completed with {partition_counts.get('failed', 0)} failed partitions"
    
    # All partitions are either completed or failed
    elif (
        partition_counts.get('completed', 0) + partition_counts.get('failed', 0) == 
        partition_counts.get('total', 0)
    ):
        new_status = JobStatus.COMPLETED
        status_message = f"Job completed with {partition_counts.get('completed', 0)} successful partitions and {partition_counts.get('failed', 0)} failed partitions"
    
    # Update job status if needed
    if new_status:
        AssetProcessor.update_job_status(
            job_id,
            new_status,
            status_message,
            stats={
                'partitionsCompleted': partition_counts.get('completed', 0),
                'partitionsFailed': partition_counts.get('failed', 0)
            }
        )
        
        logger.info(f"Updated job {job_id} status to {new_status.value}: {status_message}")

@tracer.capture_method
def process_status_updates() -> Dict[str, Any]:
    """
    Process status updates for all active jobs
    
    Returns:
        Dict with processing results
    """
    # Check for active jobs
    job_ids = check_active_jobs()
    
    results = {
        'jobsChecked': len(job_ids),
        'jobsUpdated': 0,
        'jobsCompleted': 0,
        'jobIds': job_ids
    }
    
    # Check each job
    for job_id in job_ids:
        try:
            # Get job status
            job_status = check_job_status(job_id)
            
            # Update job status based on partitions
            update_job_status_based_on_partitions(job_id, job_status)
            
            # Count updated jobs
            results['jobsUpdated'] += 1
            
            # Count completed jobs
            if job_status.get('status') == JobStatus.COMPLETED.value:
                results['jobsCompleted'] += 1
                
        except Exception as e:
            logger.error(f"Error checking job {job_id}: {str(e)}")
    
    return results

@tracer.capture_method
def handle_sns_notification(record: Dict[str, Any]) -> None:
    """
    Handle SNS notification
    
    Args:
        record: SNS record
    """
    # Parse SNS message
    message = json.loads(record['Sns']['Message'])
    job_id = message.get('jobId')
    
    if job_id:
        try:
            # Get job status
            job_status = check_job_status(job_id)
            
            # Update job status based on partitions
            update_job_status_based_on_partitions(job_id, job_status)
            
            logger.info(f"Processed SNS notification for job {job_id}")
            
        except Exception as e:
            logger.error(f"Error processing SNS notification for job {job_id}: {str(e)}")

@event_source(data_class=SNSEvent)
@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for aggregator
    
    Args:
        event: Event
        context: Lambda context
        
    Returns:
        Dict with processing results
    """
    try:
        # Check if this is an SNS notification
        if event.get('Records', []) and event['Records'][0].get('EventSource') == 'aws:sns':
            # Process SNS notifications
            for record in event['Records']:
                handle_sns_notification(record)
            
            return {
                'statusCode': 200,
                'message': 'Processed SNS notifications'
            }
        
        # Otherwise, process scheduled status updates
        results = process_status_updates()
        
        # Record metrics
        metrics.add_metric(name="JobsChecked", unit=MetricUnit.Count, value=results['jobsChecked'])
        metrics.add_metric(name="JobsUpdated", unit=MetricUnit.Count, value=results['jobsUpdated'])
        metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=results['jobsCompleted'])
        
        return {
            'statusCode': 200,
            'results': results
        }
        
    except Exception as e:
        logger.exception(f"Error in aggregator: {str(e)}")
        
        return {
            'statusCode': 500,
            'error': str(e)
        }