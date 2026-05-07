"""
Helper utility functions
"""

# TIFF byte order markers
TIFF_LITTLE_ENDIAN = 0x4949  # 'II'
TIFF_BIG_ENDIAN = 0x4D4D  # 'MM'


def throw_error(message):
    """Raise an exception with the given message"""
    raise Exception(message)


def undefined_if_empty(obj):
    """Return None if object is empty, otherwise return the object"""
    if obj is None:
        return None
    if isinstance(obj, dict) and len(obj) == 0:
        return None
    return obj


def object_assign(target, *sources):
    """JavaScript Object.assign equivalent"""
    for source in sources:
        if source:
            target.update(source)
    return target


def is_empty(obj):
    """Check if object is empty"""
    if obj is None:
        return True
    if isinstance(obj, (dict, list, set, tuple)):
        return len(obj) == 0
    return False


def normalize_string(s):
    """Normalize string by removing null terminators and whitespace"""
    if isinstance(s, bytes):
        s = s.decode("utf-8", errors="ignore")
    # Remove null terminators
    s = s.rstrip("\x00")
    # Strip whitespace
    s = s.strip()
    return s


def estimate_metadata_size(options):
    """
    Estimate metadata size for chunk reading

    Args:
        options: Options instance

    Returns:
        int: Estimated size in bytes
    """
    # Conservative estimate - most EXIF data is under 64KB
    # GPS and basic EXIF usually fit in 8-16KB
    base_size = 8192  # 8KB base

    if hasattr(options, "xmp") and options.xmp.enabled:
        base_size += 16384  # XMP can be larger
    if hasattr(options, "icc") and options.icc.enabled:
        base_size += 8192  # ICC profiles
    if hasattr(options, "iptc") and options.iptc.enabled:
        base_size += 4096  # IPTC data

    return base_size
