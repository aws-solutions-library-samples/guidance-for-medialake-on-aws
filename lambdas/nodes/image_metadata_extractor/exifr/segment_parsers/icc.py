"""
ICC segment parser - ICC color profiles

ICC (International Color Consortium) profiles describe color characteristics
of devices. They can be embedded in JPEG APP2 segments, PNG iCCP chunks,
or TIFF tags.

Large ICC profiles may be split across multiple segments.

Reference: https://www.color.org/icc_specs2.xalter
"""

from datetime import datetime

from ..parser import AppSegmentParserBase
from ..plugins import segment_parsers
from ..util.buffer_view import BufferView
from ..util.helpers import normalize_string

# ICC profile header is 84 bytes (ends at offset 84)
PROFILE_HEADER_LENGTH = 84

# ICC tag types
TAG_TYPE_DESC = "desc"  # Description (text)
TAG_TYPE_MLUC = "mluc"  # Multi-localized Unicode
TAG_TYPE_TEXT = "text"  # Simple text
TAG_TYPE_SIG = "sig "  # Signature (4 chars)

# Empty value marker
EMPTY_VALUE = "\x00\x00\x00\x00"


class Icc(AppSegmentParserBase):
    """Parser for ICC color profiles"""

    type = "icc"
    multi_segment = True
    header_length = 18  # 'ICC_PROFILE\0' header

    @staticmethod
    def can_handle(chunk, offset, length):
        """
        Check if this is an ICC segment

        ICC segments in JPEG APP2 start with 'ICC_PROFILE' signature

        Args:
            chunk: BufferView of file data
            offset: Offset to check
            length: Segment length

        Returns:
            bool: True if this is ICC
        """
        return (
            chunk.get_uint8(offset + 1) == 0xE2
            and chunk.get_uint32(offset + 4) == 0x4943435F
        )  # 'ICC_'

    @staticmethod
    def find_position(chunk, offset):
        """
        Find ICC segment position and multi-segment info

        Args:
            chunk: BufferView of file data
            offset: Offset of segment

        Returns:
            dict: Segment information
        """
        seg = AppSegmentParserBase.find_position(chunk, offset)
        seg["chunk_number"] = chunk.get_uint8(offset + 16)
        seg["chunk_count"] = chunk.get_uint8(offset + 17)
        seg["multi_segment"] = seg["chunk_count"] > 1
        return seg

    @staticmethod
    def handle_multi_segments(segments):
        """
        Combine multiple ICC segments into one BufferView

        Args:
            segments: List of segment dicts with 'chunk' key

        Returns:
            BufferView: Combined ICC profile data
        """
        return concat_chunks(segments)

    def parse(self):
        """
        Parse ICC color profile

        Returns:
            dict: Parsed ICC data
        """
        self.raw = {}
        self.parse_header()
        self.parse_tags()
        self.translate()
        return self.output

    def parse_header(self):
        """
        Parse ICC profile header (first 84 bytes)

        The header contains profile size, version, device class,
        color space, creation date, etc.
        """
        if self.chunk.byte_length < PROFILE_HEADER_LENGTH:
            raise ValueError("ICC header is too short")

        for offset, parser in HEADER_PARSERS.items():
            val = parser(self.chunk, offset)
            if val != EMPTY_VALUE:
                self.raw[offset] = val

    def parse_tags(self):
        """
        Parse ICC tags from profile

        After the header, the profile contains a tag table followed
        by tag data. Each tag has a 4-char code, offset, and length.
        """
        tag_count = self.chunk.get_uint32(128)
        offset = 132  # Tag table starts at 132
        chunk_length = self.chunk.byte_length

        while tag_count > 0:
            # Read tag table entry (12 bytes each)
            code = self.chunk.get_string(offset, 4)
            value_offset = self.chunk.get_uint32(offset + 4)
            value_length = self.chunk.get_uint32(offset + 8)
            tag_type = self.chunk.get_string(value_offset, 4)

            # Check if we have the full data
            if value_offset + value_length > chunk_length:
                print(
                    "Warning: reached end of first ICC chunk. "
                    "Enable options.tiff.multiSegment to read all ICC segments."
                )
                return

            # Parse the tag value based on its type
            value = self.parse_tag(tag_type, value_offset, value_length)

            # Store non-empty values
            if value is not None and value != EMPTY_VALUE:
                self.raw[code] = value

            offset += 12
            tag_count -= 1

    def parse_tag(self, tag_type, offset, length):
        """
        Parse a specific ICC tag based on its type

        Args:
            tag_type: Type identifier (4 chars)
            offset: Offset of tag data
            length: Length of tag data

        Returns:
            Various: Parsed tag value
        """
        if tag_type == TAG_TYPE_DESC:
            return self.parse_desc(offset)
        elif tag_type == TAG_TYPE_MLUC:
            return self.parse_mluc(offset)
        elif tag_type == TAG_TYPE_TEXT:
            return self.parse_text(offset, length)
        elif tag_type == TAG_TYPE_SIG:
            return self.parse_sig(offset)
        # TODO: implement more types (mft2, XYZ, etc.)
        else:
            # Return raw bytes for unknown types
            if offset + length <= self.chunk.byte_length:
                return self.chunk.get_uint8_array(offset, length)
            return None

    def parse_desc(self, offset):
        """
        Parse 'desc' (description) type tag

        Format: type(4) + reserved(4) + length(4) + text(length-1) + null

        Args:
            offset: Offset of tag data

        Returns:
            str: Description text
        """
        length = self.chunk.get_uint32(offset + 8) - 1  # -1 for null terminator
        return normalize_string(self.chunk.get_string(offset + 12, length))

    def parse_text(self, offset, length):
        """
        Parse 'text' type tag

        Format: type(4) + reserved(4) + text

        Args:
            offset: Offset of tag data
            length: Total length of tag data

        Returns:
            str: Text content
        """
        return normalize_string(self.chunk.get_string(offset + 8, length - 8))

    def parse_sig(self, offset):
        """
        Parse 'sig ' (signature) type tag

        Format: type(4) + reserved(4) + signature(4)

        Args:
            offset: Offset of tag data

        Returns:
            str: 4-character signature
        """
        return normalize_string(self.chunk.get_string(offset + 8, 4))

    def parse_mluc(self, tag_offset):
        """
        Parse 'mluc' (Multi Localized Unicode) type tag

        This type stores text in multiple languages. Each entry has:
        - Language code (2 chars)
        - Country code (2 chars)
        - Text length (4 bytes)
        - Text offset (4 bytes)

        Args:
            tag_offset: Offset of tag data

        Returns:
            str or list: Single text string or list of {lang, country, text} dicts
        """
        entry_count = self.chunk.get_uint32(tag_offset + 8)
        entry_size = self.chunk.get_uint32(tag_offset + 12)
        entry_offset = tag_offset + 16
        values = []

        for i in range(entry_count):
            lang = self.chunk.get_string(entry_offset + 0, 2)
            country = self.chunk.get_string(entry_offset + 2, 2)
            length = self.chunk.get_uint32(entry_offset + 4)
            offset = self.chunk.get_uint32(entry_offset + 8) + tag_offset
            text = normalize_string(self.chunk.get_unicode_string(offset, length))

            values.append({"lang": lang, "country": country, "text": text})

            entry_offset += entry_size

        # Return single text if only one entry, otherwise return all
        if entry_count == 1:
            return values[0]["text"]
        else:
            return values

    def translate_value(self, val, tag_enum):
        """
        Translate ICC value using enum dictionary

        Args:
            val: Value to translate
            tag_enum: Dictionary of translations

        Returns:
            Various: Translated value or original
        """
        if isinstance(val, str):
            return tag_enum.get(val) or tag_enum.get(val.lower()) or val
        else:
            return tag_enum.get(val, val)


