"""Item-related utilities for Collections API."""

from typing import Dict, Optional

# Constants
ITEM_SK_PREFIX = "ITEM#"
ASSET_SK_PREFIX = "ASSET#"


def generate_asset_sk(
    asset_id: str, clip_boundary: Optional[Dict[str, str]] = None
) -> str:
    """
    Generate SK for an asset item based on clip boundary.

    Args:
        asset_id: The asset ID
        clip_boundary: Optional dict with startTime and endTime

    Returns:
        SK string like ASSET#id#FULL or ASSET#id#CLIP#start-end
    """
    if not clip_boundary or (
        not clip_boundary.get("startTime") and not clip_boundary.get("endTime")
    ):
        # Full file
        return f"{ASSET_SK_PREFIX}{asset_id}#FULL"

    start_time = clip_boundary.get("startTime", "")
    end_time = clip_boundary.get("endTime", "")

    # Sanitize timecodes for use in SK (replace : with -)
    start_sanitized = start_time.replace(":", "-")
    end_sanitized = end_time.replace(":", "-")

    return f"{ASSET_SK_PREFIX}{asset_id}#CLIP#{start_sanitized}_{end_sanitized}"
