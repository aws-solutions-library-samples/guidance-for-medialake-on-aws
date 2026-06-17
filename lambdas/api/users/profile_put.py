"""PUT /users/profile - Update user profile"""

import time
from typing import Any, Dict

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response

# Fields that users should not be able to overwrite
_PROTECTED_FIELDS = {"userId", "itemKey", "createdAt", "email"}


def _update_user_profile(
    dynamodb,
    table_name: str,
    user_id: str,
    profile_data: Dict[str, Any],
    logger,
    metrics,
) -> Dict[str, Any]:
    """
    Atomically update user profile in DynamoDB using update_item.
    Creates the profile if it doesn't exist (upsert).
    """
    try:
        formatted_user_id = f"USER#{user_id}"
        item_key = "PROFILE"
        table = dynamodb.Table(table_name)
        current_time = int(time.time())

        # Filter out protected fields
        safe_data = {
            k: v for k, v in profile_data.items() if k not in _PROTECTED_FIELDS
        }
        safe_data["updatedAt"] = current_time

        # Build UpdateExpression dynamically
        update_parts = []
        expr_attr_names = {}
        expr_attr_values = {}

        for i, (key, value) in enumerate(safe_data.items()):
            alias_name = f"#f{i}"
            alias_value = f":v{i}"
            update_parts.append(f"{alias_name} = {alias_value}")
            expr_attr_names[alias_name] = key
            expr_attr_values[alias_value] = value

        # Also set createdAt if the item is new (using if_not_exists)
        update_parts.append("#createdAt = if_not_exists(#createdAt, :createdAtVal)")
        expr_attr_names["#createdAt"] = "createdAt"
        expr_attr_values[":createdAtVal"] = current_time

        update_expression = "SET " + ", ".join(update_parts)

        response = table.update_item(
            Key={"userId": formatted_user_id, "itemKey": item_key},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW",
        )

        item = response.get("Attributes", {})

        # Remove DynamoDB keys from returned data
        item.pop("userId", None)
        item.pop("itemKey", None)
        item["userId"] = user_id

        return item

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def handle_put_profile(
    app, dynamodb, user_table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to update user profile in DynamoDB
    """
    try:
        user_id = get_authenticated_user_id(app, logger)

        if not user_id:
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Unable to identify user")

        if not user_table_name:
            logger.error("USER_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return error_response(500, "Internal configuration error")

        try:
            profile_data = app.current_event.json_body
        except Exception:
            logger.error("Invalid JSON in request body")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Invalid request body format")

        if not isinstance(profile_data, dict):
            logger.error("Request body is not a JSON object")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Request body must be a JSON object")

        updated_profile = _update_user_profile(
            dynamodb, user_table_name, user_id, profile_data, logger, metrics
        )

        logger.info("Successfully updated user profile", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulProfileUpdate", unit=MetricUnit.Count, value=1
        )

        logger.info(
            "Audit: User profile updated",
            extra={
                "user_id": user_id,
                "action": "UPDATE_PROFILE",
                "timestamp": time.time(),
            },
        )

        return success_response(
            200, "User profile updated successfully", updated_profile
        )

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
