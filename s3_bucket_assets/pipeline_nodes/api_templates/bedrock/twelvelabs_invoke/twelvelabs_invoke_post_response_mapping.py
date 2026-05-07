import re


def translate_event_to_request(response_body_and_event):
    """
    Transform the TwelveLabs Bedrock invoke response.

    Args:
        response_body_and_event: Dict containing the Bedrock response and the original event

    Returns:
        Dict with the transformed response
    """
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]

    # Extract invocation ARN from Bedrock response
    invocation_arn = response_body.get("invocationArn", "")

    # Extract UID from invocation ARN
    uid = ""
    if invocation_arn:
        uid_match = re.search(r"/([^/]+)$", invocation_arn)
        if uid_match:
            uid = uid_match.group(1)

    # Get configuration from original event
    parameters = event.get("parameters", {})
    model_id = parameters.get("Model ID", "twelvelabs.marengo-embed-2-7-v1:0")
    input_type = parameters.get("Input Type", "video")
    s3_output_bucket = parameters.get("S3 Output Bucket", "")

    # Auto-detect input type from MediaLake payload if available
    payload = event.get("payload", {})
    if "assets" in payload and len(payload["assets"]) > 0:
        asset = payload["assets"][0]
        if "DigitalSourceAsset" in asset:
            asset_type = asset["DigitalSourceAsset"].get("Type", "").lower()
            if asset_type in ["image", "audio", "video"]:
                input_type = asset_type

    # Determine output prefix based on input type
    output_prefix = "videoEmbedding"
    if input_type == "image":
        output_prefix = "imageEmbedding"
    elif input_type == "text":
        output_prefix = "textEmbedding"
    elif input_type == "audio":
        output_prefix = "audioEmbedding"

    # Build output location
    output_location = f"{output_prefix}/{uid}" if uid else output_prefix

    return {
        "invocation_arn": invocation_arn,
        "uid": uid,
        "s3_bucket": s3_output_bucket,
        "output_location": output_location,
        "input_type": input_type,
        "model_id": model_id,
        "status": "submitted",
    }
