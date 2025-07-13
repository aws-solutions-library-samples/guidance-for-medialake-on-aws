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

import json
import os
import re
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

# Initialize AWS Lambda Powertools
logger = Logger(service="asset-rename-service")
tracer = Tracer(service="asset-rename-service")
metrics = Metrics(namespace="AssetRenameService", service="asset-rename-service")

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


class RenameRequest(BaseModel):
    """Request model for rename operation"""

    newName: str = Field(..., description="New name for the asset")


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


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)


@tracer.capture_method
def get_asset(inventory_id: str) -> Dict[str, Any]:
    """
    Retrieves asset details with proper path information.
    """
    try:
        response = table.get_item(Key={"InventoryID": inventory_id})

        if "Item" not in response:
            raise AssetRenameError(
                f"Asset with ID {inventory_id} not found", HTTPStatus.NOT_FOUND
            )

        asset = response["Item"]

        # Convert any Decimal values to float/str for JSON serialization
        asset = json.loads(json.dumps(asset, cls=DecimalEncoder))

        # Validate required paths exist
        if not all(
            [
                asset.get("DigitalSourceAsset"),
                asset["DigitalSourceAsset"].get("MainRepresentation"),
                asset["DigitalSourceAsset"]["MainRepresentation"].get("StorageInfo"),
                asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"].get(
                    "PrimaryLocation"
                ),
                asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
                    "PrimaryLocation"
                ].get("ObjectKey"),
            ]
        ):
            raise AssetRenameError("Invalid asset structure", HTTPStatus.BAD_REQUEST)

        return asset

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        raise AssetRenameError(f"Failed to retrieve asset: {str(e)}")


def get_object_name_from_path(full_path: str) -> str:
    """Extracts the object name from the full path."""
    return full_path.split("/")[-1]


@tracer.capture_method
def copy_s3_object_with_tags(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    inventory_id: str,
    master_id: str = None,
    is_master: bool = False,
) -> None:
    """
    Copies an S3 object with its tags and adds inventory ID tag.

    Args:
        source_bucket: Source bucket name
        source_key: Source object key
        dest_bucket: Destination bucket name
        dest_key: Destination object key
        inventory_id: The inventory ID to tag the object with
        master_id: Optional master ID for tagging master representation
        is_master: Flag indicating if this is the master representation
    """
    try:
        # Get source object tags
        try:
            tags_response = s3.get_object_tagging(Bucket=source_bucket, Key=source_key)
            existing_tags = tags_response.get("TagSet", [])

            # Remove any existing AssetID and MasterID tags if present
            tags = [
                tag
                for tag in existing_tags
                if tag["Key"] not in ["AssetID", "MasterID"]
            ]

            # Add the inventory ID tag
            tags.append({"Key": "AssetID", "Value": inventory_id})

            # Add master ID tag only for master representation
            if is_master and master_id:
                tags.append({"Key": "MasterID", "Value": master_id})

            logger.info(
                "Retrieved existing tags and added required tags",
                extra={
                    "source_bucket": source_bucket,
                    "source_key": source_key,
                    "tag_count": len(tags),
                    "inventory_id": inventory_id,
                    "master_id": master_id if is_master else None,
                    "is_master": is_master,
                },
            )

        except ClientError as e:
            logger.warning(f"Could not get tags for {source_key}: {str(e)}")
            # If we can't get existing tags, set required tags
            tags = [{"Key": "AssetID", "Value": inventory_id}]
            if is_master and master_id:
                tags.append({"Key": "MasterID", "Value": master_id})

        # Copy object with tags
        s3.copy_object(
            Bucket=dest_bucket,
            CopySource={"Bucket": source_bucket, "Key": source_key},
            Key=dest_key,
            TaggingDirective="REPLACE",
            Tagging=format_tags_for_copy(tags),
        )

        logger.info(
            "Successfully copied object with tags",
            extra={
                "source_bucket": source_bucket,
                "source_key": source_key,
                "dest_bucket": dest_bucket,
                "dest_key": dest_key,
                "tags_count": len(tags),
                "inventory_id": inventory_id,
                "master_id": master_id if is_master else None,
                "is_master": is_master,
            },
        )

    except ClientError as e:
        logger.error(
            "Failed to copy object with tags",
            extra={
                "error": str(e),
                "source_bucket": source_bucket,
                "source_key": source_key,
                "inventory_id": inventory_id,
                "master_id": master_id if is_master else None,
                "is_master": is_master,
            },
        )
        raise


