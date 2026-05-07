"""
TIFF/EXIF segment parser
Ported from src/segment-parsers/tiff-exif.mjs
"""

from ..options import TIFF_BLOCKS
from ..parser import AppSegmentParserBase
from ..plugins import segment_parsers
from ..tags import (
    TAG_GPS_LAT,
    TAG_GPS_LATREF,
    TAG_GPS_LON,
    TAG_GPS_LONREF,
    TAG_ICC,
    TAG_IFD_EXIF,
    TAG_IFD_GPS,
    TAG_IFD_INTEROP,
    TAG_IPTC,
    TAG_MAKERNOTE,
    TAG_USERCOMMENT,
    TAG_XMP,
)
from ..util.helpers import (
    TIFF_BIG_ENDIAN,
    TIFF_LITTLE_ENDIAN,
    estimate_metadata_size,
    is_empty,
    normalize_string,
    throw_error,
)

MALFORMED = "Malformed EXIF data"

# Thumbnail tags
THUMB_OFFSET = 0x0201
THUMB_LENGTH = 0x0202

# TIFF data types
BYTE = 1
ASCII = 2
SHORT = 3
LONG = 4
RATIONAL = 5
SBYTE = 6
UNDEFINED = 7
SSHORT = 8
SLONG = 9
SRATIONAL = 10
FLOAT = 11
DOUBLE = 12
IFD = 13

# Size lookup table for each type
SIZE_LOOKUP = [
    None,  # 0 - undefined
    1,  # 1 - BYTE
    1,  # 2 - ASCII
    2,  # 3 - SHORT
    4,  # 4 - LONG
    8,  # 5 - RATIONAL
    1,  # 6 - SBYTE
    1,  # 7 - UNDEFINED
    2,  # 8 - SSHORT
    4,  # 9 - SLONG
    8,  # 10 - SRATIONAL
    4,  # 11 - FLOAT
    8,  # 12 - DOUBLE
    4,  # 13 - IFD
]

# Special tags that need unpacking
TAG_FILESOURCE = 0xA300
TAG_SCENETYPE = 0xA301


def convert_dms_to_dd(degrees, minutes, seconds, direction):
    """
    Convert DMS (Degrees, Minutes, Seconds) to Decimal Degrees

    Args:
        degrees: Degrees value
        minutes: Minutes value
        seconds: Seconds value
        direction: 'N', 'S', 'E', or 'W'

    Returns:
        float: Decimal degrees
    """
    dd = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if direction in ("S", "W"):
        dd *= -1
    return dd


