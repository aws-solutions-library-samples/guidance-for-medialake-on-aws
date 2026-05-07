"""
OpenEXR metadata extraction.

This module provides functions for extracting metadata from OpenEXR files.
OpenEXR is a high dynamic range (HDR) image format developed by Industrial Light & Magic.
"""

import os
import tempfile
from typing import Any, Dict

from aws_lambda_powertools import Logger

# Initialize logger
logger = Logger(child=True)

# Try to import OpenEXR - no logging at module level to avoid Lambda crashes
OPENEXR_AVAILABLE = False
IMPORT_ERROR = None

try:
    import Imath
    import OpenEXR

    OPENEXR_AVAILABLE = True

    # Pre-compute compression type mappings at module level for performance
    COMPRESSION_NAMES = {
        int(Imath.Compression.NO_COMPRESSION): "None",
        int(Imath.Compression.RLE_COMPRESSION): "RLE",
        int(Imath.Compression.ZIPS_COMPRESSION): "ZIPS",
        int(Imath.Compression.ZIP_COMPRESSION): "ZIP",
        int(Imath.Compression.PIZ_COMPRESSION): "PIZ",
        int(Imath.Compression.PXR24_COMPRESSION): "PXR24",
        int(Imath.Compression.B44_COMPRESSION): "B44",
        int(Imath.Compression.B44A_COMPRESSION): "B44A",
    }
except ImportError as e:
    IMPORT_ERROR = str(e)
    COMPRESSION_NAMES = {}


def _extract_window_metadata(window) -> Dict[str, int]:
    """
    Extract window metadata (dataWindow or displayWindow).

    Args:
        window: OpenEXR window object with min/max coordinates

    Returns:
        dict: Window dimensions and coordinates
    """
    return {
        "width": window.max.x - window.min.x + 1,
        "height": window.max.y - window.min.y + 1,
        "xMin": window.min.x,
        "yMin": window.min.y,
        "xMax": window.max.x,
        "yMax": window.max.y,
    }


async def extract_exr_metadata_safe(buffer: bytes) -> Dict[str, Any]:
    """
    Extract metadata from OpenEXR file using the new recommended API.

    Uses OpenEXR.File (v3.3+) instead of deprecated InputFile.

    Args:
        buffer: EXR file bytes

    Returns:
        dict: EXR metadata
    """
    print(f"DEBUG EXR: extract_exr_metadata_safe called, buffer size: {len(buffer)}")
    print(f"DEBUG EXR: OPENEXR_AVAILABLE: {OPENEXR_AVAILABLE}")

    if not OPENEXR_AVAILABLE:
        return {"error": f"OpenEXR library not available: {IMPORT_ERROR}"}

    tmp_path = None
    try:
        # Write to temp file
        print(f"DEBUG EXR: Creating temp file...")
        with tempfile.NamedTemporaryFile(suffix=".exr", delete=False) as tmp_file:
            tmp_file.write(buffer)
            tmp_path = tmp_file.name
        print(f"DEBUG EXR: Temp file created: {tmp_path}")

        # Use new API: OpenEXR.File (recommended, not deprecated InputFile)
        print(f"DEBUG EXR: Opening EXR file with OpenEXR.File...")
        with OpenEXR.File(tmp_path) as exr_file:
            print(f"DEBUG EXR: EXR file opened")

            # Get header - returns a dict with direct values
            print(f"DEBUG EXR: Getting header...")
            header = exr_file.header()
            print(f"DEBUG EXR: Header retrieved, keys: {list(header.keys())[:10]}")

            # Extract metadata
            metadata = {}

            # Dimensions from dataWindow
            if "dataWindow" in header:
                min_coord, max_coord = header["dataWindow"]
                width = int(max_coord[0] - min_coord[0] + 1)
                height = int(max_coord[1] - min_coord[1] + 1)
                metadata["width"] = width
                metadata["height"] = height
                print(f"DEBUG EXR: Dimensions: {width}x{height}")

            # Channels - header["channels"] is a list of Channel objects
            if "channels" in header:
                channel_list = header["channels"]
                channel_names = [str(ch) for ch in channel_list]
                metadata["channels"] = channel_names
                print(f"DEBUG EXR: Channels: {channel_names}")

            # Compression - now it's an enum that can be compared directly
            if "compression" in header:
                compression = header["compression"]
                # Compression enum has a name attribute
                metadata["compression"] = str(compression)
                print(f"DEBUG EXR: Compression: {compression}")

            # Type (scanline, tiled, deep, etc.)
            if "type" in header:
                storage_type = header["type"]
                metadata["type"] = str(storage_type)
                print(f"DEBUG EXR: Type: {storage_type}")

            # Line order
            if "lineOrder" in header:
                line_order = header["lineOrder"]
                metadata["lineOrder"] = str(line_order)
                print(f"DEBUG EXR: Line order: {line_order}")

            # Pixel aspect ratio
            if "pixelAspectRatio" in header:
                metadata["pixelAspectRatio"] = float(header["pixelAspectRatio"])

            print(f"DEBUG EXR: Metadata extraction complete, {len(metadata)} fields")
            return metadata

    except Exception as e:
        print(f"DEBUG EXR: Exception during extraction: {e}")
        import traceback

        traceback.print_exc()
        return {"error": f"Failed to extract EXR metadata: {str(e)}"}
    finally:
        # Cleanup temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                print(f"DEBUG EXR: Cleaned up temp file")
            except Exception as cleanup_error:
                print(f"DEBUG EXR: Cleanup failed: {cleanup_error}")


