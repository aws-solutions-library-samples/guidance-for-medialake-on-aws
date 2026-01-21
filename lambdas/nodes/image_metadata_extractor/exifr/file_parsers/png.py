"""
PNG file parser - handles .png files

PNG files store metadata in chunks:
- IHDR: Image header (dimensions, bit depth)
- tEXt: Simple text key-value pairs
- iTXt: International text (can contain XMP)
- eXIf: EXIF data in TIFF format
- iCCP: ICC color profile (zlib compressed)

Reference: http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html
"""

import zlib

from ..parser import FileParserBase
from ..plugins import file_parsers

# PNG file signature (magic bytes)
PNG_MAGIC_BYTES = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"

# XMP prefix in iTXt chunks
PNG_XMP_PREFIX = "XML:com.adobe.xmp"

# Chunk structure sizes
LENGTH_SIZE = 4
TYPE_SIZE = 4
CRC_SIZE = 4

# Chunk types we care about
IHDR = "ihdr"
ICCP = "iccp"
TEXT = "text"
ITXT = "itxt"
EXIF = "exif"
PNG_META_CHUNKS = [IHDR, ICCP, TEXT, ITXT, EXIF]


class PngFileParser(FileParserBase):
    """Parser for PNG files"""

    type = "png"

    @staticmethod
    def can_handle(file_reader, first_two_bytes):
        """
        Check if file is a PNG by examining magic bytes

        PNG signature is 8 bytes: 0x89504e47 0x0d0a1a0a

        Args:
            file_reader: File reader instance
            first_two_bytes: First two bytes (0x8950 for PNG)

        Returns:
            bool: True if this is a PNG file
        """
        return (
            first_two_bytes == 0x8950
            and file_reader.get_uint32(0) == 0x89504E47
            and file_reader.get_uint32(4) == 0x0D0A1A0A
        )

    def __init__(self, options, file_reader, exifr):
        """Initialize PNG parser with empty chunk lists"""
        super().__init__(options, file_reader, exifr)
        self.meta_chunks = []
        self.unknown_chunks = []

    async def parse(self):
        """
        Parse PNG file structure

        Steps:
        1. Find all PNG chunks in the file
        2. Read metadata chunks into memory
        3. Parse IHDR (image header)
        4. Parse tEXt chunks (simple key-value pairs)
        5. Find and parse EXIF data (if present)
        6. Find and parse XMP data (if present)
        7. Find and parse ICC profile (if present)
        """
        await self.find_png_chunks_in_range(len(PNG_MAGIC_BYTES), self.file.byte_length)
        await self.read_segments(self.meta_chunks)
        self.find_ihdr()
        self.parse_text_chunks()

        # Use try-except for each segment type to continue on errors
        try:
            await self.find_exif()
        except Exception as err:
            self.errors.append(err)

        try:
            await self.find_xmp()
        except Exception as err:
            self.errors.append(err)

        try:
            await self.find_icc()
        except Exception as err:
            self.errors.append(err)

    async def find_png_chunks_in_range(self, offset, end):
        """
        Scan for PNG chunks in the file

        PNG chunk format:
        - 4 bytes: length (size of data, not including length/type/crc)
        - 4 bytes: chunk type (e.g., "IHDR", "tEXt")
        - N bytes: chunk data
        - 4 bytes: CRC checksum

        Args:
            offset: Starting offset to scan from
            end: End offset to scan to
        """
        while offset < end:
            size = self.file.get_uint32(offset)  # data size without CRC
            marker = self.file.get_uint32(offset + LENGTH_SIZE)
            name = self.file.get_string(offset + LENGTH_SIZE, 4)
            chunk_type = name.lower()
            start = offset + LENGTH_SIZE + TYPE_SIZE
            length = size + LENGTH_SIZE + TYPE_SIZE + CRC_SIZE

            seg = {
                "type": chunk_type,
                "offset": offset,
                "length": length,
                "start": start,
                "size": size,
                "marker": marker,
            }

            if chunk_type in PNG_META_CHUNKS:
                self.meta_chunks.append(seg)
            else:
                self.unknown_chunks.append(seg)

            offset += length

    def parse_text_chunks(self):
        """
        Parse PNG tEXt chunks (simple key-value pairs)

        tEXt chunks contain simple metadata as "key\0value" format.
        We parse these and inject them into the IHDR parser's raw data.

        Examples:
        - "Author\0John Doe"
        - "Description\0Beautiful sunset photo"
        """
        text_chunks = [seg for seg in self.meta_chunks if seg["type"] == TEXT]
        for seg in text_chunks:
            text = self.file.get_string(seg["start"], seg["size"])
            if "\0" in text:
                key, val = text.split("\0", 1)
                self.inject_key_val_to_ihdr(key, val)

    def inject_key_val_to_ihdr(self, key, value):
        """
        Inject a key-value pair into IHDR parser's raw data

        Args:
            key: Metadata key
            value: Metadata value
        """
        parser = self.parsers.get("ihdr")
        if parser:
            parser.raw[key] = value

    def find_ihdr(self):
        """
        Find and parse IHDR (PNG image header) chunk

        IHDR contains basic image properties like dimensions, bit depth,
        color type, etc. We create a parser for it unless user disabled it.
        """
        seg = next((s for s in self.meta_chunks if s["type"] == IHDR), None)
        if not seg:
            return

        # ihdr option is undefined by default (because we don't want JPEGs
        # and HEIC files to pick it up) so here we create it for every PNG file.
        # But only if user didn't explicitly disable it.
        if self.options.ihdr.enabled is not False:
            self.create_parser(IHDR, seg["chunk"])

    async def find_exif(self):
        """
        Find and parse EXIF data in PNG

        PNG stores EXIF in an eXIf chunk containing TIFF-format data.
        We inject this as a 'tiff' segment for the TIFF parser to handle.
        """
        seg = next((s for s in self.meta_chunks if s["type"] == "exif"), None)
        if not seg:
            return

        self.inject_segment("tiff", seg["chunk"])

    async def find_xmp(self):
        """
        Find and parse XMP data in PNG

        PNG stores XMP in iTXt chunks with prefix "XML:com.adobe.xmp".
        iTXt chunks have a complex header with null-terminated fields.
        The XMP data appears after the third null terminator.

        Reference: http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html#C.iTXt
        """
        itxt_chunks = [seg for seg in self.meta_chunks if seg["type"] == ITXT]
        for seg in itxt_chunks:
            chunk = seg["chunk"]
            prefix = chunk.get_string(0, len(PNG_XMP_PREFIX))
            if prefix == PNG_XMP_PREFIX:
                self.inject_segment("xmp", chunk)

    async def find_icc(self):
        """
        Find and parse ICC color profile in PNG

        PNG stores ICC profiles in iCCP chunks with this format:
        - Profile name (1-79 bytes, Latin-1)
        - Null terminator (1 byte)
        - Compression method (1 byte, always 0 for zlib)
        - Compressed profile data (rest of chunk)

        The profile data is always zlib compressed per PNG spec.
        """
        seg = next((s for s in self.meta_chunks if s["type"] == ICCP), None)
        if not seg:
            return

        chunk = seg["chunk"]

        # ICC profile name is variable length (up to 80 bytes) followed by null
        chunk_head = chunk.get_uint8_array(0, 81)
        name_length = 0

        # Find length of profile name by looking for null terminator
        while name_length < 80 and chunk_head[name_length] != 0:
            name_length += 1

        # Calculate actual ICC data position
        # +1 for null terminator, +1 for compression method byte
        iccp_header_length = name_length + 2
        profile_name = chunk.get_string(0, name_length)

        # Inject profile name into IHDR
        self.inject_key_val_to_ihdr("ProfileName", profile_name)

        # Decompress ICC profile data (always zlib compressed per PNG spec)
        compressed_data = chunk.get_uint8_array(iccp_header_length)
        try:
            # Python's zlib works everywhere (not Node.js specific)
            decompressed_data = zlib.decompress(bytes(compressed_data))
            self.inject_segment("icc", decompressed_data)
        except zlib.error as e:
            raise ValueError(f"Failed to decompress ICC profile: {e}")


# Register the PNG file parser
file_parsers["png"] = PngFileParser
