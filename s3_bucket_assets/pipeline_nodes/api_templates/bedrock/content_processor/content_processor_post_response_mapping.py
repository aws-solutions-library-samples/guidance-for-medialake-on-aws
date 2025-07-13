def translate_event_to_request(response_body_and_event):
    """
    Transform the Bedrock content processing response into the external API shape.
    """
    response_body = response_body_and_event["response_body"]
    event = response_body_and_event["event"]

    # 1) Extract inventory_id from the first asset
    assets = event.get("payload", {}).get("assets", [])
    inventory_id = ""
    if isinstance(assets, list) and assets:
        inventory_id = assets[0].get("InventoryID", "")

    # 2) Extract assistant text from output.message.content[0].text
    result_text = ""
    output = response_body.get("output", {})
    message = output.get("message", {})
    content_arr = message.get("content", [])
    if content_arr and isinstance(content_arr[0], dict):
        result_text = content_arr[0].get("text", "")

    # 3) Determine success by stopReason
    stop_reason = response_body.get("stopReason", "")
    status = "SUCCEEDED" if stop_reason == "end_turn" else "FAILED"

    # 4) Map to external status labels
    status_mapping = {
        "SUCCEEDED": "Completed",
        "IN_PROGRESS": "inProgress",
        "FAILED": "Started",
    }
    external_status = status_mapping.get(status, "Started")
    external_result = "Success" if status == "SUCCEEDED" else "Failed"

    # 5) Build and return the response payload
    return {
        "statusCode": 200 if status == "SUCCEEDED" else 500,
        "result": result_text,
        "status": status,
        "inventory_id": inventory_id,
        "externalJobId": f"bedrock-{inventory_id}",
        "externalJobStatus": external_status,
        "externalJobResult": external_result,
    }
