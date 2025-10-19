"""PUT /users/settings/{namespace}/{key} - Update user setting"""

import time
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class SettingResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Updated setting data")


def _update_user_setting(
    dynamodb,
    table_name: str,
    user_id: str,
    namespace: str,
    key: str,
    value: Any,
    logger,
    metrics,
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


def handle_put_setting(
    namespace: str,
    key: str,
    app,
    dynamodb,
    user_table_name: str,
    logger,
    metrics,
    tracer,
) -> Dict[str, Any]:
    """
    Lambda handler to update a specific user setting in DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
        request_context = app.current_event.raw_event.get("requestContext", {})
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

        if not user_table_name:
            logger.error("USER_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        if not namespace or not key:
            logger.error("Missing namespace or key in path parameters")
            metrics.add_metric(
                name="MissingParametersError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing namespace or key parameters")

        # Parse the request body
        try:
            setting_data = app.current_event.json_body
        except Exception:
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
            dynamodb,
            user_table_name,
            user_id,
            namespace,
            key,
            setting_data["value"],
            logger,
            metrics,
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

        # Audit event for setting update
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
