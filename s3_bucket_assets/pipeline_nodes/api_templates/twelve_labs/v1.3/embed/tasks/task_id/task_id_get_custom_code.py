import json


def process_api_response(api_response, event):
    print(f"Input event: {json.dumps(event, indent=2)}")
    print(f"API response: {json.dumps(api_response, indent=2)}")

    # Start with the existing payload or an empty dictionary if it doesn't exist
    result = event.get("payload", {})
    print(f"Initial result: {json.dumps(result, indent=2)}")

    # Ensure the assets list exists in the payload and has at least one asset
    # if "assets" not in result or not result["assets"]:
    #     result["assets"] = [{}]

    # Ensure the first asset has a 'clips' key
    if "clips" not in result["assets"][0]:
        result["assets"][0]["clips"] = []

    # Loop through the video_embeddings array in the api_response
    for embedding in api_response.get("video_embeddings", []):
        embedding_scope = embedding.get("embedding_scope")

        if embedding_scope == "clip":
            # Create a clip object for each clip embedding
            clip = {
                "startTime": embedding.get("start_offset_sec"),
                "endTime": embedding.get("end_offset_sec"),
                "embedding": embedding.get("embedding", {}).get("float", []),
            }
            result["assets"][0]["clips"].append(clip)

        elif embedding_scope == "video":
            # Add the video embedding to the parent assets object
            result["assets"][0]["embedding"] = embedding.get("embedding", {}).get(
                "float", []
            )

    # Preserve other keys in the payload
    # for key, value in event.get("payload", {}).items():
    #     if key != "assets":
    #         result[key] = value

    # Update the event's payload
    event["payload"] = result

    print(f"Final event: {json.dumps(event, indent=2)}")
    return event
