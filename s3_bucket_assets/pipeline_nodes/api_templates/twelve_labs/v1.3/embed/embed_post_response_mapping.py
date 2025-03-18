def translate_event_to_request(response_body):

    # Determine prefix based on the keys in the response

    prefix = "image" if "image_embedding" in response_body else "audio"

    segments = response_body.get(f"{prefix}_embedding", {}).get("segments", [])
    
    return {
        "task_id": response_body.get("_id"),
        "task_status": response_body.get("status"),
        "task_embedding_model": response_body.get("model_name"), 

        "segments": segments
    }
