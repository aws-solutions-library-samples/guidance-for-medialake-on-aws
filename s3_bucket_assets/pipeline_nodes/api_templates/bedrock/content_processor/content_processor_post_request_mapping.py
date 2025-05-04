import json

def translate_event_to_request(event):
    """
    Extract input parameters for Bedrock content processing.

    Expected event structure:
    {
        "payload": {
            "body": {  # may be JSON string or dict
                "inventory_id": "...",  # required if file_s3_uri not provided
                "file_s3_uri": "...",   # required if inventory_id not provided
                "model_id": "...",      # optional, will use env var if not provided
                "prompt_name": "...",   # optional
                "custom_prompt": "...", # optional
                "content_source": "..." # optional, default: transcript
            }
        }
    }
    """
    payload = event.get("payload")
    if not payload:
        raise KeyError("Missing 'payload' in event")

    body = payload.get("body")
    if isinstance(body, str):
        payload_body = json.loads(body)
    else:
        payload_body = body or {}

    inventory_id = payload_body.get("inventory_id")
    file_s3_uri = payload_body.get("file_s3_uri")
    
    if not inventory_id and not file_s3_uri:
        raise KeyError("Either 'inventory_id' or 'file_s3_uri' must be provided in payload body")

    model_id = payload_body.get("model_id")
    prompt_name = payload_body.get("prompt_name")
    custom_prompt = payload_body.get("custom_prompt")
    content_source = payload_body.get("content_source", "transcript")

    return {
        "asset_id": inventory_id,
        "file_s3_uri": file_s3_uri,
        "model_id": model_id,
        "prompt_name": prompt_name,
        "custom_prompt": custom_prompt,
        "content_source": content_source,
    }