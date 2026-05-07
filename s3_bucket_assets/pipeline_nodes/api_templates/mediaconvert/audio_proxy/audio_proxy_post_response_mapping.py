def translate_event_to_request(response_body_and_event):
    """
    Transform the MediaConvert job creation response.

    Args:
        response_body_and_event: Dict containing the MediaConvert response and the original event

    Returns:
        Dict with the transformed response
    """
    response_body = response_body_and_event["response_body"]
    response_body_and_event["event"]

    # Extract job details from the response
    job = response_body.get("Job", {})
    job_id = job.get("Id", "")
    status = job.get("Status", "")

    # Map MediaConvert status to required format
    status_mapping = {
        "COMPLETE": "Completed",
        "IN_PROGRESS": "inProgress",
        "SUBMITTED": "Started",
    }

    mapped_status = status_mapping.get(status, "Started")

    # Determine job result - for a newly created job, it should be "Success" if created successfully
    job_result = "Success" if job_id else "Failed"

    # Create the response
    result = {
        "externalJobId": job_id,
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result,
        "JobId": job_id,  # Include the raw job ID for reference
    }

    return result
