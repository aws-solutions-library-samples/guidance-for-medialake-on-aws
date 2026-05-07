"""
TIFF tag value revivers
Ported from src/dicts/tiff-revivers.mjs

Revivers convert raw values to more useful Python objects (dates, strings, etc.)
"""

from datetime import datetime

from ..tags import create_dictionary, tag_revivers
from ..util.helpers import normalize_string


def to_ascii_string(data):
    """Convert bytes to ASCII string"""
    if isinstance(data, bytes):
        return data.decode("ascii", errors="ignore").rstrip("\x00")
    return str(data)


def revive_date(string):
    """
    Convert EXIF date string to datetime object
    Formats: '2009-09-23 17:40:52 UTC' or '2010:07:06 20:45:12'
    """
    if not isinstance(string, str):
        return None

    try:
        # Split by various separators
        parts = string.strip().replace("-", ":").replace(" ", ":").split(":")
        parts = [int(p) for p in parts if p and p != "UTC"]

        if len(parts) >= 3:
            year, month, day = parts[0:3]
            date = datetime(year, month, day)

            # Add time if available
            if len(parts) >= 6:
                hours, minutes, seconds = parts[3:6]
                date = date.replace(hour=hours, minute=minutes, second=seconds)

            return date
    except (ValueError, IndexError):
        # If parsing fails, return original string
        return string

    return string


def revive_version(data):
    """Convert version bytes to version string (e.g., '2.1' or '2.31')"""
    if isinstance(data, bytes):
        array = list(data)[1:]  # Skip first byte

        # Check if values are printable ASCII
        if array[1] > 0x0F:
            array = [chr(code) for code in array]

        # Remove trailing zero
        if len(array) > 2 and (array[2] == "0" or array[2] == 0):
            array.pop()

        return ".".join(str(x) for x in array)
    return str(data)


def unwrap_exif_size_array(arr):
    """
    Unwrap single-element array to scalar
    Fixes issue with ExifImageWidth/Height sometimes being arrays
    """
    if isinstance(arr, (list, tuple)) and len(arr) > 0:
        return arr[0]
    return arr


def revive_gps_version_id(val):
    """Convert GPS version ID array to dotted string"""
    if isinstance(val, (list, tuple, bytes)):
        return ".".join(str(x) for x in val)
    return str(val)


def revive_gps_timestamp(val):
    """Convert GPS timestamp array to time string"""
    if isinstance(val, (list, tuple)) and len(val) >= 3:
        return ":".join(f"{int(x):02d}" for x in val[:3])
    return str(val)


def revive_ucs2_string(arg):
    """
    Convert UCS-2 (UTF-16) encoded bytes to string
    Used by Windows XP tags (XPTitle, XPComment, etc.)
    """
    if isinstance(arg, str):
        return arg

    if not isinstance(arg, (bytes, bytearray, list)):
        return str(arg)

    # Convert to bytes if needed
    if isinstance(arg, list):
        arg = bytes(arg)

    # Detect endianness
    # Little endian if second byte is 0 and last byte is 0
    le = len(arg) > 1 and arg[1] == 0 and arg[-1] == 0

    code_points = []
    if le:
        # Little endian
        for i in range(0, len(arg) - 1, 2):
            code_points.append((arg[i + 1] << 8) | arg[i])
    else:
        # Big endian
        for i in range(0, len(arg) - 1, 2):
            code_points.append((arg[i] << 8) | arg[i + 1])

    try:
        result = "".join(chr(cp) for cp in code_points if cp != 0)
        return normalize_string(result)
    except ValueError:
        return arg.decode("utf-16", errors="ignore")


def load_tiff_revivers():
    """Load TIFF tag value revivers"""
    # IFD0 and IFD1 revivers
    create_dictionary(
        tag_revivers,
        ["ifd0", "ifd1"],
        [
            (0xC68B, to_ascii_string),
            (0x0132, revive_date),  # ModifyDate
            # Windows XP tags (UTF-16 encoded)
            (0x9C9B, revive_ucs2_string),  # XPTitle
            (0x9C9C, revive_ucs2_string),  # XPComment
            (0x9C9D, revive_ucs2_string),  # XPAuthor
            (0x9C9E, revive_ucs2_string),  # XPKeywords
            (0x9C9F, revive_ucs2_string),  # XPSubject
        ],
    )

    # EXIF revivers
    create_dictionary(
        tag_revivers,
        "exif",
        [
            (0xA000, revive_version),  # FlashpixVersion
            (0x9000, revive_version),  # ExifVersion
            (0x9003, revive_date),  # DateTimeOriginal
            (0x9004, revive_date),  # CreateDate
            (0xA002, unwrap_exif_size_array),  # ExifImageWidth
            (0xA003, unwrap_exif_size_array),  # ExifImageHeight
        ],
    )

    # GPS revivers
    create_dictionary(
        tag_revivers,
        "gps",
        [
            (0x0000, revive_gps_version_id),  # GPSVersionID
            (0x0007, revive_gps_timestamp),  # GPSTimeStamp
        ],
    )
