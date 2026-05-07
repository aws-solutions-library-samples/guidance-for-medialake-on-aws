"""
S3 location extraction and file type routing utilities.

This module provides functions for extracting S3 location information from
asset structures and routing files to appropriate metadata extractors based
on file extension.
"""

import os
from typing import Any, Dict, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger

logger = Logger(child=True)


def extract_s3_location(asset: dict) -> Optional[Tuple[str, str]]:
    """
    Extract S3 bucket and key from asset structure.

    Extracts the bucket and object key from the asset's
    DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation structure.

    Args:
        asset: Asset dictionary containing S3 location information

    Returns:
        Tuple of (bucket, key) or None if location is invalid or missing

    Examples:
        >>> asset = {
        ...     "DigitalSourceAsset": {
        ...         "MainRepresentation": {
        ...             "StorageInfo": {
        ...                 "PrimaryLocation": {
        ...                     "Bucket": "my-bucket",
        ...                     "ObjectKey": {"FullPath": "path/to/image.jpg"}
        ...                 }
        ...             }
        ...         }
        ...     }
        ... }
        >>> extract_s3_location(asset)
        ('my-bucket', 'path/to/image.jpg')

        >>> extract_s3_location({})
        None
    """
    try:
        # Navigate through the nested structure
        digital_source = asset.get("DigitalSourceAsset")
        if not digital_source:
            return None

        main_rep = digital_source.get("MainRepresentation")
        if not main_rep:
            return None

        storage_info = main_rep.get("StorageInfo")
        if not storage_info:
            return None

        primary_location = storage_info.get("PrimaryLocation")
        if not primary_location:
            return None

        # Extract bucket and key
        bucket = primary_location.get("Bucket")
        object_key_dict = primary_location.get("ObjectKey")

        if not bucket or not object_key_dict:
            return None

        full_path = object_key_dict.get("FullPath")
        if not full_path:
            return None

        return (bucket, full_path)

    except (AttributeError, TypeError):
        # Handle cases where the structure is malformed
        return None


async def _download_file_from_s3(bucket: str, key: str) -> bytes:
    """
    Download file from S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        bytes: File content

    Raises:
        Exception: If S3 download fails
    """
    logger.debug(f"Downloading file from S3: {bucket}/{key}")
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    file_buffer = response["Body"].read()
    logger.debug(f"Downloaded {len(file_buffer)} bytes")
    return file_buffer


async def process_image_file(bucket: str, key: str) -> Dict[str, Any]:
    """
    Route file to appropriate metadata extractor based on extension.

    Determines the file type from the extension and routes to:
    - Unsupported formats (.webp, .exr): Return error message
    - SVG files (.svg): Route to XML parser
    - Supported formats: Route to exifr-py parser

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        dict: Extracted metadata or error message

    Examples:
        >>> await process_image_file("bucket", "image.webp")
        {"UnsupportedFormat": "WebP format is not supported"}

        >>> await process_image_file("bucket", "image.svg")
        {"SVGMetadata": {...}}  # or None if no metadata

        >>> await process_image_file("bucket", "image.jpg")
        {"tiff": {...}, "exif": {...}}
    """
    # Extract file extension (case-insensitive)
    _, ext = os.path.splitext(key)
    ext_lower = ext.lower()

    # Check for unsupported formats
    if ext_lower in [".webp"]:
        return {"UnsupportedFormat": "WebP format is not supported"}

    # Route to appropriate extractor
    if ext_lower == ".svg":
        from svg_parser import extract_svg_metadata

        try:
            file_buffer = await _download_file_from_s3(bucket, key)
            svg_metadata = await extract_svg_metadata(file_buffer)
            return {"SVGMetadata": svg_metadata if svg_metadata else None}
        except Exception as e:
            logger.error(f"Error processing SVG file {key}: {e}", exc_info=True)
            return {"SVGMetadata": {"error": f"Failed to process SVG: {str(e)}"}}

    elif ext_lower == ".exr":
        from exr_parser import extract_exr_metadata_safe

        try:
            logger.info(f"Processing EXR file: {key}")
            file_buffer = await _download_file_from_s3(bucket, key)

            logger.debug("Extracting EXR metadata using safe minimal approach")
            exr_metadata = await extract_exr_metadata_safe(file_buffer)
            logger.debug(
                f"EXR metadata extracted with keys: {list(exr_metadata.keys())}"
            )

            return {"EXRMetadata": exr_metadata}
        except Exception as e:
            logger.error(f"Error processing EXR file {key}: {e}", exc_info=True)
            return {"EXRMetadata": {"error": f"Failed to process EXR: {str(e)}"}}

    else:
        from exifr_parser import extract_organized_metadata

        try:
            file_buffer = await _download_file_from_s3(bucket, key)
            metadata = await extract_organized_metadata(file_buffer)
            return metadata
        except Exception as e:
            logger.error(f"Error processing image file {key}: {e}", exc_info=True)
            return {"error": f"Failed to extract metadata: {str(e)}"}
