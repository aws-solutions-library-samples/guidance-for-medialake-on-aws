import json
import os
import uuid
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
EXTERNAL_PAYLOAD_BUCKET = os.getenv("EXTERNAL_PAYLOAD_BUCKET")


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

        # Extract payload and metadata from event
        payload = event.get("payload", {})
        metadata = event.get("metadata", {})

        # Check if we need to manually download external payload
        # Sometimes middleware doesn't populate payload.data, so we handle it here
        external_payload_location = metadata.get("stepExternalPayloadLocation", {})
        job_info = payload.get("data", {})

        # If payload.data is empty but we have external payload location, download it manually
        if (
            not job_info or not isinstance(job_info, dict) or len(job_info) == 0
        ) and external_payload_location:
            bucket = external_payload_location.get("bucket")
            key = external_payload_location.get("key")

            if bucket and key:
                logger.info(
                    "Manually downloading external payload",
                    extra={"bucket": bucket, "key": key},
                )
                try:
                    response = s3.get_object(Bucket=bucket, Key=key)
                    external_data = json.loads(response["Body"].read().decode("utf-8"))
                    # Extract the data field from external payload structure
                    job_info = external_data.get("data", {})
                    logger.info(
                        "Successfully downloaded external payload",
                        extra={"has_job_info": bool(job_info)},
                    )
                except Exception as download_error:
                    logger.error(
                        "Failed to download external payload",
                        extra={"error": str(download_error)},
                    )

        # If data is a list (from external payload), get the first item
        if isinstance(job_info, list) and len(job_info) > 0:
            job_info = job_info[0]

        # If still no job info found, try the payload itself
        if not job_info or not isinstance(job_info, dict) or len(job_info) == 0:
            job_info = payload

        logger.info(
            "Job info before unwrapping",
            extra={
                "job_info_keys": (
                    list(job_info.keys()) if isinstance(job_info, dict) else "NOT_DICT"
                ),
                "has_data_field": (
                    "data" in job_info if isinstance(job_info, dict) else False
                ),
                "has_invocation_arn": (
                    "invocation_arn" in job_info
                    if isinstance(job_info, dict)
                    else False
                ),
            },
        )

        # Unwrap nested 'data' fields until we find the actual job data
        # The Status lambda may return nested data structures
        max_unwrap_depth = 5  # Prevent infinite loops
        unwrap_count = 0
        while (
            isinstance(job_info, dict)
            and "data" in job_info
            and isinstance(job_info["data"], dict)
            and "invocation_arn" not in job_info
            and unwrap_count < max_unwrap_depth
        ):
            logger.info(f"Unwrapping nested data layer {unwrap_count + 1}")
            job_info = job_info["data"]
            unwrap_count += 1

        logger.info(
            "Job info after unwrapping",
            extra={
                "unwrap_count": unwrap_count,
                "job_info_keys": (
                    list(job_info.keys()) if isinstance(job_info, dict) else "NOT_DICT"
                ),
                "has_invocation_arn": (
                    "invocation_arn" in job_info
                    if isinstance(job_info, dict)
                    else False
                ),
            },
        )

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
                "job_info_keys": (
                    list(job_info.keys())
                    if isinstance(job_info, dict)
                    else "NOT_A_DICT"
                ),
                "job_info_type": str(type(job_info)),
            },
        )

        if not all([invocation_arn, s3_bucket, output_file_key]):
            error_details = {
                "has_invocation_arn": bool(invocation_arn),
                "has_s3_bucket": bool(s3_bucket),
                "has_output_file_key": bool(output_file_key),
                "job_info_keys": (
                    list(job_info.keys()) if isinstance(job_info, dict) else []
                ),
                "job_info_sample": str(job_info)[:500] if job_info else "EMPTY",
                "payload_keys": list(payload.keys()),
                "metadata_keys": list(metadata.keys()),
                "had_external_payload": bool(external_payload_location),
            }
            logger.error(
                "Missing job information - detailed debug info",
                extra=error_details,
            )
            raise RuntimeError(
                f"Missing required job information: invocation_arn={bool(invocation_arn)}, "
                f"s3_bucket={bool(s3_bucket)}, output_file_key={bool(output_file_key)}. "
                f"Debug: {error_details}"
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

            # Also check payload_history for assets (middleware may have moved them)
            if not assets:
                payload_history = payload.get("payload_history", {})
                assets = payload_history.get("assets", [])

            asset_id = None
            inventory_id = None

            logger.info(
                "Extracting asset information",
                extra={
                    "assets_count": len(assets) if assets else 0,
                    "has_assets": bool(assets),
                    "payload_keys": list(payload.keys()),
                },
            )

            # Try to get asset_id from assets array
            if assets and len(assets) > 0:
                asset = assets[0]
                asset_id = asset.get("InventoryID") or asset.get(
                    "DigitalSourceAsset", {}
                ).get("ID")
                inventory_id = asset.get("InventoryID")

                logger.info(
                    "Extracted inventory_id from assets",
                    extra={
                        "inventory_id": inventory_id,
                        "asset_id": asset_id,
                        "asset_keys": (
                            list(asset.keys())
                            if isinstance(asset, dict)
                            else "NOT_DICT"
                        ),
                    },
                )

            # Fallback to map.item if available
            map_item = payload.get("map", {}).get("item", {})
            if not asset_id and map_item.get("inventory_id"):
                asset_id = map_item["inventory_id"]
                inventory_id = map_item["inventory_id"]
                logger.info(
                    "Extracted inventory_id from map.item",
                    extra={"inventory_id": inventory_id},
                )

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
                    embedding_option = embedding_obj.get("embeddingOption")

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
                    embedding_option = embedding_obj.get("embeddingOption")

                    # Ensure embedding is float32 format (convert to list of floats)
                    embedding_float32 = [float(x) for x in embedding_vector]

                    processed_embedding = {
                        "float": embedding_float32,  # embedding store expects "float" field
                        "dimension": len(embedding_float32),
                        "start_offset_sec": start_sec,  # embedding store expects "start_offset_sec"
                        "end_offset_sec": end_sec,  # embedding store expects "end_offset_sec"
                        "segment_index": i,
                        "embedding_scope": "clip",
                        "input_type": input_type,
                    }

                    # Only add embedding_option if it exists and is not "unknown"
                    if embedding_option and embedding_option != "unknown":
                        processed_embedding["embedding_option"] = embedding_option

                    # Add asset information if available
                    if asset_id:
                        processed_embedding["asset_id"] = asset_id
                    if inventory_id:
                        processed_embedding["inventory_id"] = inventory_id

                    processed_embeddings.append(processed_embedding)

            # Upload full embeddings to S3 for embedding store to download
            exec_id = metadata.get("pipelineExecutionId", str(uuid.uuid4()))
            step_name = "TwelveLabs_Bedrock_Results"
            embeddings_s3_key = f"{exec_id}/{step_name}_embeddings_{uuid.uuid4()}.json"

            s3.put_object(
                Bucket=EXTERNAL_PAYLOAD_BUCKET,
                Key=embeddings_s3_key,
                Body=json.dumps(processed_embeddings, default=str).encode("utf-8"),
                ContentType="application/json",
            )

            # Create lightweight references array
            embedding_count = (
                len(processed_embeddings)
                if isinstance(processed_embeddings, list)
                else 1
            )
            lightweight_refs = []

            if isinstance(processed_embeddings, list):
                for idx in range(embedding_count):
                    lightweight_refs.append(
                        {
                            "inventory_id": inventory_id,
                            "index": idx,
                            "s3_bucket": EXTERNAL_PAYLOAD_BUCKET,
                            "s3_key": embeddings_s3_key,
                            "input_type": input_type,
                        }
                    )
            else:
                lightweight_refs.append(
                    {
                        "inventory_id": inventory_id,
                        "s3_bucket": EXTERNAL_PAYLOAD_BUCKET,
                        "s3_key": embeddings_s3_key,
                        "input_type": input_type,
                    }
                )

            # Upload lightweight references to separate S3 file for Distributed Map ItemReader
            refs_s3_key = f"{exec_id}/{step_name}_references_{uuid.uuid4()}.json"
            s3.put_object(
                Bucket=EXTERNAL_PAYLOAD_BUCKET,
                Key=refs_s3_key,
                Body=json.dumps(lightweight_refs, default=str).encode("utf-8"),
                ContentType="application/json",
            )

            logger.info(
                "TwelveLabs Bedrock results uploaded to S3",
                extra={
                    "invocation_arn": invocation_arn,
                    "embedding_count": embedding_count,
                    "input_type": input_type,
                    "embeddings_s3_key": embeddings_s3_key,
                    "refs_s3_key": refs_s3_key,
                    "refs_count": len(lightweight_refs),
                    "inventory_id": inventory_id,
                },
            )

            result = {
                "data": {
                    "s3_bucket": EXTERNAL_PAYLOAD_BUCKET,
                    "s3_key": refs_s3_key,
                    "embedding_count": embedding_count,
                    "input_type": input_type,
                    "inventory_id": inventory_id,
                },
                # CRITICAL: Also store at metadata level so it survives middleware transformations
                "distributedMapConfig": {
                    "s3_bucket": EXTERNAL_PAYLOAD_BUCKET,
                    "s3_key": refs_s3_key,
                },
            }

            logger.info(
                "DMAP-FIX-v1: Results lambda returning with distributedMapConfig",
                extra={
                    "version": "DMAP-FIX-v1",
                    "result_keys": list(result.keys()),
                    "result_size_bytes": len(json.dumps(result, default=str)),
                    "has_distributedMapConfig": "distributedMapConfig" in result,
                    "s3_bucket": EXTERNAL_PAYLOAD_BUCKET,
                    "s3_key": refs_s3_key,
                    "embedding_count": embedding_count,
                    "refs_count": len(lightweight_refs),
                    "inventory_id": inventory_id,
                },
            )

            # Return minimal response with S3 location for ItemReader
            # Put S3 info at BOTH data and metadata levels to survive middleware offloading
            return result

        except Exception as s3_error:
            logger.exception("Error reading S3 output file")
            error_msg = f"Error reading S3 output file: {str(s3_error)}"
            # Return error result directly for middleware compatibility
            return {"error": error_msg, "status": "failed"}

    except Exception as e:
        logger.exception("Error in TwelveLabs Bedrock Results")
        error_msg = f"Error in TwelveLabs Bedrock Results: {str(e)}"
        raise RuntimeError(error_msg) from e
