def translate_event_to_request(response_body):

    segments = response_body.get("video_embedding", {}).get("segments", [])
    

    return {
        "task_id": response_body.get("_id"),
        "task_status": response_body.get("status"),
        "task_embedding_model": response_body.get("engine_name"),
        "segments": segments 
    }
