def translate_event_to_request(response_body_and_event):
    """
    Process Coactive status check API response and extract status information
    """
    response_body = response_body_and_event.get("response_body", {})
    event = response_body_and_event.get("event", {})

    # Extract status information from Coactive response
    # Coactive API returns status nested in 'data' object
    data = response_body.get("data", {})
    status = data.get("status", "unknown")
    job_id = data.get("asset_id")

    # If asset_id is missing from the Coactive response, preserve the previous externalJobId
    # This handles cases where:
    # 1. The API was called with an invalid asset_id (e.g., "unknown")
    # 2. The Coactive API returned an error response without asset_id
    # By preserving the previous ID, we maintain tracking continuity in the pipeline
    if not job_id:
        job_id = event.get("metadata", {}).get("externalJobId")

    # Unified mapping (status → (externalJobStatus, externalJobResult)) following MediaConvert pattern
    status_mapping = {
        "completed": ("Completed", "Success"),
        "failed": ("Failed", "Failed"),
        "error": ("Failed", "Failed"),
        "processing": ("Started", "InProgress"),
        "processing_started": ("Started", "InProgress"),
        "in_progress": ("Started", "InProgress"),  # Add in_progress status mapping
        "pending": ("Started", "Pending"),
    }

    # Get both status and result from unified mapping
    ext_status, ext_result = status_mapping.get(status, ("Started", "InProgress"))

    return {
        # External job tracking for pipeline middleware
        "externalJobId": job_id,
        "externalJobStatus": ext_status,
        "externalJobResult": ext_result,  # Simple string, not complex object
        # Template variables
        "job_id": job_id,
        "status": status,
        "coactive_status": status,
        "coactive_response": response_body,  # Keep full response for debugging
    }
