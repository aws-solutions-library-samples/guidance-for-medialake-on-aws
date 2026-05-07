"""
IHDR (PNG header) tag name translations

Maps PNG IHDR chunk field offsets to human-readable names.

Note: The numbers are buffer offsets in the standard PNG IHDR chunk,
not tag codes like in TIFF/EXIF.
"""

from ..tags import tag_keys


def load_ihdr_keys():
    """Load IHDR tag key translations into global registry"""

    ihdr_keys = {
        0: "ImageWidth",  # Offset 0-3: Width (uint32)
        4: "ImageHeight",  # Offset 4-7: Height (uint32)
        8: "BitDepth",  # Offset 8: Bit depth (uint8)
        9: "ColorType",  # Offset 9: Color type (uint8)
        10: "Compression",  # Offset 10: Compression method (uint8)
        11: "Filter",  # Offset 11: Filter method (uint8)
        12: "Interlace",  # Offset 12: Interlace method (uint8)
    }

    tag_keys["ihdr"] = ihdr_keys
