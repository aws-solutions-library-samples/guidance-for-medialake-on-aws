"""DELETE /users/favorites/{itemType}/{itemId} - Remove a favorite"""

import time
from typing import Any, Dict

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _remove_favorite(
    dynamodb,
    table_name: str,
    user_id: str,
    item_type: str,
    item_id: str,
    logger,
    metrics,
) -> Dict[str, Any]:
    """
    Remove a favorite item for a user from DynamoDB
    """
    try:
        formatted_user_id = f"USER#{user_id}"
        table = dynamodb.Table(table_name)

        query_params = {
            "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
            "FilterExpression": "itemId = :itemId",
            "ExpressionAttributeValues": {
                ":userId": formatted_user_id,
                ":prefix": f"FAV#{item_type}#",
                ":itemId": item_id,
            },
        }

        response = table.query(**query_params)
        items = response.get("Items", [])

        if not items:
            logger.warning(
                "Favorite not found",
                extra={"user_id": user_id, "item_id": item_id, "item_type": item_type},
            )
            return {
                "userId": user_id,
                "itemId": item_id,
                "itemType": item_type,
                "removed": False,
            }

        removed_count = 0
        for item in items:
            table.delete_item(
                Key={"userId": formatted_user_id, "itemKey": item["itemKey"]}
            )
            removed_count += 1

        logger.info(
            f"Removed {removed_count} favorites",
            extra={"user_id": user_id, "item_id": item_id, "item_type": item_type},
        )

        return {
            "userId": user_id,
            "itemId": item_id,
            "itemType": item_type,
            "removed": removed_count > 0,
            "count": removed_count,
        }

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def handle_delete_favorite(
    item_type: str,
    item_id: str,
    app,
    dynamodb,
    user_table_name: str,
    logger,
    metrics,
    tracer,
) -> Dict[str, Any]:
    """
    Lambda handler to remove an item from user favorites
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

        if not item_type or not item_id:
            logger.error("Missing itemType or itemId in path parameters")
            metrics.add_metric(
                name="MissingParametersError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Missing itemType or itemId parameters")

        valid_item_types = ["ASSET", "PIPELINE", "COLLECTION"]
        if item_type not in valid_item_types:
            logger.error(f"Invalid itemType: {item_type}")
            metrics.add_metric(
                name="InvalidParameterError", unit=MetricUnit.Count, value=1
            )
            return error_response(
                400, f"Invalid itemType. Must be one of: {', '.join(valid_item_types)}"
            )

        result = _remove_favorite(
            dynamodb, user_table_name, user_id, item_type, item_id, logger, metrics
        )

        message = (
            "Favorite removed successfully"
            if result["removed"]
            else "Favorite not found"
        )

        logger.info(
            "Successfully processed favorite removal request",
            extra={
                "user_id": user_id,
                "item_id": item_id,
                "item_type": item_type,
                "removed": result["removed"],
            },
        )
        metrics.add_metric(
            name="SuccessfulFavoriteRemoval", unit=MetricUnit.Count, value=1
        )

        if result["removed"]:
            logger.info(
                "Audit: User favorite removed",
                extra={
                    "user_id": user_id,
                    "action": "REMOVE_FAVORITE",
                    "item_id": item_id,
                    "item_type": item_type,
                    "timestamp": time.time(),
                },
            )

        return success_response(200, message, result)

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
