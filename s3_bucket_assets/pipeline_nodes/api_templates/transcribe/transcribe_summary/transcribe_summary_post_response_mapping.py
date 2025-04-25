def translate_event_to_request(response_body_and_event):
    """
    Transform the transcription summary response.
    
    Args:
        response_body_and_event: Dict containing the summary response and the original event
        
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
    
    asset_id = payload_body.get("asset_id", "")
    
    # Extract summary information
    summary_s3_uri = response_body.get("summary_s3_uri", "")
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
        "summary_s3_uri": summary_s3_uri,
        "status": status,
        "asset_id": asset_id,
        "externalJobId": f"summary-{asset_id}",
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result
    }
    
    return result