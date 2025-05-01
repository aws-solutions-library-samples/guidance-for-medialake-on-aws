# import json

# def translate_event_to_request(event):
#     """
#     Translate the Lambda event into variables for the API request.
#     Supports both:
#       1) { payload: { presignedUrl, mediaType, … } }
#       2) { payload: { data: { presignedUrl, mediaType, … } }, … }
#     """
#     # 1) get top-level payload
#     payload = event.get("payload")
#     if payload is None:
#         raise KeyError("Missing 'payload' in event")

#     # 2) if it’s wrapped in a `.data` object, peel that layer off
#     if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
#         payload = payload["data"]

#     # 3) extract presignedUrl
#     url = payload.get("presignedUrl")
#     if not url:
#         raise KeyError("Missing 'presignedUrl' in payload")

#     # 4) extract & normalize mediaType
#     media_type = payload.get("mediaType", "").lower() or "video"

#     # 5) return the variable your downstream step needs
#     if media_type == "image":
#         return {"image_url": url}
#     elif media_type == "audio":
#         return {"audio_url": url}
#     else:
#         return {"video_url": url}


"""
Build the variables dict for the Twelve Labs /v1.3/embed POST.

Event shapes supported
──────────────────────
• Current (“pre-signed URL” step) example you shared:

  event = {
      "payload": {
          "data":   { "presignedUrl": … },
          "assets": [
              { "payload": {
                    "assets": [
                        { "DigitalSourceAsset": { "Type": "Image" | "Audio" | … } }
                    ]
              }}
          ]
      }
  }

If the Type cannot be found we raise, so the workflow fails loudly instead of
sending an invalid request.
"""

def _digital_asset_type(event: dict) -> str:
    """
    Safely walk event ➝ payload.assets[0].payload.assets[0].DigitalSourceAsset.Type
    and return the lower-cased value or "" if missing.
    """
    try:
        first_lvl = event["payload"]["assets"][0]
        second_lvl = first_lvl["payload"]["assets"][0]
        return second_lvl["DigitalSourceAsset"]["Type"].lower()
    except (KeyError, IndexError, TypeError):
        return ""

def translate_event_to_request(event: dict) -> dict:
    # ── presigned URL ──────────────────────────────────────────────────────────
    data = (event.get("payload") or {}).get("data", {})
    url  = data.get("presignedUrl")
    if not url:
        raise KeyError("presignedUrl missing in event.payload.data")

    # ── media kind from DigitalSourceAsset.Type ───────────────────────────────
    mtype = _digital_asset_type(event)
    if not mtype:
        raise KeyError("DigitalSourceAsset.Type missing – cannot determine media kind")

    # ── map → variables for the Jinja request template ────────────────────────
    if mtype == "image":
        return {"image_url": url}
    if mtype == "audio":
        return {"audio_url": url}

    raise ValueError(
        f"Unsupported DigitalSourceAsset.Type “{mtype}” for /v1.3/embed "
        "(only image & audio embeddings are supported)."
    )
