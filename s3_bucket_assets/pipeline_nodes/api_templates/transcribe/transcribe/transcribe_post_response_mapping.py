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
        "PROCESSING": "inProgress",
        "FAILED": "Failed",
    }
    mapped_status = status_mapping.get(status, "Started")

    # Determine job result
    job_result = "Success" if job_name else "Failed"

    # Get the inventory ID from the first asset in the payload
    payload = event.get("payload", {})
    assets = payload.get("assets", [])
    if isinstance(assets, list) and assets:
        inventory_id = assets[0].get("InventoryID", "")
    else:
        inventory_id = ""

    # Build the response
    result = {
        "externalJobId": job_name,
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result,
        "message": "Successfully started transcription job",
        "inventory_id": inventory_id,
        "transcription": {
            "engine": "AMAZON_TRANSCRIBE",
            "id": job_name,
            "status": status,
            "job_name": job_name,
        },
    }

    return result
