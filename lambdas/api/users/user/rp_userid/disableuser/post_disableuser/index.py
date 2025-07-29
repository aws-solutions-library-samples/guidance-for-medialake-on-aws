import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayProxyEvent
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(service="user-management", level=os.getenv("LOG_LEVEL", "INFO"))
tracer = Tracer(service="user-management")
metrics = Metrics(namespace="UserManagement", service="user-service")

# Initialize Cognito client with X-Ray tracing
session = boto3.Session()
cognito = session.client("cognito-idp")


class DisableUserRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="The user ID to disable")


class CognitoError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to disable a user in Cognito User Pool

    Parameters:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response object
    """
    try:
        # Extract user_id from path parameters
        user_id = event.get("pathParameters", {}).get("user_id")
        if not user_id:
            logger.error("Missing user_id in path parameters")
            return {
                "statusCode": 400,
                "body": '{"message": "Missing user_id parameter"}',
            }

        # Validate user_id using Pydantic
        DisableUserRequest(user_id=user_id)

        # Get User Pool ID from environment variables
        user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
        if not user_pool_id:
            logger.error("COGNITO_USER_POOL_ID environment variable not set")
            raise CognitoError("Configuration error", 500)

        logger.debug(
            {
                "message": "Attempting to disable user",
                "user_id": user_id,
                "user_pool_id": user_pool_id,
            }
        )

        # Disable user in Cognito
        @tracer.capture_method
        def disable_user():
            return cognito.admin_disable_user(UserPoolId=user_pool_id, Username=user_id)

        response = disable_user()
        logger.info(response)

        # Add custom metrics
        metrics.add_metric(name="UserDisabled", unit=MetricUnit.Count, value=1)

        logger.info(
            {
                "message": "Successfully disabled user",
                "user_id": user_id,
                "operation": "disable_user",
                "status": "success",
            }
        )

        return {"statusCode": 200, "body": '{"message": "User successfully disabled"}'}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(
            {
                "message": "Cognito client error",
                "error_code": error_code,
                "error_message": error_message,
                "user_id": user_id,
            }
        )

        metrics.add_metric(name="UserDisableError", unit=MetricUnit.Count, value=1)

        if error_code == "UserNotFoundException":
            return {"statusCode": 404, "body": '{"message": "User not found"}'}

        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error while disabling user",
                "error": str(e),
                "user_id": user_id,
            }
        )

        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)

        return {"statusCode": 500, "body": '{"message": "Internal server error"}'}
