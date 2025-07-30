def translate_event_to_request(event):
    """
    Extract and map event data for TwelveLabs Bedrock invoke request.
    Handles MediaLake asset structure and parameter extraction.
    """
    payload = event.get("payload", {})
    parameters = event.get("parameters", {})

    # Get configuration parameters
    model_id = parameters.get("Model ID", "twelvelabs.marengo-embed-2-7-v1:0")
    input_type = parameters.get("Input Type", "video")
    region = parameters.get("Region", "us-east-1")
    s3_output_bucket = parameters.get("S3 Output Bucket")

    # Auto-detect input type from MediaLake payload if available
    detected_input_type = input_type
    if "assets" in payload and len(payload["assets"]) > 0:
        asset = payload["assets"][0]
        if "DigitalSourceAsset" in asset:
            asset_type = asset["DigitalSourceAsset"].get("Type", "").lower()
            if asset_type in ["image", "audio", "video"]:
                detected_input_type = asset_type

    # Extract S3 location from MediaLake assets structure
    video_uri = None
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

        # Look for appropriate DerivedRepresentations based on input type
        if "DerivedRepresentations" in asset:
            for rep in asset["DerivedRepresentations"]:
                if (
                    detected_input_type == "video"
                    and rep.get("Type") == "Video"
                    and rep.get("Purpose") == "proxy"
                ):
                    if "StorageInfo" in rep and "PrimaryLocation" in rep["StorageInfo"]:
                        primary_loc = rep["StorageInfo"]["PrimaryLocation"]
                        if "Bucket" in primary_loc and "ObjectKey" in primary_loc:
                            bucket = primary_loc["Bucket"]
                            key = primary_loc["ObjectKey"].get("FullPath", "")
                            if bucket and key:
                                video_uri = f"s3://{bucket}/{key}"
                                break
                elif (
                    detected_input_type == "image"
                    and rep.get("Type") == "Image"
                    and rep.get("Purpose") == "thumbnail"
                ):
                    if "StorageInfo" in rep and "PrimaryLocation" in rep["StorageInfo"]:
                        primary_loc = rep["StorageInfo"]["PrimaryLocation"]
                        if "Bucket" in primary_loc and "ObjectKey" in primary_loc:
                            bucket = primary_loc["Bucket"]
                            key = primary_loc["ObjectKey"].get("FullPath", "")
                            if bucket and key:
                                image_uri = f"s3://{bucket}/{key}"
                                break

    # Fallback to other payload structures if assets approach didn't work
    if not video_uri and not image_uri:
        for key in ["s3_location", "uri", "s3Uri", "location", "file_location"]:
            if key in payload:
                if detected_input_type == "video":
                    video_uri = payload[key]
                elif detected_input_type == "image":
                    image_uri = payload[key]
                break

        # Check bucket/key structure
        if not video_uri and not image_uri:
            if "bucket" in payload and "key" in payload:
                uri = f"s3://{payload['bucket']}/{payload['key']}"
                if detected_input_type == "video":
                    video_uri = uri
                elif detected_input_type == "image":
                    image_uri = uri

    return {
        "model_id": model_id,
        "input_type": detected_input_type,
        "region": region,
        "s3_output_bucket": s3_output_bucket,
        "video_uri": video_uri,
        "image_uri": image_uri,
        "text_content": payload.get("text")
        or payload.get("content")
        or payload.get("inputText"),
        "account_id": "{{ account_id }}",  # Will be populated by Lambda
        "uid": "{{ uid }}",  # Will be populated by Lambda
    }
