"""
HEIF/HEIC file parser - Apple HEIC and AVIF image formats

HEIF (High Efficiency Image File Format) is based on ISO Base Media File Format
(ISO BMFF) and uses nested box structures similar to MP4/MOV.

Supported formats:
- HEIC - Apple's HEIF variant (iPhone photos)
- AVIF - AV1 Image File Format

Reference: https://nokiatech.github.io/heif/technical.html
"""

from ..parser import FileParserBase
from ..plugins import file_parsers

# Box header: 4 bytes length + 4 bytes kind + optional 8 bytes for 64-bit length
BOX_HEADER_LENGTH = 16


class IsoBmffParser(FileParserBase):
    """
    Base parser for ISO Base Media File Format (ISO BMFF)

    ISO BMFF uses a hierarchical box (atom) structure where each box has:
    - 4 byte length
    - 4 byte type/kind (e.g., 'ftyp', 'meta', 'moov')
    - Optional 8 byte extended length (if length == 1)
    - Data payload
    """

    def parse_boxes(self, offset=0):
        """
        Parse all boxes starting from offset

        Args:
            offset: Starting offset

        Returns:
            list: List of box dicts
        """
        boxes = []
        while offset < self.file.byte_length - 4:
            box = self.parse_box_head(offset)
            boxes.append(box)
            if box["length"] == 0:
                break
            offset += box["length"]
        return boxes

    def parse_sub_boxes(self, box):
        """Parse boxes contained within a box"""
        box["boxes"] = self.parse_boxes(box["start"])

    def find_box(self, box, kind):
        """
        Find a sub-box by kind/type

        Args:
            box: Parent box dict
            kind: Box type to find (e.g., 'meta', 'iinf')

        Returns:
            dict or None: Found box or None
        """
        if "boxes" not in box:
            self.parse_sub_boxes(box)
        return next((b for b in box["boxes"] if b["kind"] == kind), None)

    def parse_box_head(self, offset):
        """
        Parse box header

        Format:
        - 4 bytes: length (if 1, then 64-bit length follows)
        - 4 bytes: type/kind (4-char string)
        - 8 bytes: extended length (optional, if length == 1)

        Args:
            offset: Offset of box header

        Returns:
            dict: Box information
        """
        length = self.file.get_uint32(offset)
        kind = self.file.get_string(offset + 4, 4)
        start = offset + 8  # After 4+4 bytes

        # Length can be larger than 32-bit, stored as 64-bit after header
        if length == 1:
            length = self.file.get_uint64(offset + 8)
            start += 8

        return {"offset": offset, "length": length, "kind": kind, "start": start}

    def parse_box_full_head(self, box):
        """
        Parse full box header (version + flags)

        Some ISO boxes have a 'full' variant with additional metadata:
        - 1 byte: version
        - 3 bytes: flags

        Args:
            box: Box dict to update
        """
        if "version" in box:
            return

        vflags = self.file.get_uint32(box["start"])
        box["version"] = vflags >> 24
        box["start"] += 4


