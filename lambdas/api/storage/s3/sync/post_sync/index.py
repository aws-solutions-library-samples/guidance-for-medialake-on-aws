import os
import json
import boto3
import uuid
from datetime import datetime
from common import logger, AssetProcessor, JobStatus

# Initialize clients
step_functions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')

def handle(event, context):
    """
    API handler that starts the state machine asynchronously and returns immediately
    """
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
        
        # Initialize job record in DynamoDB
        job_table = dynamodb.Table(os.environ['JOB_TABLE_NAME'])
        job_record = {
            'jobId': job_id,
            'bucketName': bucket_name,
            'concurrencyLimit': concurrency_limit,
            'batchSize': batch_size,
            'status': JobStatus.INITIALIZING,
            'createTime': datetime.utcnow().isoformat(),
            'lastUpdated': datetime.utcnow().isoformat(),
            'ttl': int((datetime.utcnow() + datetime.timedelta(days=30)).timestamp()),
            'stats': {
                'totalObjectsScanned': 0,
                'objectsToProcess': 0,
                'objectsProcessed': 0,
                'errors': 0
            }
        }
        job_table.put_item(Item=job_record)
        
        # Start the state machine execution asynchronously
        state_machine_arn = os.environ['STATE_MACHINE_ARN']
        input_data = {
            'jobId': job_id,
            'bucketName': bucket_name,
            'concurrencyLimit': concurrency_limit,
            'batchSize': batch_size
        }
        
        step_functions.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"AssetSync-{job_id}",
            input=json.dumps(input_data)
        )
        
        logger.info(f"Started sync job {job_id} for bucket {bucket_name}")
        
        # Return immediately with job ID for tracking
        return {
            'statusCode': 202,  # Accepted
            'body': json.dumps({
                'jobId': job_id,
                'status': JobStatus.INITIALIZING,
                'message': 'Sync job started successfully',
                'bucketName': bucket_name
            })
        }
    except Exception as e:
        logger.error(f"Error starting sync job: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Failed to start sync job: {str(e)}"})
        }