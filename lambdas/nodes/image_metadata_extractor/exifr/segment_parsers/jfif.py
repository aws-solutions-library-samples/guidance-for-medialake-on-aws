"""
JFIF segment parser - JFIF metadata (JPEG File Interchange Format)

JFIF is the standard format for JPEG images, stored in APP0 segments (marker 0xE0).
It contains basic image information like version, resolution, and density units.

Reference: https://exiftool.org/TagNames/JFIF.html
Reference: https://www.w3.org/Graphics/JPEG/jfif3.pdf
"""

from ..parser import AppSegmentParserBase
from ..plugins import segment_parsers


class Jfif(AppSegmentParserBase):
    """Parser for JFIF metadata in JPEG APP0 segments"""

    type = "jfif"
    header_length = 9  # 'JFIF\0' header is 5 bytes + 4 bytes for segment marker/length

    @staticmethod
    def can_handle(buffer, offset, length):
        """
        Check if this is a JFIF segment

        JFIF segments are APP0 (0xE0) with 'JFIF\0' signature

        Args:
            buffer: BufferView of file data
            offset: Offset to check
            length: Segment length

        Returns:
            bool: True if this is JFIF
        """
        return (
            buffer.get_uint8(offset + 1) == 0xE0
            and buffer.get_uint32(offset + 4) == 0x4A464946  # 'JFIF'
            and buffer.get_uint8(offset + 8) == 0x00
        )  # '\0' terminator

    def parse(self):
        """
        Parse JFIF metadata

        Returns:
            dict: Parsed JFIF data
        """
        self.parse_tags()
        self.translate()
        return self.output

    def parse_tags(self):
        """
        Parse JFIF header fields

        JFIF header format (after 'JFIF\0' signature):
        - Offset 0-1: Version (major.minor, e.g., 0x0102 = 1.2)
        - Offset 2: Density units (0=no units, 1=pixels/inch, 2=pixels/cm)
        - Offset 3-4: X density (uint16)
        - Offset 5-6: Y density (uint16)
        - Offset 7: Thumbnail width (uint8)
        - Offset 8: Thumbnail height (uint8)
        """
        self.raw = {
            0: self.chunk.get_uint16(0),  # JFIFVersion
            2: self.chunk.get_uint8(2),  # ResolutionUnit
            3: self.chunk.get_uint16(3),  # XResolution
            5: self.chunk.get_uint16(5),  # YResolution
            7: self.chunk.get_uint8(7),  # ThumbnailWidth
            8: self.chunk.get_uint8(8),  # ThumbnailHeight
        }


# Register JFIF segment parser
segment_parsers["jfif"] = Jfif
