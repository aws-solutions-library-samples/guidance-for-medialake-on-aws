"""
JFIF tag name translations

Maps JFIF header field offsets to human-readable names.

JFIF (JPEG File Interchange Format) is stored in APP0 segments and contains
basic JPEG metadata like version, resolution, and thumbnail information.

Note: The numbers are buffer offsets in the JFIF header, not tag codes
like in TIFF/EXIF.
"""

from ..tags import tag_keys


def load_jfif_keys():
    """Load JFIF tag key translations into global registry"""

    jfif_keys = {
        0: "JFIFVersion",  # Offset 0-1: Version (e.g., 0x0102 = 1.2)
        2: "ResolutionUnit",  # Offset 2: Units (0=none, 1=in, 2=cm)
        3: "XResolution",  # Offset 3-4: X resolution (uint16)
        5: "YResolution",  # Offset 5-6: Y resolution (uint16)
        7: "ThumbnailWidth",  # Offset 7: Thumbnail width (uint8)
        8: "ThumbnailHeight",  # Offset 8: Thumbnail height (uint8)
    }

    tag_keys["jfif"] = jfif_keys
