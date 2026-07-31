"""
Mapping script - returns the variables consumed by the reframe Jinja template.

Reads the values injected by the video_reframe node lambda (aspect-ratio-derived
width/height, optional segment timecodes, output naming and the UserMetadata that
lets the downstream status check create the derived representation).
"""

from typing import Any, Dict


def translate_event_to_request(event: Dict[str, Any]) -> Dict[str, Any]:
    seg_start = event.get("reframe_segment_start")
    seg_end = event.get("reframe_segment_end")
    has_segment = bool(seg_start and seg_end)

    # MediaConvert UserMetadata values must be strings. These are read back from
    # the completed job by check_media_convert_status to build the derived rep.
    user_metadata = {
        "medialake_purpose": str(event.get("reframe_purpose", "smartcrop")),
        "medialake_derived_id": str(event.get("reframe_derived_id", "")),
        "medialake_aspect_ratio": str(event.get("reframe_aspect_ratio", "")),
        "medialake_inventory_id": str(event.get("reframe_inventory_id", "")),
    }
    if has_segment:
        user_metadata["medialake_segment"] = f"{seg_start}/{seg_end}"

    return {
        "input_bucket": event["input_bucket"],
        "input_key": event["input_key"],
        "output_bucket": event["output_bucket"],
        "output_key": event["output_key"],
        "mediaconvert_role_arn": event["mediaconvert_role_arn"],
        "mediaconvert_queue_arn": event["mediaconvert_queue_arn"],
        "reframe_width": event["reframe_width"],
        "reframe_height": event["reframe_height"],
        "reframe_name_modifier": event["reframe_name_modifier"],
        "has_segment": has_segment,
        "segment_start": seg_start,
        "segment_end": seg_end,
        "user_metadata": user_metadata,
    }
