def translate_event_to_request(response_body):
    """
    Translate the Lambda event into variables for the API request.
    Customize this function based on your specific event structure and API requirements.
    """
    for embedding in response_body["video_embeddings"]:
        if embedding["embedding_scope"] == "video":
            video_embedding = embedding["embedding"]["float"]
        elif embedding["embedding_scope"] == "clip":
            print("clip embedding")
        else:
            print("embedding found other than clip and video")
    return {
        "task_id": response_body["_id"],
        "task_status": response_body["status"],
        "task_embedding_model": response_body["engine_name"],
        "task_video_embedding": video_embedding,
    }
