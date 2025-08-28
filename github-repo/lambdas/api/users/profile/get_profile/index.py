import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser.models import APIGatewayProxyEventModel
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(service="user-profile-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="user-profile-service")
metrics = Metrics(namespace="medialake", service="users-profile-get")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class ProfileResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="User profile data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEventModel, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user profile from DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
        # The authorizer context contains the user's identity
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})

        # Get the user ID from the Cognito claims
        user_id = claims.get("sub")

        if not user_id:
            logger.error("Missing user_id in Cognito claims")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Unable to identify user")

        # Get the user table name from environment variable
        user_table_name = os.getenv("USER_TABLE_NAME")
        if not user_table_name:
            logger.error("USER_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Fetch user profile from DynamoDB
        user_profile = _get_user_profile(user_table_name, user_id)

        # Create success response
        response = ProfileResponse(
            status="200",
            message="User profile retrieved successfully",
            data=user_profile,
        )

        logger.info("Successfully retrieved user profile", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulProfileLookup", unit=MetricUnit.Count, value=1
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")


@tracer.capture_method
def _get_user_profile(table_name: str, user_id: str) -> Dict[str, Any]:
    """
    Fetch user profile from DynamoDB
    """
    try:
        # Format the userId and itemKey according to the schema
        formatted_user_id = f"USER#{user_id}"
        item_key = "PROFILE"

        table = dynamodb.Table(table_name)
        response = table.get_item(
            Key={"userId": formatted_user_id, "itemKey": item_key}
        )

        # Check if the item exists
        if "Item" not in response:
            logger.warning(f"User profile not found", extra={"user_id": user_id})
            metrics.add_metric(name="ProfileNotFound", unit=MetricUnit.Count, value=1)

            # Return an empty profile if not found
            return {
                "userId": user_id,
                "displayName": "",
                "email": "",
                "createdAt": "",
                "updatedAt": "",
                "preferences": {},
            }

        # Return the profile data
        item = response["Item"]

        # Remove the PK and SK from the returned data
        if "userId" in item:
            del item["userId"]
        if "itemKey" in item:
            del item["itemKey"]

        # Add the user ID without the prefix
        item["userId"] = user_id

        return item

    except ClientError as e:
        logger.error(f"DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def _create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create standardized error response
    """
    error_response = ErrorResponse(status=str(status_code), message=message, data={})

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": error_response.model_dump_json(),
    }
