from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from boto3.session import Session
import boto3
from typing import Dict, Any, Optional
import os
from aws_lambda_powertools.utilities.validation import validate_input
import json

# Initialize PowerTools
logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()

# Initialize AWS clients with X-Ray tracing
session = Session()
cognito = session.client('cognito-idp')

# Constants
USER_POOL_ID = os.environ['USER_POOL_ID']
MAX_RESULTS = 60  # AWS Cognito limit is 60

# Input schema for validation
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "queryStringParameters": {
            "type": "object",
            "properties": {
                "pageSize": {"type": "string", "pattern": "^[0-9]+$"},
                "paginationToken": {"type": "string"}
            }
        }
    }
}

@tracer.capture_method
def get_user_attributes(user: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and format user attributes."""
    attributes = {}
    for attr in user.get('Attributes', []):
        attributes[attr['Name']] = attr['Value']
    
    return {
        'username': user.get('Username'),
        'enabled': user.get('Enabled', False),
        'status': user.get('UserStatus'),
        'created': user.get('UserCreateDate').isoformat() if user.get('UserCreateDate') else None,
        'modified': user.get('UserLastModifiedDate').isoformat() if user.get('UserLastModifiedDate') else None,
        'email': attributes.get('email'),
        'email_verified': attributes.get('email_verified'),
        'given_name': attributes.get('given_name'),
        'family_name': attributes.get('family_name'),
        'groups': user.get('Groups', [])
    }

@app.get("/users")
@tracer.capture_method
def get_users():
    """Get users from Cognito user pool with pagination support."""
    try:
        # Get query parameters
        query_params = app.current_event.query_string_parameters or {}
        page_size = min(int(query_params.get('pageSize', MAX_RESULTS)), MAX_RESULTS)
        pagination_token = query_params.get('paginationToken')

        # Start timing the Cognito API call
        with tracer.provider.in_subsegment('## cognito-list-users') as subsegment:
            params = {
                'UserPoolId': USER_POOL_ID,
                'Limit': page_size,
                'AttributesToGet': [
                    'email',
                    'email_verified',
                    'given_name',
                    'family_name'
                ]
            }
            
            if pagination_token:
                params['PaginationToken'] = pagination_token

            response = cognito.list_users(**params)
            
            # Add metadata to the subsegment
            subsegment.put_metadata('page_size', page_size)
            subsegment.put_metadata('has_pagination_token', bool(pagination_token))

        # Process users
        users = [get_user_attributes(user) for user in response.get('Users', [])]
        
        # Record metrics
        metrics.add_metric(name="UsersRetrieved", unit=MetricUnit.Count, value=len(users))
        
        # Prepare response
        result = {
            'users': users,
            'pagination': {
                'pageSize': page_size,
                'count': len(users)
            }
        }

        # Add pagination token if more results exist
        if 'PaginationToken' in response:
            result['pagination']['nextToken'] = response['PaginationToken']

        logger.info(f"Successfully retrieved {len(users)} users")
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.exception("Error retrieving users")
        metrics.add_metric(name="UsersRetrievalError", unit=MetricUnit.Count, value=1)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler with AWS PowerTools decorators for observability."""
    try:
        validate_input(event=event, schema=INPUT_SCHEMA)
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Error processing request")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
