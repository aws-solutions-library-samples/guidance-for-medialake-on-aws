def translate_event_to_request(event):
    """
    Extract the MediaConvert job ID from the event.
    
    Expected structure:
    {
        "previous_task_output": {
            "VideoProxyandThumbnailResult": {
                "Payload": {
                    "body": {
                        "JobId": "..."
                    }
                }
            }
        }
        OR
        "previous_task_output": {
            "AudioProxyandThumbnailResult": {
                "Payload": {
                    "body": {
                        "JobId": "..."
                    }
                }
            }
        }
    }
    """
    try:
        # Check if we have video or audio result
        if "VideoProxyandThumbnailResult" in event["previous_task_output"]:
            proxy_and_thumbnail_result = event["previous_task_output"]["VideoProxyandThumbnailResult"]
        elif "AudioProxyandThumbnailResult" in event["previous_task_output"]:
            proxy_and_thumbnail_result = event["previous_task_output"]["AudioProxyandThumbnailResult"]
        else:
            raise ValueError("Neither VideoProxyandThumbnailResult nor AudioProxyandThumbnailResult found in event")
        
        # Parse the payload body if it's a string
        payload_body = proxy_and_thumbnail_result["Payload"]["body"]
        if isinstance(payload_body, str):
            import json
            payload_body = json.loads(payload_body)
        
        job_id = payload_body["JobId"]
        
        return {
            "job_id": job_id,
            "region": "us-east-1"  # Default region, can be overridden if needed
        }
    except Exception as e:
        raise ValueError(f"Error extracting job ID from event: {str(e)}")