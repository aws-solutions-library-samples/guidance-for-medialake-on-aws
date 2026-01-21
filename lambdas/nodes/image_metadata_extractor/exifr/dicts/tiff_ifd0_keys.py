"""
IFD0 tag name dictionary
Ported from src/dicts/tiff-ifd0-keys.mjs

IFD0 contains basic image information like Make, Model, Orientation, etc.
IFD1 contains thumbnail information and uses the same tags.
"""

from ..tags import create_dictionary, tag_keys


def load_ifd0_keys():
    """Load IFD0 and IFD1 tag names into global registry"""
    create_dictionary(
        tag_keys,
        ["ifd0", "ifd1"],
        [
            # Core image metadata
            (0x0100, "ImageWidth"),
            (0x0101, "ImageHeight"),
            (0x0102, "BitsPerSample"),
            (0x0103, "Compression"),
            (0x0106, "PhotometricInterpretation"),
            (0x010E, "ImageDescription"),
            (0x010F, "Make"),
            (0x0110, "Model"),
            (0x0111, "StripOffsets"),  # PreviewImageStart
            (0x0112, "Orientation"),
            (0x0115, "SamplesPerPixel"),
            (0x0116, "RowsPerStrip"),
            (0x0117, "StripByteCounts"),  # PreviewImageLength
            (0x011A, "XResolution"),
            (0x011B, "YResolution"),
            (0x011C, "PlanarConfiguration"),
            (0x0128, "ResolutionUnit"),
            (0x012D, "TransferFunction"),
            (0x0131, "Software"),
            (0x0132, "ModifyDate"),
            (0x013B, "Artist"),
            (0x013C, "HostComputer"),
            (0x013D, "Predictor"),
            (0x013E, "WhitePoint"),
            (0x013F, "PrimaryChromaticities"),
            (0x0201, "ThumbnailOffset"),
            (0x0202, "ThumbnailLength"),
            (0x0211, "YCbCrCoefficients"),
            (0x0212, "YCbCrSubSampling"),
            (0x0213, "YCbCrPositioning"),
            (0x0214, "ReferenceBlackWhite"),
            (0x02BC, "ApplicationNotes"),  # Adobe XMP technote 9-14-02
            (0x8298, "Copyright"),
            # Pointers to other IFDs (not core, but useful)
            (0x83BB, "IPTC"),
            (0x8769, "ExifIFD"),
            (0x8773, "ICC"),
            (0x8825, "GpsIFD"),
            (0x014A, "SubIFD"),  # Adobe TIFF technote 1
            (0xA005, "InteropIFD"),  # Often found in IFD0
            # Windows XP tags (descriptions)
            (0x9C9B, "XPTitle"),
            (0x9C9C, "XPComment"),
            (0x9C9D, "XPAuthor"),
            (0x9C9E, "XPKeywords"),
            (0x9C9F, "XPSubject"),
        ],
    )
