import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize Powertools
logger = Logger(service="delete_user_service")
tracer = Tracer(service="delete_user_service")
metrics = Metrics(namespace="UserManagement", service="delete_user_service")
app = APIGatewayRestResolver()

# Initialize Cognito client
cognito = boto3.client("cognito-idp")
USER_POOL_ID = os.environ["USER_POOL_ID"]


@tracer.capture_method
def delete_cognito_user(user_id: str) -> Dict[str, Any]:
    """
    Delete a user from Cognito user pool

    Args:
        user_id (str): The user ID to delete

    Returns:
        Dict[str, Any]: Response containing status and message
    """
    try:
        cognito.admin_delete_user(UserPoolId=USER_POOL_ID, Username=user_id)

        metrics.add_metric(
            name="UserDeletionSuccessful", unit=MetricUnit.Count, value=1
        )
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": f"User {user_id} successfully deleted", "userId": user_id}
            ),
        }

    except cognito.exceptions.UserNotFoundException:
        logger.warning(f"User {user_id} not found in Cognito user pool")
        metrics.add_metric(name="UserDeletionNotFound", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "User not found", "userId": user_id}),
        }

    except ClientError as e:
        logger.error(f"Failed to delete user {user_id}: {str(e)}")
        metrics.add_metric(name="UserDeletionError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": "Internal server error while deleting user",
                    "userId": user_id,
                }
            ),
        }


@app.delete("/settings/users/<user_id>")
@tracer.capture_method
def handle_delete_user(user_id: str) -> Dict[str, Any]:
    """
    Handle DELETE request to delete a user

    Args:
        user_id (str): The user ID from the path parameter

    Returns:
        Dict[str, Any]: API Gateway response
    """
    logger.info(f"Received request to delete user {user_id}")
    return delete_cognito_user(user_id)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for user deletion

    Args:
        event (Dict[str, Any]): API Gateway event
        context (LambdaContext): Lambda context

    Returns:
        Dict[str, Any]: API Gateway response
    """
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Unhandled exception occurred")
        metrics.add_metric(name="UnhandledExceptions", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"}),
        }
