# lambda/api_handler/handler.py
import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.validation.exceptions import SchemaValidationError

# Import common utilities
import sys
sys.path.append('/opt/python')
from common import (
    AssetProcessor, JobStatus, ErrorType, logger, tracer, metrics,
    get_optimized_client, DecimalEncoder
)

# Initialize AWS Lambda Powertools with proper namespace
logger = Logger(service="connector_sync")
tracer = Tracer(service="connector_sync")
metrics = Metrics(namespace="MediaLake", service="connector_sync")

# JSON Schema for API validation - now all properties are optional
REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "concurrencyLimit": {"type": "integer", "minimum": 1, "maximum": 1000},
        "batchSize": {"type": "integer", "minimum": 1, "maximum": 10000},
        "maxPartitions": {"type": "integer", "minimum": 1, "maximum": 50},
        "objectPrefix": {"type": "string"}
    },
    "additionalProperties": False
}

def api_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format API Gateway response
    
    Args:
        status_code: HTTP status code
        body: Response body
        
    Returns:
        API Gateway response object
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }

@tracer.capture_method
def get_connector_details(connector_id: str) -> Dict[str, Any]:
    """
    Get connector details from DynamoDB
    
    Args:
        connector_id: The connector ID
        
    Returns:
        Connector details or None if not found
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('MEDIALAKE_CONNECTOR_TABLE')
    if not table_name:
        raise ValueError("MEDIALAKE_CONNECTOR_TABLE environment variable is not set")
    
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(Key={"id": connector_id})
    except ClientError as e:
        logger.error(f"Error retrieving connector details: {str(e)}")
        raise
    
    if "Item" not in response:
        return None
    
    return response["Item"]

@tracer.capture_method
def initialize_job(
    connector_id: str,
    bucket_name: str, 
    concurrency_limit: int = 100,
    batch_size: int = 1000,
    max_partitions: int = 10,
    object_prefix: str = None
) -> Dict[str, Any]:
    """
    Initialize a new sync job
    
    Args:
        connector_id: The connector ID
        bucket_name: S3 bucket name
        concurrency_limit: Maximum concurrent Lambda executions
        batch_size: Number of objects per batch
        max_partitions: Maximum number of partitions
        object_prefix: Optional prefix to filter objects
        
    Returns:
        Job details dict
    """
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Calculate TTL for job record (30 days)
    ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
    
    # Create job record
    job_record = {
        'jobId': job_id,
        'connectorId': connector_id,
        'bucketName': bucket_name,
        'objectPrefix': object_prefix,
        'concurrencyLimit': concurrency_limit,
        'batchSize': batch_size,
        'maxPartitions': max_partitions,
        'status': JobStatus.INITIALIZING.value,
        'createTime': datetime.utcnow().isoformat(),
        'lastUpdated': datetime.utcnow().isoformat(),
        'ttl': ttl,
        'stats': {
            'totalObjectsScanned': 0,
            'totalObjectsToProcess': 0,
            'totalObjectsProcessed': 0,
            'partitionsCreated': 0,
            'partitionsCompleted': 0,
            'errors': 0
        }
    }
    
    # Save job record to DynamoDB
    dynamodb = boto3.resource('dynamodb')
    job_table = dynamodb.Table(os.environ.get('MEDIALAKE_ASSET_SYNC_JOB_TABLE_ARN', '').split('/')[-1])
    job_table.put_item(Item=job_record)
    
    logger.info(f"Initialized sync job {job_id} for connector {connector_id} (bucket {bucket_name})")
    metrics.add_metric(name="JobsInitialized", unit=MetricUnit.Count, value=1)
    
    # Start the state machine execution
    sfn = boto3.client('stepfunctions')
    sfn.start_execution(
        stateMachineArn=os.environ['MEDIALAKE_ASSET_SYNC_STATE_MACHINE_ARN'],
        name=f"sync-job-{job_id}",
        input=json.dumps({
            'jobId': job_id,
            'connectorId': connector_id,
            'bucketName': bucket_name,
            'objectPrefix': object_prefix,
            'operation': 'DISCOVER_PARTITIONS',
            'maxPartitions': max_partitions,
            'batchSize': batch_size,
            'concurrencyLimit': concurrency_limit
        })
    )
    
    return job_record

@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for API requests
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    # Parse API Gateway event
    try:
        api_event = APIGatewayProxyEvent(event)
        
        # Extract connector_id from path parameters
        connector_id = api_event.get("pathParameters", {}).get("connector_id")
        if not connector_id:
            logger.error("No connector_id provided in path parameters")
            return api_response(400, {
                "error": "Missing connector ID",
                "message": "Connector ID is required in the path"
            })
        
        # Get connector details from DynamoDB
        connector = get_connector_details(connector_id)
        if not connector:
            logger.error(f"Connector not found with ID: {connector_id}")
            return api_response(404, {
                "error": "Connector not found",
                "message": f"No connector found with ID: {connector_id}"
            })
        
        # Extract bucket name from connector
        bucket_name = connector.get("storageIdentifier")
        if not bucket_name:
            logger.error(f"Invalid connector configuration for ID: {connector_id}")
            return api_response(400, {
                "error": "Invalid connector configuration",
                "message": "Connector does not have a valid bucket name"
            })
        
        # Parse request body if provided, otherwise use empty dict
        body = {}
        if api_event.body:
            try:
                body = json.loads(api_event.body)
                # Validate if body is provided
                validate(event=body, schema=REQUEST_SCHEMA)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in request body: {str(e)}")
                return api_response(400, {
                    "error": "Invalid JSON",
                    "message": "Request body contains invalid JSON"
                })
            except SchemaValidationError as e:
                logger.warning(f"Invalid request: {str(e)}")
                return api_response(400, {
                    "error": "Invalid request parameters",
                    "details": str(e)
                })
        
        # Set default values from connector configuration if available
        default_concurrency_limit = 100
        default_batch_size = 1000
        default_max_partitions = 10
        default_object_prefix = connector.get('objectPrefix')
        
        # Check if connector has any sync configuration
        if 'syncConfig' in connector:
            sync_config = connector.get('syncConfig', {})
            default_concurrency_limit = sync_config.get('concurrencyLimit', default_concurrency_limit)
            default_batch_size = sync_config.get('batchSize', default_batch_size)
            default_max_partitions = sync_config.get('maxPartitions', default_max_partitions)
        
        # Extract parameters with defaults
        concurrency_limit = min(int(body.get('concurrencyLimit', default_concurrency_limit)), 1000)
        batch_size = min(int(body.get('batchSize', default_batch_size)), 10000)
        max_partitions = min(int(body.get('maxPartitions', default_max_partitions)), 50)
        object_prefix = body.get('objectPrefix', default_object_prefix)
        
        # Log the configuration being used
        logger.info(f"Starting sync job for connector {connector_id} with configuration: "
                   f"concurrencyLimit={concurrency_limit}, batchSize={batch_size}, "
                   f"maxPartitions={max_partitions}, objectPrefix={object_prefix}")
        
        # Initialize the job
        job = initialize_job(
            connector_id=connector_id,
            bucket_name=bucket_name,
            concurrency_limit=concurrency_limit,
            batch_size=batch_size,
            max_partitions=max_partitions,
            object_prefix=object_prefix
        )
        
        # Return success response with configuration details
        return api_response(202, {
            "message": "Sync job started successfully",
            "jobId": job['jobId'],
            "status": job['status'],
            "connectorId": connector_id,
            "bucketName": bucket_name,
            "configuration": {
                "concurrencyLimit": concurrency_limit,
                "batchSize": batch_size,
                "maxPartitions": max_partitions,
                "objectPrefix": object_prefix
            }
        })
        
    except Exception as e:
        logger.exception(f"Error processing API request: {str(e)}")
        metrics.add_metric(name="ApiErrors", unit=MetricUnit.Count, value=1)
        
        error_id = str(uuid.uuid4())
        AssetProcessor.log_error(
            AssetProcessor.format_error(
                error_id=error_id,
                object_key="API_REQUEST",
                error_type=ErrorType.UNKNOWN_ERROR,
                error_message=str(e),
                retry_count=0,
                job_id="API_REQUEST",
                bucket_name="N/A"
            )
        )
        
        return api_response(500, {
            "error": "Internal server error",
            "message": str(e),
            "errorId": error_id
        })