async def extract_exr_metadata(buffer: bytes) -> Dict[str, Any]:
    """
    Extract metadata from OpenEXR file.

    Args:
        buffer: EXR file bytes

    Returns:
        dict: Extracted metadata organized by category

    Raises:
        RuntimeError: If OpenEXR library is not available or file processing fails

    Examples:
        >>> buffer = open("image.exr", "rb").read()
        >>> metadata = await extract_exr_metadata(buffer)
        >>> "channels" in metadata
        True
    """
    logger.debug(f"extract_exr_metadata called, buffer size: {len(buffer)}")
    logger.debug(f"OPENEXR_AVAILABLE: {OPENEXR_AVAILABLE}")
    logger.debug(f"/opt exists: {os.path.exists('/opt')}")

    if not OPENEXR_AVAILABLE:
        error_msg = f"OpenEXR library not available. Import error: {IMPORT_ERROR}"
        logger.error(error_msg)
        if os.path.exists("/opt"):
            logger.debug(f"/opt contents: {os.listdir('/opt')}")
        raise RuntimeError(error_msg)

    tmp_path = None
    try:
        logger.debug("Creating temporary file for EXR processing")
        # Write buffer to temporary file (OpenEXR requires file path)
        with tempfile.NamedTemporaryFile(suffix=".exr", delete=False) as tmp_file:
            logger.debug(f"Writing {len(buffer)} bytes to {tmp_file.name}")
            tmp_file.write(buffer)
            tmp_path = tmp_file.name
            logger.debug(f"Temporary file created: {tmp_path}")

        logger.debug("Opening EXR file with OpenEXR.File")
        # Open EXR file using modern API (OpenEXR v3.3+)
        with OpenEXR.File(tmp_path) as exr_file:
            logger.debug("EXR file opened successfully")

            logger.debug("Reading EXR header")
            header = exr_file.header()
            logger.debug(f"Header read successfully, keys: {list(header.keys())[:10]}")

            # Extract metadata
            metadata = {}

            # Data window (image dimensions)
            if "dataWindow" in header:
                metadata["dataWindow"] = _extract_window_metadata(header["dataWindow"])

            # Display window
            if "displayWindow" in header:
                metadata["displayWindow"] = _extract_window_metadata(
                    header["displayWindow"]
                )

            # Channels
            if "channels" in header:
                channels = header["channels"]
                metadata["channels"] = {
                    name: {
                        "type": str(chan.type),
                        "xSampling": chan.xSampling,
                        "ySampling": chan.ySampling,
                    }
                    for name, chan in channels.items()
                }

            # Compression
            if "compression" in header:
                compression = header["compression"]
                # Convert to int for dictionary lookup (Compression enum is not hashable)
                try:
                    compression_int = int(compression)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Failed to convert compression type to int: {e}")
                    compression_int = None

                if compression_int is not None:
                    metadata["compression"] = COMPRESSION_NAMES.get(
                        compression_int, f"Unknown ({compression_int})"
                    )
                else:
                    metadata["compression"] = f"Unknown ({compression})"

            # Line order
            if "lineOrder" in header:
                line_order = header["lineOrder"]
                # Convert to int for dictionary lookup (LineOrder object is not hashable)
                line_order_int = (
                    int(line_order) if hasattr(line_order, "__int__") else line_order
                )
                line_order_names = {
                    int(Imath.LineOrder.INCREASING_Y): "Increasing Y",
                    int(Imath.LineOrder.DECREASING_Y): "Decreasing Y",
                    int(Imath.LineOrder.RANDOM_Y): "Random Y",
                }
                metadata["lineOrder"] = line_order_names.get(
                    line_order_int, f"Unknown ({line_order_int})"
                )

            # Pixel aspect ratio
            if "pixelAspectRatio" in header:
                metadata["pixelAspectRatio"] = float(header["pixelAspectRatio"])

            # Screen window center and width
            if "screenWindowCenter" in header:
                swc = header["screenWindowCenter"]
                metadata["screenWindowCenter"] = {"x": swc.x, "y": swc.y}

            if "screenWindowWidth" in header:
                metadata["screenWindowWidth"] = float(header["screenWindowWidth"])

            # Custom attributes (metadata added by applications)
            custom_attrs = {}
            for key, value in header.items():
                if key not in [
                    "dataWindow",
                    "displayWindow",
                    "channels",
                    "compression",
                    "lineOrder",
                    "pixelAspectRatio",
                    "screenWindowCenter",
                    "screenWindowWidth",
                ]:
                    # Convert value to serializable format
                    if isinstance(value, (str, int, float, bool)):
                        custom_attrs[key] = value
                    elif hasattr(value, "__dict__"):
                        # Try to convert objects to dict
                        try:
                            custom_attrs[key] = str(value)
                        except Exception:
                            pass

            if custom_attrs:
                metadata["customAttributes"] = custom_attrs

            logger.info(
                f"Metadata extraction complete, extracted {len(metadata)} fields"
            )
            return metadata

    except Exception as e:
        logger.exception(f"Failed to extract EXR metadata: {e}")
        raise RuntimeError(f"Failed to extract EXR metadata: {str(e)}") from e
    finally:
        # Clean up temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                logger.debug(f"Cleaned up temporary file: {tmp_path}")
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to cleanup temporary file {tmp_path}: {cleanup_error}"
                )
