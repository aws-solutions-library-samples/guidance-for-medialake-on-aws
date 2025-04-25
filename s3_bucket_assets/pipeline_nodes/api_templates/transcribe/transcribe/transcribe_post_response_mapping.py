def translate_event_to_request(response_body_and_event):
    """
    Transform the transcription job creation response.
    
    Args:
        response_body_and_event: Dict containing the transcription response and the original event
        
    Returns:
        Dict with the transformed response
    """
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]
    
    # Extract job details from the response
    transcription_job = response_body.get("TranscriptionJob", {})
    job_name = transcription_job.get("TranscriptionJobName", "")
    status = transcription_job.get("TranscriptionJobStatus", "")
    
    # Map transcription job status to external status
    status_mapping = {
        "COMPLETED": "Completed",
        "IN_PROGRESS": "inProgress",
        "QUEUED": "Started",
        "PROCESSING": "inProgress"
    }
    
    mapped_status = status_mapping.get(status, "Started")
    
    # Determine job result
    job_result = "Success" if job_name else "Failed"
    
    # Get the inventory ID from the event
    input_data = event.get("detail", {}).get("outputs", {}).get("input", {})
    inventory_id = input_data.get("InventoryID", "")
    
    # Create the response
    result = {
        "externalJobId": job_name,
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result,
        "message": f"Successfully started transcription job",
        "asset_id": inventory_id,
        "transcription": {
            "engine": "AMAZON_TRANSCRIBE",
            "id": job_name,
            "status": status,
            "job_name": job_name
        }
    }
    
    return result