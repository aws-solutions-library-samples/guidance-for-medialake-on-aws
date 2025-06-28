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
from aws_lambda_powertools.utilities.parser import event_parser
from pydantic import BaseModel, Field
from botocore.exceptions import ClientError
import boto3
import os
import json
from http import HTTPStatus
import re
from decimal import Decimal

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
    updatePathsOnly: bool = Field(False, description="If true, only update DynamoDB paths without moving S3 objects")


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
    - Control characters (\x01-\x1F, \x7F-\x9F)
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
    problematic_chars = ['\x00', '\r', '\n', '\t']
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
    if len(name.encode('utf-8')) > 1024:
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
            extra={
                "inventory_id": inventory_id,
                "operation": "get_asset"
            }
        )
        
        # Use consistent read to avoid eventual consistency issues
        response = table.get_item(
            Key={"InventoryID": inventory_id},
            ConsistentRead=True
        )

        if "Item" not in response:
            logger.error(
                "Asset not found in DynamoDB",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "get_asset",
                    "dynamodb_response_keys": list(response.keys())
                }
            )
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
            logger.error(
                "Asset has invalid structure",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "get_asset",
                    "has_digital_source": bool(asset.get("DigitalSourceAsset")),
                    "has_main_rep": bool(asset.get("DigitalSourceAsset", {}).get("MainRepresentation")),
                }
            )
            raise AssetRenameError("Invalid asset location", HTTPStatus.BAD_REQUEST)

        logger.info(
            "Successfully retrieved asset",
            extra={
                "inventory_id": inventory_id,
                "operation": "get_asset",
                "has_derived_reps": len(asset["DigitalSourceAsset"].get("DerivedRepresentations", []))
            }
        )

        return asset

    except ClientError as e:
        logger.error(
            "DynamoDB error retrieving asset",
            extra={
                "inventory_id": inventory_id,
                "error_code": e.response.get("Error", {}).get("Code", "Unknown"),
                "error_message": str(e),
                "operation": "get_asset"
            }
        )
        raise AssetRenameError(f"Failed to retrieve asset: {str(e)}")


def get_object_name_from_path(full_path: str) -> str:
    """Extracts the object name from the full path with validation."""
    if not full_path or not isinstance(full_path, str):
        raise ValueError("Invalid path provided")
    
    # Remove trailing slashes and split
    clean_path = full_path.rstrip('/')
    if not clean_path:
        raise ValueError("Empty path after cleaning")
    
    return clean_path.split("/")[-1]

