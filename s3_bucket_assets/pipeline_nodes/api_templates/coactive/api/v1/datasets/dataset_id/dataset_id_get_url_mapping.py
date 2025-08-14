def translate_event_to_request(event):
    """
    Map MediaLake event to URL parameters for Coactive dataset validation
    """
    # Extract dataset_id from the event or use a default
    dataset_id = event.get("dataset_id", "medialake_dataset_2025")

    return {"dataset_id": dataset_id, "base_url": "https://app.coactive.ai/api/v1"}
