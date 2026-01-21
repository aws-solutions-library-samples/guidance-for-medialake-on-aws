"""
Parser base classes
Ported from parser.mjs
"""

from .options import Options
from .plugins import segment_parsers
from .tags import tag_keys, tag_revivers, tag_values
from .util.buffer_view import BufferView
from .util.helpers import throw_error

MAX_APP_SIZE = 65536  # 64kb
DEFAULT = "DEFAULT"


class FileParserBase:
    """
    Base class for file format parsers (JPEG, TIFF, PNG, HEIC)
    """

    def __init__(self, options, file, parsers):
        if hasattr(self, "extend_options"):
            self.extend_options(options)
        self.options = options
        self.file = file
        self.parsers = parsers
        self.errors = []

    def inject_segment(self, segment_type, chunk):
        """Inject a segment into parsers"""
        if self.options[segment_type].enabled:
            self.create_parser(segment_type, chunk)

    def create_parser(self, segment_type, chunk):
        """Create a segment parser"""
        Parser = segment_parsers.get(segment_type)
        parser = Parser(chunk, self.options, self.file)
        self.parsers[segment_type] = parser
        return parser

    def create_parsers(self, segments):
        """Create parsers for multiple segments"""
        for segment in segments:
            segment_type = segment["type"]
            chunk = segment.get("chunk")
            seg_opts = self.options[segment_type]

            if seg_opts and seg_opts.enabled:
                parser = self.parsers.get(segment_type)
                if parser and hasattr(parser, "append"):
                    # TODO: Multi-segment support
                    pass
                elif not parser:
                    self.create_parser(segment_type, chunk)

    async def read_segments(self, segments):
        """Read all segment chunks"""
        promises = [self.ensure_segment_chunk(seg) for seg in segments]
        # Execute all chunk reads
        for promise in promises:
            await promise

    async def ensure_segment_chunk(self, seg):
        """Ensure segment chunk is available"""
        start = seg.get("start", 0)
        size = seg.get("size", MAX_APP_SIZE)

        if self.file.chunked:
            if self.file.available(start, size):
                seg["chunk"] = self.file.subarray(start, size)
            else:
                try:
                    seg["chunk"] = await self.file.read_chunk(start, size)
                except Exception as err:
                    throw_error(f"Couldn't read segment: {seg}. {err}")
        elif self.file.byte_length > start + size:
            seg["chunk"] = self.file.subarray(start, size)
        elif seg.get("size") is None:
            # Unknown length and file is smaller than fallback
            seg["chunk"] = self.file.subarray(start)
        else:
            throw_error(f"Segment unreachable: {seg}")

        return seg.get("chunk")


class AppSegmentParserBase:
    """
    Base class for APP segment parsers (TIFF/EXIF, XMP, ICC, IPTC, etc.)
    """

    header_length = 4
    type = None
    multi_segment = False

    @classmethod
    def can_handle(cls, buffer, offset, length):
        """Check if this parser can handle the segment"""
        return False

    @classmethod
    def find_position(cls, buffer, offset):
        """
        Find position and size of segment

        Returns:
            dict with offset, length, headerLength, start, size, end
        """
        # Length at offset+2 includes content + 2 length bytes (not the 0xFF 0xEn marker)
        length = buffer.get_uint16(offset + 2) + 2

        if callable(cls.header_length):
            header_length = cls.header_length(buffer, offset, length)
        else:
            header_length = cls.header_length

        start = offset + header_length
        size = length - header_length
        end = start + size

        return {
            "offset": offset,
            "length": length,
            "headerLength": header_length,
            "start": start,
            "size": size,
            "end": end,
        }

    @classmethod
    async def parse(cls, input_data, seg_options=None):
        """Parse segment directly"""
        if seg_options is None:
            seg_options = {}
        options = Options({cls.type: seg_options})
        instance = cls(input_data, options, input_data)
        return await instance.parse()

    def normalize_input(self, input_data):
        """Normalize input to BufferView"""
        if isinstance(input_data, BufferView):
            return input_data
        else:
            return BufferView(input_data)

    def __init__(self, chunk, options=None, file=None):
        """
        Initialize segment parser

        Args:
            chunk: BufferView of segment data
            options: Options instance
            file: BufferView of whole file
        """
        self.chunk = self.normalize_input(chunk)
        self.file = file
        self.type = self.__class__.type
        self.global_options = self.options = options or Options()
        self.local_options = (
            options[self.type] if options and self.type in dir(options) else None
        )
        self.can_translate = (
            self.local_options and self.local_options.translate
            if self.local_options
            else False
        )
        self.errors = []
        self.raw = {}

    def translate(self):
        """Translate raw tags to readable format"""
        if self.can_translate:
            self.translated = self.translate_block(self.raw, self.type)

    @property
    def output(self):
        """Get parser output"""
        if hasattr(self, "translated"):
            return self.translated
        elif self.raw:
            return dict(self.raw)
        return {}

    def translate_block(self, raw_tags, block_key):
        """
        Translate a block of raw tags

        Args:
            raw_tags: Dict of raw tag data
            block_key: Block identifier (ifd0, exif, gps, etc.)

        Returns:
            dict: Translated tags
        """
        revivers = tag_revivers.get(block_key, {})
        val_dict = tag_values.get(block_key, {})
        key_dict = tag_keys.get(block_key, {})
        block_options = getattr(self.options, block_key, None)

        can_revive = block_options and block_options.reviveValues and revivers
        can_translate_val = block_options and block_options.translateValues and val_dict
        can_translate_key = block_options and block_options.translateKeys and key_dict

        output = {}
        items = raw_tags.items() if isinstance(raw_tags, dict) else raw_tags

        for key, val in items:
            # Revive values (e.g., dates)
            if can_revive and key in revivers:
                val = revivers[key](val)
            # Translate values (enums to strings)
            elif can_translate_val and key in val_dict:
                val = self.translate_value(val, val_dict[key])

            # Translate keys (numeric to string)
            if can_translate_key and key in key_dict:
                key = key_dict[key] or key

            output[key] = val

        return output

    def translate_value(self, val, tag_enum):
        """Translate a value using tag enum"""
        if isinstance(tag_enum, dict):
            return tag_enum.get(val, tag_enum.get(DEFAULT, val))
        return val

    def handle_error(self, error):
        """Handle parsing error"""
        if self.options.silentErrors:
            error_msg = str(error) if isinstance(error, Exception) else error
            self.errors.append(error_msg)
        else:
            raise error

    def assign_to_output(self, root, parser_output):
        """Assign parser output to root output dict"""
        self.assign_object_to_output(root, self.__class__.type, parser_output)

    def assign_object_to_output(self, root, key, parser_output):
        """Assign object to output with merge support"""
        if self.global_options.mergeOutput:
            root.update(parser_output)
        else:
            if key in root:
                root[key].update(parser_output)
            else:
                root[key] = parser_output
