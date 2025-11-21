"""
File Extension Constants for MediaLake

This module provides centralized file extension definitions for all asset types.
It serves as the single source of truth for file extension whitelisting across
the MediaLake application.

This file is deployed as part of the common_libraries Lambda layer and is
accessible to all Lambda functions.
"""

# Supported file extensions by asset type
# This is the authoritative list - changes here propagate to all lambdas
# Only includes formats verified through production testing (118/157 files successfully processed)
SUPPORTED_EXTENSIONS = {
    "Image": [
        # Standard formats (verified working)
        "apng",  # Animated PNG - verified
        "avif",  # AV1 Image File Format - verified
        "bmp",  # Bitmap - verified
        "gif",  # Graphics Interchange Format - verified
        "ico",  # Icon - verified
        "j2k",  # JPEG 2000 codestream - verified
        "jp2",  # JPEG 2000 - verified
        "jpeg",  # JPEG - verified
        "jpg",  # JPEG - verified
        "pbm",  # Portable Bitmap - verified
        "pcx",  # PC Paintbrush - verified
        "pgm",  # Portable Graymap - verified
        "png",  # Portable Network Graphics - verified
        "ppm",  # Portable Pixmap - verified
        "psd",  # Adobe Photoshop - verified
        "svg",  # Scalable Vector Graphics - verified
        "tif",  # Tagged Image File Format - verified
        "tiff",  # Tagged Image File Format - verified
        "webp",  # WebP - verified
        "wmf",  # Windows Metafile - verified
        "xbm",  # X11 Bitmap - verified
        "xpm",  # X11 Pixmap - verified
        # RAW formats (verified working)
        "cr2",  # Canon RAW 2 - verified (57/58 files, 1 CHDK-modified file failed)
        "erf",  # Epson RAW - verified
        "nef",  # Nikon Electronic Format (RAW) - verified (48 files)
    ],
    "Video": [
        "flv",  # Flash Video
        "mp4",  # MPEG-4
        "mov",  # QuickTime
        "avi",  # Audio Video Interleave
        "mkv",  # Matroska
        "webm",  # WebM
        "mxf",  # Material Exchange Format
    ],
    "Audio": [
        "wav",  # Waveform Audio
        "aiff",  # Audio Interchange File Format
        "aif",  # Audio Interchange File Format (alternative extension)
        "mp3",  # MPEG Audio Layer III
        "pcm",  # Pulse-Code Modulation
        "m4a",  # MPEG-4 Audio
    ],
}


def get_all_supported_extensions():
    """
    Get flat list of all supported extensions across all asset types.

    Returns:
        List of all supported file extensions (lowercase, without dots)
    """
    return [ext for exts in SUPPORTED_EXTENSIONS.values() for ext in exts]


def get_extensions_by_type(asset_type):
    """
    Get extensions for a specific asset type.

    Args:
        asset_type: One of "Image", "Video", or "Audio"

    Returns:
        List of file extensions for the specified type, or empty list if type not found
    """
    return SUPPORTED_EXTENSIONS.get(asset_type, [])


def is_extension_supported(extension):
    """
    Check if a file extension is supported by MediaLake.

    Args:
        extension: File extension (with or without leading dot)

    Returns:
        True if extension is supported, False otherwise

    Example:
        >>> is_extension_supported('.jpg')
        True
        >>> is_extension_supported('mp4')
        True
        >>> is_extension_supported('xyz')
        False
    """
    ext = extension.lower().lstrip(".")
    return ext in get_all_supported_extensions()


def get_asset_type_for_extension(extension):
    """
    Determine the asset type for a given file extension.

    Args:
        extension: File extension (with or without leading dot)

    Returns:
        Asset type ("Image", "Video", or "Audio") or None if not supported

    Example:
        >>> get_asset_type_for_extension('.jpg')
        'Image'
        >>> get_asset_type_for_extension('mp4')
        'Video'
        >>> get_asset_type_for_extension('unknown')
        None
    """
    ext = extension.lower().lstrip(".")
    for asset_type, extensions in SUPPORTED_EXTENSIONS.items():
        if ext in extensions:
            return asset_type
    return None


def get_extensions_as_uppercase_string(asset_type, separator=", "):
    """
    Get extensions for an asset type as an uppercase comma-separated string.
    Useful for pipeline Format fields and UI display.

    Args:
        asset_type: One of "Image", "Video", or "Audio"
        separator: String to use between extensions (default: ", ")

    Returns:
        Uppercase comma-separated string of extensions

    Example:
        >>> get_extensions_as_uppercase_string("Image")
        'APNG, AVIF, BMP, GIF, ICO, J2K, JP2, JPEG, JPG, PBM, PCX, PGM, PNG, PPM, PSD, SVG, TIF, TIFF, WEBP, WMF, XBM, XPM, CR2, ERF, NEF'
    """
    extensions = get_extensions_by_type(asset_type)
    return separator.join(ext.upper() for ext in extensions)
