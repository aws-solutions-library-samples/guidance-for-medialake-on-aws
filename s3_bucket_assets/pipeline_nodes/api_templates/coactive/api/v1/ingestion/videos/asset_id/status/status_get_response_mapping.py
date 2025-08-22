def translate_event_to_request(response_body_and_event):
    """
    Process Coactive video status check API response and extract status information
    """
    response_body = response_body_and_event.get("response_body", {})
    response_body_and_event.get("event", {})

    # Extract status information from Coactive response
    # Coactive API returns status nested in 'data' object
    data = response_body.get("data", {})
    status = data.get("status", "unknown")
    job_id = data.get("asset_id")  # Use asset_id as job identifier

    # Unified mapping (status → (externalJobStatus, externalJobResult)) following MediaConvert pattern
    status_mapping = {
        "completed": ("Completed", "Success"),
        "keyframe_generation_completed": (
            "Completed",
            "Success",
        ),  # Coactive issue. Will be removed when fixed.
        "failed": ("Failed", "Failed"),
        "error": ("Failed", "Failed"),
        "processing": ("Started", "InProgress"),
        "processing_started": ("Started", "InProgress"),  # Add missing status mapping
        "pending": ("Started", "Pending"),
    }

    # Get both status and result from unified mapping
    ext_status, ext_result = status_mapping.get(status, ("Started", "Failed"))

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
