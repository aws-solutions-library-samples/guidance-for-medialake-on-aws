import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
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
        # Initialize S3 client
        s3 = boto3.client("s3")

        # Extract payload from event
        payload = event.get("payload", {})

        # Get job information from payload - check nested structure first
        job_info = payload
        if "data" in payload:
            job_info = payload["data"]
        elif "data" in payload and "payload" in payload["data"]:
            job_info = payload["data"]["payload"]

        invocation_arn = job_info.get("invocation_arn")
        s3_bucket = job_info.get("s3_bucket")
        output_location = job_info.get("output_location")
        input_type = job_info.get("input_type")

        if not all([invocation_arn, s3_bucket, output_location]):
            raise RuntimeError(
                "Missing required job information: invocation_arn, s3_bucket, or output_location"
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

                    # Include original payload data
                    result.update({k: v for k, v in payload.items() if k not in result})

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

                    # Include original payload data
                    result.update({k: v for k, v in payload.items() if k not in result})

                    return result
                else:
                    # Job is still in progress
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

                    # Include original payload data
                    result.update({k: v for k, v in payload.items() if k not in result})

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

                # Include original payload data
                result.update({k: v for k, v in payload.items() if k not in result})

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

            # Include original payload data
            result.update({k: v for k, v in payload.items() if k not in result})

            return result

    except Exception as e:
        error_msg = f"Error in TwelveLabs Bedrock Status: {str(e)}"
        logger.exception("Error in TwelveLabs Bedrock Status")
        raise RuntimeError(error_msg) from e
