"""
DynamoDB update logic for asset metadata.

This module provides functions for updating asset records in DynamoDB
with extracted metadata.
"""

import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Initialize DynamoDB client (reused across invocations)
dynamodb_client = None


def get_dynamodb_client():
    """
    Get or create DynamoDB client.

    Returns:
        boto3 DynamoDB client
    """
    global dynamodb_client
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")
    return dynamodb_client


async def update_asset_metadata(
    inventory_id: str, metadata: Dict[str, Any], table_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update asset metadata in DynamoDB.

    Updates the asset record with the provided metadata at the path
    Metadata.EmbeddedMetadata. Uses InventoryID as the key.

    Args:
        inventory_id: Asset inventory ID (DynamoDB key)
        metadata: Marshalled metadata to store
        table_name: DynamoDB table name (defaults to MEDIALAKE_ASSET_TABLE env var)

    Returns:
        Updated asset record from DynamoDB

    Raises:
        ClientError: If DynamoDB update fails
        ValueError: If table_name is not provided and env var is not set

    Examples:
        >>> metadata = {"tiff": {"Image Width": {"value": 1920}}}
        >>> result = await update_asset_metadata("asset-123", metadata)
        >>> result["InventoryID"]
        "asset-123"
    """
    # Get table name from parameter or environment variable
    if table_name is None:
        table_name = os.environ.get("MEDIALAKE_ASSET_TABLE")
        if not table_name:
            raise ValueError(
                "table_name must be provided or MEDIALAKE_ASSET_TABLE "
                "environment variable must be set"
            )

    # Get DynamoDB client
    client = get_dynamodb_client()

    # Marshall the metadata to DynamoDB format
    import json

    from boto3.dynamodb.types import TypeSerializer

    serializer = TypeSerializer()
    marshalled_metadata = serializer.serialize(metadata)

    # Check size of marshalled metadata (DynamoDB has 400KB item size limit)
    # We need to account for the entire item, not just the metadata
    # Conservative limit: 350KB for metadata to leave room for other fields
    metadata_size = len(json.dumps(marshalled_metadata))
    MAX_METADATA_SIZE = 350 * 1024  # 350KB

    if metadata_size > MAX_METADATA_SIZE:
        print(
            f"WARNING: Metadata size ({metadata_size} bytes) exceeds limit ({MAX_METADATA_SIZE} bytes). Truncating..."
        )
        # For now, just log and try anyway - DynamoDB will reject if too large
        # TODO: Implement intelligent truncation (remove large arrays, etc.)

    try:
        # Update the item at path Metadata.EmbeddedMetadata
        response = client.update_item(
            TableName=table_name,
            Key={"InventoryID": {"S": inventory_id}},
            UpdateExpression="SET #M.#E = :m",
            ExpressionAttributeNames={"#M": "Metadata", "#E": "EmbeddedMetadata"},
            ExpressionAttributeValues={":m": marshalled_metadata},
            ReturnValues="ALL_NEW",
        )

        # Unmarshall the response
        from boto3.dynamodb.types import TypeDeserializer

        deserializer = TypeDeserializer()

        # Deserialize the attributes
        updated_asset = {}
        if "Attributes" in response:
            for key, value in response["Attributes"].items():
                updated_asset[key] = deserializer.deserialize(value)

        return updated_asset

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # Re-raise with more context
        raise ClientError(
            {
                "Error": {
                    "Code": error_code,
                    "Message": f"Failed to update asset {inventory_id}: {error_message}",
                }
            },
            "UpdateItem",
        ) from e
