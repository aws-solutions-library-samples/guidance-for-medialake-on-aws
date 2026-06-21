"""GET /users/favorites - Get user favorites"""

from typing import Any, Dict, Optional

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _get_user_favorites(
    dynamodb, table_name: str, user_id: str, item_type: Optional[str], logger, metrics
) -> Dict[str, Any]:
    """
    Fetch user favorites from DynamoDB
    """
    try:
        formatted_user_id = f"USER#{user_id}"
        table = dynamodb.Table(table_name)

        # Read favorites directly from the base table with a strongly consistent
        # read. The base table is keyed (userId, itemKey="FAV#{type}#{ts}"), so a
        # sort-key prefix returns the same per-type set that GSI1 (gsi1Sk=
        # "ITEM_TYPE#{type}#{ts}") would — but a GSI is eventually consistent and
        # cannot use ConsistentRead, so a fetch right after an add/remove could
        # return stale state until the index caught up. Querying the base table
        # avoids that index-propagation lag. (favorites_post still writes gsi1Sk,
        # so this is backwards compatible and the data model is unchanged.)
        if item_type:
            query_params = {
                "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
                "ConsistentRead": True,
                "ExpressionAttributeValues": {
                    ":userId": formatted_user_id,
                    ":prefix": f"FAV#{item_type}#",
                },
            }
        else:
            query_params = {
                "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
                "ConsistentRead": True,
                "ExpressionAttributeValues": {
                    ":userId": formatted_user_id,
                    ":prefix": "FAV#",
                },
            }

        response = table.query(**query_params)
        items = response.get("Items", [])

        favorites = []
        for item in items:
            item_key = item.get("itemKey", "")
            parts = item_key.split("#")

            if len(parts) >= 3:
                reverse_timestamp = parts[2]
                favorite = {
                    "favoriteId": reverse_timestamp,
                    "itemId": item.get("itemId"),
                    "itemType": item.get("itemType"),
                    "addedAt": item.get("addedAt"),
                }
                if "metadata" in item:
                    favorite["metadata"] = item["metadata"]
                favorites.append(favorite)

        return {"userId": user_id, "favorites": favorites, "count": len(favorites)}

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def handle_get_favorites(
    app, dynamodb, user_table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user favorites from DynamoDB
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
        item_type = query_params.get("itemType")

        user_favorites = _get_user_favorites(
            dynamodb, user_table_name, user_id, item_type, logger, metrics
        )

        logger.info("Successfully retrieved user favorites", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulFavoritesLookup", unit=MetricUnit.Count, value=1
        )

        return success_response(
            200, "User favorites retrieved successfully", user_favorites
        )

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
