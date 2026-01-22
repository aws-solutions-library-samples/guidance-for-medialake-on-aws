"""
TIFF file parser - handles .tif/.tiff files directly

Unlike JPEG files which have APP segments, TIFF files start with the TIFF
structure directly. XMP, IPTC, and ICC data are stored as tags within the
TIFF structure (IFD0 block).
"""

from ..parser import FileParserBase
from ..plugins import file_parsers
from ..tags import TAG_ICC, TAG_IPTC, TAG_XMP
from ..util.helpers import TIFF_BIG_ENDIAN, TIFF_LITTLE_ENDIAN, estimate_metadata_size


class TiffFileParser(FileParserBase):
    """Parser for TIFF files (.tif, .tiff)"""

    type = "tiff"

    @staticmethod
    def can_handle(file_reader, first_two_bytes):
        """
        Check if file is a TIFF by examining the first two bytes

        Args:
            file_reader: File reader instance
            first_two_bytes: First two bytes of the file

        Returns:
            bool: True if this is a TIFF file
        """
        return (
            first_two_bytes == TIFF_LITTLE_ENDIAN or first_two_bytes == TIFF_BIG_ENDIAN
        )

    def extend_options(self, options):
        """
        Extend options to add dependencies for embedded segments

        TIFF files can contain XMP, IPTC, and ICC data as tags within
        the TIFF structure. We need to tell IFD0 to look for these tags.

        Args:
            options: Options instance
        """
        # Note: skipping is done on global level in Options class
        ifd0 = options.ifd0
        xmp = options.xmp
        iptc = options.iptc
        icc = options.icc

        if xmp.enabled:
            ifd0.deps.add(TAG_XMP)
        if iptc.enabled:
            ifd0.deps.add(TAG_IPTC)
        if icc.enabled:
            ifd0.deps.add(TAG_ICC)

        ifd0.finalize_filters()

    async def parse(self):
        """
        Parse TIFF file structure

        Steps:
        1. Ensure we have enough data loaded (TIFF can have pointers anywhere)
        2. Parse TIFF header and IFD0 block
        3. Extract XMP, IPTC, ICC data if present (stored as TIFF tags)
        """
        tiff_opt = self.options.tiff
        xmp_opt = self.options.xmp
        iptc_opt = self.options.iptc
        icc_opt = self.options.icc

        if tiff_opt.enabled or xmp_opt.enabled or iptc_opt.enabled or icc_opt.enabled:
            # TODO: refactor this in the future
            # TIFF files start with TIFF structure (instead of JPEG's FF D8) but
            # offsets can point to any place in the file, even within single block.
            # Crude option is to just read as big chunk as possible.
            # TODO: in the future, block reading will be recursive or looped until
            # all pointers are resolved.
            # SIDE NOTE: .tif files store XMP as ApplicationNotes tag in TIFF
            # structure as well.
            length = max(estimate_metadata_size(self.options), self.options.chunkSize)
            await self.file.ensure_chunk(0, length)

            # Create TIFF parser and parse the structure
            self.create_parser("tiff", self.file)
            self.parsers["tiff"].parse_header()
            await self.parsers["tiff"].parse_ifd0_block()

            # Extract embedded segments from TIFF tags
            self._adapt_tiff_prop_as_segment("xmp")
            self._adapt_tiff_prop_as_segment("iptc")
            self._adapt_tiff_prop_as_segment("icc")

    def _adapt_tiff_prop_as_segment(self, segment_type):
        """
        Extract a TIFF tag and inject it as a segment for other parsers

        TIFF stores XMP, IPTC, ICC as tags in IFD0. We extract these tags
        and inject them as segments so the XMP/IPTC/ICC parsers can process them.

        Args:
            segment_type: Type of segment ('xmp', 'iptc', 'icc')
        """
        tiff_parser = self.parsers.get("tiff")
        if tiff_parser and hasattr(tiff_parser, segment_type):
            # TIFF stores all other segments as tags in IFD0 object. Get the tag.
            raw_data = getattr(tiff_parser, segment_type)
            if raw_data:
                self.inject_segment(segment_type, raw_data)


# Register the TIFF file parser
file_parsers["tiff"] = TiffFileParser
