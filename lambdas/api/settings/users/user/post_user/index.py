from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate_input
from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.metrics import MetricUnit
from typing import Dict, Any
import boto3
import json
import os
import uuid
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger(service="user-creation")
tracer = Tracer(service="user-creation")
metrics = Metrics(namespace="UserManagement", service="user-creation")
app = APIGatewayRestResolver()

# Initialize Cognito client
cognito = boto3.client('cognito-idp')

# Get environment variables
USER_POOL_ID = os.environ['USER_POOL_ID']
APP_CLIENT_ID = os.environ['APP_CLIENT_ID']

# Schema for request validation
create_user_schema = {
    "type": "object",
    "properties": {
        "email": {"type": "string", "format": "email"},
        "given_name": {"type": "string", "minLength": 1},
        "family_name": {"type": "string", "minLength": 1},
        "role": {"type": "string", "enum": ["admin", "user", "viewer"]},
    },
    "required": ["email", "given_name", "family_name", "role"]
}

@tracer.capture_method
def generate_temporary_password() -> str:
    """Generate a secure temporary password"""
    return f"Welcome1!{uuid.uuid4().hex[:8]}"

@app.post("/users")
@tracer.capture_method
@metrics.log_metrics(capture_cold_start_metric=True)
@validate_input(schema=create_user_schema)
def create_user() -> Dict[str, Any]:
    """Create a new user in Cognito user pool"""
    try:
        # Parse request body
        request_data = app.current_event.json_body
        
        # Generate temporary password
        temp_password = generate_temporary_password()
        
        # Prepare user attributes
        user_attributes = [
            {'Name': 'email', 'Value': request_data['email']},
            {'Name': 'email_verified', 'Value': 'true'},
            {'Name': 'given_name', 'Value': request_data['given_name']},
            {'Name': 'family_name', 'Value': request_data['family_name']},
            {'Name': 'custom:role', 'Value': request_data['role']}
        ]

        # Create user in Cognito
        response = cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=request_data['email'],
            UserAttributes=user_attributes,
            TemporaryPassword=temp_password,
            MessageAction='SUPPRESS'  # Suppress automatic email
        )

        # Add user to group based on role
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=request_data['email'],
            GroupName=request_data['role']
        )

        # Log success metrics
        metrics.add_metric(name="SuccessfulUserCreations", unit=MetricUnit.Count, value=1)
        
        logger.info("User created successfully", extra={
            "user_email": request_data['email'],
            "role": request_data['role']
        })

        return {
            "statusCode": 201,
            "body": json.dumps({
                "message": "User created successfully",
                "username": request_data['email'],
                "userStatus": response['User']['UserStatus'],
                "temporary_password": temp_password  # In production, send this via secure channel
            })
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        # Log error metrics
        metrics.add_metric(name="FailedUserCreations", unit=MetricUnit.Count, value=1)
        
        logger.error(f"Failed to create user: {error_code}", 
                    extra={
                        "error_message": error_message,
                        "error_code": error_code
                    })

        return {
            "statusCode": 400 if error_code in ['UsernameExistsException', 'InvalidParameterException'] else 500,
            "body": json.dumps({
                "error": error_code,
                "message": error_message
            })
        }

    except Exception as e:
        # Log unexpected errors
        logger.exception("Unexpected error during user creation")
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "InternalServerError",
                "message": "An unexpected error occurred"
            })
        }

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    return app.resolve(event, context)
