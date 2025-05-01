# import json

# def translate_event_to_request(event):
#     """
#     Translate the Lambda event into variables for the API request.
#     Supports both:
#       1) { payload: { presignedUrl, mediaType, … } }
#       2) { payload: { data: { presignedUrl, mediaType, … } }, … }
#     """
#     try:
#         # 1) Grab the payload
#         payload = event.get("payload")
#         if payload is None:
#             raise KeyError("Missing 'payload' in event")

#         # 2) Unwrap nested `.data` if present
#         if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
#             payload = payload["data"]

#         # 3) Extract the presigned URL
#         url = payload.get("presignedUrl")
#         if not url:
#             raise KeyError("Missing 'presignedUrl' in payload")

#         # 4) Normalize mediaType (default to video)
#         media_type = payload.get("mediaType", "").lower() or "video"

#         # 5) Return the correct key for downstream
#         if media_type == "image":
#             return {"image_url": url}
#         elif media_type == "audio":
#             return {"audio_url": url}
#         else:
#             return {"video_url": url}

#     except KeyError as e:
#         # Bubble up a clear error if something’s missing
#         raise KeyError(f"Missing expected key in event: {e}")


# embed_tasks_request_mapping.py  (replace existing file)

def _digital_asset_type(event: dict) -> str:
    """
    Walk the event and return DigitalSourceAsset.Type (lower-cased) or ''.
    Path:
        event.payload.assets[0].payload.assets[0].DigitalSourceAsset.Type
    """
    try:
        lvl1 = event["payload"]["assets"][0]
        lvl2 = lvl1["payload"]["assets"][0]
        return lvl2["DigitalSourceAsset"]["Type"].lower()
    except (KeyError, IndexError, TypeError):
        return ""


def translate_event_to_request(event: dict) -> dict:
    """
    Build the variables dict for Twelve Labs **/v1.3/embed/tasks** (video).

    Expected event shape (abbreviated):

        {
          "payload": {
            "data":   { "presignedUrl": "https://…" },
            "assets": [
              { "payload": { "assets": [
                    { "DigitalSourceAsset": { "Type": "Video" } }
              ]}}
            ]
          }
        }
    """
    # ── presigned URL ──────────────────────────────────────────────────────────
    data = (event.get("payload") or {}).get("data", {})
    url  = data.get("presignedUrl")
    if not url:
        raise KeyError("translate_event_to_request: ‘presignedUrl’ missing")

    # ── media kind from DigitalSourceAsset.Type ───────────────────────────────
    mtype = _digital_asset_type(event)
    if not mtype:
        raise KeyError("DigitalSourceAsset.Type missing – cannot determine media kind")

    # ── Only ‘video’ is valid for /embed/tasks ────────────────────────────────
    if mtype != "video":
        raise ValueError(
            f"/v1.3/embed/tasks accepts Video only; received “{mtype}”. "
            "Route Image/Audio assets to /v1.3/embed instead."
        )

    return {"video_url": url}
