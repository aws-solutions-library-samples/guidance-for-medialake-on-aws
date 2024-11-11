"""
Asset Deletion Lambda Handler

This Lambda function handles the deletion of assets from DynamoDB based on asset ID.
It implements best practices for AWS Lambda including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Input validation and error handling
- Metrics and monitoring
- Security best practices
"""

from typing import Dict, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate_request_parameters
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
import boto3
import os
import json

# Initialize AWS Lambda Powertools
logger = Logger(service="asset-deletion-service")
tracer = Tracer(service="asset-deletion-service")
metrics = Metrics(namespace="AssetDeletionService", service="asset-deletion-service")

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


class AssetDeletionError(Exception):
    """Custom exception for asset deletion errors"""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


@tracer.capture_method
def validate_asset_id(asset_id: str) -> None:
    """
    Validates the asset ID format.

    Args:
        asset_id: The asset ID to validate

    Raises:
        AssetDeletionError: If the asset ID is invalid
    """
    if not asset_id or not isinstance(asset_id, str):
        raise AssetDeletionError("Invalid asset ID format", 400)


@tracer.capture_method
def delete_asset(inventory_id: str) -> None:
    """
    Deletes an asset from DynamoDB.

    Args:
        inventory_id: The inventory ID of the asset to delete

    Raises:
        AssetDeletionError: If the deletion fails
    """
    try:
        response = table.delete_item(
            Key={"id": inventory_id},
            ReturnValues="ALL_OLD",  # Get the deleted item's attributes
        )

        # Check if the item existed before deletion
        if "Attributes" not in response:
            raise AssetDeletionError(f"Asset with ID {inventory_id} not found", 404)

        # Log the deleted asset details (excluding sensitive data)
        logger.info(
            "Asset deleted successfully",
            extra={
                "inventory_id": inventory_id,
                "deletion_timestamp": tracer.get_current_event(),
            },
        )

        # Record metric for successful deletion
        metrics.add_metric(name="AssetDeletions", unit=MetricUnit.Count, value=1)

    except ClientError as e:
        logger.error(f"Failed to delete asset: {str(e)}")
        metrics.add_metric(name="AssetDeletionErrors", unit=MetricUnit.Count, value=1)
        raise AssetDeletionError(f"Failed to delete asset: {str(e)}")


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a standardized API response.

    Args:
        status_code: HTTP status code
        body: Response body

    Returns:
        Dict containing the API Gateway response
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # Configure as needed
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: APIGatewayProxyEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for asset deletion.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Extract and validate asset ID from path parameters
        asset_id = event.get("pathParameters", {}).get("id")
        validate_asset_id(asset_id)

        # Delete the asset
        delete_asset(asset_id)

        return create_response(
            200, {"message": "Asset deleted successfully", "assetId": asset_id}
        )

    except AssetDeletionError as e:
        logger.warning(
            f"Asset deletion failed: {str(e)}",
            extra={"asset_id": asset_id, "error_code": e.status_code},
        )
        return create_response(
            e.status_code, {"message": str(e), "error_code": e.status_code}
        )

    except Exception as e:
        logger.error(
            f"Unexpected error during asset deletion: {str(e)}",
            extra={"asset_id": asset_id},
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return create_response(
            500, {"message": "Internal server error", "error_code": 500}
        )
