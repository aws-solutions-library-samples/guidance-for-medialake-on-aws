def translate_event_to_request(response_body_and_event):

    # Determine scope based on the keys in the response
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]

 

    segments = response_body.get(f"video_embedding", {}).get("segments", [])
    
    # Extract asset ID from the event
    asset_id = None
    
    try:
        asset_id = event["metadata"]["pipelineAssets"][0]["assetId"]
        print(f"Found asset ID in metadata.pipelineAssets: {asset_id}")
    except (KeyError, IndexError, TypeError):
        print("Unable to find asset ID in metadata.pipelineAssets")
    
    print(f"task id get reposne Final asset ID: {asset_id}")
    
    # Add assetId to each segment
    if asset_id and segments:
        for segment in segments:
            segment["assetId"] = asset_id
            
            # segment["embedding_scope"] = scope    

    print(f"segments: {segments}")
    return {
        "task_id": response_body.get("_id"),
        "task_status": response_body.get("status"),
        "task_embedding_model": response_body.get("model_name"),
        "segments": segments
    }
