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

import copy
import json
import os
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

# Initialize AWS Lambda Powertools
logger = Logger(service="asset-rename-service")
tracer = Tracer(service="asset-rename-service")
metrics = Metrics(namespace="AssetRenameService", service="asset-rename-service")

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])


def join_key(base_path: str, name: str) -> str:
    """
    Safely join an S3 “directory” and filename, without
    injecting a leading slash when base_path is empty.
    """
    return f"{base_path}/{name}" if base_path else name


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
    Validates the asset name format according to S3 object key requirements.

    S3 allows most Unicode characters except:
    - Null bytes (\x00)
    - Control characters (\x01-\x1f, \x7f-\x9f)
    - Some problematic characters for URLs and file systems

    Args:
        name: The name to validate

    Raises:
        AssetRenameError: If the name is invalid
    """
    if not name or not isinstance(name, str):
        raise AssetRenameError("Invalid name format", HTTPStatus.BAD_REQUEST)

    # Check for null bytes and control characters
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise AssetRenameError(
            "Name cannot contain control characters or null bytes",
            HTTPStatus.BAD_REQUEST,
        )

    # Check for problematic characters that could cause issues
    problematic_chars = ["\x00", "\r", "\n", "\t"]
    if any(char in name for char in problematic_chars):
        raise AssetRenameError(
            "Name contains invalid characters",
            HTTPStatus.BAD_REQUEST,
        )

    # Prevent path traversal and other security issues
    if ".." in name or name.startswith("/") or name.endswith("/"):
        raise AssetRenameError(
            "Name cannot contain '..' sequences or start/end with forward slashes",
            HTTPStatus.BAD_REQUEST,
        )

    # Check length (S3 limit is 1024 bytes for object keys)
    if len(name.encode("utf-8")) > 1024:
        raise AssetRenameError(
            "Name is too long (maximum 1024 bytes)",
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
        logger.info(
            "Retrieving asset from DynamoDB",
            extra={"inventory_id": inventory_id, "operation": "get_asset"},
        )

        # Use consistent read to avoid eventual consistency issues
        response = table.get_item(
            Key={"InventoryID": inventory_id}, ConsistentRead=True
        )

        if "Item" not in response:
            logger.error(
                "Asset not found in DynamoDB",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "get_asset",
                    "dynamodb_response_keys": list(response.keys()),
                },
            )
            raise AssetRenameError(
                f"Asset with ID {inventory_id} not found", HTTPStatus.NOT_FOUND
            )

        asset = response["Item"]

        # Convert any Decimal values to float/str for JSON serialization
        # asset = json.loads(json.dumps(asset, cls=DecimalEncoder))

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
            logger.error(
                "Asset has invalid structure",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "get_asset",
                    "has_digital_source": bool(asset.get("DigitalSourceAsset")),
                    "has_main_rep": bool(
                        asset.get("DigitalSourceAsset", {}).get("MainRepresentation")
                    ),
                },
            )
            raise AssetRenameError("Invalid asset location", HTTPStatus.BAD_REQUEST)

        logger.info(
            "Successfully retrieved asset",
            extra={
                "inventory_id": inventory_id,
                "operation": "get_asset",
                "has_derived_reps": len(
                    asset["DigitalSourceAsset"].get("DerivedRepresentations", [])
                ),
            },
        )

        return asset

    except ClientError as e:
        logger.error(
            "DynamoDB error retrieving asset",
            extra={
                "inventory_id": inventory_id,
                "error_code": e.response.get("Error", {}).get("Code", "Unknown"),
                "error_message": str(e),
                "operation": "get_asset",
            },
        )
        raise AssetRenameError(f"Failed to retrieve asset: {str(e)}")


def get_object_name_from_path(full_path: str) -> str:
    """Extracts the object name from the full path with validation."""
    if not full_path or not isinstance(full_path, str):
        raise ValueError("Invalid path provided")

    # Remove trailing slashes and split
    clean_path = full_path.rstrip("/")
    if not clean_path:
        raise ValueError("Empty path after cleaning")

    return clean_path.split("/")[-1]


def get_object_path(full_path: str) -> str:
    """Extracts the directory path from the full path."""
    if not full_path or not isinstance(full_path, str):
        raise ValueError("Invalid path provided")

    # Remove trailing slashes
    clean_path = full_path.rstrip("/")
    if not clean_path:
        return ""  # Root level

    # If no slash, it's at root level
    if "/" not in clean_path:
        return ""

    return clean_path.rsplit("/", 1)[0]


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
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["AccessDenied", "NoSuchTagSet"]:
                logger.info(
                    f"Cannot access tags for {source_key} (error: {error_code}), using default tags",
                    extra={
                        "source_key": source_key,
                        "error_code": error_code,
                        "inventory_id": inventory_id,
                        "operation": "get_object_tagging_fallback",
                    },
                )
            else:
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
        orig_base = get_object_name_from_path(source_path).rsplit(".", 1)[0]
        new_base = get_object_name_from_path(new_name).rsplit(".", 1)[0]
        orig_derived_paths = [
            dr["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
            for dr in asset.get("DerivedRepresentations", [])
        ]

        # Validate that the source object actually exists before attempting copy
        if not check_object_exists(source_bucket, source_path):
            logger.error(
                f"Source object does not exist in S3 at expected location",
                extra={
                    "source_bucket": source_bucket,
                    "source_path": source_path,
                    "inventory_id": inventory_id,
                    "operation": "source_validation_failed",
                },
            )

            # Try to find the file at the target location (in case previous rename failed to update DynamoDB)
            new_object_name = get_object_name_from_path(new_name)
            base_directory = get_object_path(source_path)
            potential_source_path = (
                f"{base_directory}/{new_object_name}"
                if base_directory
                else new_object_name
            )

            if check_object_exists(source_bucket, potential_source_path):
                logger.info(
                    f"Found source file at target location - DynamoDB may be out of sync",
                    extra={
                        "expected_path": source_path,
                        "found_at_path": potential_source_path,
                        "inventory_id": inventory_id,
                        "operation": "source_found_at_target",
                    },
                )
                # Update the source path to the actual location
                source_path = potential_source_path
                # Update the asset record to reflect reality
                main_storage["ObjectKey"]["FullPath"] = source_path
                main_storage["ObjectKey"]["Name"] = new_object_name
                main_rep["Name"] = new_object_name
            else:
                raise AssetRenameError(
                    f"Source file not found at expected location ({source_path}) or target location ({potential_source_path}). "
                    f"This indicates a data inconsistency between DynamoDB and S3.",
                    HTTPStatus.NOT_FOUND,
                )

        # Extract the object name from the new_name (in case it contains path elements)
        new_object_name = get_object_name_from_path(new_name)

        # Update object name in DynamoDB
        main_rep["Name"] = new_object_name

        # Get the directory path without including the object name
        base_directory = get_object_path(source_path)

        # Create new path with just the parent directory and new filename
        if base_directory:
            new_path = f"{base_directory}/{new_object_name}"
        else:
            new_path = new_object_name

        logger.info(
            "Constructed new path for main representation",
            extra={
                "source_path": source_path,
                "base_directory": base_directory,
                "new_object_name": new_object_name,
                "new_path": new_path,
                "operation": "path_construction",
            },
        )

        # Check if target already exists (but handle orphaned files from failed deletions)
        if check_object_exists(source_bucket, new_path):
            # If target exists, this indicates an orphaned file from a previous failed deletion
            logger.error(
                f"Target object {new_path} already exists",
                extra={
                    "source_path": source_path,
                    "new_path": new_path,
                    "operation": "orphaned_file_detected",
                    "inventory_id": inventory_id,
                },
            )

            # Return specific error for orphaned file detection - do not proceed with rename
            raise AssetRenameError(
                f"Cannot rename asset: target file '{new_object_name}' already exists.",
                HTTPStatus.CONFLICT,  # 409 status code for resource conflict
            )
        else:
            logger.info(
                "Target path is clear, proceeding with rename",
                extra={
                    "source_path": source_path,
                    "new_path": new_path,
                    "operation": "rename_proceed",
                },
            )

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

            # Use consistent path construction logic matching top-level DerivedRepresentations
            dirpath = get_object_path(derived_path)
            orig_filename = get_object_name_from_path(derived_path)

            try:
                # Extract base name and extension from original filename
                prefix, ext = orig_filename.rsplit(".", 1)
                # Calculate suffix by removing the original base name
                suffix = (
                    prefix[len(orig_base) :]
                    if prefix.startswith(orig_base)
                    else f"_derived_{idx}"
                )
                # Construct new filename with new base + suffix + extension
                new_derived_name = f"{new_base}{suffix}.{ext}"
                # Construct full path preserving original directory structure
                new_derived_path = join_key(dirpath, new_derived_name)

                logger.info(
                    "Processing derived representation with consistent naming",
                    extra={
                        "orig_filename": orig_filename,
                        "orig_base": orig_base,
                        "new_base": new_base,
                        "suffix": suffix,
                        "new_derived_name": new_derived_name,
                        "dirpath": dirpath,
                        "new_derived_path": new_derived_path,
                        "derived_index": idx,
                    },
                )

            except Exception as e:
                logger.error(
                    f"Error constructing derived name for index {idx}",
                    extra={
                        "error": str(e),
                        "derived_path": derived_path,
                        "source_path": source_path,
                        "new_object_name": new_object_name,
                    },
                )
                # Fallback to simple naming with preserved directory structure
                new_derived_name = f"{new_object_name}_derived_{idx}"
                new_derived_path = join_key(dirpath, new_derived_name)

            # Update object name in DynamoDB
            derived["Name"] = new_derived_name

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
        logger.info("Copy Derived Representations")
        # — now ALSO copy the top-level DerivedRepresentations —

        for dr in asset.get("DerivedRepresentations", []):
            storage = dr["StorageInfo"]["PrimaryLocation"]
            bucket = storage["Bucket"]
            old_full = storage["ObjectKey"]["FullPath"]
            dirpath = get_object_path(old_full)
            orig_filename = get_object_name_from_path(old_full)
            prefix, ext = orig_filename.rsplit(".", 1)
            suffix = prefix[len(orig_base) :]
            new_filename = f"{new_base}{suffix}.{ext}"
            new_full = join_key(dirpath, new_filename)

            storage["ObjectKey"]["FullPath"] = new_full
            storage["ObjectKey"]["Name"] = new_filename

            # now copy it
            logger.info(f"Copying {old_full} to {new_full} in {bucket}")
            copy_s3_object_with_tags(
                bucket, old_full, bucket, new_full, inventory_id, is_master=False
            )
            successful_copies.append({"bucket": bucket, "key": new_full})

        return successful_copies, orig_derived_paths

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
    if not copies:
        return

    logger.info(
        f"Starting cleanup of {len(copies)} copied objects",
        extra={"operation": "cleanup_rollback", "object_count": len(copies)},
    )

    cleanup_errors = []
    for i, copied_obj in enumerate(copies):
        try:
            s3.delete_object(Bucket=copied_obj["bucket"], Key=copied_obj["key"])
            logger.info(
                f"Successfully cleaned up copied object {i+1}/{len(copies)}",
                extra={
                    "bucket": copied_obj["bucket"],
                    "key": copied_obj["key"],
                    "operation": "cleanup_success",
                },
            )
        except ClientError as e:
            error_msg = f"Failed to cleanup copied object {copied_obj['bucket']}/{copied_obj['key']}: {str(e)}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)

    if cleanup_errors:
        logger.error(
            f"Cleanup completed with {len(cleanup_errors)} errors",
            extra={
                "operation": "cleanup_completed_with_errors",
                "error_count": len(cleanup_errors),
                "errors": cleanup_errors,
            },
        )
    else:
        logger.info(
            "All copied objects cleaned up successfully",
            extra={"operation": "cleanup_completed_success"},
        )


@tracer.capture_method
def delete_original_objects(asset: Dict[str, Any]) -> None:
    """
    Deletes original objects after successful copy.
    This function now fails fast on any deletion error to prevent data inconsistency.
    """
    inventory_id = asset.get("InventoryID", "unknown")
    objects_to_delete = []

    try:
        # Collect all objects to delete first
        main_storage = asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]
        main_bucket = main_storage["Bucket"]
        main_key = main_storage["ObjectKey"]["FullPath"]

        objects_to_delete.append(
            {
                "bucket": main_bucket,
                "key": main_key,
                "type": "main",
                "index": 0,
                "critical": True,  # Main representation deletion is critical
            }
        )

        # Add derived representations
        for idx, derived in enumerate(
            asset["DigitalSourceAsset"].get("DerivedRepresentations", [])
        ):
            if (
                not derived.get("StorageInfo", {})
                .get("PrimaryLocation", {})
                .get("ObjectKey")
            ):
                logger.warning(
                    "Skipping derived representation deletion - missing storage info",
                    extra={
                        "inventory_id": inventory_id,
                        "derived_index": idx,
                        "operation": "delete_derived_skip",
                    },
                )
                continue

            storage = derived["StorageInfo"]["PrimaryLocation"]
            derived_bucket = storage["Bucket"]
            derived_key = storage["ObjectKey"]["FullPath"]

            objects_to_delete.append(
                {
                    "bucket": derived_bucket,
                    "key": derived_key,
                    "type": "derived",
                    "index": idx,
                    "critical": True,  # All deletions are now critical for data consistency
                }
            )

        logger.info(
            f"Starting atomic deletion of {len(objects_to_delete)} original objects",
            extra={
                "inventory_id": inventory_id,
                "total_objects": len(objects_to_delete),
                "operation": "delete_original_objects_start",
            },
        )

        # Delete objects one by one - fail fast on any error
        deleted_objects = []
        for obj in objects_to_delete:
            try:
                logger.info(
                    f"Deleting {obj['type']} representation",
                    extra={
                        "inventory_id": inventory_id,
                        "bucket": obj["bucket"],
                        "key": obj["key"],
                        "type": obj["type"],
                        "index": obj["index"],
                        "operation": f"delete_{obj['type']}_representation",
                    },
                )

                # Verify object exists before attempting deletion
                if not check_object_exists(obj["bucket"], obj["key"]):
                    logger.warning(
                        f"{obj['type']} object already deleted or doesn't exist",
                        extra={
                            "inventory_id": inventory_id,
                            "bucket": obj["bucket"],
                            "key": obj["key"],
                            "type": obj["type"],
                            "operation": f"delete_{obj['type']}_already_gone",
                        },
                    )
                    # Continue - object is already gone, which is what we want
                    continue

                # Perform the deletion
                s3.delete_object(Bucket=obj["bucket"], Key=obj["key"])
                deleted_objects.append(obj)

                # Verify deletion was successful
                if check_object_exists(obj["bucket"], obj["key"]):
                    raise ClientError(
                        error_response={
                            "Error": {
                                "Code": "DeletionVerificationFailed",
                                "Message": f"Object still exists after deletion: {obj['key']}",
                            }
                        },
                        operation_name="delete_object",
                    )

                logger.info(
                    f"Successfully deleted and verified {obj['type']} representation",
                    extra={
                        "inventory_id": inventory_id,
                        "bucket": obj["bucket"],
                        "key": obj["key"],
                        "type": obj["type"],
                        "index": obj["index"],
                        "operation": f"delete_{obj['type']}_representation_success",
                    },
                )

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_msg = f"Failed to delete {obj['type']} object {obj['bucket']}/{obj['key']}: {str(e)}"

                logger.error(
                    f"CRITICAL: Deletion failed for {obj['type']} representation",
                    extra={
                        "inventory_id": inventory_id,
                        "bucket": obj["bucket"],
                        "key": obj["key"],
                        "type": obj["type"],
                        "index": obj["index"],
                        "error_code": error_code,
                        "error_message": str(e),
                        "deleted_so_far": len(deleted_objects),
                        "operation": f"delete_{obj['type']}_error_critical",
                    },
                )

                # FAIL FAST: Any deletion failure is now critical
                raise Exception(f"Critical deletion failure: {error_msg}")

        # — also delete the top-level DerivedRepresentations files —
        for dr in asset.get("DerivedRepresentations", []):
            loc = dr["StorageInfo"]["PrimaryLocation"]
            bucket = loc["Bucket"]
            key = loc["ObjectKey"]["FullPath"]
            s3.delete_object(Bucket=bucket, Key=key)

        logger.info(
            f"Successfully deleted all {len(objects_to_delete)} original objects atomically",
            extra={
                "inventory_id": inventory_id,
                "total_objects": len(objects_to_delete),
                "deleted_objects": len(deleted_objects),
                "operation": "delete_completed_success",
            },
        )

    except Exception as e:
        logger.error(
            f"CRITICAL: Deletion process failed - system may be in inconsistent state",
            extra={
                "inventory_id": inventory_id,
                "error": str(e),
                "total_objects": len(objects_to_delete),
                "operation": "delete_process_failed_critical",
            },
        )
        # Re-raise the error to trigger rollback in the calling function
        raise


@tracer.capture_method
def update_asset_paths(asset: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """
    Updates all paths in the asset record with atomic DynamoDB operation.
    This function must succeed completely or fail completely to maintain data integrity.
    """
    inventory_id = asset.get("InventoryID", "unknown")

    try:
        # 1) pull out the old master path
        main_rep = asset["DigitalSourceAsset"]["MainRepresentation"]
        old_full_master = main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
            "FullPath"
        ]
        if not old_full_master:
            raise AssetRenameError("Missing master FullPath", HTTPStatus.BAD_REQUEST)

        # 2) break the new name into base + extension
        new_filename = get_object_name_from_path(new_name)
        new_base, new_ext = new_filename.rsplit(".", 1)
        parent_dir = get_object_path(old_full_master)

        logger.info(
            "Updating asset paths in DynamoDB",
            extra={
                "inventory_id": inventory_id,
                "old_path": old_full_master,
                "new_name": new_filename,
            },
        )

        # 3) Update main representation
        master_objkey = main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"]
        new_master_full = f"{parent_dir}/{new_filename}" if parent_dir else new_filename
        master_objkey["FullPath"] = new_master_full
        master_objkey["Name"] = new_filename

        # 4) Update nested DerivedRepresentations under DigitalSourceAsset
        orig_base = old_full_master.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        derived_updates = []

        for idx, dr in enumerate(
            asset["DigitalSourceAsset"].get("DerivedRepresentations", [])
        ):
            dk = dr["StorageInfo"]["PrimaryLocation"]["ObjectKey"]
            old_full = dk["FullPath"]
            orig_name = get_object_name_from_path(old_full)
            name_only, orig_ext = orig_name.rsplit(".", 1)
            suffix = name_only[len(orig_base) :]
            new_name_derived = f"{new_base}{suffix}.{orig_ext}"
            new_full_derived = f"{get_object_path(old_full)}/{new_name_derived}"
            dk["FullPath"] = new_full_derived
            dk["Name"] = new_name_derived

            derived_updates.append(
                {
                    "index": idx,
                    "old_path": old_full,
                    "new_path": new_full_derived,
                    "new_name": new_name_derived,
                }
            )

        # 5) ALSO update the top-level DerivedRepresentations array
        for idx, dr in enumerate(asset.get("DerivedRepresentations", [])):
            dk = dr["StorageInfo"]["PrimaryLocation"]["ObjectKey"]
            old_full = dk["FullPath"]
            orig_name = get_object_name_from_path(old_full)
            name_only, orig_ext = orig_name.rsplit(".", 1)
            suffix = name_only[len(orig_base) :]
            new_name_derived = f"{new_base}{suffix}.{orig_ext}"
            new_full_derived = join_key(get_object_path(old_full), new_name_derived)
            dk["FullPath"] = new_full_derived
            dk["Name"] = new_name_derived

            derived_updates.append(
                {
                    "index": idx,
                    "old_path": old_full,
                    "new_path": new_full_derived,
                    "new_name": new_name_derived,
                }
            )

        # 6) Update the top-level StoragePath
        bucket = main_rep["StorageInfo"]["PrimaryLocation"]["Bucket"]
        asset["StoragePath"] = f"{bucket}:{new_filename}"

        logger.info(
            f"Prepared updates — main + {len(derived_updates)} derived",
            extra={
                "inventory_id": inventory_id,
                "main_new_path": new_master_full,
                "derived_updates": derived_updates,
            },
        )

        # 7) Write back atomically
        table.put_item(Item=asset, ConditionExpression="attribute_exists(InventoryID)")

        logger.info(
            "Successfully updated asset paths in DynamoDB",
            extra={
                "inventory_id": inventory_id,
                "main_new_path": new_master_full,
                "derived_count": len(derived_updates),
            },
        )
        return asset

    except ClientError as e:
        logger.error(
            "DynamoDB update failed",
            extra={"inventory_id": inventory_id, "error": str(e)},
        )
        raise AssetRenameError(f"Failed to update asset record: {str(e)}")

    except AssetRenameError:
        raise

    except Exception as e:
        logger.error(
            "Unexpected error updating asset paths",
            extra={"inventory_id": inventory_id, "error": str(e)},
        )
        raise AssetRenameError(f"Failed to update asset record: {str(e)}")


@tracer.capture_method
def check_object_exists(bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise


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
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """Lambda handler for asset renaming: 1) update DB paths, 2) copy S3 objects, 3) delete originals."""
    try:
        # 1) Extract and validate InventoryID
        inventory_id = event.get("pathParameters", {}).get("id")
        if not inventory_id:
            raise AssetRenameError("Missing inventory ID", HTTPStatus.BAD_REQUEST)

        # 2) Parse and validate newName
        body = json.loads(event.get("body", "{}"))
        new_name = body.get("newName")
        if new_name is None:
            raise AssetRenameError(
                "Missing newName in request body", HTTPStatus.BAD_REQUEST
            )
        validate_name(new_name)

        # 3) Load current asset metadata and snapshot for S3 operations
        asset = get_asset(inventory_id)
        original_asset = copy.deepcopy(asset)

        logger.info(
            "Starting full rename: DB update → S3 copy → S3 delete",
            extra={"inventory_id": inventory_id, "new_name": new_name},
        )

        # 4) Update all paths in DynamoDB first (will fail fast if something's wrong)
        update_asset_paths(asset, new_name)

        # 5) Using the pristine snapshot, copy all the original S3 objects
        copy_snapshot = copy.deepcopy(original_asset)
        copy_s3_objects(copy_snapshot, new_name)

        # 6) Then delete the originals from that same snapshot
        delete_original_objects(original_asset)

        # 7) Record successful rename
        metrics.add_metric(name="AssetRenames", unit=MetricUnit.Count, value=1)
        return create_response(HTTPStatus.OK, "Asset renamed successfully")

    except AssetRenameError as e:
        logger.warning(
            f"Asset rename failed: {e}",
            extra={"inventory_id": inventory_id, "error_code": e.status_code},
        )
        return create_response(e.status_code, str(e))

    except Exception as e:
        logger.error(
            f"Unexpected error during asset rename: {e}",
            extra={"inventory_id": event.get("pathParameters", {}).get("id")},
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error"
        )
