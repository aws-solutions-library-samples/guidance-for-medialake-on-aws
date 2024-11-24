from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.logging import correlation_paths
from typing import Dict, Any
import boto3
import json
import os
import uuid
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger(service="user-creation", level="DEBUG")
tracer = Tracer(service="user-creation")
metrics = Metrics(namespace="UserManagement", service="user-creation")
app = APIGatewayRestResolver()

# Initialize Cognito client
cognito = boto3.client("cognito-idp")

# Get environment variables
USER_POOL_ID = os.environ["USER_POOL_ID"]
APP_CLIENT_ID = os.environ["APP_CLIENT_ID"]


@tracer.capture_method
def generate_temporary_password() -> str:
    """Generate a secure temporary password"""
    return f"Welcome1!{uuid.uuid4().hex[:8]}"


@app.post("/settings/users/user")
@tracer.capture_method
def create_user():
    """Create a new user in Cognito user pool"""
    try:
        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug("Request data", extra={"request_data": request_data})

        # Generate temporary password
        temp_password = generate_temporary_password()
        logger.debug("Generated temporary password")

        # Prepare user attributes
        user_attributes = [
            {"Name": "email", "Value": request_data["email"]},
            {"Name": "email_verified", "Value": "true"},
            # {"Name": "name", "Value": request_data["given_name"]},
            # {"Name": "family_name", "Value": request_data["family_name"]},
            # {"Name": "custom:role", "Value": request_data["role"]},
        ]
        logger.debug("Prepared user attributes", extra={"attributes": user_attributes})

        # Create user in Cognito
        response = cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=request_data["email"],
            UserAttributes=user_attributes,
            TemporaryPassword=temp_password,
        )
        logger.debug(
            "Cognito user creation successful", extra={"cognito_response": response}
        )

        # Add user to group based on role
        # cognito.admin_add_user_to_group(
        #     UserPoolId=USER_POOL_ID,
        #     Username=request_data["email"],
        #     GroupName=request_data["role"],
        # )
        logger.debug("Successfully added user to group")

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulUserCreations", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "message": "User created successfully",
                    "username": request_data["email"],
                    "userStatus": response["User"]["UserStatus"],
                    "temporary_password": temp_password,
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            "Cognito client error during user creation",
            extra={
                "error_code": error_code,
                "error_message": error_message,
                "user_email": request_data.get("email"),
                "stack_trace": True,
            },
        )

        metrics.add_metric(name="FailedUserCreations", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": (
                400
                if error_code
                in ["UsernameExistsException", "InvalidParameterException"]
                else 500
            ),
            "body": json.dumps({"error": error_code, "message": error_message}),
        }

    except Exception as e:
        logger.exception(
            "Unexpected error during user creation",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred",
                }
            ),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug("Lambda handler invoked", extra={"event": event})
    return app.resolve(event, context)
