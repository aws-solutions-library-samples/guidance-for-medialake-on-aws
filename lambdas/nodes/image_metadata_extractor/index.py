"""
Image Metadata Extractor Lambda Function.

This Lambda function extracts embedded metadata (EXIF, XMP, GPS, JFIF, IHDR, etc.)
from image files stored in S3 and updates the MediaLake asset table in DynamoDB.
"""

import asyncio
import json
import os
from typing import Any, Dict, List

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from dynamodb_updater import update_asset_metadata
from helpers import (
    clean_exception_objects,
    convert_datetime_objects,
    convert_decimals_for_json,
    convert_floats_to_decimals,
    force_all_objects,
    sanitize_metadata,
)
from lambda_middleware import lambda_middleware
from s3_utils import extract_s3_location, process_image_file

# ── config / clients ───────────────────────────────────────────────
logger = Logger()
tracer = Tracer()

TABLE_NAME = os.environ.get("MEDIALAKE_ASSET_TABLE", "")


# ── async processing function ──────────────────────────────────────
async def process_assets_async(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process assets asynchronously.

    Args:
        assets: List of asset dictionaries

    Returns:
        List of result dictionaries
    """
    results: List[Dict[str, Any]] = []

    # Process each asset
    for asset in assets:
        inventory_id = asset.get("InventoryID")

        # Skip assets without InventoryID
        if not inventory_id:
            logger.warning("Skipping asset without InventoryID", extra={"asset": asset})
            continue

        try:
            # Extract S3 location
            location = extract_s3_location(asset)

            # Skip assets without S3 location
            if not location:
                logger.error(
                    f"Skipping asset {inventory_id} with missing S3 location",
                    extra={"asset": asset},
                )
                continue

            bucket, key = location
            logger.info(
                f"Processing asset {inventory_id}", extra={"bucket": bucket, "key": key}
            )

            # Extract metadata based on file type
            raw_metadata = await process_image_file(bucket, key)

            # Clean any exception objects that might have been returned
            cleaned_metadata = clean_exception_objects(raw_metadata)

            # Convert datetime objects to ISO strings
            datetime_converted_metadata = convert_datetime_objects(cleaned_metadata)

            # Sanitize metadata
            sanitized_metadata = sanitize_metadata(datetime_converted_metadata)

            # Convert floats to decimals
            decimal_metadata = convert_floats_to_decimals(sanitized_metadata)

            # Force all leaf values to be objects
            transformed_metadata = force_all_objects(decimal_metadata)

            # Update DynamoDB
            updated_asset = await update_asset_metadata(
                inventory_id=inventory_id,
                metadata=transformed_metadata,
                table_name=TABLE_NAME,
            )

            # Add successful result
            results.append(
                {
                    "inventoryId": inventory_id,
                    "status": "OK",
                    "updatedAsset": updated_asset,
                }
            )

            logger.info(f"Successfully processed asset {inventory_id}")

        except Exception as e:
            # Log error and add error result
            logger.error(
                f"Error processing asset {inventory_id}: {str(e)}",
                extra={"error": str(e), "inventory_id": inventory_id},
            )

            results.append(
                {"inventoryId": inventory_id, "status": "ERROR", "message": str(e)}
            )

    return results


# ── handler ────────────────────────────────────────────────────────
@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Process image metadata extraction for multiple assets.

    Extracts embedded metadata from image files and updates DynamoDB records.

    Args:
        event: Lambda event containing payload.assets array
        context: Lambda context

    Returns:
        dict: Response with statusCode and results array
    """
    logger.info("Received event", extra={"event": event})

    # Extract assets array from event
    assets = event.get("payload", {}).get("assets", [])

    if not assets:
        logger.warning("No assets found in event.payload.assets")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "No assets to process", "results": []}),
        }

    logger.info(f"Processing {len(assets)} assets")

    # Run async processing
    results = asyncio.run(process_assets_async(assets))

    # Convert Decimals to regular numbers for JSON serialization
    json_safe_results = convert_decimals_for_json(results)

    # Return results
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Processed {len(results)} assets",
                "results": json_safe_results,
            }
        ),
    }
