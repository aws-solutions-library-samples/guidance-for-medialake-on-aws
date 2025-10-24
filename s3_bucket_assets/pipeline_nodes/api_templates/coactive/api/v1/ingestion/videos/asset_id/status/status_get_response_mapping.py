def translate_event_to_request(response_body_and_event):
    """
    Process Coactive video status check API response and extract status information
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

    # Extract additional fields from the response
    dataset_id = data.get("dataset_id")
    error_code = data.get("error_code")
    error_reason = data.get("error_reason")
    source_path = data.get("source_path")
    asset_type = data.get("asset_type")

    # Extract latest event information
    latest_event = data.get("latest_event", {})
    latest_event_type = (
        latest_event.get("event_type") if isinstance(latest_event, dict) else None
    )
    latest_event_entity = (
        latest_event.get("event_entity") if isinstance(latest_event, dict) else None
    )
    latest_event_timestamp = (
        latest_event.get("timestamp_dt") if isinstance(latest_event, dict) else None
    )

    # Unified mapping (status → (externalJobStatus, externalJobResult)) following MediaConvert pattern
    status_mapping = {
        "completed": ("Completed", "Success"),
        # "keyframe_generation_completed": (
        #     "Completed",
        #     "Success",
        # ),  # Coactive issue. Will be removed when fixed.
        "failed": ("Failed", "Failed"),
        "error": ("Failed", "Failed"),
        "processing": ("Started", "InProgress"),
        "processing_started": ("Started", "InProgress"),
        "in_progress": ("Started", "InProgress"),  # Add in_progress status mapping
        "pending": ("Started", "Pending"),
    }

    # Get both status and result from unified mapping
    ext_status, ext_result = status_mapping.get(status, ("Started", "InProgress"))

    # Determine completion timestamp from latest event or use current time for completed status
    completed_at = ""
    if status == "completed" and latest_event_timestamp:
        completed_at = latest_event_timestamp

    # Create message based on latest event or error information
    message = ""
    if error_reason:
        message = error_reason
    elif latest_event_type:
        message = f"Latest event: {latest_event_type}"

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
        # Additional Coactive-specific fields
        "dataset_id": dataset_id,
        "error_code": error_code,
        "error_reason": error_reason,
        "source_path": source_path,
        "asset_type": asset_type,
        "latest_event_type": latest_event_type,
        "latest_event_entity": latest_event_entity,
        "latest_event_timestamp": latest_event_timestamp,
        "completed_at": completed_at,
        "message": message,
    }