class HeifFileParser(IsoBmffParser):
    """Parser for HEIF-based formats (HEIC, AVIF)"""

    @classmethod
    def can_handle(cls, file, first_two_bytes):
        """
        Check if file is HEIF/HEIC/AVIF

        HEIF files start with an 'ftyp' box. The first 4 bytes are the box length,
        which is typically small (< 50 bytes), so first two bytes should be 0.

        Args:
            file: File reader instance
            first_two_bytes: First two bytes

        Returns:
            bool: True if this is a HEIF file of the parser's type
        """
        # First two bytes should be 0 for small ftyp box
        if first_two_bytes != 0:
            return False

        ftyp_length = file.get_uint16(2)
        if ftyp_length > 50:
            return False

        # Check compatible brands in ftyp box
        offset = 16
        compatible_brands = []
        while offset < ftyp_length:
            compatible_brands.append(file.get_string(offset, 4))
            offset += 4

        # Check if this parser's type is in compatible brands
        return hasattr(cls, "type") and cls.type in compatible_brands

    async def parse(self):
        """
        Parse HEIF file structure

        Steps:
        1. Find 'meta' box (contains all metadata)
        2. Parse ICC profile from iprp/ipco/colr boxes (if enabled)
        3. Parse EXIF from iinf/iloc boxes (if enabled)
        """
        # Find meta box
        next_box_offset = self.file.get_uint32(0)
        meta = self.parse_box_head(next_box_offset)

        while meta["kind"] != "meta":
            next_box_offset += meta["length"]
            await self.file.ensure_chunk(next_box_offset, BOX_HEADER_LENGTH)
            meta = self.parse_box_head(next_box_offset)

        # Load meta box
        await self.file.ensure_chunk(meta["offset"], meta["length"])
        self.parse_box_full_head(meta)
        self.parse_sub_boxes(meta)

        # Extract metadata
        if self.options.icc.enabled:
            await self.find_icc(meta)
        if self.options.tiff.enabled:
            await self.find_exif(meta)

    async def register_segment(self, key, offset, length):
        """
        Register a metadata segment for parsing

        Args:
            key: Segment type ('icc', 'tiff', etc.)
            offset: Offset of segment data
            length: Length of segment data
        """
        await self.file.ensure_chunk(offset, length)
        chunk = self.file.subarray(offset, length)
        self.create_parser(key, chunk)

    async def find_icc(self, meta):
        """
        Find and extract ICC color profile

        ICC is stored in: meta -> iprp -> ipco -> colr

        Args:
            meta: Meta box dict
        """
        iprp = self.find_box(meta, "iprp")
        if iprp is None:
            return

        ipco = self.find_box(iprp, "ipco")
        if ipco is None:
            return

        colr = self.find_box(ipco, "colr")
        if colr is None:
            return

        await self.register_segment("icc", colr["offset"] + 12, colr["length"])

    async def find_exif(self, meta):
        """
        Find and extract EXIF data

        EXIF is referenced in iinf (item info) and located via iloc (item location)

        Args:
            meta: Meta box dict
        """
        iinf = self.find_box(meta, "iinf")
        if iinf is None:
            return

        iloc = self.find_box(meta, "iloc")
        if iloc is None:
            return

        # Find EXIF item ID in iinf
        exif_loc_id = self.find_exif_loc_id_in_iinf(iinf)
        if exif_loc_id is None:
            return

        # Find EXIF extent (offset/length) in iloc
        extent = self.find_extent_in_iloc(iloc, exif_loc_id)
        if extent is None:
            return

        exif_offset, exif_length = extent
        await self.file.ensure_chunk(exif_offset, exif_length)

        # EXIF extent has 4-byte name size prefix
        name_size = self.file.get_uint32(exif_offset)
        extent_content_shift = 4 + name_size
        exif_offset += extent_content_shift
        exif_length -= extent_content_shift

        await self.register_segment("tiff", exif_offset, exif_length)

    def find_exif_loc_id_in_iinf(self, box):
        """
        Find EXIF item ID in iinf (item info) box

        Args:
            box: iinf box dict

        Returns:
            int or None: EXIF item ID
        """
        self.parse_box_full_head(box)
        offset = box["start"]
        count = self.file.get_uint16(offset)
        offset += 2

        while count > 0:
            infe = self.parse_box_head(offset)
            self.parse_box_full_head(infe)
            infe_offset = infe["start"]

            if infe["version"] >= 2:
                id_size = 4 if infe["version"] == 3 else 2
                name = self.file.get_string(infe_offset + id_size + 2, 4)
                if name == "Exif":
                    return self.file.get_uint_bytes(infe_offset, id_size)

            offset += infe["length"]
            count -= 1

        return None

    def get_8bits(self, offset):
        """
        Split byte into two 4-bit values

        Args:
            offset: Offset of byte

        Returns:
            tuple: (high 4 bits, low 4 bits)
        """
        n = self.file.get_uint8(offset)
        n0 = n >> 4
        n1 = n & 0x0F
        return (n0, n1)

    def find_extent_in_iloc(self, box, wanted_loc_id):
        """
        Find extent (offset/length) for item ID in iloc box

        iloc contains location information for items referenced in the file

        Args:
            box: iloc box dict
            wanted_loc_id: Item ID to find

        Returns:
            tuple or None: (offset, length) or None
        """
        self.parse_box_full_head(box)
        offset = box["start"]

        offset_size, length_size = self.get_8bits(offset)
        offset += 1
        base_offset_size, index_size = self.get_8bits(offset)
        offset += 1

        item_id_size = 4 if box["version"] == 2 else 2
        const_method_size = 2 if box["version"] in (1, 2) else 0
        extent_size = index_size + offset_size + length_size
        item_count_size = 4 if box["version"] == 2 else 2
        item_count = self.file.get_uint_bytes(offset, item_count_size)
        offset += item_count_size

        while item_count > 0:
            item_id = self.file.get_uint_bytes(offset, item_id_size)
            offset += item_id_size + const_method_size + 2 + base_offset_size
            extent_count = self.file.get_uint16(offset)
            offset += 2

            if item_id == wanted_loc_id:
                if extent_count > 1:
                    print(
                        "Warning: ILOC box has more than one extent but only processing one"
                    )

                return (
                    self.file.get_uint_bytes(offset + index_size, offset_size),
                    self.file.get_uint_bytes(
                        offset + index_size + offset_size, length_size
                    ),
                )

            offset += extent_count * extent_size
            item_count -= 1

        return None


class HeicFileParser(HeifFileParser):
    """Parser for HEIC files (Apple HEIF variant)"""

    type = "heic"


class AvifFileParser(HeifFileParser):
    """Parser for AVIF files (AV1 Image File Format)"""

    type = "avif"


# Register HEIF-based file parsers
file_parsers["heic"] = HeicFileParser
file_parsers["avif"] = AvifFileParser
