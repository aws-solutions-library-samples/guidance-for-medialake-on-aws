import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
from common import logger, AssetProcessor, JobStatus

def handle(event, context):
    try:
        # Extract parameters from the API request
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
            
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Extract configuration parameters with defaults
        bucket_name = body.get('bucketName')
        if not bucket_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'bucketName is required'})
            }
            
        concurrency_limit = min(int(body.get('concurrencyLimit', 20)), 100)  # Cap at 100
        batch_size = min(int(body.get('batchSize', 1000)), 10000)  # Cap at 10,000
        
        # Calculate TTL for job record (30 days)
        ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        
        # Create job record
        job_record = {
            'jobId': job_id,
            'bucketName': bucket_name,
            'concurrencyLimit': concurrency_limit,
            'batchSize': batch_size,
            'status': JobStatus.INITIALIZING,
            'createTime': datetime.utcnow().isoformat(),
            'lastUpdated': datetime.utcnow().isoformat(),
            'ttl': ttl,
            'stats': {
                'totalObjectsScanned': 0,
                'objectsToProcess': 0,
                'objectsProcessed': 0,
                'errors': 0
            }
        }
        
        # Save job record to DynamoDB
        dynamodb = boto3.resource('dynamodb')
        job_table = dynamodb.Table(os.environ['JOB_TABLE_NAME'])
        job_table.put_item(Item=job_record)
        
        logger.info(f"Initialized sync job {job_id} for bucket {bucket_name}")
        
        return {
            'jobId': job_id,
            'bucketName': bucket_name,
            'concurrencyLimit': concurrency_limit,
            'batchSize': batch_size
        }
    except Exception as e:
        logger.error(f"Error initializing job: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Failed to initialize job: {str(e)}"})
        }
