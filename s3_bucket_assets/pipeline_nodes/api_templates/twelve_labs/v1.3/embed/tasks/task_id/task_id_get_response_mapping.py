def translate_event_to_request(response_body_and_event):
    """
    Build a list of segment embeddings from GET /embed/tasks/{task_id}.

    The Twelve-Labs payload looks like:
        {
          "video_embedding": {
            "segments": [
              {
                "float": [...],
                "start_offset_sec": 0.0,
                "end_offset_sec": 2.0,
                "embedding_option": "video",
                "embedding_scope": "general"
              },
              ...
            ]
          }
        }

    For every segment that contains a non-empty `float` vector we return:
        {
          "float":             [...],
          "start_offset_sec":  <float|None>,
          "end_offset_sec":    <float|None>,
          "embedding_option":  <str|None>,
          "embedding_scope":   <str|None>,
        }

    The Jinja template (downstream) will receive a key called `vectors`
    whose value is this list.
    """
    body = response_body_and_event["response_body"]
    segments = body.get("video_embedding", {}).get("segments", [])

    if not segments:
        raise ValueError("No segments returned by Twelve Labs")

    vectors = [
        {
            "float":            seg["float"],
            "start_offset_sec": seg.get("start_offset_sec"),
            "end_offset_sec":   seg.get("end_offset_sec"),
            "embedding_option": seg.get("embedding_option"),
            "embedding_scope":  seg.get("embedding_scope"),
        }
        for seg in segments
        if seg.get("float")  # keep only segments that actually have vectors
    ]

    if not vectors:
        raise ValueError("No float vectors on returned segments")

    return {"vectors": vectors}
