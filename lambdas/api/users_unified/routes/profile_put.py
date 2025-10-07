"""PUT /users/profile - Update user profile"""

import time
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class ProfileResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Updated user profile data")


def _sanitize_profile_data(profile_data: Dict[str, Any]) -> None:
    """
    Remove fields that shouldn't be updated by the user
    """
    protected_fields = ["userId", "itemKey", "createdAt", "email"]

    for field in protected_fields:
        if field in profile_data:
            del profile_data[field]


def _update_user_profile(
    dynamodb, table_name: str, user_id: str, profile_data: Dict[str, Any], logger, metrics
) -> Dict[str, Any]:
    """
    Update user profile in DynamoDB
    """
    try:
        # Format the userId and itemKey according to the schema
        formatted_user_id = f"USER#{user_id}"
        item_key = "PROFILE"

        table = dynamodb.Table(table_name)

        # First, check if the profile exists
        response = table.get_item(
            Key={"userId": formatted_user_id, "itemKey": item_key}
        )

        current_time = int(time.time())

        # Prepare the item to be saved
        if "Item" in response:
            # Update existing profile
            existing_item = response["Item"]

            # Merge the existing profile with the new data
            for key, value in profile_data.items():
                existing_item[key] = value

            # Update the updatedAt timestamp
            existing_item["updatedAt"] = current_time

            # Save the updated item
            table.put_item(Item=existing_item)

            # Remove the PK and SK from the returned data
            if "userId" in existing_item:
                del existing_item["userId"]
            if "itemKey" in existing_item:
                del existing_item["itemKey"]

            # Add the user ID without the prefix
            existing_item["userId"] = user_id

            return existing_item
        else:
            # Create new profile
            new_item = {
                "userId": formatted_user_id,
                "itemKey": item_key,
                "displayName": profile_data.get("displayName", ""),
                "preferences": profile_data.get("preferences", {}),
                "createdAt": current_time,
                "updatedAt": current_time,
            }

            # Add any additional fields from the request
            for key, value in profile_data.items():
                if key not in ["displayName", "preferences"]:
                    new_item[key] = value

            # Save the new item
            table.put_item(Item=new_item)

            # Remove the PK and SK from the returned data
            del new_item["userId"]
            del new_item["itemKey"]

            # Add the user ID without the prefix
            new_item["userId"] = user_id

            return new_item

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


def handle_put_profile(app, dynamodb, user_table_name: str, logger, metrics, tracer) -> Dict[str, Any]:
    """
    Lambda handler to update user profile in DynamoDB
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

        # Parse the request body
        try:
            profile_data = app.current_event.json_body
        except Exception:
            logger.error("Invalid JSON in request body")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Invalid request body format")

        # Validate the profile data
        if not isinstance(profile_data, dict):
            logger.error("Request body is not a JSON object")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Request body must be a JSON object")

        # Remove any fields that shouldn't be updated by the user
        _sanitize_profile_data(profile_data)

        # Update the user profile in DynamoDB
        updated_profile = _update_user_profile(dynamodb, user_table_name, user_id, profile_data, logger, metrics)

        # Create success response
        response = ProfileResponse(
            status="200",
            message="User profile updated successfully",
            data=updated_profile,
        )

        logger.info("Successfully updated user profile", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulProfileUpdate", unit=MetricUnit.Count, value=1
        )

        # Audit event for profile update
        logger.info(
            "Audit: User profile updated",
            extra={
                "user_id": user_id,
                "action": "UPDATE_PROFILE",
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
