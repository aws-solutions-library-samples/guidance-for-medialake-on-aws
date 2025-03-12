# lambda/dlq_processor/handler.py
import os
import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

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
    get_optimized_client, DecimalEncoder
)

# Initialize batch processor
processor = BatchProcessor(event_type=EventType.SQS)

@tracer.capture_method
def analyze_failed_message(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a failed SQS message
    
    Args:
        record: SQS record
        
    Returns:
        Analysis results
    """
    # Extract information from the message
    try:
        body = json.loads(record.get('body', '{}'))
        attributes = record.get('messageAttributes', {})
        
        job_id = body.get('jobId')
        if not job_id and 'jobId' in attributes:
            job_id = attributes['jobId'].get('stringValue')
            
        bucket_name = body.get('bucketName')
        partition_id = body.get('partitionId')
        operation = body.get('operation')
        
        # Get message metadata
        message_id = record.get('messageId')
        approximate_receive_count = int(record.get('attributes', {}).get('ApproximateReceiveCount', '0'))
        sent_timestamp = record.get('attributes', {}).get('SentTimestamp')
        
        # Calculate time in queue
        time_in_queue = None
        if sent_timestamp:
            sent_time = datetime.fromtimestamp(int(sent_timestamp) / 1000)
            time_in_queue = (datetime.utcnow() - sent_time).total_seconds()
        
        return {
            'messageId': message_id,
            'jobId': job_id,
            'bucketName': bucket_name,
            'partitionId': partition_id,
            'operation': operation,
            'approximateReceiveCount': approximate_receive_count,
            'timeInQueue': time_in_queue,
            'body': body
        }
    except Exception as e:
        logger.error(f"Error analyzing failed message: {str(e)}")
        return {
            'messageId': record.get('messageId'),
            'error': str(e),
            'rawMessage': record
        }

@tracer.capture_method
def process_record(record: Dict[str, Any]) -> None:
    """
    Process a single SQS record from the DLQ
    
    Args:
        record: SQS record
    """
    try:
        # Analyze the failed message
        analysis = analyze_failed_message(record)
        job_id = analysis.get('jobId', 'unknown')
        partition_id = analysis.get('partitionId', 'unknown')
        operation = analysis.get('operation', 'unknown')
        
        # Generate error ID
        error_id = str(uuid.uuid4())
        
        # Log detailed error information
        error_details = {
            'errorId': error_id,
            'timestamp': datetime.utcnow().isoformat(),
            'jobId': job_id,
            'partitionId': partition_id,
            'operation': operation,
            'messageId': analysis.get('messageId'),
            'approximateReceiveCount': analysis.get('approximateReceiveCount'),
            'timeInQueue': analysis.get('timeInQueue'),
            'errorType': ErrorType.PROCESS_ERROR.value,
            'errorMessage': f"Message failed processing and was sent to DLQ after {analysis.get('approximateReceiveCount')} attempts",
            'ttl': int((datetime.utcnow() + timedelta(days=30)).timestamp())
        }
        
        # Store error in DynamoDB
        dynamodb = boto3.resource('dynamodb')
        error_table = dynamodb.Table(os.environ.get('ERROR_TABLE_NAME'))
        error_table.put_item(Item=error_details)
        
        # Update job counters
        if job_id != 'unknown':
            AssetProcessor.increment_job_counter(job_id, 'errors', 1)
            
        # Update partition counters
        if job_id != 'unknown' and partition_id != 'unknown':
            AssetProcessor.increment_partition_counter(job_id, partition_id, 'errors', 1)
        
        # Record metrics
        metrics.add_metric(name="DLQMessagesProcessed", unit=MetricUnit.Count, value=1)
        
        # Optionally publish to SNS for alerting
        if os.environ.get('STATUS_TOPIC_ARN'):
            sns = get_optimized_client('sns')
            sns.publish(
                TopicArn=os.environ.get('STATUS_TOPIC_ARN'),
                Message=json.dumps({
                    'jobId': job_id,
                    'partitionId': partition_id,
                    'operation': operation,
                    'error': error_details,
                    'timestamp': datetime.utcnow().isoformat()
                }, cls=DecimalEncoder),
                MessageAttributes={
                    'errorType': {
                        'DataType': 'String',
                        'StringValue': 'DLQ_ERROR'
                    }
                }
            )
        
        logger.info(f"Processed DLQ message {analysis.get('messageId')} for job {job_id}, operation {operation}")
        
    except Exception as e:
        logger.error(f"Error processing DLQ record: {str(e)}")
        # We don't re-raise here because we want to continue processing other messages
        # and not send this message back to the DLQ again

@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for DLQ processor
    
    Args:
        event: SQS event
        context: Lambda context
        
    Returns:
        Dict with processing results
    """
    # Process each record from the DLQ
    processed_count = 0
    error_count = 0
    
    for record in event.get('Records', []):
        try:
            process_record(record)
            processed_count += 1
        except Exception as e:
            logger.error(f"Error processing DLQ record: {str(e)}")
            error_count += 1
    
    # Record metrics
    metrics.add_metric(name="DLQMessagesBatchSize", unit=MetricUnit.Count, value=len(event.get('Records', [])))
    
    return {
        'processedCount': processed_count,
        'errorCount': error_count,
        'totalCount': len(event.get('Records', []))
    }