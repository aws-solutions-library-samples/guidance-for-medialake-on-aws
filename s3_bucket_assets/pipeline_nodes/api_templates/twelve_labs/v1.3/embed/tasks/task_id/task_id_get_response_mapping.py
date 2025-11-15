import json
import os
import uuid

import boto3


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
        raise ValueError("No segments returned by Twelve Labs")

    # ── Source event – pull the MainRepresentation.ID ───────────────
    event = response_body_and_event["event"]
    asset_id = None
    try:
        assets = event.get("payload", {}).get("assets", [])
        if assets:
            asset_id = assets[0].get("DigitalSourceAsset", {}).get("ID")
    except (AttributeError, TypeError):
        pass  # we'll complain below if still None

    if not asset_id:
        raise KeyError("DigitalSourceAsset ID ('asset_id') not found on the event")

    inventory_id = None
    try:
        assets = event.get("payload", {}).get("assets", [])
        if assets:
            inventory_id = assets[0].get("InventoryID")
    except (AttributeError, TypeError):
        pass  # we'll complain below if still None

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

    # ── Upload vectors to S3 like Bedrock Lambda does ──────────────
    # This gives us control over S3 location for distributedMapConfig
    s3_client = boto3.client("s3")
    external_payload_bucket = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")

    if not external_payload_bucket:
        raise RuntimeError("EXTERNAL_PAYLOAD_BUCKET environment variable not set")

    metadata = event.get("metadata", {})
    exec_id = metadata.get("pipelineExecutionId", str(uuid.uuid4()))
    step_name = "TwelveLabs_Get"

    # Upload full vectors to S3
    vectors_s3_key = f"{exec_id}/{step_name}_vectors_{uuid.uuid4()}.json"
    s3_client.put_object(
        Bucket=external_payload_bucket,
        Key=vectors_s3_key,
        Body=json.dumps(vectors, default=str).encode("utf-8"),
        ContentType="application/json",
    )

    # Create lightweight references for each vector
    lightweight_refs = []
    for idx in range(len(vectors)):
        lightweight_refs.append(
            {
                "inventory_id": inventory_id,
                "index": idx,
                "s3_bucket": external_payload_bucket,
                "s3_key": vectors_s3_key,
            }
        )

    # Upload lightweight references to separate S3 file for Distributed Map ItemReader
    refs_s3_key = f"{exec_id}/{step_name}_references_{uuid.uuid4()}.json"
    s3_client.put_object(
        Bucket=external_payload_bucket,
        Key=refs_s3_key,
        Body=json.dumps(lightweight_refs, default=str).encode("utf-8"),
        ContentType="application/json",
    )

    print(
        f"[RESPONSE_MAPPING] Uploaded {len(vectors)} vectors to s3://{external_payload_bucket}/{vectors_s3_key}"
    )
    print(
        f"[RESPONSE_MAPPING] Uploaded {len(lightweight_refs)} references to s3://{external_payload_bucket}/{refs_s3_key}"
    )

    # Return like Bedrock Lambda does
    return {
        "data": {
            "s3_bucket": external_payload_bucket,
            "s3_key": refs_s3_key,
            "vector_count": len(vectors),
            "inventory_id": inventory_id,
        },
        "distributedMapConfig": {
            "s3_bucket": external_payload_bucket,
            "s3_key": refs_s3_key,
        },
    }
