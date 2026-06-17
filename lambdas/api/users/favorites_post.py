"""POST /users/favorites - Add a favorite"""

import time
from typing import Any, Dict

from auth_utils import get_authenticated_user_id
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _add_favorite(
    dynamodb,
    table_name: str,
    user_id: str,
    item_id: str,
    item_type: str,
    metadata: Dict[str, Any],
    logger,
    metrics,
) -> Dict[str, Any]:
    """
    Add a favorite item for a user in DynamoDB
    """
    try:
        formatted_user_id = f"USER#{user_id}"

        current_time_ms = int(time.time() * 1000)
        reverse_timestamp = str(9999999999999 - current_time_ms)

        item_key = f"FAV#{item_type}#{reverse_timestamp}"
        gsi1_sk = f"ITEM_TYPE#{item_type}#{reverse_timestamp}"
        gsi2_pk = f"ITEM_TYPE#{item_type}"
        gsi2_sk = f"USER#{user_id}#{reverse_timestamp}"

        table = dynamodb.Table(table_name)
        added_at = int(time.time())

        item = {
            "userId": formatted_user_id,
            "itemKey": item_key,
            "itemId": item_id,
            "itemType": item_type,
            "addedAt": added_at,
            "gsi1Sk": gsi1_sk,
            "gsi2Pk": gsi2_pk,
            "gsi2Sk": gsi2_sk,
        }

        if metadata:
            item["metadata"] = metadata

        table.put_item(Item=item)

        result = {
            "userId": user_id,
            "itemId": item_id,
            "itemType": item_type,
            "addedAt": added_at,
            "favoriteId": reverse_timestamp,
        }

        if metadata:
            result["metadata"] = metadata

        return result

    except ClientError as e:
        logger.error("DynamoDB error", extra={"error": str(e)})
        metrics.add_metric(name="DynamoDBError", unit=MetricUnit.Count, value=1)
        raise


def handle_post_favorite(
    app, dynamodb, user_table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to add a favorite item for a user in DynamoDB
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
            favorite_data = app.current_event.json_body
        except Exception:
            logger.error("Invalid JSON in request body")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Invalid request body format")

        if not isinstance(favorite_data, dict):
            logger.error("Request body is not a JSON object")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Request body must be a JSON object")

        required_fields = ["itemId", "itemType"]
        for field in required_fields:
            if field not in favorite_data:
                logger.error(f"Missing required field: {field}")
                metrics.add_metric(
                    name="InvalidRequestError", unit=MetricUnit.Count, value=1
                )
                return error_response(400, f"Missing required field: {field}")

        valid_item_types = ["ASSET", "PIPELINE", "COLLECTION"]
        if favorite_data["itemType"] not in valid_item_types:
            logger.error(f"Invalid itemType: {favorite_data['itemType']}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return error_response(
                400, f"Invalid itemType. Must be one of: {', '.join(valid_item_types)}"
            )

        added_favorite = _add_favorite(
            dynamodb,
            user_table_name,
            user_id,
            favorite_data["itemId"],
            favorite_data["itemType"],
            favorite_data.get("metadata", {}),
            logger,
            metrics,
        )

        logger.info(
            "Successfully added favorite",
            extra={
                "user_id": user_id,
                "item_id": favorite_data["itemId"],
                "item_type": favorite_data["itemType"],
            },
        )
        metrics.add_metric(name="SuccessfulFavoriteAdd", unit=MetricUnit.Count, value=1)

        logger.info(
            "Audit: User favorite added",
            extra={
                "user_id": user_id,
                "action": "ADD_FAVORITE",
                "item_id": favorite_data["itemId"],
                "item_type": favorite_data["itemType"],
                "timestamp": time.time(),
            },
        )

        return success_response(201, "Favorite added successfully", added_favorite)

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