def format_tags_for_copy(tags: List[Dict[str, str]]) -> str:
    """Formats tags for S3 copy operation."""
    return "&".join([f"{tag['Key']}={tag['Value']}" for tag in tags])


@tracer.capture_method
def copy_s3_objects(asset: Dict[str, Any], new_name: str) -> List[Dict[str, Any]]:
    """
    Copies all S3 objects with new names.
    Returns list of successful copies for cleanup if needed.
    """
    successful_copies = []
    try:
        # Get inventory ID and master ID from asset
        inventory_id = asset.get("InventoryID")
        master_id = asset["DigitalSourceAsset"]["MainRepresentation"].get("ID")

        if not inventory_id:
            raise AssetRenameError("Missing inventory ID in asset data")

        # Copy main representation
        main_rep = asset["DigitalSourceAsset"]["MainRepresentation"]
        main_storage = main_rep["StorageInfo"]["PrimaryLocation"]
        source_bucket = main_storage["Bucket"]
        source_path = main_storage["ObjectKey"]["FullPath"]

        # Update object name in DynamoDB
        main_rep["Name"] = get_object_name_from_path(new_name)
        new_path = f"{new_name}"

        logger.info(
            "Starting main representation copy",
            extra={
                "source_bucket": source_bucket,
                "source_path": source_path,
                "destination_path": new_path,
                "object_name": main_rep["Name"],
                "inventory_id": inventory_id,
                "master_id": master_id,
                "operation": "copy_main_representation",
            },
        )

        # Copy main representation with both inventory ID and master ID tags
        copy_s3_object_with_tags(
            source_bucket,
            source_path,
            source_bucket,
            new_path,
            inventory_id,
            master_id,
            is_master=True,  # This is the master representation
        )

        successful_copies.append({"bucket": source_bucket, "key": new_path})

        # Copy derived representations (only with inventory ID)
        for idx, derived in enumerate(
            asset["DigitalSourceAsset"].get("DerivedRepresentations", [])
        ):
            if not derived.get("StorageInfo", {}).get("PrimaryLocation"):
                continue

            storage = derived["StorageInfo"]["PrimaryLocation"]
            derived_bucket = storage["Bucket"]
            derived_path = storage["ObjectKey"]["FullPath"]
            new_derived_path = derived_path.replace(source_path, new_path)

            # Update object name in DynamoDB
            derived["Name"] = get_object_name_from_path(new_derived_path)

            logger.info(
                f"Copying derived representation {idx + 1}",
                extra={
                    "derived_index": idx,
                    "source_bucket": derived_bucket,
                    "source_path": derived_path,
                    "destination_path": new_derived_path,
                    "object_name": derived["Name"],
                    "inventory_id": inventory_id,
                    "operation": "copy_derived_representation",
                },
            )

            # Copy derived representation with only inventory ID tag
            copy_s3_object_with_tags(
                derived_bucket,
                derived_path,
                derived_bucket,
                new_derived_path,
                inventory_id,
                is_master=False,  # This is not the master representation
            )

            successful_copies.append(
                {"bucket": derived_bucket, "key": new_derived_path}
            )

        return successful_copies

    except ClientError as e:
        logger.error(
            "S3 copy operation failed",
            extra={
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "successful_copies": successful_copies,
                "operation": "copy_error",
                "inventory_id": inventory_id if "inventory_id" in locals() else None,
                "master_id": master_id if "master_id" in locals() else None,
            },
        )
        # If any copy fails, clean up successful copies
        cleanup_copied_objects(successful_copies)
        raise AssetRenameError(f"Failed to copy S3 objects: {str(e)}")


