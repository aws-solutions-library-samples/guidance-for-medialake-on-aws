import os
import boto3
import json
import uuid
from common import logger, AssetProcessor, JobStatus, ErrorType

def lambda_handler(event, context):
    try:
        job_id = event['jobId']
        bucket_name = event['bucketName']
        concurrency_limit = event.get('concurrencyLimit', 20)
        query_result = event['queryResult']
        objects = query_result['objectsToProcess']
        
        if not objects:
            logger.info(f"No objects to process for job {job_id}")
            return {
                'processedCount': 0,
                'batchCount': 0
            }
        
        # Get SQS queue URL from environment
        sqs = boto3.client('sqs')
        queue_url = os.environ['PROCESSING_QUEUE_URL']
        
        # Split objects into chunks based on concurrency limit
        chunks = AssetProcessor.chunk_list(objects, min(len(objects), 10))  # Max 10 objects per message
        batch_count = len(chunks)
        
        logger.info(f"Processing {len(objects)} objects in {batch_count} batches for job {job_id}")
        
        # Update job status
        status_msg = f"Sending {len(objects)} objects to processing queue"
        AssetProcessor.update_job_status(job_id, JobStatus.PROCESSING, status_msg)
        
        # Send messages to SQS
        error_count = 0
        for i, chunk in enumerate(chunks):
            try:
                # Send message to SQS
                message_body = json.dumps({
                    'jobId': job_id,
                    'bucketName': bucket_name,
                    'objects': chunk,
                    'batchNumber': i + 1,
                    'totalBatches': batch_count
                })
                
                sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=message_body,
                    MessageAttributes={
                        'JobId': {
                            'DataType': 'String',
                            'StringValue': job_id
                        },
                        'BatchNumber': {
                            'DataType': 'Number',
                            'StringValue': str(i + 1)
                        }
                    }
                )
                
                logger.info(f"Sent batch {i+1}/{batch_count} with {len(chunk)} objects for job {job_id}")
                
            except Exception as e:
                error_count += 1
                error_id = str(uuid.uuid4())
                error_details = AssetProcessor.format_error(
                    error_id,
                    "batch-" + str(i),
                    ErrorType.SQS_SEND_ERROR,
                    str(e),
                    0,
                    job_id,
                    bucket_name
                )
                AssetProcessor.log_error(error_details)
        
        # Update job statistics if there were errors
        if error_count > 0:
            AssetProcessor.increment_job_counter(job_id, 'errors', error_count)
        
        return {
            'processedCount': len(objects),
            'batchCount': batch_count,
            'errorCount': error_count
        }
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_details = AssetProcessor.format_error(
            error_id,
            "N/A",
            ErrorType.SQS_SEND_ERROR,
            str(e),
            0,
            event.get('jobId', 'unknown'),
            event.get('bucketName', 'unknown')
        )
        AssetProcessor.log_error(error_details)
        
        # Update job status to reflect error
        AssetProcessor.update_job_status(
            event.get('jobId', 'unknown'),
            JobStatus.FAILED,
            f"Failed to send messages to processing queue: {str(e)}"
        )
        
        raise
