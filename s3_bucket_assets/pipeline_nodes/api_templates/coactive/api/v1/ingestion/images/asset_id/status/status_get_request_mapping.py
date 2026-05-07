def translate_event_to_request(event):
    """
    Map MediaLake event to request parameters for Coactive status check
    This is a GET request so no request body is needed
    """
    # For GET requests, we typically don't need a request body
    # The asset_id will be extracted by the URL mapping
    return {}
