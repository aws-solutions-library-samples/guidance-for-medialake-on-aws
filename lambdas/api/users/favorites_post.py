"""POST /users/favorites - Add a favorite"""

import time
from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class FavoriteResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Added favorite data")


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
        # Format the userId according to the schema
        formatted_user_id = f"USER#{user_id}"

        # Generate a reverse timestamp for sorting (newest first)
        current_time_ms = int(time.time() * 1000)
        reverse_timestamp = str(9999999999999 - current_time_ms)

        # Format the itemKey according to the schema
        item_key = f"FAV#{item_type}#{reverse_timestamp}"

        # Format GSI keys
        gsi1_sk = f"ITEM_TYPE#{item_type}#{reverse_timestamp}"
        gsi2_pk = f"ITEM_TYPE#{item_type}"
        gsi2_sk = f"USER#{user_id}#{reverse_timestamp}"

        table = dynamodb.Table(table_name)
        added_at = int(time.time())

        # Create the item to be saved
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

        # Add metadata if provided
        if metadata:
            item["metadata"] = metadata

        # Save the item
        table.put_item(Item=item)

        # Return the favorite data without the DynamoDB keys
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


def handle_post_favorite(
    app, dynamodb, user_table_name: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to add a favorite item for a user in DynamoDB
    """
    try:
        # Extract user ID from Cognito authorizer context
        request_context = app.current_event.raw_event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # Get the user ID directly from the authorizer context
        user_id = authorizer.get("userId")

        if not user_id:
            logger.error("Missing user_id in authorizer context")
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
            favorite_data = app.current_event.json_body
        except Exception:
            logger.error("Invalid JSON in request body")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Invalid request body format")

        # Validate the favorite data
        if not isinstance(favorite_data, dict):
            logger.error("Request body is not a JSON object")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Request body must be a JSON object")

        # Check required fields
        required_fields = ["itemId", "itemType"]
        for field in required_fields:
            if field not in favorite_data:
                logger.error(f"Missing required field: {field}")
                metrics.add_metric(
                    name="InvalidRequestError", unit=MetricUnit.Count, value=1
                )
                return _create_error_response(400, f"Missing required field: {field}")

        # Validate itemType
        valid_item_types = ["ASSET", "PIPELINE", "COLLECTION"]
        if favorite_data["itemType"] not in valid_item_types:
            logger.error(f"Invalid itemType: {favorite_data['itemType']}")
            metrics.add_metric(
                name="InvalidRequestError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                400, f"Invalid itemType. Must be one of: {', '.join(valid_item_types)}"
            )

        # Add the favorite to DynamoDB
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

        # Create success response
        response = FavoriteResponse(
            status="201",
            message="Favorite added successfully",
            data=added_favorite,
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

        # Audit event for favorite addition
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

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")
