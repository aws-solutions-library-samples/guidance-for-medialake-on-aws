from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.logging import correlation_paths
from typing import Dict, Any
import boto3
import json
import os
import uuid
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="user-creation",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="user-creation")
metrics = Metrics(namespace="medialake", service="user-creation")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize Cognito client
cognito = boto3.client("cognito-idp")

# Get environment variables
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]


@tracer.capture_method
def generate_temporary_password() -> str:
    """Generate a secure temporary password"""
    return f"Welcome1!{uuid.uuid4().hex[:8]}"


@app.post("/users/user")
@tracer.capture_method
def create_user():
    """Create a new user in Cognito user pool"""
    try:
        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing user creation request",
                "request_data": request_data,
                "operation": "create_user",
            }
        )

        # Generate temporary password
        temp_password = generate_temporary_password()
        logger.debug(
            {
                "message": "Generated temporary password",
                "operation": "password_generation",
            }
        )

        # Prepare user attributes with only required fields
        user_attributes = [
            {"Name": "email", "Value": request_data["email"]},
            {"Name": "email_verified", "Value": "true"},
        ]

        # Add optional attributes if they exist
        if "name" in request_data:
            user_attributes.append({"Name": "name", "Value": request_data["name"]})
        if "family_name" in request_data:
            user_attributes.append(
                {"Name": "family_name", "Value": request_data["family_name"]}
            )

        logger.debug(
            {
                "message": "Prepared user attributes",
                "attributes": user_attributes,
                "operation": "attribute_preparation",
            }
        )

        # Create user in Cognito
        response = cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=request_data["email"],
            UserAttributes=user_attributes,
            TemporaryPassword=temp_password,
        )
        logger.info(
            {
                "message": "User created successfully in Cognito",
                "username": request_data["email"],
                "user_status": response["User"]["UserStatus"],
                "operation": "cognito_create_user",
            }
        )

        # Log success metrics
        metrics.add_metric(
            name="SuccessfulUserCreations", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "status": 201,
                    "message": "User created successfully",
                    "data": {
                        "username": request_data["email"],
                        "userStatus": response["User"]["UserStatus"],
                    },
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        (
            logger.warning(
                {
                    "message": "Cognito client error during user creation",
                    "error_code": error_code,
                    "error_message": error_message,
                    "user_email": request_data.get("email"),
                    "operation": "cognito_create_user",
                    "status": "failed",
                }
            )
            if error_code in ["UsernameExistsException", "InvalidParameterException"]
            else logger.error(
                {
                    "message": "Severe Cognito client error during user creation",
                    "error_code": error_code,
                    "error_message": error_message,
                    "user_email": request_data.get("email"),
                    "operation": "cognito_create_user",
                    "status": "failed",
                }
            )
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
        logger.error(
            {
                "message": "Unexpected error during user creation",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "create_user",
                "status": "failed",
            }
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
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
