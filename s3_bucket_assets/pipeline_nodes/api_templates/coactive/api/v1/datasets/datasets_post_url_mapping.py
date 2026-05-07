def translate_event_to_request(event):
    """
    Map MediaLake event to URL parameters for Coactive dataset creation
    Uses placeholder-based URL construction to ensure correct API domain
    """
    # Return subdomain mapping to use correct API domain (api.coactive.ai)
    # This works with the URL template to construct the full URL
    return {"subdomain": "app"}
