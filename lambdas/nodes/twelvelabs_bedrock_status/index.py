import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from bedrock_utils import bedrock_get_async_invoke_with_retry
from lambda_middleware import lambda_middleware

# Powertools / logging
logger = Logger()
tracer = Tracer()

# Environment
EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default-event-bus")


def _map_status_to_external(internal_status: str) -> str:
    """Map internal status values to standardized external status values."""
    status_mapping = {
        "completed": "Completed",
        "in_progress": "InProgress",
        "submitted": "Started",
        "failed": "Failed",
    }
    return status_mapping.get(internal_status, "InProgress")


@lambda_middleware(event_bus_name=EVENT_BUS_NAME)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for TwelveLabs Bedrock Status node.
    Checks if async embedding job is complete by polling S3 for output.json file.
    """
    try:
        logger.info(
            "STATUS: Lambda handler invoked",
            extra={
                "event_keys": list(event.keys()),
                "has_payload": "payload" in event,
                "has_metadata": "metadata" in event,
            },
        )

        # Initialize S3 client
        s3 = boto3.client("s3")

        # Extract payload from event
        payload = event.get("payload", {})

        logger.info(
            "STATUS: Extracted payload",
            extra={
                "payload_keys": (
                    list(payload.keys()) if isinstance(payload, dict) else "N/A"
                ),
                "has_data": "data" in payload,
                "data_keys": (
                    list(payload["data"].keys())
                    if isinstance(payload.get("data"), dict)
                    else "N/A"
                ),
            },
        )

        # Get job information from payload - check multiple locations in priority order
        job_info = None

        # Priority 1: Check data field if it contains job info (from Invoke lambda)
        if "data" in payload and isinstance(payload["data"], dict):
            data_dict = payload["data"]
            if (
                data_dict.get("invocation_arn")
                and data_dict.get("s3_bucket")
                and data_dict.get("output_location")
            ):
                job_info = data_dict
                logger.info("Found job info in payload.data")

        # Priority 2: Check top-level payload for job info (from previous Status iteration)
        if (
            job_info is None
            and payload.get("invocation_arn")
            and payload.get("s3_bucket")
            and payload.get("output_location")
        ):
            job_info = payload
            logger.info("Found job info at top-level payload")

        # Priority 3: Check explicit job_info field (from Results lambda)
        if (
            job_info is None
            and "job_info" in payload
            and isinstance(payload["job_info"], dict)
        ):
            job_info = payload["job_info"]
            logger.info("Found job info in payload.job_info")

        # Priority 4: Check payload_history for job info
        if (
            job_info is None
            and "payload_history" in payload
            and isinstance(payload.get("payload_history"), dict)
        ):
            history_data = payload["payload_history"].get("data", {})
            if isinstance(history_data, dict) and history_data.get("invocation_arn"):
                job_info = history_data
                logger.info("Found job info in payload_history.data")

        # Fallback: use payload as-is
        if job_info is None:
            job_info = payload
            logger.warning("Using payload as job_info (fallback)")

        invocation_arn = job_info.get("invocation_arn")
        s3_bucket = job_info.get("s3_bucket")
        output_location = job_info.get("output_location")
        input_type = job_info.get("input_type")

        logger.info(
            "STATUS: Extracted job information",
            extra={
                "job_info_keys": (
                    list(job_info.keys()) if isinstance(job_info, dict) else "N/A"
                ),
                "invocation_arn": invocation_arn,
                "s3_bucket": s3_bucket,
                "output_location": output_location,
                "input_type": input_type,
                "all_present": all([invocation_arn, s3_bucket, output_location]),
            },
        )

        if not all([invocation_arn, s3_bucket, output_location]):
            raise RuntimeError(
                "Missing required job information: invocation_arn, s3_bucket, or output_location"
            )

        # First, check the actual Bedrock invocation status
        bedrock_runtime = boto3.client("bedrock-runtime")

        try:
            logger.info(
                "STATUS: Checking Bedrock invocation status",
                extra={"invocation_arn": invocation_arn},
            )

            bedrock_response = bedrock_get_async_invoke_with_retry(
                bedrock_client=bedrock_runtime, invocation_arn=invocation_arn
            )

            bedrock_status = bedrock_response.get("status")
            failure_message = bedrock_response.get("failureMessage")

            logger.info(
                "STATUS: Bedrock invocation status retrieved",
                extra={
                    "bedrock_status": bedrock_status,
                    "has_failure_message": bool(failure_message),
                },
            )

            # If Bedrock reports failure, raise an error immediately
            if bedrock_status == "Failed":
                error_msg = f"Bedrock embedding job failed: {failure_message or 'Unknown error'}"
                logger.error(
                    "STATUS: Bedrock job failed",
                    extra={
                        "invocation_arn": invocation_arn,
                        "failure_message": failure_message,
                    },
                )
                raise RuntimeError(error_msg)

            # If status is Completed, proceed to check S3 for output
            # If status is InProgress, we'll check S3 anyway (belt and suspenders)

        except RuntimeError:
            # Re-raise RuntimeError (our failure detection)
            raise
        except Exception as bedrock_error:
            # If we can't check Bedrock status, log but continue to S3 check
            logger.warning(
                "STATUS: Unable to check Bedrock status, falling back to S3 check",
                extra={"error": str(bedrock_error)},
            )

        # Check for output.json file in S3
        try:
            response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=output_location)

            if "Contents" in response:
                # Look for output.json file (success) or error.txt file (failure)
                output_files = [
                    obj
                    for obj in response["Contents"]
                    if obj["Key"].endswith("output.json")
                ]

                error_files = [
                    obj
                    for obj in response["Contents"]
                    if obj["Key"].endswith("error.txt")
                ]

                if output_files:
                    # Job is complete
                    output_file_key = output_files[0]["Key"]

                    logger.info(
                        "STATUS: Job completed - output.json found",
                        extra={
                            "output_file_key": output_file_key,
                        },
                    )

                    result = {
                        "invocation_arn": invocation_arn,
                        "s3_bucket": s3_bucket,
                        "output_location": output_location,
                        "output_file_key": output_file_key,
                        "input_type": input_type,
                        "status": "completed",
                        "message": "Embedding job completed successfully",
                        # Force override external job metadata
                        "externalJobId": invocation_arn,
                        "externalJobStatus": _map_status_to_external("completed"),
                    }

                    # DO NOT include original payload data - it contains massive assets array
                    # Only pass through inventory_id if present
                    if "assets" in payload and payload["assets"]:
                        inventory_id = payload["assets"][0].get("InventoryID")
                        if inventory_id:
                            result["inventory_id"] = inventory_id

                    logger.info(
                        "STATUS: Returning completed result",
                        extra={
                            "result_keys": list(result.keys()),
                            "externalJobStatus": result.get("externalJobStatus"),
                        },
                    )

                    logger.info(
                        "DMAP-FIX-v1: Status lambda returning result",
                        extra={
                            "version": "DMAP-FIX-v1",
                            "result_keys": list(result.keys()),
                            "result_size_bytes": len(json.dumps(result)),
                            "has_inventory_id": "inventory_id" in result,
                            "invocation_arn": invocation_arn,
                        },
                    )

                    return result
                elif error_files:
                    # Job has failed
                    error_file_key = error_files[0]["Key"]

                    result = {
                        "invocation_arn": invocation_arn,
                        "s3_bucket": s3_bucket,
                        "output_location": output_location,
                        "error_file_key": error_file_key,
                        "input_type": input_type,
                        "status": "failed",
                        "message": "Embedding job failed",
                        # Force override external job metadata
                        "externalJobId": invocation_arn,
                        "externalJobStatus": _map_status_to_external("failed"),
                    }

                    # DO NOT include original payload data
                    return result
                else:
                    # Job is still in progress
                    logger.info(
                        "STATUS: Job still in progress - no output/error files found",
                        extra={
                            "files_found": len(response.get("Contents", [])),
                        },
                    )

                    result = {
                        "invocation_arn": invocation_arn,
                        "s3_bucket": s3_bucket,
                        "output_location": output_location,
                        "input_type": input_type,
                        "status": "in_progress",
                        "message": "Embedding job is still in progress",
                        # Force override external job metadata
                        "externalJobId": invocation_arn,
                        "externalJobStatus": _map_status_to_external("in_progress"),
                    }

                    # DO NOT include original payload data
                    logger.info(
                        "STATUS: Returning in_progress result",
                        extra={
                            "result_keys": list(result.keys()),
                            "externalJobStatus": result.get("externalJobStatus"),
                        },
                    )

                    return result
            else:
                # No objects found yet - job is still in progress
                result = {
                    "invocation_arn": invocation_arn,
                    "s3_bucket": s3_bucket,
                    "output_location": output_location,
                    "input_type": input_type,
                    "status": "in_progress",
                    "message": "Embedding job is still in progress - no output files found yet",
                    # Force override external job metadata
                    "externalJobId": invocation_arn,
                    "externalJobStatus": _map_status_to_external("in_progress"),
                }

                # DO NOT include original payload data
                return result

        except Exception as s3_error:
            # If we can't access S3, assume job is still in progress
            result = {
                "invocation_arn": invocation_arn,
                "s3_bucket": s3_bucket,
                "output_location": output_location,
                "input_type": input_type,
                "status": "in_progress",
                "message": f"Unable to check S3 status: {str(s3_error)}",
                # Force override external job metadata
                "externalJobId": invocation_arn,
                "externalJobStatus": _map_status_to_external("in_progress"),
            }

            # DO NOT include original payload data
            return result

    except Exception as e:
        error_msg = f"Error in TwelveLabs Bedrock Status: {str(e)}"
        logger.exception("Error in TwelveLabs Bedrock Status")
        raise RuntimeError(error_msg) from e