def get_object_path(full_path: str) -> str:
    """Extracts the directory path from the full path."""
    if not full_path or not isinstance(full_path, str):
        raise ValueError("Invalid path provided")
    
    # Remove trailing slashes
    clean_path = full_path.rstrip('/')
    if not clean_path:
        return ""  # Root level
    
    # If no slash, it's at root level
    if '/' not in clean_path:
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
                        "operation": "get_object_tagging_fallback"
                    }
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

        # Validate that the source object actually exists before attempting copy
        if not check_object_exists(source_bucket, source_path):
            logger.error(
                f"Source object does not exist in S3 at expected location",
                extra={
                    "source_bucket": source_bucket,
                    "source_path": source_path,
                    "inventory_id": inventory_id,
                    "operation": "source_validation_failed"
                }
            )
            
            # Try to find the file at the target location (in case previous rename failed to update DynamoDB)
            new_object_name = get_object_name_from_path(new_name)
            base_directory = get_object_path(source_path)
            potential_source_path = f"{base_directory}/{new_object_name}" if base_directory else new_object_name
            
            if check_object_exists(source_bucket, potential_source_path):
                logger.info(
                    f"Found source file at target location - DynamoDB may be out of sync",
                    extra={
                        "expected_path": source_path,
                        "found_at_path": potential_source_path,
                        "inventory_id": inventory_id,
                        "operation": "source_found_at_target"
                    }
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
                    HTTPStatus.NOT_FOUND
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
                "operation": "path_construction"
            }
        )

        # Check if target already exists (but handle orphaned files from failed deletions)
        if check_object_exists(source_bucket, new_path):
            # If target exists, check if it's an orphaned file from a previous failed deletion
            logger.warning(
                f"Target object {new_path} already exists - this may be from a previous failed deletion",
                extra={
                    "source_path": source_path,
                    "new_path": new_path,
                    "operation": "orphaned_file_detected"
                }
            )
            
            # For now, we'll allow the operation to proceed and overwrite
            # The copy operation will replace the orphaned file
            logger.info(
                "Proceeding with rename - will overwrite existing target",
                extra={
                    "source_path": source_path,
                    "new_path": new_path,
                    "operation": "overwrite_orphaned_file"
                }
            )
        else:
            logger.info(
                "Target path is clear, proceeding with rename",
                extra={
                    "source_path": source_path,
                    "new_path": new_path,
                    "operation": "rename_proceed"
                }
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
            
            # Simplified derived name generation to prevent path construction errors
            try:
                original_name = get_object_name_from_path(source_path)
                derived_name = get_object_name_from_path(derived_path)
                
                logger.info(
                    "Processing derived representation naming",
                    extra={
                        "original_name": original_name,
                        "derived_name": derived_name,
                        "new_object_name": new_object_name,
                        "derived_index": idx,
                    }
                )
                
                # Simple replacement approach - if original name is part of derived name, replace it
                if original_name in derived_name:
                    new_derived_name = derived_name.replace(original_name, new_object_name)
                else:
                    # Fallback: use new name with derived extension if different
                    original_parts = original_name.split('.')
                    derived_parts = derived_name.split('.')
                    new_parts = new_object_name.split('.')
                    
                    if len(derived_parts) > 1 and len(original_parts) > 1:
                        # If derived has different extension, preserve it
                        if derived_parts[-1] != original_parts[-1]:
                            new_base = '.'.join(new_parts[:-1]) if len(new_parts) > 1 else new_object_name
                            new_derived_name = f"{new_base}.{derived_parts[-1]}"
                        else:
                            new_derived_name = new_object_name
                    else:
                        new_derived_name = new_object_name
                
                # Construct new path safely
                derived_base_path = get_object_path(derived_path)
                if derived_base_path:
                    new_derived_path = f"{derived_base_path}/{new_derived_name}"
                else:
                    new_derived_path = new_derived_name
                    
            except Exception as e:
                logger.error(
                    f"Error constructing derived name for index {idx}",
                    extra={
                        "error": str(e),
                        "derived_path": derived_path,
                        "source_path": source_path,
                        "new_object_name": new_object_name,
                    }
                )
                # Fallback to simple naming
                new_derived_name = f"{new_object_name}_derived_{idx}"
                derived_base_path = get_object_path(derived_path)
                new_derived_path = f"{derived_base_path}/{new_derived_name}" if derived_base_path else new_derived_name

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
    if not copies:
        return
        
    logger.info(
        f"Starting cleanup of {len(copies)} copied objects",
        extra={"operation": "cleanup_rollback", "object_count": len(copies)}
    )
    
    cleanup_errors = []
    for i, copy in enumerate(copies):
        try:
            s3.delete_object(Bucket=copy["bucket"], Key=copy["key"])
            logger.info(
                f"Successfully cleaned up copied object {i+1}/{len(copies)}",
                extra={
                    "bucket": copy["bucket"],
                    "key": copy["key"],
                    "operation": "cleanup_success"
                }
            )
        except ClientError as e:
            error_msg = f"Failed to cleanup copied object {copy['bucket']}/{copy['key']}: {str(e)}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
    
    if cleanup_errors:
        logger.error(
            f"Cleanup completed with {len(cleanup_errors)} errors",
            extra={
                "operation": "cleanup_completed_with_errors",
                "error_count": len(cleanup_errors),
                "errors": cleanup_errors
            }
        )
    else:
        logger.info(
            "All copied objects cleaned up successfully",
            extra={"operation": "cleanup_completed_success"}
        )


@tracer.capture_method
def delete_original_objects(asset: Dict[str, Any]) -> None:
    """Deletes original objects after successful copy with improved error handling."""
    deletion_errors = []
    objects_to_delete = []
    
    try:
        # Collect all objects to delete first
        main_storage = asset["DigitalSourceAsset"]["MainRepresentation"]["StorageInfo"][
            "PrimaryLocation"
        ]
        main_bucket = main_storage["Bucket"]
        main_key = main_storage["ObjectKey"]["FullPath"]
        
        objects_to_delete.append({
            "bucket": main_bucket,
            "key": main_key,
            "type": "main",
            "index": 0
        })

        # Add derived representations
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
            
            objects_to_delete.append({
                "bucket": derived_bucket,
                "key": derived_key,
                "type": "derived",
                "index": idx
            })

        logger.info(
            f"Starting deletion of {len(objects_to_delete)} original objects",
            extra={
                "total_objects": len(objects_to_delete),
                "operation": "delete_original_objects_start"
            }
        )

        # Delete objects one by one with individual error handling
        for obj in objects_to_delete:
            try:
                logger.info(
                    f"Deleting {obj['type']} representation",
                    extra={
                        "bucket": obj["bucket"],
                        "key": obj["key"],
                        "type": obj["type"],
                        "index": obj["index"],
                        "operation": f"delete_{obj['type']}_representation",
                    },
                )

                s3.delete_object(Bucket=obj["bucket"], Key=obj["key"])

                logger.info(
                    f"Successfully deleted {obj['type']} representation",
                    extra={
                        "bucket": obj["bucket"],
                        "key": obj["key"],
                        "type": obj["type"],
                        "index": obj["index"],
                        "operation": f"delete_{obj['type']}_representation_success",
                    },
                )

            except ClientError as e:
                error_msg = f"Failed to delete {obj['type']} object {obj['bucket']}/{obj['key']}: {str(e)}"
                logger.error(
                    error_msg,
                    extra={
                        "bucket": obj["bucket"],
                        "key": obj["key"],
                        "type": obj["type"],
                        "index": obj["index"],
                        "error_code": e.response.get("Error", {}).get("Code", "Unknown"),
                        "operation": f"delete_{obj['type']}_error",
                    },
                )
                deletion_errors.append(error_msg)

        # Report results
        if deletion_errors:
            logger.error(
                f"Deletion completed with {len(deletion_errors)} errors out of {len(objects_to_delete)} objects",
                extra={
                    "total_objects": len(objects_to_delete),
                    "error_count": len(deletion_errors),
                    "success_count": len(objects_to_delete) - len(deletion_errors),
                    "errors": deletion_errors,
                    "operation": "delete_completed_with_errors",
                },
            )
            # Don't raise error - partial success is acceptable for delete operations
            # The copy was successful and DynamoDB will be updated
        else:
            logger.info(
                f"Successfully deleted all {len(objects_to_delete)} original objects",
                extra={
                    "total_objects": len(objects_to_delete),
                    "operation": "delete_completed_success",
                }
            )

    except Exception as e:
        logger.error(
            "Unexpected error during deletion process",
            extra={
                "error": str(e),
                "operation": "delete_unexpected_error",
            },
        )
        # Don't raise error - the copy was successful, deletion failure shouldn't fail the rename


@tracer.capture_method
def update_asset_paths(asset: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """Updates all paths in the asset record."""
    try:
        main_rep = asset["DigitalSourceAsset"]["MainRepresentation"]
        old_path = main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"]
        new_object_path = get_object_path(old_path)
        new_object_name = get_object_name_from_path(new_name)

        # Update main representation path and name
        main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"]["FullPath"] = f"{new_object_path}/{new_object_name}"
        main_rep["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
            "Name"
        ] = new_object_name
        main_rep["Name"] = new_object_name

        # Update derived representation paths and names
        for derived in asset["DigitalSourceAsset"].get("DerivedRepresentations", []):
            if not derived.get("StorageInfo", {}).get("PrimaryLocation"):
                continue

            derived_path = derived["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                "FullPath"
            ]
            # Get the parent directory path without the filename
            derived_base_path = get_object_path(derived_path)
            
            # Use the derived name that was set in copy_s3_objects
            new_derived_name = derived["Name"]
            
            # Construct the new path properly
            new_derived_path = f"{derived_base_path}/{new_derived_name}"
            
            derived["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                "FullPath"
            ] = new_derived_path

            derived["StorageInfo"]["PrimaryLocation"]["ObjectKey"][
                "Name"
            ] = new_derived_name

        # DynamoDB put_item operation
        table.put_item(Item=asset)
        return asset

    except ClientError as e:
        logger.error(f"Failed to update asset record: {str(e)}")
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
    """Lambda handler for asset renaming."""
    try:
        # Extract and validate parameters
        inventory_id = event.get("pathParameters", {}).get("id")
        if not inventory_id:
            raise AssetRenameError("Missing inventory ID", HTTPStatus.BAD_REQUEST)

        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))
            rename_request = RenameRequest(
                newName=body.get("newName"),
                updatePathsOnly=body.get("updatePathsOnly", False)
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise AssetRenameError(
                f"Invalid request body: {str(e)}", HTTPStatus.BAD_REQUEST
            )

        # Validate new name
        validate_name(rename_request.newName)

        # Get asset
        asset = get_asset(inventory_id)

        logger.info(
            f"Starting asset rename operation",
            extra={
                "inventory_id": inventory_id,
                "new_name": rename_request.newName,
                "update_paths_only": rename_request.updatePathsOnly,
                "operation": "rename_start"
            }
        )

        if rename_request.updatePathsOnly:
            # Mode 1: Only update DynamoDB paths without moving S3 objects
            logger.info(
                "Performing paths-only rename (no S3 operations)",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "paths_only_rename"
                }
            )
            
            # Update asset record with new paths
            updated_asset = update_asset_paths(asset, rename_request.newName)
            
            logger.info(
                "Paths-only rename completed successfully",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "paths_only_rename_success"
                }
            )
        else:
            # Mode 2: Full rename with S3 copy+delete operations
            logger.info(
                "Performing full rename with S3 copy+delete",
                extra={
                    "inventory_id": inventory_id,
                    "operation": "full_rename"
                }
            )
            
            successful_copies = []
            try:
                # Copy all objects with new names
                successful_copies = copy_s3_objects(asset, rename_request.newName)

                # Update asset record with new paths BEFORE deleting originals
                # This ensures DynamoDB is consistent even if deletion fails
                updated_asset = update_asset_paths(asset, rename_request.newName)

                # Delete original objects - now with better error handling
                try:
                    delete_original_objects(asset)
                    logger.info(
                        "Full rename completed successfully",
                        extra={
                            "inventory_id": inventory_id,
                            "copied_objects": len(successful_copies),
                            "operation": "full_rename_success"
                        }
                    )
                except Exception as delete_error:
                    # Log deletion failure but don't fail the entire operation
                    # The copy and DynamoDB update were successful
                    logger.error(
                        f"Deletion failed during rename - original files may still exist",
                        extra={
                            "inventory_id": inventory_id,
                            "copied_objects": len(successful_copies),
                            "deletion_error": str(delete_error),
                            "operation": "deletion_failed_non_fatal"
                        }
                    )
                    # Continue with success since copy and DB update worked
                    logger.info(
                        "Rename completed with deletion warnings - copied objects exist at new location",
                        extra={
                            "inventory_id": inventory_id,
                            "operation": "rename_success_with_warnings"
                        }
                    )

            except Exception as e:
                # If anything fails after copying, clean up the copied objects
                if successful_copies:
                    logger.error(
                        f"Rename failed after copying {len(successful_copies)} objects, initiating rollback",
                        extra={
                            "inventory_id": inventory_id,
                            "error": str(e),
                            "copied_objects": len(successful_copies),
                            "operation": "rename_rollback"
                        }
                    )
                    cleanup_copied_objects(successful_copies)
                raise

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
