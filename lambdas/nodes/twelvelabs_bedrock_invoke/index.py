import json
import os
import re
from typing import Any, Dict

import boto3


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for TwelveLabs Bedrock Invoke node.
    Submits async embedding job to TwelveLabs Marengo 2.7 on Bedrock.
    """
    try:
        # Extract parameters from event
        payload = event.get("payload", {})
        parameters = event.get("parameters", {})

        # Get configuration
        model_id = parameters.get("Model ID", "twelvelabs.marengo-embed-2-7-v1:0")
        input_type = parameters.get("Input Type", "video")
        region = parameters.get("Region", "us-east-1")

        # Initialize clients with region
        bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
        boto3.client("s3")
        sts = boto3.client("sts")

        # Get account ID for bucket owner
        account_id = sts.get_caller_identity()["Account"]

        # Get S3 bucket from environment or payload
        s3_bucket = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")
        if not s3_bucket:
            raise ValueError("S3 bucket not configured")

        # Prepare model input based on input type
        model_input = {"inputType": input_type}

        if input_type == "video":
            # Extract video S3 location from payload
            video_uri = payload.get("s3_location") or payload.get("uri")
            if not video_uri:
                raise ValueError("Video S3 location not found in payload")

            model_input["mediaSource"] = {
                "s3Location": {"uri": video_uri, "bucketOwner": account_id}
            }
            output_prefix = "videoEmbedding"

        elif input_type == "text":
            # Extract text from payload
            input_text = payload.get("text") or payload.get("content")
            if not input_text:
                raise ValueError("Input text not found in payload")

            model_input["inputText"] = input_text
            output_prefix = "textEmbedding"

        elif input_type == "image":
            # Extract image S3 location from payload
            image_uri = payload.get("s3_location") or payload.get("uri")
            if not image_uri:
                raise ValueError("Image S3 location not found in payload")

            model_input["mediaSource"] = {
                "s3Location": {"uri": image_uri, "bucketOwner": account_id}
            }
            output_prefix = "imageEmbedding"
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

        # Start async invoke
        response = bedrock_runtime.start_async_invoke(
            modelId=model_id,
            modelInput=model_input,
            outputDataConfig={
                "s3OutputDataConfig": {"s3Uri": f"s3://{s3_bucket}/{output_prefix}"}
            },
        )

        invocation_arn = response["invocationArn"]

        # Extract UID from invocation ARN
        uid_match = re.search(r"/([^/]+)$", invocation_arn)
        if uid_match:
            uid = uid_match.group(1)
            output_location = f"{output_prefix}/{uid}"
        else:
            raise ValueError("Could not extract UID from invocation ARN")

        # Prepare response
        result = {
            "invocation_arn": invocation_arn,
            "uid": uid,
            "s3_bucket": s3_bucket,
            "output_location": output_location,
            "input_type": input_type,
            "model_id": model_id,
            "status": "submitted",
        }

        return {"statusCode": 200, "body": json.dumps(result), "payload": result}

    except Exception as e:
        error_msg = f"Error in TwelveLabs Bedrock Invoke: {str(e)}"
        print(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg}),
            "payload": {"error": error_msg},
        }
