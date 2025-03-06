import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayProxyEvent

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()

# Initialize clients
step_functions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')

class JobStatus:
    INITIALIZING = "INITIALIZING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext):
    """
    API handler that starts the state machine asynchronously and returns immediately.
    Gets connector ID from path parameter, looks up the S3 bucket in the connector table,
    and then starts the step function job.
    """
    try:
        # Extract connector ID from path parameters
        connector_id = event.get("pathParameters", {}).get("connector_id")
        
        if not connector_id:
            logger.error("No connector_id provided in path parameters")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Connector ID is required'})
            }
        
        # Look up connector details in DynamoDB
        connector_table = dynamodb.Table(os.environ['MEDIALAKE_CONNECTOR_TABLE'])
        response = connector_table.get_item(Key={"id": connector_id})
        
        if 'Item' not in response:
            logger.error(f"Connector with ID {connector_id} not found")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': f'Connector with ID {connector_id} not found'})
            }
        
        connector = response['Item']
        bucket_name = connector.get('storageIdentifier')
        
        if not bucket_name:
            logger.error(f"Connector {connector_id} has no associated S3 bucket")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Connector has no associated S3 bucket'})
            }
        
        # Log the bucket name for debugging
        logger.info(f"Retrieved bucket name: {bucket_name}")
        
        # Extract configuration parameters from request body with defaults
        body = event.get('body')
        if body is None:
            body = {}
        elif isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {}
            
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Get configuration parameters with defaults
        concurrency_limit = min(int(body.get('concurrencyLimit', 20)), 100)  # Cap at 100
        batch_size = min(int(body.get('batchSize', 500)), 10000)  # Cap at 10,000
        
        # Get object prefix from connector if available
        object_prefix = connector.get('objectPrefix', '')
        
        # Initialize job record in DynamoDB
        job_table = dynamodb.Table(os.environ['MEDIALAKE_ASSET_SYNC_JOB_TABLE_ARN'].split('/')[-1])
        job_record = {
            'jobId': job_id,
            'connectorId': connector_id,
            'bucketName': bucket_name,
            'objectPrefix': object_prefix,
            'concurrencyLimit': concurrency_limit,
            'batchSize': batch_size,
            'status': JobStatus.INITIALIZING,
            'createTime': datetime.utcnow().isoformat(),
            'lastUpdated': datetime.utcnow().isoformat(),
            'ttl': int((datetime.utcnow() + timedelta(days=30)).timestamp()),
            'stats': {
                'totalObjectsScanned': 0,
                'objectsToProcess': 0,
                'objectsProcessed': 0,
                'errors': 0
            }
        }
        job_table.put_item(Item=job_record)
        
        # Start the state machine execution asynchronously
        state_machine_arn = os.environ['MEDIALAKE_ASSET_SYNC_STATE_MACHINE_ARN']
        input_data = {
            'jobId': job_id,
            'connectorId': connector_id,
            'bucketName': bucket_name,
            'objectPrefix': object_prefix,
            'concurrencyLimit': concurrency_limit,
            'batchSize': batch_size,
            'continuationToken': ""
        }
        
        # Log the input data for debugging
        logger.info(f"State machine input: {json.dumps(input_data)}")
        
        step_functions.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"AssetSync-{job_id}",
            input=json.dumps(input_data)
        )
        
        logger.info(f"Started sync job {job_id} for connector {connector_id} (bucket: {bucket_name})")
        
        # Return immediately with job ID for tracking
        return {
            'statusCode': 202,  # Accepted
            'body': json.dumps({
                'jobId': job_id,
                'connectorId': connector_id,
                'status': JobStatus.INITIALIZING,
                'message': 'Sync job started successfully',
                'bucketName': bucket_name,
                'objectPrefix': object_prefix,
            })
        }
    except Exception as e:
        logger.exception(f"Error starting sync job: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Failed to start sync job: {str(e)}"})
        }