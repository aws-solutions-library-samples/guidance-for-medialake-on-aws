def translate_event_to_request(event):
    """
    Extract the transcription job name from the event.
    
    Expected structure:
    {
        "payload": {
            "body": {
                "transcription": {
                    "job_name": "..."
                }
            }
        }
    }
    """
    try:
        # Extract payload from event
        if "payload" not in event:
            raise KeyError("Missing 'payload' in event")
        
        payload = event["payload"]
        
        # If payload body is a string, parse it as JSON
        if isinstance(payload.get("body"), str):
            import json
            payload_body = json.loads(payload["body"])
        else:
            payload_body = payload.get("body", {})
        
        # Extract job name from payload
        job_name = payload_body.get("transcription", {}).get("job_name")
        if not job_name:
            raise KeyError("Missing 'job_name' in payload.body.transcription")
        
        # Extract asset ID from payload
        asset_id = payload_body.get("asset_id")
        
        return {
            "job_name": job_name,
            "asset_id": asset_id
        }
    except KeyError as e:
        raise KeyError(f"Missing expected key in event: {e}")
    except Exception as e:
        raise ValueError(f"Error extracting job name from event: {str(e)}")