# Header field parsers
# Maps offset -> parser function
HEADER_PARSERS = {
    4: lambda view, offset: parse_string(view, offset),
    8: lambda view, offset: parse_version(view, offset),
    12: lambda view, offset: parse_string(view, offset),
    16: lambda view, offset: parse_string(view, offset),
    20: lambda view, offset: parse_string(view, offset),
    24: lambda view, offset: parse_date(view, offset),
    36: lambda view, offset: parse_string(view, offset),
    40: lambda view, offset: parse_string(view, offset),
    48: lambda view, offset: parse_string(view, offset),
    52: lambda view, offset: parse_string(view, offset),
    64: lambda view, offset: view.get_uint32(offset),
    80: lambda view, offset: parse_string(view, offset),
}


def parse_string(view, offset):
    """Parse 4-character string from ICC header"""
    return normalize_string(view.get_string(offset, 4))


def parse_version(view, offset):
    """
    Parse ICC version number

    Format: major.minor.bugfix (e.g., "4.3.0")

    Args:
        view: BufferView
        offset: Offset of version field

    Returns:
        str: Version string
    """
    major = view.get_uint8(offset)
    minor_byte = view.get_uint8(offset + 1)
    minor = minor_byte >> 4
    bugfix = minor_byte & 0x0F
    return f"{major}.{minor}.{bugfix}"


def parse_date(view, offset):
    """
    Parse ICC date/time

    Format: year(2) month(2) day(2) hours(2) minutes(2) seconds(2)
    All values are uint16, month is 1-based

    Args:
        view: BufferView
        offset: Offset of date field

    Returns:
        datetime: Parsed datetime object (UTC)
    """
    year = view.get_uint16(offset)
    month = view.get_uint16(offset + 2)
    day = view.get_uint16(offset + 4)
    hours = view.get_uint16(offset + 6)
    minutes = view.get_uint16(offset + 8)
    seconds = view.get_uint16(offset + 10)

    # Month is 1-based in ICC, but 1-based in Python datetime too
    return datetime(year, month, day, hours, minutes, seconds)


def concat_chunks(chunks):
    """
    Concatenate multiple ICC chunk segments

    Args:
        chunks: List of segment dicts with 'chunk' BufferView

    Returns:
        BufferView: Combined buffer
    """
    buffers = [seg["chunk"].to_uint8() for seg in chunks]
    combined = concat_buffers(buffers)
    return BufferView(combined)


def concat_buffers(buffers):
    """
    Concatenate multiple byte arrays

    Args:
        buffers: List of byte arrays (bytes or bytearray)

    Returns:
        bytearray: Combined buffer
    """
    total_length = sum(len(buf) for buf in buffers)
    result = bytearray(total_length)
    offset = 0

    for buf in buffers:
        result[offset : offset + len(buf)] = buf
        offset += len(buf)

    return result


# Register ICC segment parser
segment_parsers["icc"] = Icc
