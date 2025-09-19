def translate_event_to_request(response_body_and_event):
    """
    Translate the Lambda event into variables for the API request.
    Customize this function based on your specific event structure and API requirements.
    """
    response_body = response_body_and_event["response_body"]
    task_id = response_body["_id"]
    task_status = response_body["status"]

    # Map Twelve Labs status to standardized external job status
    status_mapping = {
        "ready": "Completed",
        "indexing": "inProgress",
        "pending": "Started",
        "failed": "Failed",  # Failed tasks should have Failed status
    }

    # Determine job result based on status
    if task_status == "ready":
        job_result = "Success"
    elif task_status == "failed":
        job_result = "Failed"
    else:
        job_result = "inProgress"

    return {
        "task_id": task_id,
        "task_status": task_status,
        "externalJobId": task_id,
        "externalJobStatus": status_mapping.get(task_status, "Started"),
        "externalJobResult": job_result,
    }
