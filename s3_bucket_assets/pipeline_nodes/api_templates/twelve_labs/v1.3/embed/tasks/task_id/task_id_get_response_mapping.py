def translate_event_to_request(response_body_and_event):
    """
    Build a list of segment embeddings from GET /embed/tasks/{task_id}.

    The Twelve‑Labs payload looks like
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
              …
            ]
          }
        }

    For every segment with a non‑empty `float` vector we return:
        {
          "float":        [...],
          "start_offset_sec": <float|None>,
          "end_offset_sec":   <float|None>,
          "embedding_option": <str|None>,
          "embedding_scope":  <str|None>,
          "asset_id":         <str|None>,
          "framerate":        <float|None>
        }

    Downstream (Jinja) receives one key called `vectors`.
    """

    # ── Response body ────────────────────────────────────────────────
    body = response_body_and_event["response_body"]
    segments = body.get("video_embedding", {}).get("segments", [])

    if not segments:
        raise ValueError("No segments returned by Twelve Labs")

    # ── Source event – pull the MainRepresentation.ID ───────────────
    event = response_body_and_event["event"]
    asset_id = None
    try:
        assets = event.get("payload", {}).get("assets", [])
        if assets:
            asset_id = assets[0].get("DigitalSourceAsset", {}).get("ID")
    except (AttributeError, TypeError):
        pass  # we’ll complain below if still None

    if not asset_id:
        raise KeyError("DigitalSourceAsset ID (‘asset_id’) not found on the event")

    inventory_id = None
    try:
        assets = event.get("payload", {}).get("assets", [])
        if assets:
            inventory_id = assets[0].get("InventoryID")
    except (AttributeError, TypeError):
        pass  # we’ll complain below if still None

    if not inventory_id:
        raise KeyError("InventoryID ('inventory_id') not found on the event")

    # ── Extract framerate from embedded metadata ────────────────────
    framerate = None
    try:
        assets = event.get("payload", {}).get("assets", [])
        if assets:
            embedded_metadata = (
                assets[0].get("Metadata", {}).get("EmbeddedMetadata", {})
            )
            general_metadata = embedded_metadata.get("general", {})
            framerate_str = general_metadata.get("FrameRate")
            if framerate_str:
                framerate = float(framerate_str)
    except (AttributeError, TypeError, ValueError):
        pass  # framerate will remain None if extraction fails

    # ── Build the list of vectors ───────────────────────────────────
    vectors = [
        {
            "float": seg["float"],
            "start_offset_sec": seg.get("start_offset_sec"),
            "end_offset_sec": seg.get("end_offset_sec"),
            "embedding_option": seg.get("embedding_option"),
            "embedding_scope": seg.get("embedding_scope"),
            "asset_id": asset_id,
            "inventory_id": inventory_id,
            "framerate": framerate,
        }
        for seg in segments
        if seg.get("float")  # keep only segments that actually have vectors
    ]

    if not vectors:
        raise ValueError("No float vectors on returned segments")

    return {"vectors": vectors}
