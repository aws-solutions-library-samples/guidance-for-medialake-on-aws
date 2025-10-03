"""
Build the variables dict for the Twelve Labs /v1.3/embed POST.

Accepted event shape
────────────────────
event = {
    "payload": {
        "data":   { "presignedUrl": "…" },
        "assets": [
            { "DigitalSourceAsset": { "Type": "Image" | "Audio" } }
        ]
    }
}

Anything else is considered invalid and triggers a hard failure.
"""


def _digital_asset_type(event: dict) -> str:
    """
    Return payload.assets[0].DigitalSourceAsset.Type, lower-cased.

    Raises KeyError if the path is missing so the caller can fail loudly.
    """
    try:
        return event["payload"]["assets"][0]["DigitalSourceAsset"]["Type"].lower()
    except (KeyError, IndexError, TypeError) as exc:
        raise KeyError("DigitalSourceAsset.Type missing in payload.assets[0]") from exc


def translate_event_to_request(event: dict) -> dict:
    # ── presigned URL ────────────────────────────────────────────────────────
    url = event.get("payload", {}).get("data", {}).get("presignedUrl")
    if not url:
        raise KeyError("presignedUrl missing in event.payload.data")

    # ── media kind ──────────────────────────────────────────────────────────
    mtype = _digital_asset_type(event)

    # ── map → variables for the Jinja request template ──────────────────────
    if mtype == "image":
        return {"image_url": url}
    if mtype == "audio":
        return {"audio_url": url}

    raise ValueError(
        f"Unsupported DigitalSourceAsset.Type “{mtype}” for /v1.3/embed "
        "(only image & audio embeddings are supported)."
    )
