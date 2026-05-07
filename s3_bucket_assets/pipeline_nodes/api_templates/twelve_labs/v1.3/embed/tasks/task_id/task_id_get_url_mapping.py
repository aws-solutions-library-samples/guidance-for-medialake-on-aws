def translate_event_to_request(event):
    """
    Translate the Lambda event into variables for the API request.
    Customize this function based on your specific event structure and API requirements.
    """
    return {"task_id": event["metadata"]["externalJobId"]}
