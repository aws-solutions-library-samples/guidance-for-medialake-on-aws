import json
from typing import Any, Dict

import boto3
import numpy as np


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for TwelveLabs Bedrock Results node.
    Retrieves and parses embeddings from completed TwelveLabs Bedrock async job.
    """
    try:
        # Initialize S3 client
        s3 = boto3.client("s3")

        # Extract payload from event
        payload = event.get("payload", {})

        # Get job information from payload
        invocation_arn = payload.get("invocation_arn")
        s3_bucket = payload.get("s3_bucket")
        output_file_key = payload.get("output_file_key")
        input_type = payload.get("input_type", "video")

        if not all([invocation_arn, s3_bucket, output_file_key]):
            raise ValueError(
                "Missing required job information: invocation_arn, s3_bucket, or output_file_key"
            )

        # Download and parse the output.json file
        try:
            response_obj = s3.get_object(Bucket=s3_bucket, Key=output_file_key)
            response_content = response_obj["Body"].read().decode("utf-8")
            response_data = json.loads(response_content)

            # Extract embeddings data
            if "data" not in response_data:
                raise ValueError("No 'data' field found in response")

            embeddings_data = response_data["data"]

            if not embeddings_data or len(embeddings_data) == 0:
                raise ValueError("No embedding data found in response")

            # Process embeddings based on input type
            processed_embeddings = []

            if input_type == "text":
                # For text, there's typically one embedding
                if len(embeddings_data) > 0:
                    embedding_obj = embeddings_data[0]
                    embedding_vector = embedding_obj.get("embedding", [])

                    # Ensure embedding is float32 format
                    embedding_float32 = np.array(
                        embedding_vector, dtype=np.float32
                    ).tolist()

                    processed_embedding = {
                        "embedding": embedding_float32,
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

                    # Ensure embedding is float32 format
                    embedding_float32 = np.array(
                        embedding_vector, dtype=np.float32
                    ).tolist()

                    processed_embedding = {
                        "embedding": embedding_float32,
                        "dimension": len(embedding_float32),
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                        "embedding_option": embedding_option,
                        "segment_index": i,
                        "input_type": input_type,
                    }
                    processed_embeddings.append(processed_embedding)

            # Prepare result
            result = {
                "invocation_arn": invocation_arn,
                "s3_bucket": s3_bucket,
                "output_file_key": output_file_key,
                "input_type": input_type,
                "embeddings": processed_embeddings,
                "embedding_count": len(processed_embeddings),
                "status": "completed",
                "message": f"Successfully retrieved {len(processed_embeddings)} embeddings",
            }

            # Include original payload data (excluding large embeddings to avoid duplication)
            for k, v in payload.items():
                if k not in result and k != "embeddings":
                    result[k] = v

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "invocation_arn": invocation_arn,
                        "embedding_count": len(processed_embeddings),
                        "status": "completed",
                    }
                ),
                "payload": result,
            }

        except Exception as s3_error:
            error_msg = f"Error reading S3 output file: {str(s3_error)}"
            print(error_msg)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": error_msg}),
                "payload": {"error": error_msg},
            }

    except Exception as e:
        error_msg = f"Error in TwelveLabs Bedrock Results: {str(e)}"
        print(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg}),
            "payload": {"error": error_msg},
        }
