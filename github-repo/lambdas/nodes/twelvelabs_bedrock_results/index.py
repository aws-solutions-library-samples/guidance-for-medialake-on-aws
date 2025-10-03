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

            # Extract asset information from the input event to preserve for embedding store
            assets = payload.get("assets", [])
            asset_id = None
            inventory_id = None

            # Try to get asset_id from assets array
            if assets and len(assets) > 0:
                asset = assets[0]
                asset_id = asset.get("InventoryID") or asset.get(
                    "DigitalSourceAsset", {}
                ).get("ID")
                inventory_id = asset.get("InventoryID")

            # Fallback to map.item if available
            map_item = payload.get("map", {}).get("item", {})
            if not asset_id and map_item.get("inventory_id"):
                asset_id = map_item["inventory_id"]
                inventory_id = map_item["inventory_id"]

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
                        "dimension": len(embedding_float32),
                        "input_type": input_type,
                    }

                    # Add asset information if available
                    if asset_id:
                        processed_embedding["asset_id"] = asset_id
                    if inventory_id:
                        processed_embedding["inventory_id"] = inventory_id

                    processed_embeddings.append(processed_embedding)

            elif input_type == "image":
                # For images, return a single embedding object (not an array)
                if len(embeddings_data) > 0:
                    embedding_obj = embeddings_data[
                        0
                    ]  # Take the first (and typically only) embedding
                    embedding_vector = embedding_obj.get("embedding", [])
                    embedding_option = embedding_obj.get("embeddingOption", "unknown")

                    # Ensure embedding is float32 format (convert to list of floats)
                    embedding_float32 = [float(x) for x in embedding_vector]

                    processed_embedding = {
                        "float": embedding_float32,  # embedding store expects "float" field
                        "embedding_scope": "image",  # Use embedding_scope for images
                    }

                    # Add asset information if available
                    if asset_id:
                        processed_embedding["asset_id"] = asset_id
                    if inventory_id:
                        processed_embedding["inventory_id"] = inventory_id

                    # For images, return single object instead of array
                    processed_embeddings = processed_embedding

            elif input_type in ["video", "audio"]:
                # For video/audio, there can be multiple embeddings with time segments
                for i, embedding_obj in enumerate(embeddings_data):
                    embedding_vector = embedding_obj.get("embedding", [])
                    start_sec = embedding_obj.get("startSec", 0.0)
                    end_sec = embedding_obj.get("endSec", 0.0)
                    embedding_option = embedding_obj.get("embeddingOption", "unknown")

                    # Ensure embedding is float32 format (convert to list of floats)
                    embedding_float32 = [float(x) for x in embedding_vector]

                    processed_embedding = {
                        "float": embedding_float32,  # embedding store expects "float" field
                        "dimension": len(embedding_float32),
                        "start_offset_sec": start_sec,  # embedding store expects "start_offset_sec"
                        "end_offset_sec": end_sec,  # embedding store expects "end_offset_sec"
                        "embedding_option": embedding_option,
                        "segment_index": i,
                        "embedding_scope": "clip",
                        "input_type": input_type,
                    }

                    # Add asset information if available
                    if asset_id:
                        processed_embedding["asset_id"] = asset_id
                    if inventory_id:
                        processed_embedding["inventory_id"] = inventory_id

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
