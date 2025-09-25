import json
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
logger = Logger(service="user-service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="user-service")
metrics = Metrics(namespace="medialake", service="users-userid-put")

# Initialize Cognito client
cognito = boto3.client("cognito-idp")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class UserResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="User data from Cognito")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEventModel, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to update user details in Cognito User Pool
    """
    try:
        # Extract user_id from path parameters
        user_id = event.get("pathParameters", {}).get("user_id")

        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return _create_error_response(400, "Invalid request body")

        if not user_id:
            logger.error("Missing user_id in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing user_id parameter")

        # Get Cognito User Pool ID from environment variable
        user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
        if not user_pool_id:
            logger.error("COGNITO_USER_POOL_ID environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Update user attributes in Cognito
        updated_user = _update_cognito_user(user_pool_id, user_id, body)

        # Create success response
        response = UserResponse(
            status="200",
            message="User details updated successfully",
            data=updated_user,
        )

        logger.info("Successfully updated user details", extra={"user_id": user_id})
        metrics.add_metric(name="SuccessfulUserUpdate", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, str(e))


@tracer.capture_method
def _update_cognito_user(
    user_pool_id: str, user_id: str, update_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update user attributes in Cognito User Pool
    """
    try:
        # Prepare user attributes for update
        user_attributes = []

        # Map frontend fields to Cognito attributes
        attribute_mapping = {
            "given_name": "given_name",  # Using given_name instead of name
            "family_name": "family_name",
            "email": "email",
            "phone_number": "phone_number",
        }

        for frontend_field, cognito_attr in attribute_mapping.items():
            if frontend_field in update_data:
                user_attributes.append(
                    {"Name": cognito_attr, "Value": update_data[frontend_field]}
                )

        if user_attributes:
            # Update user attributes
            cognito.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=user_id,
                UserAttributes=user_attributes,
            )

            # Get updated user details
            response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_id)

            # Transform Cognito response into a cleaner format
            updated_attributes = {
                attr["Name"]: attr["Value"]
                for attr in response.get("UserAttributes", [])
            }

            return {
                "username": response.get("Username"),
                "user_status": response.get("UserStatus"),
                "enabled": response.get("Enabled", False),
                "user_created": response.get("UserCreateDate").isoformat(),
                "last_modified": response.get("UserLastModifiedDate").isoformat(),
                "attributes": updated_attributes,
            }
        else:
            raise ValueError("No valid attributes provided for update")

    except cognito.exceptions.UserNotFoundException:
        logger.warning(f"User not found", extra={"user_id": user_id})
        metrics.add_metric(name="UserNotFound", unit=MetricUnit.Count, value=1)
        raise ValueError("User not found")

    except ClientError as e:
        logger.error(f"Cognito API error", extra={"error": str(e)})
        metrics.add_metric(name="CognitoAPIError", unit=MetricUnit.Count, value=1)
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
