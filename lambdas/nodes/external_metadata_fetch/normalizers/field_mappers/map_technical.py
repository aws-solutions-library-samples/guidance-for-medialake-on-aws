"""Configuration-driven technical metadata field mapping for MEC elements.

This module provides functions to map source system technical metadata to MEC-compliant
Video, Audio, and Subtitle elements. All field names are configuration-driven -
NO hardcoded customer-specific values.

Technical metadata includes:
- Video attributes: frame_rate, aspect_ratio, resolution, color type, codec
- Audio attributes: language, DVS (descriptive video service), track references
- Subtitle/caption attributes: language, type (CC, SDH, Forced)

Example configuration:
    {
        "frame_rate_field": "frame_rate",
        "aspect_ratio_field": "video_dar",
        "resolution_field": "resolution",
        "color_flag_field": "in_color_flag",
        "video_codec_field": "videoattributes/videocodec",
        "source_materials_field": "source_materials",
        "component_field": "component",
        "component_type_attr": "@componenttype",
        "audio_language_attr": "audiolanguage",
        "audio_dvs_attr": "DVS",
        "audio_track_attr": "fileposition",
        "audio_pair_attr": "audiopairnumber",
        "audio_description_attr": "audiodescription",
        "audio_codec_attr": "audiocodec",
        "cc_language_attr": "language",
        "subtitle_language_attr": "language",
        "forced_narrative_field": "forced_narrative"
    }

Reference: MovieLabs MEC v2.25 - DigitalAsset/Video, Audio, Subtitle elements
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.mec_schema import (
        AudioAttributes,
        SubtitleAttributes,
        VideoAttributes,
    )
except ImportError:
    from normalizers.mec_schema import (
        AudioAttributes,
        SubtitleAttributes,
        VideoAttributes,
    )


def convert_frame_rate(frame_rate_value: Any) -> str | None:
    """Convert frame rate from ×100 format to decimal string.

    Source systems often store frame rates as integers multiplied by 100
    (e.g., 2400 for 24.00 fps, 2997 for 29.97 fps).

    Args:
        frame_rate_value: Frame rate value, either as integer ×100 format
            or already as a decimal string.

    Returns:
        Frame rate as decimal string (e.g., "24.00", "29.97"), or None if invalid.

    Examples:
        >>> convert_frame_rate(2400)
        '24.00'
        >>> convert_frame_rate(2997)
        '29.97'
        >>> convert_frame_rate("23.976")
        '23.976'
        >>> convert_frame_rate(None)
        None
    """
    if frame_rate_value is None:
        return None

    # Handle string input
    if isinstance(frame_rate_value, str):
        frame_rate_value = frame_rate_value.strip()
        if not frame_rate_value:
            return None

        # Check if already in decimal format (contains decimal point)
        if "." in frame_rate_value:
            try:
                # Validate it's a valid number
                float(frame_rate_value)
                return frame_rate_value
            except ValueError:
                return None

        # Try to convert string to integer for ×100 format
        try:
            frame_rate_value = int(frame_rate_value)
        except ValueError:
            return None

    # Handle integer ×100 format
    if isinstance(frame_rate_value, int):
        if frame_rate_value <= 0:
            return None
        # Convert from ×100 format to decimal
        decimal_rate = frame_rate_value / 100.0
        # Format with 2 decimal places, but handle special cases
        if decimal_rate == int(decimal_rate):
            return f"{int(decimal_rate)}.00"
        return f"{decimal_rate:.2f}"

    # Handle float input
    if isinstance(frame_rate_value, float):
        if frame_rate_value <= 0:
            return None
        return f"{frame_rate_value:.2f}"

    return None


def convert_aspect_ratio(aspect_ratio_value: Any) -> str | None:
    """Convert aspect ratio to standard format.

    Handles various input formats:
    - Decimal format: "1.78" → "16:9"
    - Ratio format: "16:9" → "16:9" (pass through)
    - Common values are mapped to standard ratios

    Args:
        aspect_ratio_value: Aspect ratio value in decimal or ratio format.

    Returns:
        Aspect ratio in standard format (e.g., "16:9", "4:3"), or None if invalid.

    Examples:
        >>> convert_aspect_ratio("1.78")
        '16:9'
        >>> convert_aspect_ratio("16:9")
        '16:9'
        >>> convert_aspect_ratio(1.33)
        '4:3'
    """
    if aspect_ratio_value is None:
        return None

    value_str = str(aspect_ratio_value).strip()
    if not value_str:
        return None

    # If already in ratio format, return as-is
    if ":" in value_str:
        return value_str

    # Common decimal to ratio mappings
    decimal_to_ratio = {
        "1.78": "16:9",
        "1.77": "16:9",
        "1.777": "16:9",
        "1.7777": "16:9",
        "1.33": "4:3",
        "1.333": "4:3",
        "1.3333": "4:3",
        "2.35": "2.35:1",
        "2.39": "2.39:1",
        "2.40": "2.40:1",
        "1.85": "1.85:1",
        "1.90": "1.90:1",
    }

    # Try to match common values
    try:
        decimal_value = float(value_str)
        # Round to 2 decimal places for matching
        rounded = f"{decimal_value:.2f}"
        if rounded in decimal_to_ratio:
            return decimal_to_ratio[rounded]

        # For 16:9 range (1.77-1.79)
        if 1.77 <= decimal_value <= 1.79:
            return "16:9"

        # For 4:3 range (1.32-1.34)
        if 1.32 <= decimal_value <= 1.34:
            return "4:3"

        # Return as ratio format for other values
        return f"{decimal_value}:1"
    except ValueError:
        return value_str


def parse_resolution(resolution_value: Any) -> tuple[int | None, int | None]:
    """Parse resolution string into width and height pixels.

    Handles various formats:
    - "1920x1080" → (1920, 1080)
    - "1920×1080" → (1920, 1080)
    - "1920 x 1080" → (1920, 1080)

    Args:
        resolution_value: Resolution string in WxH format.

    Returns:
        Tuple of (width_pixels, height_pixels), or (None, None) if invalid.

    Examples:
        >>> parse_resolution("1920x1080")
        (1920, 1080)
        >>> parse_resolution("3840×2160")
        (3840, 2160)
    """
    if resolution_value is None:
        return None, None

    value_str = str(resolution_value).strip()
    if not value_str:
        return None, None

    # Try different separators
    for separator in ["x", "×", "X"]:
        if separator in value_str:
            parts = value_str.split(separator)
            if len(parts) == 2:
                try:
                    width = int(parts[0].strip())
                    height = int(parts[1].strip())
                    return width, height
                except ValueError:
                    pass

    return None, None


def convert_color_flag(color_flag_value: Any) -> str | None:
    """Convert color flag to MEC PictureColorType value.

    Args:
        color_flag_value: Color flag value (Y/N, true/false, Color/BW, etc.)

    Returns:
        MEC PictureColorType value ("Color" or "BlackAndWhite"), or None.

    Examples:
        >>> convert_color_flag("Y")
        'Color'
        >>> convert_color_flag("N")
        'BlackAndWhite'
        >>> convert_color_flag(True)
        'Color'
    """
    if color_flag_value is None:
        return None

    value_str = str(color_flag_value).strip().lower()

    if value_str in ("y", "yes", "true", "1", "color"):
        return "Color"
    if value_str in ("n", "no", "false", "0", "bw", "b&w", "blackandwhite"):
        return "BlackAndWhite"

    return None


def map_video_attributes(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> VideoAttributes | None:
    """Map video technical attributes from source metadata.

    Extracts video attributes from the raw metadata using configuration-driven
    field names. Handles frame rate conversion from ×100 format.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing field name mappings:
            - frame_rate_field: Field name for frame rate (default: "frame_rate")
            - aspect_ratio_field: Field name for aspect ratio (default: "video_dar")
            - resolution_field: Field name for resolution (default: "resolution")
            - color_flag_field: Field name for color flag (default: "in_color_flag")
            - video_codec_field: Field name for video codec
            - active_picture_field: Field name for active picture dimensions

    Returns:
        VideoAttributes if any video data found, None otherwise.

    Example:
        >>> raw = {"frame_rate": 2400, "video_dar": "16:9", "in_color_flag": "Y"}
        >>> config = {}
        >>> video = map_video_attributes(raw, config)
        >>> video.frame_rate
        '24.00'
    """
    # Get field names from config with defaults
    frame_rate_field = config.get("frame_rate_field", "frame_rate")
    aspect_ratio_field = config.get("aspect_ratio_field", "video_dar")
    resolution_field = config.get("resolution_field", "resolution")
    color_flag_field = config.get("color_flag_field", "in_color_flag")
    video_codec_field = config.get("video_codec_field", "videocodec")
    active_picture_field = config.get("active_picture_field", "activepicture")

    # Also check nested videoattributes structure
    video_attrs_container = config.get("video_attributes_container", "videoattributes")
    nested_frame_rate = config.get("nested_frame_rate_field", "framerate")
    nested_aspect_ratio = config.get("nested_aspect_ratio_field", "aspectratio")
    nested_codec = config.get("nested_codec_field", "videocodec")
    nested_active_picture = config.get("nested_active_picture_field", "activepicture")

    # Extract values from top-level fields
    frame_rate = raw_metadata.get(frame_rate_field)
    aspect_ratio = raw_metadata.get(aspect_ratio_field)
    resolution = raw_metadata.get(resolution_field)
    color_flag = raw_metadata.get(color_flag_field)
    codec = raw_metadata.get(video_codec_field)
    active_picture = raw_metadata.get(active_picture_field)

    # Check nested videoattributes structure
    video_attrs = raw_metadata.get(video_attrs_container, {})
    if isinstance(video_attrs, dict):
        if not frame_rate:
            frame_rate = video_attrs.get(nested_frame_rate)
        if not aspect_ratio:
            aspect_ratio = video_attrs.get(nested_aspect_ratio)
        if not codec:
            codec = video_attrs.get(nested_codec)
        if not active_picture:
            active_picture = video_attrs.get(nested_active_picture)

    # Convert values
    converted_frame_rate = convert_frame_rate(frame_rate)
    converted_aspect_ratio = convert_aspect_ratio(aspect_ratio)
    width_pixels, height_pixels = parse_resolution(resolution)
    converted_color = convert_color_flag(color_flag)

    # Parse active picture dimensions
    active_width, active_height = parse_resolution(active_picture)

    # Check if we have any video data
    has_data = any(
        [
            converted_frame_rate,
            converted_aspect_ratio,
            width_pixels,
            height_pixels,
            active_width,
            active_height,
            converted_color,
            codec,
        ]
    )

    if not has_data:
        return None

    return VideoAttributes(
        frame_rate=converted_frame_rate,
        aspect_ratio=converted_aspect_ratio,
        width_pixels=width_pixels,
        height_pixels=height_pixels,
        active_width_pixels=active_width,
        active_height_pixels=active_height,
        color_type=converted_color,
        codec=str(codec).strip() if codec else None,
    )


def is_dvs_audio(audio_data: dict[str, Any], config: dict[str, Any]) -> bool:
    """Check if audio track is a Descriptive Video Service (DVS) track.

    DVS tracks provide audio descriptions for visually impaired viewers.

    Args:
        audio_data: Audio component data dictionary.
        config: Configuration dictionary containing:
            - audio_dvs_attr: Attribute name for DVS flag (default: "DVS")

    Returns:
        True if this is a DVS audio track, False otherwise.

    Example:
        >>> audio_data = {"DVS": "true", "audiolanguage": "en-US"}
        >>> is_dvs_audio(audio_data, {})
        True
    """
    dvs_attr = config.get("audio_dvs_attr", "DVS")
    dvs_value = audio_data.get(dvs_attr)

    if dvs_value is None:
        return False

    # Handle various boolean representations
    value_str = str(dvs_value).strip().lower()
    return value_str in ("true", "yes", "1", "y")


def map_audio_track(
    audio_data: dict[str, Any],
    config: dict[str, Any],
) -> AudioAttributes | None:
    """Map a single audio track to MEC AudioAttributes.

    Args:
        audio_data: Audio component data dictionary containing:
            - Language code
            - DVS flag (for visually impaired audio)
            - Track reference/position
            - Audio description (type)
            - Codec information
        config: Configuration dictionary containing attribute name mappings.

    Returns:
        AudioAttributes if valid audio data, None otherwise.

    Example:
        >>> audio_data = {"audiolanguage": "en-US", "DVS": "false", "fileposition": "1"}
        >>> config = {}
        >>> audio = map_audio_track(audio_data, config)
        >>> audio.language
        'en-US'
    """
    if not audio_data:
        return None

    # Get attribute names from config with defaults
    language_attr = config.get("audio_language_attr", "audiolanguage")
    config.get("audio_dvs_attr", "DVS")
    track_attr = config.get("audio_track_attr", "fileposition")
    pair_attr = config.get("audio_pair_attr", "audiopairnumber")
    description_attr = config.get("audio_description_attr", "audiodescription")
    codec_attr = config.get("audio_codec_attr", "audiocodec")

    # Extract language (required)
    language = audio_data.get(language_attr)
    if not language or not str(language).strip():
        return None

    language = str(language).strip()

    # Determine audio type based on DVS flag
    audio_type = None
    if is_dvs_audio(audio_data, config):
        audio_type = "VisuallyImpaired"

    # Get audio description as sub_type if not DVS
    sub_type = None
    description = audio_data.get(description_attr)
    if description and not audio_type:
        sub_type = str(description).strip()

    # Build track reference from position and pair number
    track_ref = None
    track_pos = audio_data.get(track_attr)
    pair_num = audio_data.get(pair_attr)

    if track_pos:
        track_ref = str(track_pos).strip()
    elif pair_num:
        track_ref = str(pair_num).strip()

    # Get codec
    codec = audio_data.get(codec_attr)
    codec_str = str(codec).strip() if codec else None

    return AudioAttributes(
        language=language,
        type=audio_type,
        sub_type=sub_type,
        internal_track_reference=track_ref,
        codec=codec_str,
    )


def map_audio_attributes(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[AudioAttributes]:
    """Map all audio tracks from source metadata.

    Extracts audio attributes from source materials/components structure.
    Handles multiple audio tracks per asset (surround, stereo, DVS, dubs).

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - source_materials_field: Container for source materials
            - component_field: Component element name
            - component_type_attr: Attribute for component type
            - audio_component_type: Value indicating audio component
            - audio_attributes_container: Container for audio attributes
            - Plus audio attribute field names

    Returns:
        List of AudioAttributes for all audio tracks found.

    Example:
        >>> raw = {
        ...     "source_materials": {
        ...         "component": [
        ...             {"@componenttype": "Audio", "audioattributes": {"audiolanguage": "en-US"}}
        ...         ]
        ...     }
        ... }
        >>> config = {}
        >>> audios = map_audio_attributes(raw, config)
        >>> len(audios)
        1
    """
    audio_tracks: list[AudioAttributes] = []

    # Get field names from config with defaults
    source_materials_field = config.get("source_materials_field", "source_materials")
    component_field = config.get("component_field", "component")
    component_type_attr = config.get("component_type_attr", "@componenttype")
    audio_component_type = config.get("audio_component_type", "Audio")
    audio_attrs_container = config.get("audio_attributes_container", "audioattributes")

    # Get source materials container
    source_materials = raw_metadata.get(source_materials_field, {})
    if not source_materials:
        return audio_tracks

    # Get components list
    components = source_materials.get(component_field, [])
    if isinstance(components, dict):
        components = [components]

    # Process each component
    for component in components:
        if not isinstance(component, dict):
            continue

        # Check if this is an audio component
        comp_type = component.get(component_type_attr)
        if comp_type != audio_component_type:
            continue

        # Get audio attributes
        audio_attrs = component.get(audio_attrs_container, {})
        if isinstance(audio_attrs, dict):
            audio = map_audio_track(audio_attrs, config)
            if audio:
                audio_tracks.append(audio)

    return audio_tracks


def map_subtitle_track(
    subtitle_data: dict[str, Any],
    config: dict[str, Any],
    is_closed_caption: bool = False,
) -> SubtitleAttributes | None:
    """Map a single subtitle/caption track to MEC SubtitleAttributes.

    Args:
        subtitle_data: Subtitle/caption component data dictionary.
        config: Configuration dictionary containing attribute name mappings.
        is_closed_caption: True if this is a closed caption track.

    Returns:
        SubtitleAttributes if valid data, None otherwise.

    Example:
        >>> subtitle_data = {"language": "en-US"}
        >>> config = {}
        >>> sub = map_subtitle_track(subtitle_data, config, is_closed_caption=True)
        >>> sub.type
        'CC'
    """
    if not subtitle_data:
        return None

    # Get attribute names from config with defaults
    language_attr = config.get("subtitle_language_attr", "language")
    type_attr = config.get("subtitle_type_attr", "type")
    format_attr = config.get("subtitle_format_attr", "format")

    # Extract language (required)
    language = subtitle_data.get(language_attr)
    if not language or not str(language).strip():
        return None

    language = str(language).strip()

    # Determine subtitle type
    subtitle_type = subtitle_data.get(type_attr)
    if subtitle_type:
        subtitle_type = str(subtitle_type).strip()
    elif is_closed_caption:
        subtitle_type = "CC"

    # Get format
    subtitle_format = subtitle_data.get(format_attr)
    format_str = str(subtitle_format).strip() if subtitle_format else None

    return SubtitleAttributes(
        language=language,
        type=subtitle_type,
        format=format_str,
    )


def map_subtitle_attributes(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[SubtitleAttributes]:
    """Map all subtitle and caption tracks from source metadata.

    Extracts subtitle attributes from source materials/components structure.
    Handles both closed captions and subtitles, including forced narrative.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - source_materials_field: Container for source materials
            - component_field: Component element name
            - component_type_attr: Attribute for component type
            - cc_component_type: Value indicating closed caption component
            - subtitle_component_type: Value indicating subtitle component
            - cc_attributes_container: Container for CC attributes
            - subtitle_attributes_container: Container for subtitle attributes
            - forced_narrative_field: Field for forced narrative flag

    Returns:
        List of SubtitleAttributes for all subtitle/caption tracks found.

    Example:
        >>> raw = {
        ...     "source_materials": {
        ...         "component": [
        ...             {"@componenttype": "Closed Captions", "closedcaptionsattributes": {"language": "en-US"}}
        ...         ]
        ...     }
        ... }
        >>> config = {}
        >>> subs = map_subtitle_attributes(raw, config)
        >>> len(subs)
        1
    """
    subtitle_tracks: list[SubtitleAttributes] = []

    # Get field names from config with defaults
    source_materials_field = config.get("source_materials_field", "source_materials")
    component_field = config.get("component_field", "component")
    component_type_attr = config.get("component_type_attr", "@componenttype")
    cc_component_type = config.get("cc_component_type", "Closed Captions")
    subtitle_component_type = config.get("subtitle_component_type", "Subtitle")
    cc_attrs_container = config.get(
        "cc_attributes_container", "closedcaptionsattributes"
    )
    subtitle_attrs_container = config.get(
        "subtitle_attributes_container", "subtitleattributes"
    )
    forced_narrative_field = config.get("forced_narrative_field", "forced_narrative")

    # Get source materials container
    source_materials = raw_metadata.get(source_materials_field, {})
    if not source_materials:
        # Check for forced narrative at top level
        forced = raw_metadata.get(forced_narrative_field)
        if forced and str(forced).strip().lower() in ("true", "yes", "1", "y"):
            # Create a forced subtitle entry if language is available
            language = raw_metadata.get("language", "en-US")
            subtitle_tracks.append(
                SubtitleAttributes(
                    language=str(language).strip(),
                    type="Forced",
                )
            )
        return subtitle_tracks

    # Get components list
    components = source_materials.get(component_field, [])
    if isinstance(components, dict):
        components = [components]

    # Process each component
    for component in components:
        if not isinstance(component, dict):
            continue

        comp_type = component.get(component_type_attr)

        # Handle closed captions
        if comp_type == cc_component_type:
            cc_attrs = component.get(cc_attrs_container, {})
            if isinstance(cc_attrs, dict):
                subtitle = map_subtitle_track(cc_attrs, config, is_closed_caption=True)
                if subtitle:
                    subtitle_tracks.append(subtitle)

        # Handle subtitles
        elif comp_type == subtitle_component_type:
            sub_attrs = component.get(subtitle_attrs_container, {})
            if isinstance(sub_attrs, dict):
                subtitle = map_subtitle_track(
                    sub_attrs, config, is_closed_caption=False
                )
                if subtitle:
                    subtitle_tracks.append(subtitle)

    # Check for forced narrative flag at top level
    forced = raw_metadata.get(forced_narrative_field)
    if forced and str(forced).strip().lower() in ("true", "yes", "1", "y"):
        # Add forced subtitle if not already present
        has_forced = any(s.type == "Forced" for s in subtitle_tracks)
        if not has_forced:
            language = raw_metadata.get("language", "en-US")
            subtitle_tracks.append(
                SubtitleAttributes(
                    language=str(language).strip(),
                    type="Forced",
                )
            )

    return subtitle_tracks


def map_all_technical(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Map all technical metadata from source to MEC format.

    This is the main entry point for technical metadata mapping.
    It extracts video, audio, and subtitle attributes.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing all field name mappings.

    Returns:
        Dictionary containing:
            - video_attributes: VideoAttributes or None
            - audio_attributes: List of AudioAttributes
            - subtitle_attributes: List of SubtitleAttributes

    Example:
        >>> raw = {"frame_rate": 2400, "video_dar": "16:9"}
        >>> config = {}
        >>> result = map_all_technical(raw, config)
        >>> result["video_attributes"].frame_rate
        '24.00'
    """
    return {
        "video_attributes": map_video_attributes(raw_metadata, config),
        "audio_attributes": map_audio_attributes(raw_metadata, config),
        "subtitle_attributes": map_subtitle_attributes(raw_metadata, config),
    }
