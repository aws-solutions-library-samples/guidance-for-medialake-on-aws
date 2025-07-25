"""
AWS Lambda handler for S3 asset processing.

This module provides the thin Lambda entry point that:
- Parses AWS S3 events
- Extracts essential information
- Delegates to the service layer
- Returns appropriate responses
"""

import json
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from service import AssetProcessingService
from utils import extract_s3_details_from_event

logger = Logger()
tracer = Tracer()
metrics = Metrics()


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for S3 asset processing events.

    Args:
        event: AWS Lambda event containing S3 notifications
        context: AWS Lambda context object

    Returns:
        Response dictionary with processing results
    """
    try:
        logger.info(
            "Processing S3 asset event",
            extra={"event_records": len(event.get("Records", []))},
        )

        # Initialize service
        service = AssetProcessingService()

        # Process each record in the event
        results = []
        for record in event.get("Records", []):
            try:
                # Extract S3 details from the event record
                bucket, key, event_name, version_id = extract_s3_details_from_event(
                    record
                )

                if not bucket or not key:
                    logger.warning(
                        "Skipping record with missing S3 details",
                        extra={"record": record},
                    )
                    continue

                logger.info(
                    "Processing S3 object",
                    extra={
                        "bucket": bucket,
                        "key": key,
                        "event_name": event_name,
                        "version_id": version_id,
                    },
                )

                # Delegate to service layer based on event type
                if event_name and event_name.startswith("ObjectRemoved"):
                    result = service.delete_asset(bucket, key, version_id)
                else:
                    result = service.process_asset(bucket, key)

                results.append(
                    {
                        "bucket": bucket,
                        "key": key,
                        "status": "success",
                        "result": result,
                    }
                )

                # Add success metric
                metrics.add_metric(
                    name="ProcessedAssets", unit=MetricUnit.Count, value=1
                )

            except Exception as e:
                logger.exception(
                    "Error processing individual record",
                    extra={"error": str(e), "record": record},
                )

                results.append(
                    {
                        "bucket": bucket if "bucket" in locals() else "unknown",
                        "key": key if "key" in locals() else "unknown",
                        "status": "error",
                        "error": str(e),
                    }
                )

                # Add error metric
                metrics.add_metric(
                    name="ProcessingErrors", unit=MetricUnit.Count, value=1
                )

        # Return summary response
        successful = len([r for r in results if r["status"] == "success"])
        failed = len([r for r in results if r["status"] == "error"])

        logger.info(
            "Completed processing",
            extra={"successful": successful, "failed": failed, "total": len(results)},
        )

        return {
            "statusCode": (
                200 if failed == 0 else 207
            ),  # 207 = Multi-Status for partial success
            "body": json.dumps(
                {
                    "message": f"Processed {successful} assets successfully, {failed} failed",
                    "successful": successful,
                    "failed": failed,
                    "results": results,
                }
            ),
        }

    except Exception as e:
        logger.exception("Fatal error in lambda handler", extra={"error": str(e)})

        # Add fatal error metric
        metrics.add_metric(name="FatalErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error", "error": str(e)}),
        }
