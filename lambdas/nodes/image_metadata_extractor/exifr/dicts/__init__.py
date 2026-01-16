"""
Tag dictionaries for translating EXIF codes to readable names and values
"""

from .icc_keys import load_icc_keys
from .icc_values import load_icc_values
from .ihdr_keys import load_ihdr_keys
from .ihdr_values import load_ihdr_values
from .iptc_keys import load_iptc_keys
from .jfif_keys import load_jfif_keys
from .tiff_exif_keys import load_exif_keys
from .tiff_exif_values import load_exif_values
from .tiff_gps_keys import load_gps_keys
from .tiff_ifd0_keys import load_ifd0_keys
from .tiff_ifd0_values import load_ifd0_values
from .tiff_revivers import load_tiff_revivers

__all__ = [
    "load_ifd0_keys",
    "load_exif_keys",
    "load_gps_keys",
    "load_ifd0_values",
    "load_exif_values",
    "load_tiff_revivers",
    "load_icc_keys",
    "load_icc_values",
    "load_ihdr_keys",
    "load_ihdr_values",
    "load_iptc_keys",
    "load_jfif_keys",
]


def load_all_dictionaries():
    """Load all tag dictionaries into the global registry"""
    # Load TIFF/EXIF tag name dictionaries
    load_ifd0_keys()
    load_exif_keys()
    load_gps_keys()

    # Load TIFF/EXIF value translation dictionaries
    load_ifd0_values()
    load_exif_values()

    # Load TIFF/EXIF value revivers (converters to Python objects)
    load_tiff_revivers()

    # Load ICC tag dictionaries
    load_icc_keys()
    load_icc_values()

    # Load PNG IHDR dictionaries
    load_ihdr_keys()
    load_ihdr_values()

    # Load IPTC tag names
    load_iptc_keys()

    # Load JFIF tag names
    load_jfif_keys()
