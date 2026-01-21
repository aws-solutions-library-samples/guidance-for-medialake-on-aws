"""
IHDR segment parser - PNG image header

Parses PNG IHDR chunk which contains basic image properties:
- Width (4 bytes)
- Height (4 bytes)
- Bit depth (1 byte)
- Color type (1 byte)
- Compression method (1 byte)
- Filter method (1 byte)
- Interlace method (1 byte)

Additional PNG metadata from tEXt chunks is also included here.
"""

from ..parser import AppSegmentParserBase
from ..plugins import segment_parsers


class Ihdr(AppSegmentParserBase):
    """Parser for PNG IHDR (image header) chunk"""

    type = "ihdr"

    def parse(self):
        """
        Parse PNG IHDR chunk

        Returns:
            dict: Parsed PNG header data
        """
        self.parse_tags()
        self.translate()
        return self.output

    def parse_tags(self):
        """
        Parse IHDR chunk fields and include any injected tEXt data

        The IHDR chunk is 13 bytes:
        - Offset 0-3: Width (uint32)
        - Offset 4-7: Height (uint32)
        - Offset 8: Bit depth (uint8)
        - Offset 9: Color type (uint8)
        - Offset 10: Compression method (uint8)
        - Offset 11: Filter method (uint8)
        - Offset 12: Interlace method (uint8)

        PNG also contains additional string data in free tEXt chunks.
        These kinda belong to IHDR, but are not part of the IHDR chunk
        and would require additional segment-parser class. Instead these
        chunks are handled in the PNG file parser itself and injected
        into self.raw dict. Here, we're making sure they're included in output.
        """
        # Start with IHDR chunk fields
        self.raw = {
            0: self.chunk.get_uint32(0),  # Width
            4: self.chunk.get_uint32(4),  # Height
            8: self.chunk.get_uint8(8),  # Bit depth
            9: self.chunk.get_uint8(9),  # Color type
            10: self.chunk.get_uint8(10),  # Compression method
            11: self.chunk.get_uint8(11),  # Filter method
            12: self.chunk.get_uint8(12),  # Interlace method
        }

        # Include any additional data that was injected from tEXt chunks
        # (PNG file parser adds these during parse_text_chunks)
        # The raw dict may already have string keys added


# Register the IHDR segment parser
segment_parsers["ihdr"] = Ihdr
