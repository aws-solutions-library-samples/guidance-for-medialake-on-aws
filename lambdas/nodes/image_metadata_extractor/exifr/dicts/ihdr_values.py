"""
IHDR (PNG header) value translations

Maps PNG IHDR numeric codes to human-readable strings for color types,
compression methods, filter methods, and interlace methods.
"""

from ..tags import tag_values


def load_ihdr_values():
    """Load IHDR value translations into global registry"""

    ihdr_values = {
        # ColorType (offset 9)
        9: {
            0: "Grayscale",
            2: "RGB",
            3: "Palette",
            4: "Grayscale with Alpha",
            6: "RGB with Alpha",
            "DEFAULT": "Unknown",
        },
        # Compression (offset 10)
        10: {
            0: "Deflate/Inflate",
            "DEFAULT": "Unknown",
        },
        # Filter (offset 11)
        11: {
            0: "Adaptive",
            "DEFAULT": "Unknown",
        },
        # Interlace (offset 12)
        12: {
            0: "Noninterlaced",
            1: "Adam7 Interlace",
            "DEFAULT": "Unknown",
        },
    }

    tag_values["ihdr"] = ihdr_values
