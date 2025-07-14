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

import json
import os
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS Lambda Powertools
logger = Logger(service="asset-deletion-service")
tracer = Tracer(service="asset-deletion-service")
metrics = Metrics(namespace="AssetDeletionService", service="asset-deletion-service")

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)


class AssetDeletionError(Exception):
    """Custom exception for asset deletion errors"""

    def __init__(
        self, message: str, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        super().__init__(message)
        self.status_code = status_code


class DeleteRequest(BaseModel):
    """Request model for delete operation"""

    inventoryId: str = Field(..., description="Inventory ID of the asset to delete")


@tracer.capture_method
def get_asset(inventory_id: str) -> Dict[str, Any]:
    """
    Retrieves asset details for deletion.
    """
    try:
        response = table.get_item(Key={"InventoryID": inventory_id})

        if "Item" not in response:
            raise AssetDeletionError(
                f"Asset with ID {inventory_id} not found", HTTPStatus.NOT_FOUND
            )

        # Convert Decimal objects for JSON serialization
        return json.loads(json.dumps(response["Item"], cls=DecimalEncoder))

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        raise AssetDeletionError(f"Failed to retrieve asset: {str(e)}")


@tracer.capture_method
def delete_s3_objects(asset: Dict[str, Any]) -> None:
    """
    Deletes all S3 objects associated with the asset.
    """
    try:
        # Delete main representation
        main_rep = asset["DigitalSourceAsset"]["MainRepresentation"]
        main_storage = main_rep["StorageInfo"]["PrimaryLocation"]
        main_bucket = main_storage["Bucket"]
        main_key = main_storage["ObjectKey"]["FullPath"]

        logger.info(
            "Deleting main representation",
            extra={
                "bucket": main_bucket,
                "key": main_key,
                "operation": "delete_main_representation",
            },
        )

        s3.delete_object(Bucket=main_bucket, Key=main_key)

        # Delete derived representations
        for derived in asset["DigitalSourceAsset"].get("DerivedRepresentations", []):
            if not derived.get("StorageInfo", {}).get("PrimaryLocation"):
                continue

            storage = derived["StorageInfo"]["PrimaryLocation"]
            derived_bucket = storage["Bucket"]
            derived_key = storage["ObjectKey"]["FullPath"]

            logger.info(
                "Deleting derived representation",
                extra={
                    "bucket": derived_bucket,
                    "key": derived_key,
                    "operation": "delete_derived_representation",
                },
            )

            s3.delete_object(Bucket=derived_bucket, Key=derived_key)

    except ClientError as e:
        logger.error(f"S3 deletion error: {str(e)}")
        raise AssetDeletionError(f"Failed to delete S3 objects: {str(e)}")


def create_response(
    status_code: int, message: str, data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Creates a standardized API response."""
    body = {
        "status": "success" if status_code < 400 else "error",
        "message": message,
        "data": data or {},
    }

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """Lambda handler for asset deletion."""
    try:
        # Extract and validate inventory ID from path parameters
        inventory_id = event.get("pathParameters", {}).get("id")
        if not inventory_id:
            raise AssetDeletionError("Missing inventory ID", HTTPStatus.BAD_REQUEST)

        # Get asset details
        asset = get_asset(inventory_id)

        # Delete S3 objects
        delete_s3_objects(asset)

        # Delete DynamoDB record
        table.delete_item(Key={"InventoryID": inventory_id})

        # Record successful deletion metric
        metrics.add_metric(name="AssetDeletions", unit=MetricUnit.Count, value=1)

        return create_response(
            HTTPStatus.OK, "Asset deleted successfully", {"inventoryId": inventory_id}
        )

    except AssetDeletionError as e:
        logger.warning(
            f"Asset deletion failed: {str(e)}",
            extra={"inventory_id": inventory_id, "error_code": e.status_code},
        )
        return create_response(e.status_code, str(e))

    except Exception as e:
        logger.error(
            f"Unexpected error during asset deletion: {str(e)}",
            extra={"inventory_id": inventory_id},
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error"
        )
