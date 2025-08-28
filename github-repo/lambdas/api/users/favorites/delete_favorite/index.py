import os
import time
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(
    service="user-favorites-service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="user-favorites-service")
metrics = Metrics(namespace="medialake", service="users-favorites-delete")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class DeleteResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Deletion result")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to remove an item from user favorites
    """
    try:
        # Extract user ID from Cognito authorizer context
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # Get the user ID directly from the authorizer context
        user_id = authorizer.get("userId")

        if not user_id:
            logger.error("Missing user_id in authorizer context")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Unable to identify user")

        # Get the user table name from environment variable
        user_table_name = os.getenv("USER_TABLE_NAME")
        if not user_table_name:
            logger.error("USER_TABLE_NAME environment variable not set")
            metrics.add_metric(
                name="MissingConfigError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(500, "Internal configuration error")

        # Extract itemType and itemId from path parameters
        path_params = event.get("pathParameters", {}) or {}
        item_type = path_params.get("itemType")
        item_id = path_params.get("itemId")

        # Check if we have the required parameters
        if not item_type or not item_id:
            logger.error("Missing itemType or itemId in path parameters")
            metrics.add_metric(
                name="MissingParametersError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing itemType or itemId parameters")

        # Validate itemType
        valid_item_types = ["ASSET", "PIPELINE", "COLLECTION"]
        if item_type not in valid_item_types:
            logger.error(f"Invalid itemType: {item_type}")
            metrics.add_metric(
                name="InvalidParameterError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(
                400, f"Invalid itemType. Must be one of: {', '.join(valid_item_types)}"
            )

        # Remove the favorite from DynamoDB
        result = _remove_favorite(user_table_name, user_id, item_type, item_id)

        # Create success response
        response = DeleteResponse(
            status="200",
            message=(
                "Favorite removed successfully"
                if result["removed"]
                else "Favorite not found"
            ),
            data=result,
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

        # TODO: Generate audit event for favorite removal
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

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, f"Internal server error: {str(e)}")


@tracer.capture_method
def _remove_favorite(
    table_name: str, user_id: str, item_type: str, item_id: str
) -> Dict[str, Any]:
    """
    Remove a favorite item for a user from DynamoDB
    """
    try:
        # Format the userId according to the schema
        formatted_user_id = f"USER#{user_id}"

        table = dynamodb.Table(table_name)

        # First, find the favorite item by querying with the userId and itemType prefix
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
                f"Favorite not found",
                extra={"user_id": user_id, "item_id": item_id, "item_type": item_type},
            )
            return {
                "userId": user_id,
                "itemId": item_id,
                "itemType": item_type,
                "removed": False,
            }

        # Delete each matching favorite (should typically be just one)
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
