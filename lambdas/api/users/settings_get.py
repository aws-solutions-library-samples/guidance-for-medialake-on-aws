"""GET /users/settings - Get user settings"""

from typing import Any, Dict, Optional

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _get_user_settings(
    dynamodb, table_name: str, user_id: str, namespace: Optional[str], logger, metrics
) -> Dict[str, Any]:
    """
    Fetch user settings from DynamoDB
    """
    try:
        formatted_user_id = f"USER#{user_id}"
        table = dynamodb.Table(table_name)

        prefix = f"SETTING#{namespace}#" if namespace else "SETTING#"

        query_params = {
            "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
            "ExpressionAttributeValues": {
                ":userId": formatted_user_id,
                ":prefix": prefix,
            },
        }
        response = table.query(**query_params)
        items = response.get("Items", [])

        settings = {}
        for item in items:
            item_key = item.get("itemKey", "")
            parts = item_key.split("#")

            if len(parts) >= 3:
                setting_namespace = parts[1]
                setting_key = parts[2]

                if setting_namespace not in settings:
                    settings[setting_namespace] = {}

                settings[setting_namespace][setting_key] = item.get("value")

        return {"userId": user_id, "settings": settings}

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def handle_get_settings(
    app, dynamodb, user_table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user settings from DynamoDB
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

        query_params = app.current_event.query_string_parameters or {}
        namespace = query_params.get("namespace")

        user_settings = _get_user_settings(
            dynamodb, user_table_name, user_id, namespace, logger, metrics
        )

        logger.info("Successfully retrieved user settings", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulSettingsLookup", unit=MetricUnit.Count, value=1
        )

        return success_response(
            200, "User settings retrieved successfully", user_settings
        )

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
