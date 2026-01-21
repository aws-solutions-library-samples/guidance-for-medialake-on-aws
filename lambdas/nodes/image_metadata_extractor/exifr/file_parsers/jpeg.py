"""
JPEG file parser
Ported from src/file-parsers/jpeg.mjs
"""

from ..parser import AppSegmentParserBase, FileParserBase
from ..plugins import file_parsers, segment_parsers

# JPEG markers
JPEG_SOI = 0xFFD8

MARKER_1 = 0xFF
MARKER_2_APP0 = 0xE0  # FF E0
MARKER_2_APP15 = 0xEF  # FF EF
MARKER_2_SOF0 = 0xC0  # FF C0
MARKER_2_SOF2 = 0xC2  # FF C2
MARKER_2_DHT = 0xC4  # FF C4
MARKER_2_DQT = 0xDB  # FF DB
MARKER_2_DRI = 0xDD  # FF DD
MARKER_2_SOS = 0xDA  # FF DA
MARKER_2_COMMENT = 0xFE  # FF FE


def is_jpg_marker(marker2):
    """Check if marker is a JPEG structure marker"""
    return marker2 in (
        MARKER_2_SOF0,
        MARKER_2_SOF2,
        MARKER_2_DHT,
        MARKER_2_DQT,
        MARKER_2_DRI,
        MARKER_2_SOS,
        MARKER_2_COMMENT,
    )


def is_app_marker(marker2):
    """Check if marker is an APP marker"""
    return MARKER_2_APP0 <= marker2 <= MARKER_2_APP15


def get_segment_type(buffer, offset, length):
    """Determine segment type from buffer"""
    for seg_type, Parser in segment_parsers:
        if Parser.can_handle(buffer, offset, length):
            return seg_type
    return None


