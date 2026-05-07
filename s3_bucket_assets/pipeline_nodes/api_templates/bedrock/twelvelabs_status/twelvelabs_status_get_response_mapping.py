"""
Response mapping for TwelveLabs Bedrock Status node.
Transforms the Bedrock GetModelInvocation response into MediaLake format.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def map_response(response: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Bedrock GetModelInvocation response to MediaLake format.

    Args:
        response: Raw response from Bedrock GetModelInvocation API
        payload: Original request payload containing context

    Returns:
        Dict containing mapped response variables for Jinja template
    """
    try:
        logger.info("Mapping TwelveLabs Bedrock status response")

        # Extract invocation details from payload
        invocation_arn = payload.get("invocation_arn", "")
        s3_bucket = payload.get("s3_bucket", "")
        output_location = payload.get("output_location", "")

        # Extract status from Bedrock response
        invocation_status = response.get("invocationStatus", "Unknown")

        # Map Bedrock status to MediaLake status
        status_mapping = {
            "InProgress": "IN_PROGRESS",
            "Completed": "COMPLETED",
            "Failed": "FAILED",
            "Stopped": "FAILED",
            "Stopping": "IN_PROGRESS",
        }

        mapped_status = status_mapping.get(invocation_status, "UNKNOWN")

        # Create status message
        if invocation_status == "Completed":
            message = "TwelveLabs Bedrock embedding generation completed successfully"
        elif invocation_status == "InProgress":
            message = "TwelveLabs Bedrock embedding generation in progress"
        elif invocation_status == "Failed":
            failure_message = response.get("failureMessage", "Unknown error")
            message = (
                f"TwelveLabs Bedrock embedding generation failed: {failure_message}"
            )
        else:
            message = (
                f"TwelveLabs Bedrock embedding generation status: {invocation_status}"
            )

        # Prepare template variables
        variables = {
            "invocation_arn": invocation_arn,
            "s3_bucket": s3_bucket,
            "output_location": output_location,
            "status": mapped_status,
            "message": message,
        }

        # Add output file key if completed
        if invocation_status == "Completed" and "outputDataConfig" in response:
            output_config = response["outputDataConfig"]
            if "s3OutputDataConfig" in output_config:
                s3_config = output_config["s3OutputDataConfig"]
                output_uri = s3_config.get("s3Uri", "")
                if output_uri:
                    # Extract key from S3 URI
                    if output_uri.startswith("s3://"):
                        parts = output_uri[5:].split("/", 1)
                        if len(parts) > 1:
                            variables["output_file_key"] = parts[1]

        logger.info(f"Successfully mapped status response: {mapped_status}")
        return variables

    except Exception as e:
        logger.error(f"Error mapping TwelveLabs Bedrock status response: {str(e)}")
        # Return error state
        return {
            "invocation_arn": payload.get("invocation_arn", ""),
            "s3_bucket": payload.get("s3_bucket", ""),
            "output_location": payload.get("output_location", ""),
            "status": "ERROR",
            "message": f"Error processing status response: {str(e)}",
        }
