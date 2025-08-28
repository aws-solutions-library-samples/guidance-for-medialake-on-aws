"""
Mapping script – returns the variables consumed by the Jinja request template.
"""

from typing import Any, Dict


def clean_asset_id(asset_str: str) -> str:
    parts = asset_str.split(":")
    uuid = parts[-1] if parts[-1] != "master" else parts[-2]
    return f"asset:uuid:{uuid}"


def translate_event_to_request(event: Dict[str, Any]) -> Dict[str, Any]:
    inp = event["input"]  # set by Lambda shim
    dsa = inp["DigitalSourceAsset"]
    main = dsa["MainRepresentation"]
    loc = main["StorageInfo"]["PrimaryLocation"]

    duration_frames = event.get("duration_frames") or dsa.get(  # Lambda may pass it
        "Metadata", {}
    ).get("Technical", {}).get("Video", {}).get(
        "FrameCount"
    )  # or dig it out of metadata

    return {
        # ── required by Jinja template ────────────────────────────────
        "input_bucket": loc["Bucket"],
        "input_key": loc["ObjectKey"]["FullPath"],
        "output_bucket": event["output_bucket"],
        "output_key": event["output_key"],  # prefix, ends “/”
        "mediaconvert_role_arn": event["mediaconvert_role_arn"],
        "mediaconvert_queue_arn": event["mediaconvert_queue_arn"],
        # thumbnail parameters (defaults 300×400)
        "thumbnail_width": event.get("thumbnail_width", 300),
        "thumbnail_height": event.get("thumbnail_height", 400),
        "duration_frames": duration_frames,  # may be None
        # ── handy for logs / future use ───────────────────────────────
        "inventory_id": inp["InventoryID"],
        "asset_id": clean_asset_id(dsa["ID"]),
    }
