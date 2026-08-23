"""GET /users/settings - Get user settings"""

from decimal import Decimal
from typing import Any, Dict, Optional

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _to_native_json(value: Any) -> Any:
    """
    Convert integral DynamoDB ``Decimal`` values into native ints, recursively.

    This endpoint stores and returns arbitrary client JSON, so types must round-trip.
    boto3 deserialises every DynamoDB number as ``Decimal``, and ``success_response``
    serialises with ``json.dumps(..., default=str)`` — which renders ``Decimal('1')`` as
    the string ``"1"``. Callers that wrote a number therefore read back a string, while the
    ``PUT`` response (which echoes the in-memory value) correctly showed a number. That
    asymmetry silently broke schema-version checks on the client.

    Only integral values are converted. Fractional Decimals are passed through untouched
    rather than cast to ``float``: DynamoDB carries up to 38 significant digits while a
    float holds ~16, so the cast would silently corrupt a high-precision value
    (``Decimal("1.12345678901234567890123456789012345678")`` becomes
    ``1.1234567890123457``). Leaving them alone preserves the existing behaviour — the
    fallback serialiser stringifies them — and loses no data.

    Note that fractional values cannot currently be written through this API at all:
    ``settings_put`` hands the parsed JSON body straight to ``put_item``, and boto3 rejects
    Python floats ("Float types are not supported. Use Decimal types instead."), so a
    fractional literal fails on write. This branch therefore only guards values written by
    some other path.

    Non-finite Decimals are likewise passed through; DynamoDB cannot store NaN/Infinity,
    so that is defensive only.
    """
    if isinstance(value, Decimal):
        if value.is_finite() and value == value.to_integral_value():
            return int(value)
        return value
    if isinstance(value, list):
        return [_to_native_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_native_json(item) for key, item in value.items()}
    return value


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

                settings[setting_namespace][setting_key] = _to_native_json(
                    item.get("value")
                )

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
