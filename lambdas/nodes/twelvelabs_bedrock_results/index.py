import json
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


@lambda_middleware(event_bus_name=EVENT_BUS_NAME)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for TwelveLabs Bedrock Results node.
    Retrieves and parses embeddings from completed TwelveLabs Bedrock async job.
    """
    logger.info("Incoming event", extra={"event": event})

    try:
        # Initialize S3 client
        s3 = boto3.client("s3")

        # Extract payload from event
        payload = event.get("payload", {})

        # Get job information from payload - middleware handles external payload download
        # The middleware puts the downloaded external payload data in payload["data"]
        job_info = payload.get("data", {})

        # If data is a list (from external payload), get the first item
        if isinstance(job_info, list) and len(job_info) > 0:
            job_info = job_info[0]

        # If still no job info found, try the payload itself
        if not job_info or not isinstance(job_info, dict):
            job_info = payload

        invocation_arn = job_info.get("invocation_arn")
        s3_bucket = job_info.get("s3_bucket")
        output_file_key = job_info.get("output_file_key")
        input_type = job_info.get("input_type", "video")

        logger.info(
            "Processing TwelveLabs Bedrock results",
            extra={
                "invocation_arn": invocation_arn,
                "s3_bucket": s3_bucket,
                "output_file_key": output_file_key,
                "input_type": input_type,
            },
        )

        if not all([invocation_arn, s3_bucket, output_file_key]):
            raise RuntimeError(
                "Missing required job information: invocation_arn, s3_bucket, or output_file_key"
            )

        # Download and parse the output.json file
        try:
            response_obj = s3.get_object(Bucket=s3_bucket, Key=output_file_key)
            response_content = response_obj["Body"].read().decode("utf-8")
            response_data = json.loads(response_content)

            # Extract embeddings data
            if "data" not in response_data:
                raise RuntimeError("No 'data' field found in response")

            embeddings_data = response_data["data"]

            if not embeddings_data or len(embeddings_data) == 0:
                raise RuntimeError("No embedding data found in response")

            # Process embeddings based on input type
            processed_embeddings = []

            if input_type == "text":
                # For text, there's typically one embedding
                if len(embeddings_data) > 0:
                    embedding_obj = embeddings_data[0]
                    embedding_vector = embedding_obj.get("embedding", [])

                    # Ensure embedding is float32 format (convert to list of floats)
                    embedding_float32 = [float(x) for x in embedding_vector]

                    processed_embedding = {
                        "float": embedding_float32,  # embedding store expects "float" field
                        "embedding": embedding_float32,  # keep for backward compatibility
                        "dimension": len(embedding_float32),
                        "input_type": input_type,
                    }
                    processed_embeddings.append(processed_embedding)

            elif input_type in ["video", "image"]:
                # For video/image, there can be multiple embeddings with time segments
                for i, embedding_obj in enumerate(embeddings_data):
                    embedding_vector = embedding_obj.get("embedding", [])
                    start_sec = embedding_obj.get("startSec", 0.0)
                    end_sec = embedding_obj.get("endSec", 0.0)
                    embedding_option = embedding_obj.get("embeddingOption", "unknown")

                    # Ensure embedding is float32 format (convert to list of floats)
                    embedding_float32 = [float(x) for x in embedding_vector]

                    processed_embedding = {
                        "float": embedding_float32,  # embedding store expects "float" field
                        "embedding": embedding_float32,  # keep for backward compatibility
                        "dimension": len(embedding_float32),
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                        "embedding_option": embedding_option,
                        "segment_index": i,
                        "input_type": input_type,
                    }
                    processed_embeddings.append(processed_embedding)

            # For middleware compatibility, return just the embeddings list
            # The middleware will wrap this in payload.data, making it available for batch processing
            logger.info(
                "TwelveLabs Bedrock results processing completed successfully",
                extra={
                    "invocation_arn": invocation_arn,
                    "embedding_count": len(processed_embeddings),
                    "input_type": input_type,
                },
            )

            return processed_embeddings

        except Exception as s3_error:
            logger.exception("Error reading S3 output file")
            error_msg = f"Error reading S3 output file: {str(s3_error)}"
            # Return error result directly for middleware compatibility
            return {"error": error_msg, "status": "failed"}

    except Exception as e:
        logger.exception("Error in TwelveLabs Bedrock Results")
        error_msg = f"Error in TwelveLabs Bedrock Results: {str(e)}"
        raise RuntimeError(error_msg) from e
