# embed_post_response_mapping.py   (replace everything with the block below)


def translate_event_to_request(response_body_and_event):
    """
    Flattens Twelve-Labs /embed POST response → just the embedding float array.
    Expected Twelve Labs JSON   { "<scope>_embedding": { "segments": [ { "float": [...] } ] } }
    """
    body = response_body_and_event["response_body"]
    scope = "image" if "image_embedding" in body else "audio"
    segs = body.get(f"{scope}_embedding", {}).get("segments", [])

    if not segs:
        raise ValueError("No segments returned by Twelve Labs")

    # Grab the first segment’s float vector
    embedding = segs[0].get("float", [])
    if not embedding:
        raise ValueError("No float vector on returned segment")

    return {"embedding": embedding, "embedding_scope": scope}
