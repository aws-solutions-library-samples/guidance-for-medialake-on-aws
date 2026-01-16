"""
exifr - The fastest and most versatile Python EXIF reading library

Ported from the JavaScript library by Mike Kovařík
https://github.com/MikeKovarik/exifr
"""

from .core import Exifr, parse

# Load tag dictionaries on import
from .dicts import load_all_dictionaries
from .highlevel import gps, orientation, rotation, thumbnail

load_all_dictionaries()

from .file_parsers import (
    AvifFileParser,
    HeicFileParser,
    JpegFileParser,
    PngFileParser,
    TiffFileParser,
)

# Load all file parsers
from .plugins import file_parsers as file_parser_registry

# Register file parsers
file_parser_registry.register("jpeg", JpegFileParser)
file_parser_registry.register("jpg", JpegFileParser)
file_parser_registry.register("tiff", TiffFileParser)
file_parser_registry.register("tif", TiffFileParser)
file_parser_registry.register("png", PngFileParser)
file_parser_registry.register("heic", HeicFileParser)
file_parser_registry.register("avif", AvifFileParser)

# Load all segment parsers
from .plugins import segment_parsers as segment_parser_registry
from .segment_parsers import Icc, Ihdr, Iptc, Jfif, TiffExif, Xmp

# Register segment parsers
segment_parser_registry.register("tiff", TiffExif)
segment_parser_registry.register("exif", TiffExif)
segment_parser_registry.register("gps", TiffExif)
segment_parser_registry.register("interop", TiffExif)
segment_parser_registry.register("ihdr", Ihdr)
segment_parser_registry.register("xmp", Xmp)
segment_parser_registry.register("icc", Icc)
segment_parser_registry.register("iptc", Iptc)
segment_parser_registry.register("jfif", Jfif)

# Load all file readers (self-register on import)

__version__ = "0.1.0"
__all__ = [
    "Exifr",
    "parse",
    "gps",
    "orientation",
    "rotation",
    "thumbnail",
]