class TiffCore(AppSegmentParserBase):
    """
    Core TIFF parsing functionality
    """

    def parse_header(self):
        """Parse TIFF header to determine endianness"""
        byte_order = self.chunk.get_uint16(0)

        if byte_order == TIFF_LITTLE_ENDIAN:
            self.le = True  # Little endian
        elif byte_order == TIFF_BIG_ENDIAN:
            self.le = False  # Big endian
        else:
            # Some files may have invalid byte order, try to continue anyway
            self.le = True

        # Set endianness on chunk
        self.chunk.set_endian(not self.le)  # BufferView uses big_endian flag
        self.header_parsed = True

    def parse_tags(self, offset, block_key, block=None):
        """
        Parse TIFF tags from a block

        Args:
            offset: Offset to start of block
            block_key: Block identifier (ifd0, exif, gps, etc.)
            block: Optional dict to populate

        Returns:
            dict: Parsed tags
        """
        if block is None:
            block = {}

        block_opts = getattr(self.options, block_key)
        pick = set(block_opts.pick) if block_opts.pick else set()
        skip = block_opts.skip if block_opts.skip else set()

        only_pick = len(pick) > 0
        nothing_to_skip = len(skip) == 0

        entries_count = self.chunk.get_uint16(offset)
        offset += 2

        for i in range(entries_count):
            tag = self.chunk.get_uint16(offset)

            if only_pick:
                if tag in pick:
                    # This tag is in pick list, so read it
                    block[tag] = self.parse_tag(offset, tag, block_key)
                    pick.discard(tag)
                    if len(pick) == 0:
                        break
            elif nothing_to_skip or tag not in skip:
                # Not limiting picks and tag not in skip list
                block[tag] = self.parse_tag(offset, tag, block_key)

            offset += 12

        return block

    def parse_tag(self, offset, tag, block_key):
        """
        Parse a single TIFF tag

        Args:
            offset: Offset to tag entry
            tag: Tag code
            block_key: Block identifier

        Returns:
            Parsed tag value
        """
        chunk = self.chunk

        tag_type = chunk.get_uint16(offset + 2)
        value_count = chunk.get_uint32(offset + 4)
        value_size = SIZE_LOOKUP[tag_type] if tag_type < len(SIZE_LOOKUP) else 0
        total_size = value_size * value_count

        # Value is stored inline if <= 4 bytes, otherwise it's an offset
        if total_size <= 4:
            value_offset = offset + 8
        else:
            value_offset = chunk.get_uint32(offset + 8)

        # Validate type
        if tag_type < BYTE or tag_type > IFD:
            throw_error(
                f"Invalid TIFF value type. block: {block_key.upper()}, "
                f"tag: {hex(tag)}, type: {tag_type}, offset: {value_offset}"
            )

        # Validate offset
        if value_offset > chunk.byte_length:
            throw_error(
                f"Invalid TIFF value offset. block: {block_key.upper()}, "
                f"tag: {hex(tag)}, type: {tag_type}, offset: {value_offset} "
                f"is outside of chunk size {chunk.byte_length}"
            )

        # Handle special types
        if tag_type == BYTE:
            return chunk.get_bytes(value_offset, value_count)

        if tag_type == ASCII:
            return normalize_string(chunk.get_string(value_offset, value_count))

        if tag_type == UNDEFINED:
            return chunk.get_bytes(value_offset, value_count)

        # Handle single vs multiple values
        if value_count == 1:
            return self.parse_tag_value(tag_type, value_offset)
        else:
            # Return array of values
            arr = []
            for i in range(value_count):
                arr.append(self.parse_tag_value(tag_type, value_offset))
                value_offset += value_size
            return arr

    def parse_tag_value(self, tag_type, offset):
        """
        Parse a single tag value based on type

        Args:
            tag_type: TIFF data type
            offset: Offset to value

        Returns:
            Parsed value
        """
        chunk = self.chunk

        if tag_type == BYTE:
            return chunk.get_uint8(offset)
        elif tag_type == SHORT:
            return chunk.get_uint16(offset)
        elif tag_type == LONG:
            return chunk.get_uint32(offset)
        elif tag_type == RATIONAL:
            numerator = chunk.get_uint32(offset)
            denominator = chunk.get_uint32(offset + 4)
            return numerator / denominator if denominator != 0 else 0
        elif tag_type == SBYTE:
            return chunk.get_int8(offset)
        elif tag_type == SSHORT:
            return chunk.get_int16(offset)
        elif tag_type == SLONG:
            return chunk.get_int32(offset)
        elif tag_type == SRATIONAL:
            numerator = chunk.get_int32(offset)
            denominator = chunk.get_int32(offset + 4)
            return numerator / denominator if denominator != 0 else 0
        elif tag_type == FLOAT:
            return chunk.get_float32(offset)
        elif tag_type == DOUBLE:
            return chunk.get_float64(offset)
        elif tag_type == IFD:
            return chunk.get_uint32(offset)
        else:
            throw_error(f"Invalid TIFF type {tag_type}")


