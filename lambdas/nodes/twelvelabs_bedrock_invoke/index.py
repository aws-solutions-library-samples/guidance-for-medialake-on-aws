import os
import re
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from bedrock_utils import BEDROCK_RETRY_CONFIGS, bedrock_start_async_invoke_with_retry
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
    Lambda handler for TwelveLabs Bedrock Invoke node.
    Submits async embedding job to TwelveLabs Marengo 2.7 on Bedrock.
    """
    logger.info("Incoming event", extra={"event": event})

    try:
        # Extract parameters from event
        payload = event.get("payload", {})

        # Get configuration from environment variables (set during pipeline deployment)
        model_id = os.environ.get("MODEL_ID", "twelvelabs.marengo-embed-2-7-v1:0")
        region = os.environ.get("AWS_REGION", "us-east-1")
        s3_output_bucket = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")

        # Get input type from environment variable set during pipeline deployment
        input_type = os.environ.get("CONNECTION_INPUT_TYPE")
        if not input_type:
            raise RuntimeError(
                "CONNECTION_INPUT_TYPE environment variable not set. This should be configured during pipeline deployment based on the incoming connection type."
            )

        logger.info(
            "Configuration",
            extra={
                "model_id": model_id,
                "input_type": input_type,
                "region": region,
                "s3_output_bucket": s3_output_bucket,
            },
        )

        # Initialize clients with region
        bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
        boto3.client("s3")
        sts = boto3.client("sts")

        # Get account ID for bucket owner
        account_id = sts.get_caller_identity()["Account"]

        # Use S3 bucket from parameter or environment
        if not s3_output_bucket:
            raise RuntimeError(
                "S3 Output Bucket parameter not configured and EXTERNAL_PAYLOAD_BUCKET environment variable not set"
            )

        # Prepare model input based on input type
        model_input = {"inputType": input_type}

        if input_type == "video":
            # Always get video URI from assets[0]['DerivedRepresentations'] with proxy purpose
            video_uri = None

            # Check MediaLake nested structure first (detail.payload.assets)
            assets_to_check = []
            if (
                "detail" in payload
                and "payload" in payload["detail"]
                and "assets" in payload["detail"]["payload"]
            ):
                assets_to_check = payload["detail"]["payload"]["assets"]
            elif "assets" in payload:
                assets_to_check = payload["assets"]

            if assets_to_check and len(assets_to_check) > 0:
                asset = assets_to_check[0]

                # Always look for proxy DerivedRepresentations
                if "DerivedRepresentations" in asset:
                    for rep in asset["DerivedRepresentations"]:
                        if rep.get("Type") == "Video" and rep.get("Purpose") == "proxy":
                            if (
                                "StorageInfo" in rep
                                and "PrimaryLocation" in rep["StorageInfo"]
                            ):
                                primary_loc = rep["StorageInfo"]["PrimaryLocation"]
                                if (
                                    "Bucket" in primary_loc
                                    and "ObjectKey" in primary_loc
                                ):
                                    bucket = primary_loc["Bucket"]
                                    key = primary_loc["ObjectKey"].get("FullPath", "")
                                    if bucket and key:
                                        video_uri = f"s3://{bucket}/{key}"
                                        logger.info(
                                            f"Found MediaLake proxy DerivedRepresentation: bucket={bucket}, key={key}"
                                        )
                                        break

            # Fallback to other payload structures if assets approach didn't work
            if not video_uri:
                if "s3_location" in payload:
                    video_uri = payload["s3_location"]
                elif "uri" in payload:
                    video_uri = payload["uri"]
                elif "s3Uri" in payload:
                    video_uri = payload["s3Uri"]
                elif "bucket" in payload and "key" in payload:
                    video_uri = f"s3://{payload['bucket']}/{payload['key']}"
                elif "Bucket" in payload and "Key" in payload:
                    video_uri = f"s3://{payload['Bucket']}/{payload['Key']}"
                elif "location" in payload:
                    video_uri = payload["location"]
                elif "file_location" in payload:
                    video_uri = payload["file_location"]
                # Check MediaLake data structure (from pipeline output)
                elif "data" in payload and isinstance(payload["data"], dict):
                    data = payload["data"]
                    if "bucket" in data and "key" in data:
                        video_uri = f"s3://{data['bucket']}/{data['key']}"

            if not video_uri:
                # Log payload structure for debugging
                logger.error(
                    "Video S3 location not found in payload", extra={"payload": payload}
                )
                raise RuntimeError(
                    "Video S3 location not found in payload. Expected 's3_location', 'uri', 's3Uri', 'bucket+key', 'location', 'file_location', or MediaLake assets structure"
                )

            model_input["mediaSource"] = {
                "s3Location": {"uri": video_uri, "bucketOwner": account_id}
            }
            output_prefix = "videoEmbedding"

        elif input_type == "text":
            # Extract text from payload with multiple possible field names
            input_text = None

            if "text" in payload:
                input_text = payload["text"]
            elif "content" in payload:
                input_text = payload["content"]
            elif "inputText" in payload:
                input_text = payload["inputText"]
            elif "message" in payload:
                input_text = payload["message"]
            elif "query" in payload:
                input_text = payload["query"]

            if not input_text:
                logger.error(
                    "Input text not found in payload", extra={"payload": payload}
                )
                raise RuntimeError(
                    "Input text not found in payload. Expected 'text', 'content', 'inputText', 'message', or 'query' fields"
                )

            model_input["inputText"] = input_text
            output_prefix = "textEmbedding"

        elif input_type == "image":
            # Always get image URI from assets[0]['DerivedRepresentations'] with thumbnail purpose
            image_uri = None

            # Check MediaLake nested structure first (detail.payload.assets)
            assets_to_check = []
            if (
                "detail" in payload
                and "payload" in payload["detail"]
                and "assets" in payload["detail"]["payload"]
            ):
                assets_to_check = payload["detail"]["payload"]["assets"]
            elif "assets" in payload:
                assets_to_check = payload["assets"]

            if assets_to_check and len(assets_to_check) > 0:
                asset = assets_to_check[0]

                # Always look for thumbnail DerivedRepresentations for images
                if "DerivedRepresentations" in asset:
                    for rep in asset["DerivedRepresentations"]:
                        if (
                            rep.get("Type") == "Image"
                            and rep.get("Purpose") == "thumbnail"
                        ):
                            if (
                                "StorageInfo" in rep
                                and "PrimaryLocation" in rep["StorageInfo"]
                            ):
                                primary_loc = rep["StorageInfo"]["PrimaryLocation"]
                                if (
                                    "Bucket" in primary_loc
                                    and "ObjectKey" in primary_loc
                                ):
                                    bucket = primary_loc["Bucket"]
                                    key = primary_loc["ObjectKey"].get("FullPath", "")
                                    if bucket and key:
                                        image_uri = f"s3://{bucket}/{key}"
                                        logger.info(
                                            f"Found MediaLake thumbnail DerivedRepresentation: bucket={bucket}, key={key}"
                                        )
                                        break

            # Fallback to other payload structures if assets approach didn't work
            if not image_uri:
                if "s3_location" in payload:
                    image_uri = payload["s3_location"]
                elif "uri" in payload:
                    image_uri = payload["uri"]
                elif "s3Uri" in payload:
                    image_uri = payload["s3Uri"]
                elif "bucket" in payload and "key" in payload:
                    image_uri = f"s3://{payload['bucket']}/{payload['key']}"
                elif "Bucket" in payload and "Key" in payload:
                    image_uri = f"s3://{payload['Bucket']}/{payload['Key']}"
                elif "location" in payload:
                    image_uri = payload["location"]
                elif "file_location" in payload:
                    image_uri = payload["file_location"]
                # Check MediaLake data structure (from pipeline output)
                elif "data" in payload and isinstance(payload["data"], dict):
                    data = payload["data"]
                    if "bucket" in data and "key" in data:
                        image_uri = f"s3://{data['bucket']}/{data['key']}"

            if not image_uri:
                logger.error(
                    "Image S3 location not found in payload", extra={"payload": payload}
                )
                raise RuntimeError(
                    "Image S3 location not found in payload. Expected 's3_location', 'uri', 's3Uri', 'bucket+key', 'location', 'file_location', or MediaLake assets structure"
                )

            model_input["mediaSource"] = {
                "s3Location": {"uri": image_uri, "bucketOwner": account_id}
            }
            output_prefix = "imageEmbedding"

        elif input_type == "audio":
            # Always get audio URI from assets[0]['DerivedRepresentations'] with proxy purpose
            audio_uri = None

            # Check MediaLake nested structure first (detail.payload.assets)
            assets_to_check = []
            if (
                "detail" in payload
                and "payload" in payload["detail"]
                and "assets" in payload["detail"]["payload"]
            ):
                assets_to_check = payload["detail"]["payload"]["assets"]
            elif "assets" in payload:
                assets_to_check = payload["assets"]

            if assets_to_check and len(assets_to_check) > 0:
                asset = assets_to_check[0]

                # Always look for proxy DerivedRepresentations
                if "DerivedRepresentations" in asset:
                    for rep in asset["DerivedRepresentations"]:
                        if rep.get("Type") == "Audio" and rep.get("Purpose") == "proxy":
                            if (
                                "StorageInfo" in rep
                                and "PrimaryLocation" in rep["StorageInfo"]
                            ):
                                primary_loc = rep["StorageInfo"]["PrimaryLocation"]
                                if (
                                    "Bucket" in primary_loc
                                    and "ObjectKey" in primary_loc
                                ):
                                    bucket = primary_loc["Bucket"]
                                    key = primary_loc["ObjectKey"].get("FullPath", "")
                                    if bucket and key:
                                        audio_uri = f"s3://{bucket}/{key}"
                                        logger.info(
                                            f"Found MediaLake proxy DerivedRepresentation: bucket={bucket}, key={key}"
                                        )
                                        break

            # Fallback to other payload structures if assets approach didn't work
            if not audio_uri:
                if "s3_location" in payload:
                    audio_uri = payload["s3_location"]
                elif "uri" in payload:
                    audio_uri = payload["uri"]
                elif "s3Uri" in payload:
                    audio_uri = payload["s3Uri"]
                elif "bucket" in payload and "key" in payload:
                    audio_uri = f"s3://{payload['bucket']}/{payload['key']}"
                elif "Bucket" in payload and "Key" in payload:
                    audio_uri = f"s3://{payload['Bucket']}/{payload['Key']}"
                elif "location" in payload:
                    audio_uri = payload["location"]
                elif "file_location" in payload:
                    audio_uri = payload["file_location"]
                # Check MediaLake data structure (from pipeline output)
                elif "data" in payload and isinstance(payload["data"], dict):
                    data = payload["data"]
                    if "bucket" in data and "key" in data:
                        audio_uri = f"s3://{data['bucket']}/{data['key']}"

            if not audio_uri:
                logger.error(
                    "Audio S3 location not found in payload", extra={"payload": payload}
                )
                raise RuntimeError(
                    "Audio S3 location not found in payload. Expected 's3_location', 'uri', 's3Uri', 'bucket+key', 'location', 'file_location', or MediaLake assets structure"
                )

            model_input["mediaSource"] = {
                "s3Location": {"uri": audio_uri, "bucketOwner": account_id}
            }
            output_prefix = "audioEmbedding"

        else:
            raise RuntimeError(f"Unsupported input type: {input_type}")

        # Start async invoke with retry logic
        logger.info(
            "Starting Bedrock async invoke with retry protection",
            extra={
                "model_id": model_id,
                "input_type": input_type,
                "s3_output_bucket": s3_output_bucket,
                "output_prefix": output_prefix,
            },
        )

        # Use the retry-enabled function from bedrock_utils
        # Using 'default' config which provides reasonable retry behavior
        response = bedrock_start_async_invoke_with_retry(
            bedrock_client=bedrock_runtime,
            model_id=model_id,
            model_input=model_input,
            output_data_config={
                "s3OutputDataConfig": {
                    "s3Uri": f"s3://{s3_output_bucket}/{output_prefix}"
                }
            },
            config=BEDROCK_RETRY_CONFIGS["default"],
        )

        invocation_arn = response["invocationArn"]
        logger.info(
            "Bedrock async invoke started", extra={"invocation_arn": invocation_arn}
        )

        # Extract UID from invocation ARN
        uid_match = re.search(r"/([^/]+)$", invocation_arn)
        if uid_match:
            uid = uid_match.group(1)
            output_location = f"{output_prefix}/{uid}"
        else:
            raise RuntimeError("Could not extract UID from invocation ARN")

        # Prepare response - we need to ensure our values override any existing ones
        # The middleware uses 'or' logic, so we need to make sure our data values are truthy
        # and take precedence over original metadata values
        result = {
            "invocation_arn": invocation_arn,
            "uid": uid,
            "s3_bucket": s3_output_bucket,
            "output_location": output_location,
            "input_type": input_type,
            "model_id": model_id,
            "status": "submitted",
            # These values MUST be set to override any existing metadata
            "externalJobId": invocation_arn,
            "externalJobStatus": "Started",
        }

        logger.info(
            "TwelveLabs Bedrock invoke completed successfully", extra={"result": result}
        )

        # Return the result directly so middleware can access externalJobId/externalJobStatus
        # The middleware expects these fields at the top level of the returned data
        return result

    except Exception as e:
        logger.exception("Error in TwelveLabs Bedrock Invoke")

        # Provide more specific error information for throttling issues
        error_msg = f"Error in TwelveLabs Bedrock Invoke: {str(e)}"

        # Check if this is a throttling-related error from our bedrock_utils
        if "BedrockThrottlingError" in str(type(e)) or "Max retries exceeded" in str(e):
            error_msg = f"TwelveLabs Bedrock Invoke failed due to persistent throttling: {str(e)}. This indicates the service is experiencing high load. Consider implementing request rate limiting or trying again later."

        raise RuntimeError(error_msg) from e
