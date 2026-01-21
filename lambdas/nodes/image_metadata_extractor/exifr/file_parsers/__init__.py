"""
File format parsers
"""

from .heif import AvifFileParser, HeicFileParser
from .jpeg import JpegFileParser
from .png import PngFileParser
from .tiff import TiffFileParser

__all__ = [
    "JpegFileParser",
    "TiffFileParser",
    "PngFileParser",
    "HeicFileParser",
    "AvifFileParser",
]
