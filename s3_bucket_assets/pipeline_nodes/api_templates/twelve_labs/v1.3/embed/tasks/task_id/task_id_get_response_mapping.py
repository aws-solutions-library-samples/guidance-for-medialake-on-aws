def translate_event_to_request(response_body_and_event):

    
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]

    segments = response_body.get("video_embedding", {}).get("segments", [])

    # Extract asset ID from the event
    asset_id = None
    
    # Try to get asset ID from the payload.assets array
    if event and "payload" in event and "assets" in event["payload"] and event["payload"]["assets"]:
        asset_id = event["payload"]["assets"][0]  # Use the first asset ID in the array
        print(f"Found asset ID in payload.assets: {asset_id}")
    
    # Fallback: try to get InventoryID from the detail.outputs.input path (original implementation)
    if not asset_id and event and "detail" in event and "outputs" in event["detail"] and "input" in event["detail"]["outputs"]:
        asset_id = event["detail"]["outputs"]["input"].get("InventoryID")
        print(f"Found asset ID in detail.outputs.input.InventoryID: {asset_id}")
    
    print(f"Final asset ID: {asset_id}")
        
    # Add assetId to each segment
    if asset_id and segments:
        for segment in segments:
            segment["assetId"] = asset_id

    return {
        "task_id": response_body.get("_id"),
        "task_status": response_body.get("status"),
        "task_embedding_model": response_body.get("engine_name"),
        "segments": segments 
    }
