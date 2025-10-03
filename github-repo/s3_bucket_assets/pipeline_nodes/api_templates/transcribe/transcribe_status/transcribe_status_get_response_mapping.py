def translate_event_to_request(response_body_and_event):
    """
    Transform the transcription job status response.

    Args:
        response_body_and_event: Dict containing the transcription response and the original event

    Returns:
        Dict with the transformed response
    """
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]

    # Extract job details
    transcription_job = response_body.get("TranscriptionJob", {})
    job_name = transcription_job.get("TranscriptionJobName", "")
    status = transcription_job.get("TranscriptionJobStatus", "")

    # Extract inventory_id from the first asset in the original event payload
    payload = event.get("payload", {})
    assets = payload.get("assets", [])
    if isinstance(assets, list) and assets:
        inventory_id = assets[0].get("InventoryID", "")
    else:
        inventory_id = ""

    # Build base result
    result = {
        "statusCode": 200,
        "inventory_id": inventory_id,
        "status": status,
        "transcription": {"job_name": job_name},
    }

    # If completed, pull transcript info
    if status == "COMPLETED":
        detected_language = transcription_job.get("LanguageCode", "")
        transcript_uri = transcription_job.get("Transcript", {}).get(
            "TranscriptFileUri", ""
        )
        # parse S3 URI
        import re

        m = re.match(
            r"https://s3\.(?:[a-z0-9-]+)\.amazonaws\.com/([^/]+)/(.*)", transcript_uri
        )
        if m:
            bucket, s3_key = m.group(1), m.group(2)
            # (in your real code you'd read S3; here we simulate)
            transcript = "…actual transcript text from S3…"
            result["transcription"].update(
                {
                    "transcript": transcript,
                    "detected_language": detected_language,
                    "object": {"bucket": bucket, "key": s3_key},
                }
            )

    # If failed, include an error
    if status == "FAILED":
        result["error"] = "Transcription failed"

    # External-task readiness
    result["externalTaskStatus"] = "ready" if status == "COMPLETED" else "not_ready"

    # Map job status → your pipeline’s externalJobStatus
    status_mapping = {
        "COMPLETED": "Completed",
        "IN_PROGRESS": "inProgress",
        "QUEUED": "Started",
        "PROCESSING": "inProgress",
        "FAILED": "Failed",
    }
    result["externalJobStatus"] = status_mapping.get(status, "Started")

    # Only mark Success/Failed once done; otherwise “Running”
    if status == "COMPLETED":
        result["externalJobResult"] = "Success"
    elif status == "FAILED":
        result["externalJobResult"] = "Failed"
    else:
        result["externalJobResult"] = "Running"

    # Always include the job’s externalJobId
    result["externalJobId"] = job_name

    return result
