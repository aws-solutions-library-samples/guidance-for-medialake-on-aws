"""
exifr-py metadata extraction wrapper.

This module provides functions for extracting and organizing image metadata
using the exifr-py library, maintaining compatibility with the Node.js version.
"""

from typing import Any, Dict

from exifr import parse


async def extract_organized_metadata(buffer: bytes) -> Dict[str, Any]:
    """
    Extract and organize metadata using exifr-py.

    Configures exifr-py with options matching the Node.js version and
    organizes the output by segment (tiff, exif, gps, xmp, etc.).

    Args:
        buffer: Image file bytes

    Returns:
        dict: Organized metadata by segment

    Examples:
        >>> buffer = open("image.jpg", "rb").read()
        >>> metadata = await extract_organized_metadata(buffer)
        >>> "tiff" in metadata
        True
        >>> "exif" in metadata
        True
    """
    # Configure options to enable all segments (like Node.js version)
    options = {
        "tiff": True,
        "exif": True,
        "gps": True,
        "xmp": True,  # Enable XMP parsing
        "iptc": True,  # Enable IPTC parsing
        "icc": True,  # Enable ICC parsing
        "interop": True,
        "jfif": True,
        "ihdr": True,
        "ifd0": True,  # Enable IFD0 parsing
        "ifd1": True,  # Enable IFD1 parsing (thumbnails)
        "mergeOutput": False,  # Keep segments separate
        "sanitize": True,
        "reviveValues": True,
        "translateKeys": True,
        "translateValues": True,
        "multiSegment": True,
        "silentErrors": True,  # Collect errors but don't throw
    }

    try:
        # Parse metadata using exifr-py
        raw_metadata = await parse(buffer, options)

        if not raw_metadata:
            return {}

        # Handle errors from exifr library (should be rare now that we fixed the bug)
        if isinstance(raw_metadata, dict) and "errors" in raw_metadata:
            errors = raw_metadata.pop("errors")  # Remove errors from metadata
            # Log any remaining errors for debugging
            if errors:
                print(f"Exifr reported {len(errors)} errors: {errors}")

        # Clean any remaining exception objects
        if isinstance(raw_metadata, dict):
            for key, value in raw_metadata.items():
                if isinstance(value, Exception):
                    # Convert exception objects to string representations
                    raw_metadata[key] = f"Error: {type(value).__name__}: {value}"

        # Organize metadata by segment
        organized = organize_metadata(raw_metadata)

        return organized

    except KeyError as e:
        # Handle specific KeyError from exifr library
        print(f"KeyError in exifr parsing: {e}")
        print(f"KeyError traceback:")
        import traceback

        traceback.print_exc()
        return {}
    except Exception as e:
        # Log the error and return empty metadata
        print(f"Error parsing metadata with exifr: {type(e).__name__}: {e}")
        print(f"Exception traceback:")
        import traceback

        traceback.print_exc()
        return {}


def organize_metadata(raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Organize metadata by segment and handle duplicate keys.

    Takes the raw output from exifr-py and structures it by segment
    (tiff, exif, gps, xmp, interop, jfif, ihdr). When duplicate keys
    appear across segments, only the first occurrence is kept.

    Args:
        raw_metadata: Raw metadata from exifr-py

    Returns:
        dict: Metadata organized by segment with duplicates removed

    Examples:
        >>> raw = {
        ...     "tiff": {"ImageWidth": 1920, "Make": "Canon"},
        ...     "exif": {"ISO": 400, "ImageWidth": 1920}
        ... }
        >>> organized = organize_metadata(raw)
        >>> "ImageWidth" in organized["tiff"]
        True
        >>> "ImageWidth" in organized["exif"]
        False
    """
    # Valid segment names (matching JavaScript version)
    valid_segments = [
        "tiff",
        "exif",
        "gps",
        "xmp",
        "iptc",
        "icc",
        "interop",
        "jfif",
        "ihdr",
    ]

    # Track seen keys to handle duplicates
    seen_keys = set()

    # Organized output
    organized = {}

    # Process segments in order (tiff first, then others)
    # This ensures tiff values take precedence for duplicates
    segment_order = [
        "tiff",
        "exif",
        "gps",
        "xmp",
        "iptc",
        "icc",
        "interop",
        "jfif",
        "ihdr",
    ]

    for segment_name in segment_order:
        if segment_name not in raw_metadata:
            continue

        segment_data = raw_metadata[segment_name]

        if not isinstance(segment_data, dict):
            # If it's not a dict, just include it as-is
            organized[segment_name] = segment_data
            continue

        # Filter out duplicate keys
        filtered_segment = {}

        for key, value in segment_data.items():
            if key not in seen_keys:
                filtered_segment[key] = value
                seen_keys.add(key)

        # Only include segment if it has data after filtering
        if filtered_segment:
            organized[segment_name] = filtered_segment

    # Handle any other segments not in the standard list (but skip errors like JS version)
    for segment_name, segment_data in raw_metadata.items():
        if segment_name == "errors":
            continue  # Skip errors segment like JavaScript version
        if segment_name not in valid_segments and segment_name not in organized:
            organized[segment_name] = segment_data

    return organized
