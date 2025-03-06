import json


def translate_event_to_request(event):
    """
    Translate the Lambda event into variables for the API request.
    This version extracts the video URL (pre-signed URL) from the event body.
    The event is expected to have a "body" key containing a JSON string.
    """
    try:
        # Parse the event body if it's a JSON string.
        body = event.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)

        # Extract the pre-signed URL.
        if "presignedUrl" in body:
            video_url = body["presignedUrl"]
            return {"video_url": video_url}
        else:
            raise KeyError("Missing 'presignedUrl' in event body")
    except (KeyError, json.JSONDecodeError) as e:
        raise KeyError(f"Missing expected key or invalid JSON in event: {e}")
