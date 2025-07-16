# embed_tasks_request_mapping.py
def _digital_asset_type(event: dict) -> str:
    """
    Return payload.assets[0].DigitalSourceAsset.Type (lower-cased) or ''.
    """
    try:
        return event["payload"]["assets"][0]["DigitalSourceAsset"]["Type"].lower()
    except (KeyError, IndexError, TypeError):
        return ""


def translate_event_to_request(event: dict) -> dict:
    """
    Build variables for Twelve Labs **/v1.3/embed/tasks** (video embeddings).

    Accepted shape (abbreviated):

        {
          "payload": {
            "data":   { "presignedUrl": "…" },
            "assets": [
              { "DigitalSourceAsset": { "Type": "Video" } }
            ]
          }
        }
    """
    data = (event.get("payload") or {}).get("data", {})
    url = data.get("presignedUrl")
    if not url:
        raise KeyError("presignedUrl missing in payload.data")

    mtype = _digital_asset_type(event)
    if not mtype:
        raise KeyError("DigitalSourceAsset.Type missing – cannot determine media kind")

    if mtype != "video":
        raise ValueError(
            f"/v1.3/embed/tasks accepts Video only; received “{mtype}”. "
            "Route Image/Audio assets to /v1.3/embed instead."
        )

    return {"video_url": url}
