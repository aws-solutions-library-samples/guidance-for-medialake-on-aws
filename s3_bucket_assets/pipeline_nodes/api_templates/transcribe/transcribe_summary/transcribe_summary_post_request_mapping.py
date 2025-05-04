import json

def translate_event_to_request(event):
    """
    Extract input parameters for summarization.

    Expected event structure:
    {
        "payload": {
            "body": {  # may be JSON string or dict
                "inventory_id": "...",  # required
                "prompt_name": "...",    # optional
                "custom_prompt": "..."   # optional
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
    if not inventory_id:
        raise KeyError("Missing 'inventory_id' in payload body")

    prompt_name = payload_body.get("prompt_name")
    custom_prompt = payload_body.get("custom_prompt")

    return {
        "asset_id": inventory_id,
        "prompt_name": prompt_name,
        "custom_prompt": custom_prompt
    }