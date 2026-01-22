"""
EXIF tag name dictionary
Ported from src/dicts/tiff-exif-keys.mjs

EXIF (Exchangeable Image File Format) contains detailed camera settings
like ISO, aperture, shutter speed, focal length, etc.
"""

from ..tags import create_dictionary, tag_keys


def load_exif_keys():
    """Load EXIF tag names into global registry"""
    create_dictionary(
        tag_keys,
        "exif",
        [
            # Exposure settings
            (0x829A, "ExposureTime"),
            (0x829D, "FNumber"),
            (0x8822, "ExposureProgram"),
            (0x8824, "SpectralSensitivity"),
            (0x8827, "ISO"),
            (0x882A, "TimeZoneOffset"),
            (0x882B, "SelfTimerMode"),
            (0x8830, "SensitivityType"),
            (0x8831, "StandardOutputSensitivity"),
            (0x8832, "RecommendedExposureIndex"),
            (0x8833, "ISOSpeed"),
            (0x8834, "ISOSpeedLatitudeyyy"),
            (0x8835, "ISOSpeedLatitudezzz"),
            # Version and dates
            (0x9000, "ExifVersion"),
            (0x9003, "DateTimeOriginal"),
            (0x9004, "CreateDate"),
            (0x9009, "GooglePlusUploadCode"),
            (0x9010, "OffsetTime"),
            (0x9011, "OffsetTimeOriginal"),
            (0x9012, "OffsetTimeDigitized"),
            # Image configuration
            (0x9101, "ComponentsConfiguration"),
            (0x9102, "CompressedBitsPerPixel"),
            # Camera settings
            (0x9201, "ShutterSpeedValue"),
            (0x9202, "ApertureValue"),
            (0x9203, "BrightnessValue"),
            (0x9204, "ExposureCompensation"),
            (0x9205, "MaxApertureValue"),
            (0x9206, "SubjectDistance"),
            (0x9207, "MeteringMode"),
            (0x9208, "LightSource"),
            (0x9209, "Flash"),
            (0x920A, "FocalLength"),
            (0x9211, "ImageNumber"),
            (0x9212, "SecurityClassification"),
            (0x9213, "ImageHistory"),
            (0x9214, "SubjectArea"),
            # Notes and comments
            (0x927C, "MakerNote"),
            (0x9286, "UserComment"),
            (0x9290, "SubSecTime"),
            (0x9291, "SubSecTimeOriginal"),
            (0x9292, "SubSecTimeDigitized"),
            # Environmental conditions
            (0x9400, "AmbientTemperature"),
            (0x9401, "Humidity"),
            (0x9402, "Pressure"),
            (0x9403, "WaterDepth"),
            (0x9404, "Acceleration"),
            (0x9405, "CameraElevationAngle"),
            # Color and image settings
            (0xA000, "FlashpixVersion"),
            (0xA001, "ColorSpace"),
            (0xA002, "ExifImageWidth"),
            (0xA003, "ExifImageHeight"),
            (0xA004, "RelatedSoundFile"),
            (0xA20B, "FlashEnergy"),
            (0xA20E, "FocalPlaneXResolution"),
            (0xA20F, "FocalPlaneYResolution"),
            (0xA210, "FocalPlaneResolutionUnit"),
            (0xA214, "SubjectLocation"),
            (0xA215, "ExposureIndex"),
            (0xA217, "SensingMethod"),
            (0xA300, "FileSource"),
            (0xA301, "SceneType"),
            (0xA302, "CFAPattern"),
            # Image processing
            (0xA401, "CustomRendered"),
            (0xA402, "ExposureMode"),
            (0xA403, "WhiteBalance"),
            (0xA404, "DigitalZoomRatio"),
            (0xA405, "FocalLengthIn35mmFormat"),
            (0xA406, "SceneCaptureType"),
            (0xA407, "GainControl"),
            (0xA408, "Contrast"),
            (0xA409, "Saturation"),
            (0xA40A, "Sharpness"),
            (0xA40C, "SubjectDistanceRange"),
            # Image identification
            (0xA420, "ImageUniqueID"),
            (0xA430, "OwnerName"),
            (0xA431, "SerialNumber"),
            # Lens information
            (0xA432, "LensInfo"),
            (0xA433, "LensMake"),
            (0xA434, "LensModel"),
            (0xA435, "LensSerialNumber"),
            # Composite images
            (0xA460, "CompositeImage"),
            (0xA461, "CompositeImageCount"),
            (0xA462, "CompositeImageExposureTimes"),
            # Color management
            (0xA500, "Gamma"),
            # Padding and offsets
            (0xEA1C, "Padding"),
            (0xEA1D, "OffsetSchema"),
            # Additional proprietary tags
            (0xFDE8, "OwnerName"),
            (0xFDE9, "SerialNumber"),
            (0xFDEA, "Lens"),
            (0xFE4C, "RawFile"),
            (0xFE4D, "Converter"),
            (0xFE4E, "WhiteBalance"),
            (0xFE51, "Exposure"),
            (0xFE52, "Shadows"),
            (0xFE53, "Brightness"),
            (0xFE54, "Contrast"),
            (0xFE55, "Saturation"),
            (0xFE56, "Sharpness"),
            (0xFE57, "Smoothness"),
            (0xFE58, "MoireFilter"),
            # Interop pointer (often found in EXIF)
            (0xA005, "InteropIFD"),
        ],
    )
