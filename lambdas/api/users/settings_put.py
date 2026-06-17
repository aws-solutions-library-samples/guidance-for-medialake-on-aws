"""PUT /users/settings/{namespace}/{key} - Update user setting"""

import time
from typing import Any, Dict

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


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
        formatted_user_id = f"USER#{user_id}"
        item_key = f"SETTING#{namespace}#{key}"

        table = dynamodb.Table(table_name)
        current_time = int(time.time())

        item = {
            "userId": formatted_user_id,
            "itemKey": item_key,
            "namespace": namespace,
            "key": key,
            "value": value,
            "updatedAt": current_time,
        }

        table.put_item(Item=item)

        return {
            "userId": user_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "updatedAt": current_time,
        }

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


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

        if not namespace or not key:
            logger.error("Missing namespace or key in path parameters")
            metrics.add_metric(
                name="MissingParametersError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Missing namespace or key parameters")

        try:
            setting_data = app.current_event.json_body
        except Exception:
            logger.error("Invalid JSON in request body")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Invalid request body format")

        if not isinstance(setting_data, dict) or "value" not in setting_data:
            logger.error("Request body is missing 'value' field")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Request body must contain a 'value' field")

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

        logger.info(
            "Successfully updated user setting",
            extra={"user_id": user_id, "namespace": namespace, "key": key},
        )
        metrics.add_metric(
            name="SuccessfulSettingUpdate", unit=MetricUnit.Count, value=1
        )

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

        return success_response(
            200, "User setting updated successfully", updated_setting
        )

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
