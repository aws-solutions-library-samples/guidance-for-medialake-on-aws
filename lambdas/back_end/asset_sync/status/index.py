# lambda/job_status/handler.py
import os
import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from boto3.dynamodb.conditions import Key, Attr

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
    AssetProcessor, JobStatus, PartitionStatus, ErrorType, logger, tracer, metrics,
    get_optimized_client, DecimalEncoder
)

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
def get_job_details(job_id: str, include_partitions: bool = False, include_errors: bool = False) -> Dict[str, Any]:
    """
    Get job details
    
    Args:
        job_id: Job ID
        include_partitions: Whether to include partition details
        include_errors: Whether to include error details
        
    Returns:
        Job details dict
    """
    dynamodb = boto3.resource('dynamodb')
    job_table = dynamodb.Table(os.environ.get('JOB_TABLE_NAME'))
    
    # Get job details
    response = job_table.get_item(Key={'jobId': job_id})
    job = response.get('Item', {})
    
    if not job:
        return {}
    
    result = {
        'jobId': job_id,
        'status': job.get('status'),
        'bucketName': job.get('bucketName'),
        'createTime': job.get('createTime'),
        'lastUpdated': job.get('lastUpdated'),
        'stats': job.get('stats', {}),
        'statusMessage': job.get('statusMessage')
    }
    
    # Include partition details if requested
    if include_partitions:
        partition_table = dynamodb.Table(os.environ.get('PARTITION_TABLE_NAME'))
        
        # Query for all partitions
        partition_response = partition_table.query(
            KeyConditionExpression=Key('jobId').eq(job_id)
        )
        
        partitions = partition_response.get('Items', [])
        
        # Handle pagination for large result sets
        while 'LastEvaluatedKey' in partition_response:
            partition_response = partition_table.query(
                KeyConditionExpression=Key('jobId').eq(job_id),
                ExclusiveStartKey=partition_response['LastEvaluatedKey']
            )
            
            partitions.extend(partition_response.get('Items', []))
        
        result['partitions'] = partitions
    
    # Include error details if requested
    if include_errors:
        error_table = dynamodb.Table(os.environ.get('ERROR_TABLE_NAME'))
        
        # Query for errors
        error_response = error_table.query(
            KeyConditionExpression=Key('jobId').eq(job_id),
            Limit=100  # Limit to 100 most recent errors
        )
        
        errors = error_response.get('Items', [])
        
        result['errors'] = {
            'count': len(errors),
            'items': errors,
            'hasMore': 'LastEvaluatedKey' in error_response
        }
    
    return result

@tracer.capture_method
def get_partition_details(job_id: str, partition_id: str) -> Dict[str, Any]:
    """
    Get partition details
    
    Args:
        job_id: Job ID
        partition_id: Partition ID
        
    Returns:
        Partition details dict
    """
    dynamodb = boto3.resource('dynamodb')
    partition_table = dynamodb.Table(os.environ.get('PARTITION_TABLE_NAME'))
    
    # Get partition details
    response = partition_table.get_item(Key={'jobId': job_id, 'partitionId': partition_id})
    partition = response.get('Item', {})
    
    if not partition:
        return {}
    
    return partition

@tracer.capture_method
def get_paginated_errors(
    job_id: str, 
    limit: int = 100, 
    last_evaluated_key: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get paginated error details
    
    Args:
        job_id: Job ID
        limit: Maximum number of errors to return
        last_evaluated_key: Last evaluated key for pagination
        
    Returns:
        Paginated error details
    """
    dynamodb = boto3.resource('dynamodb')
    error_table = dynamodb.Table(os.environ.get('ERROR_TABLE_NAME'))
    
    # Query parameters
    query_params = {
        'KeyConditionExpression': Key('jobId').eq(job_id),
        'Limit': limit,
        'ScanIndexForward': False  # Most recent errors first
    }
    
    if last_evaluated_key:
        query_params['ExclusiveStartKey'] = last_evaluated_key
    
    # Query for errors
    error_response = error_table.query(**query_params)
    
    errors = error_response.get('Items', [])
    
    result = {
        'count': len(errors),
        'items': errors,
        'hasMore': 'LastEvaluatedKey' in error_response
    }
    
    if 'LastEvaluatedKey' in error_response:
        result['lastEvaluatedKey'] = error_response['LastEvaluatedKey']
    
    return result

@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for job status API
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    try:
        # Parse API Gateway event
        api_event = APIGatewayProxyEvent(event)
        
        # Extract path parameters
        path_params = api_event.path_parameters or {}
        job_id = path_params.get('jobId')
        
        if not job_id:
            return api_response(400, {
                'error': 'Missing job ID'
            })
        
        # Extract query string parameters
        query_params = api_event.query_string_parameters or {}
        include_partitions = query_params.get('includePartitions', 'false').lower() == 'true'
        include_errors = query_params.get('includeErrors', 'false').lower() == 'true'
        partition_id = query_params.get('partitionId')
        error_limit = min(int(query_params.get('errorLimit', '100')), 1000)
        
        # Parse last evaluated key if provided
        last_evaluated_key = None
        if 'errorLastKey' in query_params:
            try:
                last_evaluated_key = json.loads(query_params.get('errorLastKey', '{}'))
            except ValueError:
                return api_response(400, {
                    'error': 'Invalid errorLastKey format'
                })
        
        # If partition ID is provided, return partition details
        if partition_id:
            partition = get_partition_details(job_id, partition_id)
            
            if not partition:
                return api_response(404, {
                    'error': 'Partition not found'
                })
            
            return api_response(200, partition)
        
        # If error pagination is requested
        if include_errors and 'errorsOnly' in query_params:
            errors = get_paginated_errors(job_id, error_limit, last_evaluated_key)
            
            return api_response(200, errors)
        
        # Get job details
        job = get_job_details(job_id, include_partitions, include_errors)
        
        if not job:
            return api_response(404, {
                'error': 'Job not found'
            })
        
        # Record metrics
        metrics.add_metric(name="JobStatusRequests", unit=MetricUnit.Count, value=1)
        
        return api_response(200, job)
        
    except Exception as e:
        logger.exception(f"Error getting job status: {str(e)}")
        
        # Record error metrics
        metrics.add_metric(name="JobStatusErrors", unit=MetricUnit.Count, value=1)
        
        return api_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })