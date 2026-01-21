"""
IPTC segment parser - IPTC metadata (copyright, captions, keywords)

IPTC (International Press Telecommunications Council) metadata contains
editorial information like captions, copyright, keywords, credits, etc.

IPTC is embedded in Photoshop APP13 segments (marker 0xED).
The APP13 segment uses Photoshop's "Image Resources" format with 8BIM chunks.
IPTC data is in the 8BIM chunk with ID 0x0404.

Reference: http://fileformats.archiveteam.org/wiki/Photoshop_Image_Resources
Reference: https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/

Additional Photoshop chunks:
- 0x0404: IPTC data
- 0x040c: Thumbnail in JPEG/JFIF format
- 0x040F: ICC profile
- 0x0422: Exif data
- 0x0424: XMP data
"""

from ..parser import AppSegmentParserBase
from ..plugins import segment_parsers

# Photoshop segment markers
HEADER_8 = 0x38  # '8' - first byte of 8BIM
HEADER_8BIM = 0x3842494D  # '8BIM' - Photoshop chunk signature
HEADER_IPTC = 0x0404  # IPTC chunk ID
MARKER = 0xED  # APP13 marker
PHOTOSHOP = "Photoshop"


class Iptc(AppSegmentParserBase):
    """Parser for IPTC metadata in Photoshop APP13 segments"""

    type = "iptc"

    # IPTC values don't need translation or revival by default
    translate_values = False
    revive_values = False

    @staticmethod
    def can_handle(file_reader, offset, length):
        """
        Check if this is an IPTC segment

        APP13 segments are complicated - they contain Photoshop data with
        multiple 8BIM chunks. IPTC is just one of those chunks and may start
        several hundred bytes into the segment. We need to traverse it.

        Args:
            file_reader: File reader instance
            offset: Offset of segment
            length: Length of segment

        Returns:
            bool: True if this contains IPTC data
        """
        # Check if this is APP13 with Photoshop signature
        is_app13 = (
            file_reader.get_uint8(offset + 1) == MARKER
            and file_reader.get_string(offset + 4, 9) == PHOTOSHOP
        )
        if not is_app13:
            return False

        # Check if it contains IPTC 8BIM chunk
        i = Iptc.contains_iptc_8bim(file_reader, offset, length)
        return i is not None

    @staticmethod
    def header_length(chunk, offset, length):
        """
        Calculate header length to skip before IPTC data

        The header includes Photoshop signature and 8BIM chunk header.
        The name field is padded to even number of bytes.

        Args:
            chunk: BufferView of file data
            offset: Offset of segment
            length: Length of segment

        Returns:
            int: Header length to skip
        """
        i = Iptc.contains_iptc_8bim(chunk, offset, length)
        if i is not None:
            # Get length of name header (padded to even bytes)
            name_header_length = chunk.get_uint8(offset + i + 7)
            if name_header_length % 2 != 0:
                name_header_length += 1

            # Check for pre-Photoshop 6 format
            if name_header_length == 0:
                name_header_length = 4

            return i + 8 + name_header_length
        return None

    @staticmethod
    def contains_iptc_8bim(chunk, offset, length):
        """
        Search for IPTC 8BIM chunk in Photoshop data

        Args:
            chunk: BufferView of file data
            offset: Offset to start search
            length: Length to search within

        Returns:
            int or None: Offset of IPTC chunk relative to start, or None
        """
        for i in range(length):
            if Iptc.is_iptc_segment_head(chunk, offset + i):
                return i
        return None

    @staticmethod
    def is_iptc_segment_head(chunk, offset):
        """
        Check if offset points to IPTC 8BIM chunk header

        This is called on each byte while traversing - optimize by checking
        first byte before reading more data.

        Args:
            chunk: BufferView of file data
            offset: Offset to check

        Returns:
            bool: True if this is IPTC chunk header
        """
        # Quick check: first byte should be '8'
        if chunk.get_uint8(offset) != HEADER_8:
            return False

        # Full check: '8BIM' signature followed by IPTC ID
        return (
            chunk.get_uint32(offset) == HEADER_8BIM
            and chunk.get_uint16(offset + 4) == HEADER_IPTC
        )

    def parse(self):
        """
        Parse IPTC metadata tags

        IPTC tags have variable header. Data can start immediately or after
        a few bytes. We seek through until we find 0x1C02 markers.

        Format: 0x1C 0x02 [tag_id] [size_hi] [size_lo] [data...]

        Returns:
            dict: Parsed IPTC data
        """
        iterable_length = self.chunk.byte_length - 1
        found_first_prop = False
        offset = 0

        while offset < iterable_length:
            # Look for IPTC tag marker (0x1C 0x02)
            # Read bytes separately to avoid unnecessary reads when iterating
            if (
                self.chunk.get_uint8(offset) == 0x1C
                and self.chunk.get_uint8(offset + 1) == 0x02
            ):

                found_first_prop = True

                # Parse IPTC tag
                key = self.chunk.get_uint8(offset + 2)
                size = self.chunk.get_uint16(offset + 3)
                val = self.chunk.get_latin1_string(offset + 5, size)

                # Store value (may be repeated, so pluralize)
                self.raw[key] = self.pluralize_value(self.raw.get(key), val)

                # Skip over the tag we just read
                offset += 4 + size

            elif found_first_prop:
                # After finding first property, if we don't find another tag,
                # we've reached the end of IPTC data (due to dynamic header)
                break
            else:
                # Keep searching for first tag
                offset += 1

        self.translate()
        return self.output

    def pluralize_value(self, existing_val, new_val):
        """
        Handle repeated IPTC tags by creating arrays

        Some IPTC tags can appear multiple times (e.g., keywords).
        First occurrence is stored as string, subsequent ones create array.

        Args:
            existing_val: Existing value (None, str, or list)
            new_val: New value to add

        Returns:
            str or list: Single value or list of values
        """
        if existing_val is not None:
            if isinstance(existing_val, list):
                existing_val.append(new_val)
                return existing_val
            else:
                return [existing_val, new_val]
        else:
            return new_val


# Register IPTC segment parser
segment_parsers["iptc"] = Iptc
