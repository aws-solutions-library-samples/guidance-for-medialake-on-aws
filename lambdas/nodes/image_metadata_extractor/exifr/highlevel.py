"""
High-level convenience functions
Ported from src/highlevel/
"""

from .core import Exifr


async def gps(file):
    """
    Extract GPS coordinates from file

    Args:
        file: File path, URL, bytes, or file-like object

    Returns:
        dict: {'latitude': float, 'longitude': float} or None
    """
    options = {
        "gps": ["GPSLatitude", "GPSLongitude", "GPSLatitudeRef", "GPSLongitudeRef"],
        "ifd0": False,
        "exif": False,
        "interop": False,
        "translateValues": False,
        "reviveValues": False,
        "sanitize": False,
        "mergeOutput": False,
    }

    exr = Exifr(options)
    await exr.read(file)
    output = await exr.parse()

    if not output or "gps" not in output:
        return None

    gps_data = output["gps"]

    # Extract latitude
    lat = gps_data.get("GPSLatitude")
    lat_ref = gps_data.get("GPSLatitudeRef", "N")

    # Extract longitude
    lon = gps_data.get("GPSLongitude")
    lon_ref = gps_data.get("GPSLongitudeRef", "E")

    if lat is None or lon is None:
        return None

    # Convert DMS to decimal degrees
    latitude = _dms_to_decimal(lat, lat_ref)
    longitude = _dms_to_decimal(lon, lon_ref)

    return {"latitude": latitude, "longitude": longitude}


async def orientation(file):
    """
    Extract orientation from file

    Args:
        file: File path, URL, bytes, or file-like object

    Returns:
        int: Orientation value (1-8) or None
    """
    options = {
        "ifd0": ["Orientation"],
        "exif": False,
        "gps": False,
        "interop": False,
        "translateValues": False,
        "reviveValues": False,
    }

    exr = Exifr(options)
    await exr.read(file)
    output = await exr.parse()

    if output:
        return output.get("Orientation")
    return None


async def rotation(file):
    """
    Extract rotation information from file

    Args:
        file: File path, URL, bytes, or file-like object

    Returns:
        dict: Rotation info with deg, rad, scaleX, scaleY, dimensionSwapped
    """
    import math

    orient = await orientation(file)

    if orient is None:
        return None

    # Rotation mapping
    rotation_map = {
        1: {"deg": 0, "scaleX": 1, "scaleY": 1, "dimensionSwapped": False},
        2: {"deg": 0, "scaleX": -1, "scaleY": 1, "dimensionSwapped": False},
        3: {"deg": 180, "scaleX": 1, "scaleY": 1, "dimensionSwapped": False},
        4: {"deg": 180, "scaleX": -1, "scaleY": 1, "dimensionSwapped": False},
        5: {"deg": 90, "scaleX": 1, "scaleY": -1, "dimensionSwapped": True},
        6: {"deg": 90, "scaleX": 1, "scaleY": 1, "dimensionSwapped": True},
        7: {"deg": 270, "scaleX": 1, "scaleY": -1, "dimensionSwapped": True},
        8: {"deg": 270, "scaleX": 1, "scaleY": 1, "dimensionSwapped": True},
    }

    info = rotation_map.get(
        orient, {"deg": 0, "scaleX": 1, "scaleY": 1, "dimensionSwapped": False}
    )

    # Add radian conversion
    info["rad"] = math.radians(info["deg"])

    # CSS and canvas support (always true in Python, unlike browser quirks)
    info["css"] = True
    info["canvas"] = True

    return info


async def thumbnail(file):
    """
    Extract embedded thumbnail from file

    Args:
        file: File path, URL, bytes, or file-like object

    Returns:
        bytes: Thumbnail data or None
    """
    options = {
        "ifd1": True,
        "mergeOutput": False,
        "translateKeys": False,
        "translateValues": False,
        "reviveValues": False,
    }

    exr = Exifr(options)
    await exr.read(file)
    return await exr.extract_thumbnail()


def _dms_to_decimal(dms, ref):
    """
    Convert DMS (Degrees, Minutes, Seconds) to decimal degrees

    Args:
        dms: List or tuple of [degrees, minutes, seconds]
        ref: Reference ('N', 'S', 'E', 'W')

    Returns:
        float: Decimal degrees
    """
    if isinstance(dms, (int, float)):
        decimal = float(dms)
    elif isinstance(dms, (list, tuple)) and len(dms) >= 3:
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    else:
        return 0.0

    # Apply sign based on reference
    if ref in ("S", "W"):
        decimal = -decimal

    return decimal
