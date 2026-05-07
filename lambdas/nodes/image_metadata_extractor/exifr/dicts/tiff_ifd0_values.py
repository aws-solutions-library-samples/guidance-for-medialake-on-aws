"""
IFD0 tag value translations
Ported from src/dicts/tiff-ifd0-values.mjs

Translates enum values to readable strings
"""

from ..tags import create_dictionary, tag_values


def load_ifd0_values():
    """Load IFD0 and IFD1 tag value translations"""
    create_dictionary(
        tag_values,
        ["ifd0", "ifd1"],
        [
            # Orientation - How the image should be displayed
            (
                0x0112,
                {
                    1: "Horizontal (normal)",
                    2: "Mirror horizontal",
                    3: "Rotate 180",
                    4: "Mirror vertical",
                    5: "Mirror horizontal and rotate 270 CW",
                    6: "Rotate 90 CW",
                    7: "Mirror horizontal and rotate 90 CW",
                    8: "Rotate 270 CW",
                },
            ),
            # ResolutionUnit - Units for XResolution and YResolution
            (
                0x0128,
                {
                    1: "None",
                    2: "inches",
                    3: "cm",
                },
            ),
        ],
    )
