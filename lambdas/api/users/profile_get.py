"""GET /users/profile - Get user profile"""

from typing import Any, Dict

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _get_user_profile(
    dynamodb, table_name: str, user_id: str, logger, metrics
) -> Dict[str, Any]:
    """
    Fetch user profile from DynamoDB
    """
    try:
        formatted_user_id = f"USER#{user_id}"
        item_key = "PROFILE"

        table = dynamodb.Table(table_name)
        response = table.get_item(
            Key={"userId": formatted_user_id, "itemKey": item_key}
        )

        if "Item" not in response:
            logger.warning("User profile not found", extra={"user_id": user_id})
            metrics.add_metric(name="ProfileNotFound", unit=MetricUnit.Count, value=1)

            return {
                "userId": user_id,
                "displayName": "",
                "email": "",
                "createdAt": "",
                "updatedAt": "",
                "preferences": {},
            }

        item = response["Item"]

        # Remove DynamoDB keys from returned data
        if "userId" in item:
            del item["userId"]
        if "itemKey" in item:
            del item["itemKey"]

        item["userId"] = user_id
        return item

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def handle_get_profile(
    app, dynamodb, user_table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user profile from DynamoDB
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

        user_profile = _get_user_profile(
            dynamodb, user_table_name, user_id, logger, metrics
        )

        logger.info("Successfully retrieved user profile", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulProfileLookup", unit=MetricUnit.Count, value=1
        )

        return success_response(
            200, "User profile retrieved successfully", user_profile
        )

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
