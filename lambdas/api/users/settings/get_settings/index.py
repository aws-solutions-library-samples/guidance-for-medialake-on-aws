import os
from typing import Any, Dict, Optional

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
metrics = Metrics(namespace="medialake", service="users-settings-get")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SettingsResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="User settings data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEventModel, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user settings from DynamoDB
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

        # Check if namespace filter is provided in query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        namespace = query_params.get("namespace")

        # Fetch user settings from DynamoDB
        user_settings = _get_user_settings(user_table_name, user_id, namespace)

        # Create success response
        response = SettingsResponse(
            status="200",
            message="User settings retrieved successfully",
            data=user_settings,
        )

        logger.info("Successfully retrieved user settings", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulSettingsLookup", unit=MetricUnit.Count, value=1
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
def _get_user_settings(
    table_name: str, user_id: str, namespace: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch user settings from DynamoDB
    """
    try:
        # Format the userId according to the schema
        formatted_user_id = f"USER#{user_id}"

        table = dynamodb.Table(table_name)

        # If namespace is provided, filter by the specific namespace
        if namespace:
            # Query for settings with the specific namespace
            query_params = {
                "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
                "ExpressionAttributeValues": {
                    ":userId": formatted_user_id,
                    ":prefix": f"SETTING#{namespace}#",
                },
            }
            response = table.query(**query_params)
            items = response.get("Items", [])
        else:
            # Query for all settings
            query_params = {
                "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
                "ExpressionAttributeValues": {
                    ":userId": formatted_user_id,
                    ":prefix": "SETTING#",
                },
            }
            response = table.query(**query_params)
            items = response.get("Items", [])

        # Process the settings into a structured format
        settings = {}

        for item in items:
            # Extract namespace and key from the itemKey
            # Format: SETTING#{namespace}#{key}
            item_key = item.get("itemKey", "")
            parts = item_key.split("#")

            if len(parts) >= 3:
                setting_namespace = parts[1]
                setting_key = parts[2]

                # Initialize namespace dictionary if it doesn't exist
                if setting_namespace not in settings:
                    settings[setting_namespace] = {}

                # Add the setting value to the namespace
                setting_value = item.get("value")
                settings[setting_namespace][setting_key] = setting_value

        return {"userId": user_id, "settings": settings}

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