class JpegFileParser(FileParserBase):
    """
    JPEG file format parser

    Structure:
    - SOI (Start of Image)
    - APP0-APP15 segments (metadata)
    - DQT, DHT, and other JPEG segments
    - SOS (Start of Scan) followed by image data

    APP segments contain metadata:
    - APP1: TIFF/EXIF data
    - APP1: XMP data (separate from EXIF APP1)
    - APP2: ICC color profile
    - APP13: IPTC data
    """

    type = "jpeg"

    @classmethod
    def can_handle(cls, file, first_two_bytes):
        """Check if file is JPEG"""
        return first_two_bytes == JPEG_SOI

    def __init__(self, options, file, parsers):
        super().__init__(options, file, parsers)
        self.app_segments = []
        self.jpeg_segments = []
        self.unknown_segments = []
        self.merged_app_segments = None

    async def parse(self):
        """Parse JPEG file"""
        await self.find_app_segments()
        await self.read_segments(self.app_segments)
        self.merge_multi_segments()
        segments = self.merged_app_segments or self.app_segments
        self.create_parsers(segments)

    def setup_segment_finder_args(self, wanted):
        """Setup arguments for segment finding"""
        if wanted is True:
            self.find_all = True
            self.wanted = set(segment_parsers._plugins.keys())
        else:
            if wanted is None:
                wanted = [
                    key
                    for key in segment_parsers._plugins.keys()
                    if getattr(self.options, key).enabled
                ]
            else:
                wanted = [
                    key
                    for key in wanted
                    if getattr(self.options, key).enabled and segment_parsers.has(key)
                ]

            self.find_all = False
            self.remaining = set(wanted)
            self.wanted = set(wanted)

        self.unfinished_multi_segment = False

    async def find_app_segments(self, offset=0, wanted_array=None):
        """Find APP segments in JPEG file"""
        self.setup_segment_finder_args(wanted_array)

        file = self.file
        find_all = self.find_all
        wanted = self.wanted
        remaining = self.remaining

        # Check if we need to read whole file for multi-segment support
        if not find_all and hasattr(file, "chunked") and file.chunked:
            find_all = any(
                segment_parsers.get(seg_type).multi_segment
                and getattr(self.options, seg_type).multiSegment
                for seg_type in wanted
                if segment_parsers.has(seg_type)
            )
            if find_all and hasattr(file, "read_whole"):
                await file.read_whole()

        # Find segments in current range
        offset = self.find_app_segments_in_range(offset, file.byte_length)

        # Return early if only TIFF is requested
        if self.options.only_tiff:
            return

        # Continue reading chunks if needed
        if hasattr(file, "chunked") and file.chunked:
            eof = False
            while (
                len(remaining) > 0
                and not eof
                and (
                    hasattr(file, "can_read_next_chunk")
                    and (file.can_read_next_chunk or self.unfinished_multi_segment)
                )
            ):

                next_chunk_offset = getattr(file, "next_chunk_offset", file.byte_length)

                # Check for incomplete segments
                has_incomplete = any(
                    not file.available(
                        seg.get("offset", seg.get("start", 0)),
                        seg.get("length", seg.get("size", 0)),
                    )
                    for seg in self.app_segments
                )

                # Read next chunk
                if offset > next_chunk_offset and not has_incomplete:
                    eof = not await file.read_next_chunk(offset)
                else:
                    eof = not await file.read_next_chunk(next_chunk_offset)

                offset = self.find_app_segments_in_range(offset, file.byte_length)

                if offset is None:
                    return

    def find_app_segments_in_range(self, offset, end):
        """Find APP segments in byte range"""
        # Leave room for marker and length
        end -= 2

        file = self.file
        find_all = self.find_all
        wanted = self.wanted
        remaining = self.remaining
        options = self.options

        while offset < end:
            if file.get_uint8(offset) != MARKER_1:
                offset += 1
                continue

            marker2 = file.get_uint8(offset + 1)

            if is_app_marker(marker2):
                # APP segment found
                length = file.get_uint16(offset + 2)
                seg_type = get_segment_type(file, offset, length)

                if seg_type and seg_type in wanted:
                    # Known and parseable segment
                    Parser = segment_parsers.get(seg_type)
                    seg = Parser.find_position(file, offset)
                    seg_opts = getattr(options, seg_type)
                    seg["type"] = seg_type
                    self.app_segments.append(seg)

                    if not find_all:
                        if Parser.multi_segment and seg_opts.multiSegment:
                            # Multi-segment handling
                            self.unfinished_multi_segment = seg.get(
                                "chunkNumber", 0
                            ) < seg.get("chunkCount", 1)
                            if not self.unfinished_multi_segment:
                                remaining.discard(seg_type)
                        else:
                            remaining.discard(seg_type)

                        if len(remaining) == 0:
                            break

                elif (
                    hasattr(options, "recordUnknownSegments")
                    and options.recordUnknownSegments
                ):
                    # Unknown segment
                    seg = AppSegmentParserBase.find_position(file, offset)
                    seg["marker"] = marker2
                    self.unknown_segments.append(seg)

                offset += length + 1

            elif is_jpg_marker(marker2):
                # JPEG structure segment
                length = file.get_uint16(offset + 2)

                # Stop after SOS (Start of Scan)
                if marker2 == MARKER_2_SOS and getattr(options, "stopAfterSos", True):
                    return None

                if (
                    hasattr(options, "recordJpegSegments")
                    and options.recordJpegSegments
                ):
                    self.jpeg_segments.append(
                        {"offset": offset, "length": length, "marker": marker2}
                    )

                offset += length + 1
            else:
                offset += 1

        return offset

    def merge_multi_segments(self):
        """Merge multi-segment data"""
        has_multi = any(seg.get("multiSegment", False) for seg in self.app_segments)
        if not has_multi:
            return

        # Group by type
        grouped = {}
        for seg in self.app_segments:
            seg_type = seg["type"]
            if seg_type not in grouped:
                grouped[seg_type] = []
            grouped[seg_type].append(seg)

        self.merged_app_segments = []
        for seg_type, type_segments in grouped.items():
            Parser = segment_parsers.get(seg_type, self.options)
            if hasattr(Parser, "handle_multi_segments"):
                chunk = Parser.handle_multi_segments(type_segments)
                self.merged_app_segments.append({"type": seg_type, "chunk": chunk})
            else:
                self.merged_app_segments.append(type_segments[0])

    def get_segment(self, seg_type):
        """Get segment by type"""
        for seg in self.app_segments:
            if seg.get("type") == seg_type:
                return seg
        return None

    async def get_or_find_segment(self, seg_type):
        """Get segment or find it if not already found"""
        seg = self.get_segment(seg_type)
        if seg is None:
            await self.find_app_segments(0, [seg_type])
            seg = self.get_segment(seg_type)
        return seg


# Register parser
file_parsers.register("jpeg", JpegFileParser)
