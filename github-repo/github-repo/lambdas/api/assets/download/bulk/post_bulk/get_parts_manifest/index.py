"""
Bulk Download Get Parts Manifest Lambda

This Lambda function retrieves the parts manifest for a multipart upload:
1. Gets the manifest file from S3
2. Returns the parts information in a format suitable for the Step Functions workflow

The function implements AWS best practices including:
- Structured logging with AWS Lambda Powertools
- Tracing with AWS X-Ray
- Error handling
- Metrics and monitoring
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config

# Initialize AWS Lambda Powertools
logger = Logger(service="bulk-download-get-parts-manifest")
tracer = Tracer(service="bulk-download-get-parts-manifest")
metrics = Metrics(
    namespace="BulkDownloadService", service="bulk-download-get-parts-manifest"
)

# Initialize AWS clients
s3 = boto3.client("s3", config=Config(signature_version="s3v4"))

# Get environment variables
MEDIA_ASSETS_BUCKET = os.environ["MEDIA_ASSETS_BUCKET"]


@tracer.capture_method
def get_parts_manifest(
    bucket: str, manifest_key: str, start_part: int = None, end_part: int = None
) -> Dict[str, Any]:
    """
    Retrieve the parts manifest from S3.

    Args:
        bucket: S3 bucket name
        manifest_key: S3 key of the manifest file
        start_part: Start part number (1-based, optional)
        end_part: End part number (1-based, optional)

    Returns:
        Dictionary containing parts or metadata
    """
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=manifest_key,
        )

        manifest = json.loads(response["Body"].read().decode("utf-8"))
        total_parts = len(manifest)

        # If start_part and end_part are provided, return the specific range
        if start_part is not None and end_part is not None:
            # Filter parts by part number (convert to 0-based indexing)
            filtered_parts = [
                part
                for part in manifest
                if part["partNumber"] >= start_part and part["partNumber"] <= end_part
            ]

            logger.info(
                f"Retrieved {len(filtered_parts)} parts from manifest (range {start_part}-{end_part})",
                extra={
                    "manifestKey": manifest_key,
                    "startPart": start_part,
                    "endPart": end_part,
                },
            )

            return {
                "parts": filtered_parts,
                "totalParts": total_parts,
                "manifestKey": manifest_key,
            }

        # Otherwise, return metadata about the parts for batch processing
        logger.info(
            f"Retrieved manifest with {total_parts} parts",
            extra={"manifestKey": manifest_key, "totalParts": total_parts},
        )

        # Return metadata about the parts instead of the full list
        return {
            "totalParts": total_parts,
            "manifestKey": manifest_key,
            # Return batch information for processing parts in chunks
            "partBatches": [
                {"startPart": i + 1, "endPart": min(i + 100, total_parts)}
                for i in range(0, total_parts, 100)
            ],
        }

    except Exception as e:
        logger.error(
            "Failed to retrieve parts manifest",
            extra={
                "error": str(e),
                "bucket": bucket,
                "manifestKey": manifest_key,
            },
        )
        raise


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for getting parts manifest.

    Args:
        event: Event containing job details
        context: Lambda context

    Returns:
        Dictionary containing parts information
    """
    try:
        # Extract parameters from the event
        job_id = event.get("jobId")
        manifest_key = event.get("manifestKey")

        if not job_id or not manifest_key:
            raise ValueError("Missing required parameters in event")

        # Extract optional parameters for batch processing
        start_part = event.get("startPart")
        end_part = event.get("endPart")

        # Get the parts manifest
        parts_data = get_parts_manifest(
            MEDIA_ASSETS_BUCKET, manifest_key, start_part, end_part
        )

        # Add metrics
        metrics.add_metric(
            name="PartsManifestRetrieved", unit=MetricUnit.Count, value=1
        )

        # Return the appropriate response based on whether this is a batch request
        if start_part is not None and end_part is not None:
            return {
                "jobId": job_id,
                "manifestKey": manifest_key,
                "parts": parts_data["parts"],
                "totalParts": parts_data["totalParts"],
            }
        else:
            return {
                "jobId": job_id,
                "manifestKey": manifest_key,
                "totalParts": parts_data["totalParts"],
                "partBatches": parts_data["partBatches"],
            }

    except Exception as e:
        logger.error(
            f"Error getting parts manifest: {str(e)}",
            exc_info=True,
        )

        # Add metrics
        metrics.add_metric(name="PartsManifestErrors", unit=MetricUnit.Count, value=1)

        # Re-raise the exception to be handled by Step Functions
        raise
