def translate_event_to_request(response_body_and_event):
    """
    Transform the MediaConvert reframe job creation response.

    Args:
        response_body_and_event: Dict containing the MediaConvert response and
            the original event

    Returns:
        Dict with the transformed response (externalJobId/status/result).
    """
    response_body = response_body_and_event["response_body"]

    job = response_body.get("Job", {})
    job_id = job.get("Id", "")
    status = job.get("Status", "")

    status_mapping = {
        "COMPLETE": "Completed",
        "IN_PROGRESS": "inProgress",
        "SUBMITTED": "Started",
    }
    mapped_status = status_mapping.get(status, "Started")
    job_result = "Success" if job_id else "Failed"

    return {
        "externalJobId": job_id,
        "externalJobStatus": mapped_status,
        "externalJobResult": job_result,
        "JobId": job_id,
    }
