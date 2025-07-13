import json


def translate_event_to_request(event):
    """
    Extract input parameters for Bedrock content processing.

    Supports two shapes:
      1) event["payload"]["body"]
      2) event["payload"]["data"]["body"]
    """
    payload = event.get("payload")
    if payload is None:
        raise KeyError("Missing 'payload' in event")

    # support both payload.body and payload.data.body
    if "body" in payload:
        raw_body = payload["body"]
    elif isinstance(payload.get("data"), dict) and "body" in payload["data"]:
        raw_body = payload["data"]["body"]
    else:
        raise KeyError(
            "Missing 'body' in payload; found neither payload.body nor payload.data.body"
        )

    # if the body is still a JSON string, parse it
    if isinstance(raw_body, str):
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse body as JSON: {e}")
    else:
        body = raw_body or {}

    # pull out the two required identifiers
    inventory_id = body.get("inventory_id")
    file_s3_uri = body.get("file_s3_uri")

    if not inventory_id and not file_s3_uri:
        raise KeyError(
            "Either 'inventory_id' or 'file_s3_uri' must be provided in payload body"
        )

    return {
        "asset_id": inventory_id,
        "file_s3_uri": file_s3_uri,
        "model_id": body.get("model_id"),
        "prompt_name": body.get("prompt_name"),
        "custom_prompt": body.get("custom_prompt"),
        "content_source": body.get("content_source", "transcript"),
    }
