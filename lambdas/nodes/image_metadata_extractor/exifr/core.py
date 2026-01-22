"""
Core Exifr class and parse function
Ported from Exifr.mjs and core.mjs
"""

from .options import Options
from .plugins import file_parsers, segment_parsers
from .reader import read
from .util.helpers import throw_error, undefined_if_empty


class Exifr:
    """
    Main EXIF reader class
    """

    def __init__(self, options=None):
        """
        Initialize Exifr

        Args:
            options: Options dict, list, bool, or None
        """
        self.options = Options.use_cached(options)
        self.parsers = {}
        self.output = {}
        self.errors = []
        self.file = None
        self.file_parser = None

    def push_to_errors(self, err):
        """Add error to error list"""
        self.errors.append(err)

    async def read(self, arg):
        """
        Read file input

        Args:
            arg: File path, URL, bytes, or file-like object
        """
        self.file = await read(arg, self.options)

    def setup(self):
        """
        Setup file parser based on file type
        """
        if self.file_parser:
            return

        # Detect file type from header
        file = self.file
        marker = file.get_uint16(0)

        for file_type, FileParser in file_parsers:
            if FileParser.can_handle(file, marker):
                self.file_parser = FileParser(self.options, self.file, self.parsers)
                setattr(file, file_type, True)
                return

        # Close file if setup fails
        if hasattr(self.file, "close"):
            self.file.close()
        throw_error("Unknown file format")

    async def parse(self):
        """
        Parse EXIF data from file

        Returns:
            dict: Parsed EXIF data or None
        """
        output = self.output
        errors = self.errors

        self.setup()

        # Execute parsers with error handling
        if self.options.silentErrors:
            try:
                await self.execute_parsers()
            except Exception as e:
                self.push_to_errors(e)
            errors.extend(self.file_parser.errors)
        else:
            await self.execute_parsers()

        # Close file
        if hasattr(self.file, "close"):
            self.file.close()

        # Add errors to output if any
        if self.options.silentErrors and len(errors) > 0:
            output["errors"] = errors

        return undefined_if_empty(output)

    async def execute_parsers(self):
        """Execute all segment parsers"""
        output = self.output

        # Parse file structure first
        await self.file_parser.parse()

        # Parse all segments
        promises = []
        for parser in self.parsers.values():
            promises.append(self._parse_segment(parser, output))

        # Handle errors if silent mode
        if self.options.silentErrors:
            results = []
            for promise in promises:
                try:
                    result = await promise
                    results.append(result)
                except Exception as e:
                    self.push_to_errors(e)
                    results.append(None)
        else:
            # Execute all parsers
            for promise in promises:
                await promise

    async def _parse_segment(self, parser, output):
        """Parse a single segment"""
        import inspect

        # Check if parse() is async
        parse_result = parser.parse()
        if inspect.iscoroutine(parse_result):
            parser_output = await parse_result
        else:
            parser_output = parse_result

        # Each parser may merge its output differently
        parser.assign_to_output(output, parser_output)

    async def extract_thumbnail(self):
        """
        Extract embedded thumbnail

        Returns:
            bytes: Thumbnail data or None
        """
        self.setup()

        options = self.options
        file = self.file

        TiffParser = segment_parsers.get("tiff", options)
        seg = None

        if getattr(file, "tiff", False):
            seg = {"start": 0, "type": "tiff"}
        elif getattr(file, "jpeg", False):
            seg = await self.file_parser.get_or_find_segment("tiff")

        if seg is None:
            return None

        chunk = await self.file_parser.ensure_segment_chunk(seg)
        parser = TiffParser(chunk, options, file)
        self.parsers["tiff"] = parser
        thumb = await parser.extract_thumbnail()

        # Close file
        if hasattr(file, "close"):
            file.close()

        return thumb


async def parse(input_arg, options=None):
    """
    Parse EXIF data from file

    Args:
        input_arg: File path, URL, bytes, or file-like object
        options: Options dict, list, bool, or None

    Returns:
        dict: Parsed EXIF data or None
    """
    exr = Exifr(options)
    await exr.read(input_arg)
    return await exr.parse()
