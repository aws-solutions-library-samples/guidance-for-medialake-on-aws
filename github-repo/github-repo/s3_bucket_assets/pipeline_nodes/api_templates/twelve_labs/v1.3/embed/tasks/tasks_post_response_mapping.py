def translate_event_to_request(response_body_and_event):
    """
    Translate the Lambda event into variables for the API request.
    Customize this function based on your specific event structure and API requirements.
    """
    response_body = response_body_and_event["response_body"]
    task_id = response_body["_id"]

    # For task creation, we always set the status to "Started" and result to "Success"
    # since the task was successfully created
    return {
        "task_id": task_id,
        "externalJobId": task_id,
        "externalJobStatus": "Started",
        "externalJobResult": "Success",
    }
