import json
import os
import time
from typing import Any, Dict

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
metrics = Metrics(namespace="medialake", service="users-favorites-post")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class FavoriteResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="Added favorite data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEventModel, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler to add a favorite item for a user in DynamoDB
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

        # Parse the request body
        try:
            body = event.get("body", "{}")
            if isinstance(body, str):
                favorite_data = json.loads(body)
            else:
                favorite_data = body
        except json.JSONDecodeError:
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
            user_table_name,
            user_id,
            favorite_data["itemId"],
            favorite_data["itemType"],
            favorite_data.get("metadata", {}),
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

        # TODO: Generate audit event for favorite addition
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


@tracer.capture_method
def _add_favorite(
    table_name: str,
    user_id: str,
    item_id: str,
    item_type: str,
    metadata: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Add a favorite item for a user in DynamoDB
    """
    try:
        # Format the userId according to the schema
        formatted_user_id = f"USER#{user_id}"

        # Generate a reverse timestamp for sorting (newest first)
        # 9999999999999 - current_time_ms ensures newest items appear first when sorted
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
            "favoriteId": reverse_timestamp,  # Use the reverse timestamp as the favorite ID
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
