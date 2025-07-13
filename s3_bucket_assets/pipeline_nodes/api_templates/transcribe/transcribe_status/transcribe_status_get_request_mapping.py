def translate_event_to_request(event):
    """
    Extract the transcription job name from the event.

    Expected structure can be either:
    {
        "payload": {
            "body": {
                "transcription": {
                    "job_name": "..."
                }
            }
        }
    }

    Or from metadata:
    {
        "metadata": {
            "externalJobId": "job-name-here"
        }
    }
    """
    try:
        # Extract payload from event
        if "payload" not in event:
            raise KeyError("Missing 'payload' in event")

        payload = event["payload"]

        # First try to get job name from metadata
        if "metadata" in event and event["metadata"].get("externalJobId"):
            job_name = event["metadata"]["externalJobId"]

            # Extract asset ID from assets if available
            inventory_id = None
            if "assets" in payload and len(payload["assets"]) > 0:
                inventory_id = payload["assets"][0].get("InventoryID")

            return {"job_name": job_name, "inventory_id": inventory_id}

        # If not in metadata, try the original expected structure
        # If payload body is a string, parse it as JSON
        if isinstance(payload.get("body"), str):
            import json

            try:
                payload_body = json.loads(payload["body"])
            except json.JSONDecodeError:
                payload_body = {}
        else:
            payload_body = payload.get("body", {})

        # Extract job name from payload
        job_name = payload_body.get("transcription", {}).get("job_name")
        if not job_name:
            # Try to extract from data if it exists
            if "data" in payload and isinstance(payload["data"].get("body"), str):
                try:
                    data_body = json.loads(payload["data"]["body"])
                    if (
                        "transcription" in data_body
                        and "job_name" in data_body["transcription"]
                    ):
                        job_name = data_body["transcription"]["job_name"]
                except (json.JSONDecodeError, KeyError):
                    pass

        if not job_name:
            raise KeyError(
                "Missing 'job_name' in payload.body.transcription and not found in metadata"
            )

        # Extract asset ID from payload
        inventory_id = payload_body.get("inventory_id")
        if not inventory_id and "assets" in payload and len(payload["assets"]) > 0:
            inventory_id = payload["assets"][0].get("InventoryID")

        return {"job_name": job_name, "inventory_id": inventory_id}
    except KeyError as e:
        raise KeyError(f"Missing expected key in event: {e}")
    except Exception as e:
        raise ValueError(f"Error extracting job name from event: {str(e)}")
