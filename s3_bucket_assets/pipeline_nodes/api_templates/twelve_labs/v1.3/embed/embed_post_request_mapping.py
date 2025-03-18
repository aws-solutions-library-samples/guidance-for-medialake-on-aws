import json


def translate_event_to_request(event):
    """
    Translate the Lambda event into variables for the API request.
    This version extracts the URL (pre-signed URL) from the event payload and
    determines the media type (video, image, or audio) from the event payload.
    
    Expected structure:
    {
      "metadata": {...},
      "payload": {
        "presignedUrl": "...",
        "mediaType": "Image|Video|Audio",
        ...
      }
    }
    """
    try:
        # Extract payload from event
        if "payload" not in event:
            raise KeyError("Missing 'payload' in event")
        
        payload = event["payload"]
        
        # Extract presignedUrl from payload
        if "presignedUrl" not in payload:
            raise KeyError("Missing 'presignedUrl' in payload")
        
        url = payload["presignedUrl"]
        
        # Extract mediaType from payload and convert to lowercase
        media_type = payload.get("mediaType", "")
        if media_type:
            media_type = media_type.lower()
        else:
            # Default to video if mediaType is not provided
            media_type = "video"
        
        # Set the appropriate URL variable based on the media type
        if media_type == "image":
            return {"image_url": url}
        elif media_type == "audio":
            return {"audio_url": url}
        else:
            # Default to video for any other media type or if not specified
            return {"video_url": url}
    except KeyError as e:
        raise KeyError(f"Missing expected key in event: {e}")
