import os
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser.models import APIGatewayProxyEventModel
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS PowerTools
logger = Logger(
    service="user-favorites-service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="user-favorites-service")
metrics = Metrics(namespace="medialake", service="users-favorites-get")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class FavoritesResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="User favorites data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEventModel, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user favorites from DynamoDB
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

        # Check if itemType filter is provided in query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        item_type = query_params.get("itemType")

        # Fetch user favorites from DynamoDB
        user_favorites = _get_user_favorites(user_table_name, user_id, item_type)

        # Create success response
        response = FavoritesResponse(
            status="200",
            message="User favorites retrieved successfully",
            data=user_favorites,
        )

        logger.info("Successfully retrieved user favorites", extra={"user_id": user_id})
        metrics.add_metric(
            name="SuccessfulFavoritesLookup", unit=MetricUnit.Count, value=1
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
def _get_user_favorites(
    table_name: str, user_id: str, item_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch user favorites from DynamoDB
    """
    try:
        # Format the userId according to the schema
        formatted_user_id = f"USER#{user_id}"

        table = dynamodb.Table(table_name)

        # If itemType is provided, use GSI1 to filter by itemType
        if item_type:
            # Query using GSI1 to filter by itemType
            query_params = {
                "IndexName": "GSI1",
                "KeyConditionExpression": "userId = :userId AND begins_with(gsi1Sk, :prefix)",
                "ExpressionAttributeValues": {
                    ":userId": formatted_user_id,
                    ":prefix": f"ITEM_TYPE#{item_type}#",
                },
            }
            response = table.query(**query_params)
        else:
            # Query for all favorites
            query_params = {
                "KeyConditionExpression": "userId = :userId AND begins_with(itemKey, :prefix)",
                "ExpressionAttributeValues": {
                    ":userId": formatted_user_id,
                    ":prefix": "FAV#",
                },
            }
            response = table.query(**query_params)

        items = response.get("Items", [])

        # Process the favorites into a structured format
        favorites = []

        for item in items:
            # Extract the reverse timestamp from the itemKey
            # Format: FAV#{item_type}#{reverse_timestamp}
            item_key = item.get("itemKey", "")
            parts = item_key.split("#")

            if len(parts) >= 3:
                reverse_timestamp = parts[2]

                # Create a favorite object
                favorite = {
                    "favoriteId": reverse_timestamp,
                    "itemId": item.get("itemId"),
                    "itemType": item.get("itemType"),
                    "addedAt": item.get("addedAt"),
                }

                # Add metadata if it exists
                if "metadata" in item:
                    favorite["metadata"] = item["metadata"]

                favorites.append(favorite)

        return {"userId": user_id, "favorites": favorites, "count": len(favorites)}

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