@tracer.capture_method
def cleanup_copied_objects(copies: List[Dict[str, Any]]) -> None:
    """Deletes any successfully copied objects during rollback."""
    for copy in copies:
        try:
            s3.delete_object(Bucket=copy["bucket"], Key=copy["key"])
        except ClientError as e:
            logger.error(f"Failed to cleanup copied object: {str(e)}")


@tracer.capture_method
def delete_original_objects(asset: Dict[str, Any]) -> None:
    """Deletes original objects after successful copy."""
    try:
        # Delete main representation
        main_storage = asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]
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

        logger.info(
            "Successfully deleted main representation",
            extra={
                "bucket": main_bucket,
                "key": main_key,
                "operation": "delete_main_representation_success",
            },
        )

        # Delete derived representations
        for idx, derived in enumerate(
            asset["DigitalSourceAsset"].get("DerivedRepresentations", [])
        ):
            if not derived.get("StorageInfo", {}).get("PrimaryLocation"):
                logger.warning(
                    "Skipping derived representation deletion - missing storage info",
                    extra={"derived_index": idx, "operation": "delete_derived_skip"},
                )
                continue

            storage = derived["StorageInfo"]["PrimaryLocation"]
            derived_bucket = storage["Bucket"]
            derived_key = storage["ObjectKey"]["FullPath"]

            logger.info(
                f"Deleting derived representation {idx + 1}",
                extra={
                    "derived_index": idx,
                    "bucket": derived_bucket,
                    "key": derived_key,
                    "operation": "delete_derived_representation",
                },
            )

            s3.delete_object(Bucket=derived_bucket, Key=derived_key)

            logger.info(
                f"Successfully deleted derived representation {idx + 1}",
                extra={
                    "derived_index": idx,
                    "bucket": derived_bucket,
                    "key": derived_key,
                    "operation": "delete_derived_representation_success",
                },
            )

    except ClientError as e:
        logger.error(
            "Failed to delete original objects",
            extra={
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "operation": "delete_error",
            },
        )
        raise AssetRenameError("Failed to delete original objects after copy")


@tracer.capture_method
def update_asset_paths(asset: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """Updates all paths in the asset record."""
    try:
        main_rep = asset["DigitalSourceAsset"]["MainRepresentation"]
        old_path = main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]

        # Update main representation path
        main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"] = new_name

        # Update derived representation paths
        for derived in asset["DigitalSourceAsset"].get("DerivedRepresentations", []):
            if not derived.get("StorageInfo", {}).get("PrimaryLocation"):
                continue

            derived_path = derived["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                "FullPath"
            ]
            new_derived_path = derived_path.replace(old_path, new_name)
            derived["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                "FullPath"
            ] = new_derived_path

        # DynamoDB put_item operation (not SQL, safe from injection)
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
        "body": json.dumps(body, cls=DecimalEncoder),  # Use custom encoder
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: APIGatewayProxyEvent, context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for asset renaming."""
    try:
        # Extract and validate parameters
        inventory_id = event.get("pathParameters", {}).get("id")
        if not inventory_id:
            raise AssetRenameError("Missing inventory ID", HTTPStatus.BAD_REQUEST)

        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))
            rename_request = RenameRequest(newName=body.get("newName"))
        except (json.JSONDecodeError, ValueError) as e:
            raise AssetRenameError(
                f"Invalid request body: {str(e)}", HTTPStatus.BAD_REQUEST
            )

        # Validate new name
        validate_name(rename_request.newName)

        # Get asset
        asset = get_asset(inventory_id)

        # Copy all objects with new names
        copy_s3_objects(asset, rename_request.newName)

        # Delete original objects
        delete_original_objects(asset)

        # Update asset record with new paths
        updated_asset = update_asset_paths(asset, rename_request.newName)

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
