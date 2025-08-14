def translate_event_to_request(event):
    """
    Map MediaLake event to URL parameters for Coactive video status check
    """
    # Extract asset_id from the event or previous step output
    asset_id = event.get("asset_id") or event.get("payload", {}).get("data", {}).get(
        "asset_id", "unknown"
    )

    return {"asset_id": asset_id, "base_url": "https://app.coactive.ai/api/v1"}
