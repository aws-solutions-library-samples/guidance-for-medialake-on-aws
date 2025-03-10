def translate_event_to_request(response_body):
    # video_embeddings = []
    # clip_embeddings = []
    segments = response_body.get("video_embedding", {}).get("segments", [])
    
    # Optionally, still process segments if you need the separated lists:
    # for embedding in segments:
    #     embedding_scope = embedding.get("embedding_scope")
    #     embedding_float = embedding.get("float")
    #     if embedding_scope == "video":
    #         video_embeddings.append(embedding_float)
    #     elif embedding_scope == "clip":
    #         clip_embeddings.append(embedding_float)
    #     else:
    #         print(f"Embedding found other than 'clip' or 'video': {embedding_scope}")
    
    return {
        "task_id": response_body.get("_id"),
        "task_status": response_body.get("status"),
        "task_embedding_model": response_body.get("engine_name"),
        # "task_video_embeddings": video_embeddings,
        # "task_clip_embeddings": clip_embeddings,
        "segments": segments  # New: return the whole segments array
    }
