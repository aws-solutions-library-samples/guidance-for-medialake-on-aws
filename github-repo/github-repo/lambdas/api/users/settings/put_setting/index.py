import json
import os
import time
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
logger = Logger(
    service="user-settings-service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="user-settings-service")
metrics = Metrics(namespace="medialake", service="users-settings-put")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SettingResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Updated setting data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEventModel, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to update a specific user setting in DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
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

        # Extract namespace and key from path parameters
        path_params = event.get("pathParameters", {}) or {}
        namespace = path_params.get("namespace")
        key = path_params.get("key")

        if not namespace or not key:
            logger.error("Missing namespace or key in path parameters")
            metrics.add_metric(
                name="MissingParametersError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing namespace or key parameters")

        # Parse the request body
        try:
            body = event.get("body", "{}")
            if isinstance(body, str):
                setting_data = json.loads(body)
            else:
                setting_data = body
        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Invalid request body format")

        # Validate the setting data
        if not isinstance(setting_data, dict) or "value" not in setting_data:
            logger.error("Request body is missing 'value' field")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                400, "Request body must contain a 'value' field"
            )

        # Update the user setting in DynamoDB
        updated_setting = _update_user_setting(
            user_table_name, user_id, namespace, key, setting_data["value"]
        )

        # Create success response
        response = SettingResponse(
            status="200",
            message="User setting updated successfully",
            data=updated_setting,
        )

        logger.info(
            "Successfully updated user setting",
            extra={"user_id": user_id, "namespace": namespace, "key": key},
        )
        metrics.add_metric(
            name="SuccessfulSettingUpdate", unit=MetricUnit.Count, value=1
        )

        # TODO: Generate audit event for setting update
        logger.info(
            "Audit: User setting updated",
            extra={
                "user_id": user_id,
                "action": "UPDATE_SETTING",
                "namespace": namespace,
                "key": key,
                "timestamp": time.time(),
            },
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
def _update_user_setting(
    table_name: str, user_id: str, namespace: str, key: str, value: Any
) -> Dict[str, Any]:
    """
    Update a specific user setting in DynamoDB
    """
    try:
        # Format the userId and itemKey according to the schema
        formatted_user_id = f"USER#{user_id}"
        item_key = f"SETTING#{namespace}#{key}"

        table = dynamodb.Table(table_name)
        current_time = int(time.time())

        # Create the item to be saved
        item = {
            "userId": formatted_user_id,
            "itemKey": item_key,
            "namespace": namespace,
            "key": key,
            "value": value,
            "updatedAt": current_time,
        }

        # Save the item
        table.put_item(Item=item)

        # Return the setting data without the DynamoDB keys
        return {
            "userId": user_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "updatedAt": current_time,
        }

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
