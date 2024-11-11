"""
Asset Rename Lambda Handler

This Lambda function handles renaming assets and their derived representations in S3.
It implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Input validation and error handling
- Metrics and monitoring
- Security best practices
- Performance optimization through batch operations
"""

from typing import Dict, Any, List
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import parse_json_body, ValidationError
from botocore.exceptions import ClientError
import boto3
import os
import json
from http import HTTPStatus
import re

# Initialize AWS Lambda Powertools
logger = Logger(service="asset-rename-service")
tracer = Tracer(service="asset-rename-service")
metrics = Metrics(namespace="AssetRenameService", service="asset-rename-service")

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


class AssetRenameError(Exception):
    """Custom exception for asset rename errors"""

    def __init__(
        self, message: str, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        super().__init__(message)
        self.status_code = status_code


@tracer.capture_method
def validate_name(name: str) -> None:
    """
    Validates the asset name format.

    Args:
        name: The name to validate

    Raises:
        AssetRenameError: If the name is invalid
    """
    if not name or not isinstance(name, str):
        raise AssetRenameError("Invalid name format", HTTPStatus.BAD_REQUEST)

    # Add additional name validation rules as needed
    if not re.match(r"^[a-zA-Z0-9_\-\.\/]+$", name):
        raise AssetRenameError(
            "Name can only contain alphanumeric characters, underscores, hyphens, dots, and forward slashes",
            HTTPStatus.BAD_REQUEST,
        )


@tracer.capture_method
def get_asset(inventory_id: str, old_name: str) -> Dict[str, Any]:
    """
    Retrieves asset details and validates old name.

    Args:
        inventory_id: The inventory ID of the asset
        old_name: The current name to verify

    Returns:
        Dict containing the asset details

    Raises:
        AssetRenameError: If retrieval fails or name doesn't match
    """
    try:
        response = table.get_item(Key={"id": inventory_id})

        if "Item" not in response:
            raise AssetRenameError(
                f"Asset with ID {inventory_id} not found", HTTPStatus.NOT_FOUND
            )

        asset = response["Item"]
        if asset["mainRepresentation"]["storage"]["path"] != old_name:
            raise AssetRenameError(
                "Current name does not match asset record", HTTPStatus.CONFLICT
            )

        return asset

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        raise AssetRenameError(f"Failed to retrieve asset: {str(e)}")


@tracer.capture_method
def rename_s3_object(bucket: str, old_key: str, new_key: str) -> None:
    """
    Renames (copies and deletes) an S3 object.

    Args:
        bucket: The S3 bucket name
        old_key: The current object key
        new_key: The new object key

    Raises:
        AssetRenameError: If the rename operation fails
    """
    try:
        # Copy object to new key
        s3.copy_object(Bucket=bucket, CopySource=f"{bucket}/{old_key}", Key=new_key)

        # Delete old object
        s3.delete_object(Bucket=bucket, Key=old_key)

    except ClientError as e:
        logger.error(f"S3 error: {str(e)}")
        raise AssetRenameError(f"Failed to rename S3 object: {str(e)}")


@tracer.capture_method
def update_asset_record(asset: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """
    Updates the asset record in DynamoDB with the new name.

    Args:
        asset: The asset record to update
        new_name: The new name to set

    Returns:
        Dict containing the updated asset

    Raises:
        AssetRenameError: If the update fails
    """
    try:
        # Update main representation path
        asset["mainRepresentation"]["storage"]["path"] = new_name

        # Update derived representations paths
        for rep in asset.get("derivedRepresentations", []):
            old_path = rep["storage"]["path"]
            rep["storage"]["path"] = old_path.replace(
                asset["mainRepresentation"]["storage"]["path"], new_name
            )

        # Update DynamoDB record
        table.put_item(Item=asset)
        return asset

    except ClientError as e:
        logger.error(f"Failed to update asset record: {str(e)}")
        raise AssetRenameError(f"Failed to update asset record: {str(e)}")


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
        "body": json.dumps(body),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: APIGatewayProxyEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for asset renaming.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Extract and validate path parameter
        inventory_id = event.get("pathParameters", {}).get("id")
        if not inventory_id:
            raise AssetRenameError("Missing inventory ID", HTTPStatus.BAD_REQUEST)

        # Parse and validate request body
        try:
            body = parse_json_body(event)
            old_name = body.get("oldName")
            new_name = body.get("newName")

            if not old_name or not new_name:
                raise AssetRenameError(
                    "Missing oldName or newName in request body", HTTPStatus.BAD_REQUEST
                )

            validate_name(new_name)

        except ValidationError as e:
            raise AssetRenameError(str(e), HTTPStatus.BAD_REQUEST)

        # Get and validate asset
        asset = get_asset(inventory_id, old_name)

        # Rename main representation in S3
        rename_s3_object(
            asset["mainRepresentation"]["storage"]["bucket"], old_name, new_name
        )

        # Rename derived representations in S3
        for rep in asset.get("derivedRepresentations", []):
            old_path = rep["storage"]["path"]
            new_path = old_path.replace(old_name, new_name)
            rename_s3_object(rep["storage"]["bucket"], old_path, new_path)

        # Update asset record
        updated_asset = update_asset_record(asset, new_name)

        # Record successful rename metric
        metrics.add_metric(name="AssetRenames", unit=MetricUnit.Count, value=1)

        return create_response(
            HTTPStatus.OK, "Asset renamed successfully", {"asset": updated_asset}
        )

    except AssetRenameError as e:
        logger.warning(
            f"Asset rename failed: {str(e)}",
            extra={"inventory_id": inventory_id, "error_code": e.status_code},
        )
        return create_response(e.status_code, str(e))

    except Exception as e:
        logger.error(
            f"Unexpected error during asset rename: {str(e)}",
            extra={"inventory_id": inventory_id},
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error"
        )