class TiffExif(TiffCore):
    """
    TIFF/EXIF segment parser

    Handles APP1 segment in JPEG files and TIFF files directly.
    Parses IFD0, EXIF, GPS, Interop, and IFD1 (thumbnail) blocks.
    """

    type = "tiff"
    header_length = 10

    @classmethod
    def can_handle(cls, view, offset, length=None):
        """Check if segment is TIFF/EXIF"""
        try:
            return (
                view.get_uint8(offset + 1) == 0xE1
                and view.get_uint32(offset + 4) == 0x45786966  # 'Exif'
                and view.get_uint16(offset + 8) == 0x0000
            )  # '\0\0'
        except:
            return False

    def __init__(self, chunk, options, file):
        super().__init__(chunk, options, file)
        self.ifd0 = None
        self.ifd1 = None
        self.exif = None
        self.gps = None
        self.interop = None
        self.ifd0_offset = None
        self.ifd1_offset = None
        self.exif_offset = None
        self.gps_offset = None
        self.interop_offset = None
        self.xmp = None
        self.iptc = None
        self.icc = None
        self.maker_note = None
        self.user_comment = None
        self.ifd1_parsed = False
        self.header_parsed = False

    async def parse(self):
        """Parse TIFF/EXIF data"""
        self.parse_header()
        options = self.options

        # Parse blocks in order
        if options.ifd0.enabled:
            await self.parse_ifd0_block()
        if options.exif.enabled:
            await self.safe_parse("parse_exif_block")
        if options.gps.enabled:
            await self.safe_parse("parse_gps_block")
        if options.interop.enabled:
            await self.safe_parse("parse_interop_block")
        if options.ifd1.enabled:
            await self.safe_parse("parse_thumbnail_block")

        return self.create_output()

    async def safe_parse(self, method_name):
        """Safely call a parse method with error handling"""
        try:
            method = getattr(self, method_name)
            result = method()
            # Handle both sync and async methods
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            self.handle_error(e)

    def find_ifd0_offset(self):
        """Find offset to IFD0"""
        if self.ifd0_offset is None:
            self.ifd0_offset = self.chunk.get_uint32(4)

    def find_ifd1_offset(self):
        """Find offset to IFD1 (thumbnail)"""
        if self.ifd1_offset is None:
            self.find_ifd0_offset()
            ifd0_entries = self.chunk.get_uint16(self.ifd0_offset)
            temp = self.ifd0_offset + 2 + (ifd0_entries * 12)
            self.ifd1_offset = self.chunk.get_uint32(temp)

    def parse_block(self, offset, block_key):
        """
        Parse a TIFF block

        Args:
            offset: Offset to block
            block_key: Block identifier

        Returns:
            dict: Parsed block
        """
        block = {}
        setattr(self, block_key, block)
        self.parse_tags(offset, block_key, block)
        return block

    async def parse_ifd0_block(self):
        """Parse IFD0 block (main image info)"""
        if self.ifd0:
            return self.ifd0

        file = self.file
        self.find_ifd0_offset()

        if self.ifd0_offset < 8:
            throw_error(MALFORMED)

        if not hasattr(file, "chunked") or not file.chunked:
            if self.ifd0_offset > file.byte_length:
                throw_error(
                    f"IFD0 offset points outside of file. "
                    f"offset: {self.ifd0_offset}, length: {file.byte_length}"
                )

        # Ensure chunk is available for TIFF files
        if hasattr(file, "tiff") and file.tiff:
            if hasattr(file, "ensure_chunk"):
                await file.ensure_chunk(
                    self.ifd0_offset, estimate_metadata_size(self.options)
                )

        # Parse IFD0
        ifd0 = self.parse_block(self.ifd0_offset, "ifd0")

        if len(ifd0) == 0:
            return ifd0

        # Store offsets to other blocks
        self.exif_offset = ifd0.get(TAG_IFD_EXIF)
        self.interop_offset = ifd0.get(TAG_IFD_INTEROP)
        self.gps_offset = ifd0.get(TAG_IFD_GPS)
        self.xmp = ifd0.get(TAG_XMP)
        self.iptc = ifd0.get(TAG_IPTC)
        self.icc = ifd0.get(TAG_ICC)

        # Remove pointer tags if sanitizing
        if self.options.sanitize:
            ifd0.pop(TAG_IFD_EXIF, None)
            ifd0.pop(TAG_IFD_INTEROP, None)
            ifd0.pop(TAG_IFD_GPS, None)
            ifd0.pop(TAG_XMP, None)
            ifd0.pop(TAG_IPTC, None)
            ifd0.pop(TAG_ICC, None)

        return ifd0

    async def parse_exif_block(self):
        """Parse EXIF block"""
        if self.exif:
            return self.exif

        if not self.ifd0:
            await self.parse_ifd0_block()

        if self.exif_offset is None:
            return None

        # Ensure chunk for TIFF files
        if hasattr(self.file, "tiff") and self.file.tiff:
            if hasattr(self.file, "ensure_chunk"):
                await self.file.ensure_chunk(
                    self.exif_offset, estimate_metadata_size(self.options)
                )

        exif = self.parse_block(self.exif_offset, "exif")

        # Check for interop offset in EXIF
        if not self.interop_offset:
            self.interop_offset = exif.get(TAG_IFD_INTEROP)

        self.maker_note = exif.get(TAG_MAKERNOTE)
        self.user_comment = exif.get(TAG_USERCOMMENT)

        # Sanitize
        if self.options.sanitize:
            exif.pop(TAG_IFD_INTEROP, None)
            exif.pop(TAG_MAKERNOTE, None)
            exif.pop(TAG_USERCOMMENT, None)

        # Unpack single-element arrays
        self.unpack(exif, TAG_FILESOURCE)
        self.unpack(exif, TAG_SCENETYPE)

        return exif

    def unpack(self, block, key):
        """Unpack single-element array"""
        value = block.get(key)
        if value and isinstance(value, (list, tuple)) and len(value) == 1:
            block[key] = value[0]

    async def parse_gps_block(self):
        """Parse GPS block"""
        if self.gps:
            return self.gps

        if not self.ifd0:
            await self.parse_ifd0_block()

        if self.gps_offset is None:
            return None

        gps = self.parse_block(self.gps_offset, "gps")

        # Convert DMS to decimal degrees
        if gps and TAG_GPS_LAT in gps and TAG_GPS_LON in gps:
            lat = gps.get(TAG_GPS_LAT)
            lat_ref = gps.get(TAG_GPS_LATREF, "N")
            lon = gps.get(TAG_GPS_LON)
            lon_ref = gps.get(TAG_GPS_LONREF, "E")

            if lat and lon:
                gps["latitude"] = convert_dms_to_dd(*lat, lat_ref)
                gps["longitude"] = convert_dms_to_dd(*lon, lon_ref)

        return gps

    async def parse_interop_block(self):
        """Parse Interop block"""
        if self.interop:
            return self.interop

        if not self.ifd0:
            await self.parse_ifd0_block()

        if self.interop_offset is None and not self.exif:
            await self.parse_exif_block()

        if self.interop_offset is None:
            return None

        return self.parse_block(self.interop_offset, "interop")

    async def parse_thumbnail_block(self, force=False):
        """Parse thumbnail block (IFD1)"""
        if self.ifd1 or self.ifd1_parsed:
            return self.ifd1

        if self.options.mergeOutput and not force:
            return None

        self.find_ifd1_offset()

        if self.ifd1_offset > 0:
            self.parse_block(self.ifd1_offset, "ifd1")
            self.ifd1_parsed = True

        return self.ifd1

    async def extract_thumbnail(self):
        """Extract embedded thumbnail"""
        if not self.header_parsed:
            self.parse_header()

        if not self.ifd1_parsed:
            await self.parse_thumbnail_block(force=True)

        if self.ifd1 is None:
            return None

        offset = self.ifd1.get(THUMB_OFFSET)
        length = self.ifd1.get(THUMB_LENGTH)

        if offset is None or length is None:
            return None

        return self.chunk.get_bytes(offset, length)

    @property
    def image(self):
        """Alias for ifd0"""
        return self.ifd0

    @property
    def thumbnail(self):
        """Alias for ifd1"""
        return self.ifd1

    def create_output(self):
        """Create final output from parsed blocks"""
        tiff = {}

        for block_key in TIFF_BLOCKS:
            block = getattr(self, block_key, None)
            if is_empty(block):
                continue

            if self.can_translate:
                block_output = self.translate_block(block, block_key)
            else:
                block_output = dict(block)

            if self.options.mergeOutput:
                # Don't include thumbnail (IFD1) in merged output
                if block_key == "ifd1":
                    continue
                tiff.update(block_output)
            else:
                tiff[block_key] = block_output

        # Add notable tags
        if self.maker_note:
            tiff["makerNote"] = self.maker_note
        if self.user_comment:
            tiff["userComment"] = self.user_comment

        return tiff

    def assign_to_output(self, root, tiff):
        """Assign TIFF output to root"""
        if self.global_options.mergeOutput:
            root.update(tiff)
        else:
            for block_key, block in tiff.items():
                self.assign_object_to_output(root, block_key, block)


# Register parser
segment_parsers.register("tiff", TiffExif)
