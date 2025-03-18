def translate_event_to_request(response_body_and_event):
    """
    Translate the Lambda event into variables for the API request.
    Customize this function based on your specific event structure and API requirements.
    """
    response_body = response_body_and_event["response_body"]
    return {"task_id": response_body["_id"], "task_status": response_body["status"]}
