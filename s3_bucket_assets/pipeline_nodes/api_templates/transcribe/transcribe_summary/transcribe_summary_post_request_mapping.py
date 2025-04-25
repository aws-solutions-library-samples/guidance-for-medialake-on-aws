def translate_event_to_request(event):
    """
    Extract input parameters for creating a transcription summary.
    
    Expected structure:
    {
        "payload": {
            "body": {
                "asset_id": "..."
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
        
        # Extract asset ID from payload
        asset_id = payload_body.get("asset_id")
        if not asset_id:
            raise KeyError("Missing 'asset_id' in payload.body")
        
        # Get bedrock model ID from environment variable
        bedrock_model_id = "${BEDROCK_MODEL_ID}"
        if not bedrock_model_id:
            bedrock_model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        
        # Get summary instructions from environment variable
        summary_instructions = "${SUMMARY_INSTRUCTIONS}"
        if not summary_instructions:
            summary_instructions = "Summarize the following audio transcript in 100 words or less."
        
        return {
            "asset_id": asset_id,
            "bedrock_model_id": bedrock_model_id,
            "summary_instructions": summary_instructions
        }
    except KeyError as e:
        raise KeyError(f"Missing expected key in event: {e}")
    except Exception as e:
        raise ValueError(f"Error extracting parameters from event: {str(e)}")