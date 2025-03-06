import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.validation.exceptions import SchemaValidationError
from common import logger, AssetProcessor, JobStatus

# Define JSON schema for input validation
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "jobId": {"type": "string"},
        "connectorId": {"type": "string"},
        "bucketName": {"type": "string"},
        "objectPrefix": {"type": ["string", "null"]},
        "concurrencyLimit": {"type": "integer", "minimum": 1, "maximum": 100},
        "batchSize": {"type": "integer", "minimum": 1, "maximum": 10000},
        "continuationToken": {"type": ["string", "null"]}
    },
    "required": ["bucketName"],
    "additionalProperties": True
}

def lambda_handler(event, context):
    try:
        # Validate input against schema
        try:
            validate(event=event, schema=INPUT_SCHEMA)
        except SchemaValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return {
                'jobId': None,
                'bucketName': None,
                'concurrencyLimit': 20,
                'batchSize': 1000,
                'error': str(e),
                'statusCode': 400
            }
            
        # Extract configuration parameters with defaults
        bucket_name = event.get('bucketName')
        connector_id = event.get('connectorId')
        object_prefix = event.get('objectPrefix')
        
        # Use provided job ID if available, otherwise generate a new one
        job_id = event.get('jobId') or str(uuid.uuid4())
        
        concurrency_limit = min(int(event.get('concurrencyLimit', 20)), 100)  # Cap at 100
        batch_size = min(int(event.get('batchSize', 1000)), 10000)  # Cap at 10,000
        
        # Calculate TTL for job record (30 days)
        ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        
        # Create job record
        job_record = {
            'jobId': job_id,
            'bucketName': bucket_name,
            'connectorId': connector_id,
            'objectPrefix': object_prefix,
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
            'batchSize': batch_size,
            'continuationToken': '',
            'statusCode': 200
        }
    except Exception as e:
        logger.error(f"Error initializing job: {str(e)}")
        return {
            'jobId': event.get('jobId'),
            'bucketName': event.get('bucketName'),
            'concurrencyLimit': event.get('concurrencyLimit', 20),
            'batchSize': event.get('batchSize', 1000),
            'error': f"Failed to initialize job: {str(e)}",
            'statusCode': 500,
            'continuationToken': ''
        }