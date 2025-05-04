def translate_event_to_request(response_body_and_event):
    """
    Transform the Bedrock content processing response.
    
    Args:
        response_body_and_event: Dict containing the processing response and the original event
        
    Returns:
        Dict with the transformed response
    """
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]
    
    # Extract asset ID from the event
    payload = event.get("payload", {})
    if isinstance(payload.get("body"), str):
        import json
        payload_body = json.loads(payload["body"])
    else:
        payload_body = payload.get("body", {})
    
    inventory_id = payload_body.get("inventory_id", "")
    
    # Extract result information
    result = response_body.get("result", "")
    status = response_body.get("status", "FAILED")
    
    # Map status to external job status
    status_mapping = {
        "SUCCEEDED": "Completed",
        "IN_PROGRESS": "inProgress",
        "FAILED": "Started"  # Even if failed, we use "Started" as per requirements
    }
    
    mapped_status = status_mapping.get(status, "Started")
    
    # Determine job result
    job_result = "Success" if status == "SUCCEEDED" else "Failed"
    
    # Create the response
    result = {
        "statusCode": 200 if status == "SUCCEEDED" else 500,
        "result": result,
        "status": status,
        "inventory_id": inventory_id,
        "externalJobId": f"bedrock-{inventory_id}",
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result
    }
    
    return result