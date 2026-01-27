"""
Unit tests for the technical metadata field mapper module.

These tests verify that:
- convert_frame_rate() correctly converts ×100 format to decimal
- convert_aspect_ratio() correctly converts decimal to ratio format
- map_video_attributes() extracts video technical specs
- map_audio_attributes() extracts audio tracks with DVS support
- map_subtitle_attributes() extracts subtitle/caption tracks
- Forced narrative subtitles are handled correctly
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_technical import (
    convert_aspect_ratio,
    convert_color_flag,
    convert_frame_rate,
    is_dvs_audio,
    map_all_technical,
    map_audio_attributes,
    map_audio_track,
    map_subtitle_attributes,
    map_subtitle_track,
    map_video_attributes,
    parse_resolution,
)


@pytest.mark.unit
class TestConvertFrameRate:
    """Tests for convert_frame_rate function"""

    def test_converts_2400_to_24_00(self):
        """Converts 2400 (×100 format) to 24.00."""
        result = convert_frame_rate(2400)
        assert result == "24.00"

    def test_converts_2997_to_29_97(self):
        """Converts 2997 (×100 format) to 29.97."""
        result = convert_frame_rate(2997)
        assert result == "29.97"

    def test_converts_3000_to_30_00(self):
        """Converts 3000 (×100 format) to 30.00."""
        result = convert_frame_rate(3000)
        assert result == "30.00"

    def test_converts_2398_to_23_98(self):
        """Converts 2398 (×100 format) to 23.98."""
        result = convert_frame_rate(2398)
        assert result == "23.98"

    def test_converts_string_integer_format(self):
        """Converts string integer ×100 format."""
        result = convert_frame_rate("2400")
        assert result == "24.00"

    def test_passes_through_decimal_string(self):
        """Passes through already decimal string format."""
        result = convert_frame_rate("23.976")
        assert result == "23.976"

    def test_returns_none_for_none(self):
        """Returns None for None input."""
        result = convert_frame_rate(None)
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None for empty string."""
        result = convert_frame_rate("")
        assert result is None

    def test_returns_none_for_whitespace(self):
        """Returns None for whitespace-only string."""
        result = convert_frame_rate("   ")
        assert result is None

    def test_returns_none_for_zero(self):
        """Returns None for zero value."""
        result = convert_frame_rate(0)
        assert result is None

    def test_returns_none_for_negative(self):
        """Returns None for negative value."""
        result = convert_frame_rate(-2400)
        assert result is None

    def test_handles_float_input(self):
        """Handles float input."""
        result = convert_frame_rate(29.97)
        assert result == "29.97"


@pytest.mark.unit
class TestConvertAspectRatio:
    """Tests for convert_aspect_ratio function"""

    def test_converts_1_78_to_16_9(self):
        """Converts 1.78 decimal to 16:9 ratio."""
        result = convert_aspect_ratio("1.78")
        assert result == "16:9"

    def test_converts_1_77_to_16_9(self):
        """Converts 1.77 decimal to 16:9 ratio."""
        result = convert_aspect_ratio("1.77")
        assert result == "16:9"

    def test_converts_1_33_to_4_3(self):
        """Converts 1.33 decimal to 4:3 ratio."""
        result = convert_aspect_ratio("1.33")
        assert result == "4:3"

    def test_passes_through_ratio_format(self):
        """Passes through already ratio format."""
        result = convert_aspect_ratio("16:9")
        assert result == "16:9"

    def test_passes_through_4_3_ratio(self):
        """Passes through 4:3 ratio format."""
        result = convert_aspect_ratio("4:3")
        assert result == "4:3"

    def test_converts_2_35_to_ratio(self):
        """Converts 2.35 to 2.35:1 ratio."""
        result = convert_aspect_ratio("2.35")
        assert result == "2.35:1"

    def test_returns_none_for_none(self):
        """Returns None for None input."""
        result = convert_aspect_ratio(None)
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None for empty string."""
        result = convert_aspect_ratio("")
        assert result is None

    def test_handles_float_input(self):
        """Handles float input."""
        result = convert_aspect_ratio(1.78)
        assert result == "16:9"


@pytest.mark.unit
class TestParseResolution:
    """Tests for parse_resolution function"""

    def test_parses_1920x1080(self):
        """Parses 1920x1080 resolution."""
        width, height = parse_resolution("1920x1080")
        assert width == 1920
        assert height == 1080

    def test_parses_3840x2160(self):
        """Parses 4K resolution."""
        width, height = parse_resolution("3840x2160")
        assert width == 3840
        assert height == 2160

    def test_parses_with_unicode_x(self):
        """Parses resolution with unicode × character."""
        width, height = parse_resolution("1920×1080")
        assert width == 1920
        assert height == 1080

    def test_parses_with_uppercase_x(self):
        """Parses resolution with uppercase X."""
        width, height = parse_resolution("1920X1080")
        assert width == 1920
        assert height == 1080

    def test_returns_none_for_none(self):
        """Returns None tuple for None input."""
        width, height = parse_resolution(None)
        assert width is None
        assert height is None

    def test_returns_none_for_empty_string(self):
        """Returns None tuple for empty string."""
        width, height = parse_resolution("")
        assert width is None
        assert height is None

    def test_returns_none_for_invalid_format(self):
        """Returns None tuple for invalid format."""
        width, height = parse_resolution("invalid")
        assert width is None
        assert height is None


@pytest.mark.unit
class TestConvertColorFlag:
    """Tests for convert_color_flag function"""

    def test_converts_y_to_color(self):
        """Converts Y to Color."""
        result = convert_color_flag("Y")
        assert result == "Color"

    def test_converts_yes_to_color(self):
        """Converts yes to Color."""
        result = convert_color_flag("yes")
        assert result == "Color"

    def test_converts_true_to_color(self):
        """Converts true to Color."""
        result = convert_color_flag("true")
        assert result == "Color"

    def test_converts_n_to_blackandwhite(self):
        """Converts N to BlackAndWhite."""
        result = convert_color_flag("N")
        assert result == "BlackAndWhite"

    def test_converts_no_to_blackandwhite(self):
        """Converts no to BlackAndWhite."""
        result = convert_color_flag("no")
        assert result == "BlackAndWhite"

    def test_converts_false_to_blackandwhite(self):
        """Converts false to BlackAndWhite."""
        result = convert_color_flag("false")
        assert result == "BlackAndWhite"

    def test_returns_none_for_none(self):
        """Returns None for None input."""
        result = convert_color_flag(None)
        assert result is None

    def test_handles_boolean_true(self):
        """Handles boolean True input."""
        result = convert_color_flag(True)
        assert result == "Color"

    def test_handles_boolean_false(self):
        """Handles boolean False input."""
        result = convert_color_flag(False)
        assert result == "BlackAndWhite"


@pytest.mark.unit
class TestMapVideoAttributes:
    """Tests for map_video_attributes function"""

    def test_maps_frame_rate_from_x100_format(self):
        """Maps frame rate from ×100 format."""
        raw_metadata = {"frame_rate": 2400}
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.frame_rate == "24.00"

    def test_maps_aspect_ratio(self):
        """Maps aspect ratio to standard format."""
        raw_metadata = {"video_dar": "16:9"}
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.aspect_ratio == "16:9"

    def test_maps_aspect_ratio_from_decimal(self):
        """Maps aspect ratio from decimal format."""
        raw_metadata = {"video_dar": "1.78"}
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.aspect_ratio == "16:9"

    def test_maps_resolution(self):
        """Maps resolution to width and height pixels."""
        raw_metadata = {"resolution": "1920x1080"}
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.width_pixels == 1920
        assert result.height_pixels == 1080

    def test_maps_color_flag(self):
        """Maps color flag to color type."""
        raw_metadata = {"in_color_flag": "Y"}
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.color_type == "Color"

    def test_maps_all_video_attributes(self):
        """Maps all video attributes together."""
        raw_metadata = {
            "frame_rate": 2400,
            "video_dar": "16:9",
            "resolution": "1920x1080",
            "in_color_flag": "Y",
        }
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.frame_rate == "24.00"
        assert result.aspect_ratio == "16:9"
        assert result.width_pixels == 1920
        assert result.height_pixels == 1080
        assert result.color_type == "Color"

    def test_returns_none_when_no_video_data(self):
        """Returns None when no video data present."""
        raw_metadata = {"title": "Test Content"}
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is None

    def test_uses_custom_field_names(self):
        """Uses custom field names from config."""
        raw_metadata = {
            "custom_frame_rate": 2997,
            "custom_aspect": "4:3",
        }
        config = {
            "frame_rate_field": "custom_frame_rate",
            "aspect_ratio_field": "custom_aspect",
        }

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.frame_rate == "29.97"
        assert result.aspect_ratio == "4:3"

    def test_extracts_from_nested_videoattributes(self):
        """Extracts video attributes from nested structure."""
        raw_metadata = {
            "videoattributes": {
                "framerate": 2400,
                "aspectratio": "1.78",
                "videocodec": "Apple Pro Res",
            }
        }
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        assert result.frame_rate == "24.00"
        assert result.aspect_ratio == "16:9"
        assert result.codec == "Apple Pro Res"

    def test_to_dict_serialization(self):
        """Verifies VideoAttributes to_dict works correctly."""
        raw_metadata = {
            "frame_rate": 2400,
            "video_dar": "16:9",
            "in_color_flag": "Y",
        }
        config = {}

        result = map_video_attributes(raw_metadata, config)

        assert result is not None
        dict_result = result.to_dict()
        assert dict_result["FrameRate"] == "24.00"
        assert dict_result["AspectRatio"] == "16:9"
        assert dict_result["ColorType"] == "Color"


@pytest.mark.unit
class TestIsDvsAudio:
    """Tests for is_dvs_audio function"""

    def test_returns_true_for_dvs_true(self):
        """Returns True when DVS is true."""
        audio_data = {"DVS": "true"}
        config = {}

        result = is_dvs_audio(audio_data, config)

        assert result is True

    def test_returns_true_for_dvs_yes(self):
        """Returns True when DVS is yes."""
        audio_data = {"DVS": "yes"}
        config = {}

        result = is_dvs_audio(audio_data, config)

        assert result is True

    def test_returns_true_for_dvs_1(self):
        """Returns True when DVS is 1."""
        audio_data = {"DVS": "1"}
        config = {}

        result = is_dvs_audio(audio_data, config)

        assert result is True

    def test_returns_false_for_dvs_false(self):
        """Returns False when DVS is false."""
        audio_data = {"DVS": "false"}
        config = {}

        result = is_dvs_audio(audio_data, config)

        assert result is False

    def test_returns_false_for_missing_dvs(self):
        """Returns False when DVS is not present."""
        audio_data = {"audiolanguage": "en-US"}
        config = {}

        result = is_dvs_audio(audio_data, config)

        assert result is False

    def test_uses_custom_dvs_attribute(self):
        """Uses custom DVS attribute name from config."""
        audio_data = {"descriptive_audio": "true"}
        config = {"audio_dvs_attr": "descriptive_audio"}

        result = is_dvs_audio(audio_data, config)

        assert result is True


@pytest.mark.unit
class TestMapAudioTrack:
    """Tests for map_audio_track function"""

    def test_maps_audio_language(self):
        """Maps audio language correctly."""
        audio_data = {"audiolanguage": "en-US"}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is not None
        assert result.language == "en-US"

    def test_maps_dvs_audio_type(self):
        """Maps DVS flag to VisuallyImpaired type."""
        audio_data = {"audiolanguage": "en-US", "DVS": "true"}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is not None
        assert result.type == "VisuallyImpaired"

    def test_maps_track_reference(self):
        """Maps track reference from fileposition."""
        audio_data = {"audiolanguage": "en-US", "fileposition": "1"}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is not None
        assert result.internal_track_reference == "1"

    def test_maps_audio_description_as_subtype(self):
        """Maps audio description as sub_type when not DVS."""
        audio_data = {"audiolanguage": "en-US", "audiodescription": "Surround Front"}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is not None
        assert result.sub_type == "Surround Front"

    def test_returns_none_for_missing_language(self):
        """Returns None when language is missing."""
        audio_data = {"DVS": "false"}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is None

    def test_returns_none_for_empty_language(self):
        """Returns None when language is empty."""
        audio_data = {"audiolanguage": ""}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is None

    def test_returns_none_for_empty_data(self):
        """Returns None for empty audio data."""
        result = map_audio_track({}, {})

        assert result is None

    def test_returns_none_for_none_data(self):
        """Returns None for None audio data."""
        result = map_audio_track(None, {})

        assert result is None

    def test_uses_custom_attribute_names(self):
        """Uses custom attribute names from config."""
        audio_data = {"lang": "es-419", "is_dvs": "true"}
        config = {
            "audio_language_attr": "lang",
            "audio_dvs_attr": "is_dvs",
        }

        result = map_audio_track(audio_data, config)

        assert result is not None
        assert result.language == "es-419"
        assert result.type == "VisuallyImpaired"

    def test_to_dict_serialization(self):
        """Verifies AudioAttributes to_dict works correctly."""
        audio_data = {"audiolanguage": "en-US", "DVS": "true", "fileposition": "1"}
        config = {}

        result = map_audio_track(audio_data, config)

        assert result is not None
        dict_result = result.to_dict()
        assert dict_result["Language"] == "en-US"
        assert dict_result["Type"] == "VisuallyImpaired"
        assert dict_result["InternalTrackReference"] == "1"


@pytest.mark.unit
class TestMapAudioAttributes:
    """Tests for map_audio_attributes function"""

    def test_extracts_audio_from_source_materials(self):
        """Extracts audio tracks from source materials structure."""
        raw_metadata = {
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {"audiolanguage": "en-US"},
                    }
                ]
            }
        }
        config = {}

        result = map_audio_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].language == "en-US"

    def test_extracts_multiple_audio_tracks(self):
        """Extracts multiple audio tracks."""
        raw_metadata = {
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {"audiolanguage": "en-US"},
                    },
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {"audiolanguage": "es-419"},
                    },
                ]
            }
        }
        config = {}

        result = map_audio_attributes(raw_metadata, config)

        assert len(result) == 2
        languages = {a.language for a in result}
        assert "en-US" in languages
        assert "es-419" in languages

    def test_filters_non_audio_components(self):
        """Filters out non-audio components."""
        raw_metadata = {
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Video",
                        "videoattributes": {"framerate": 2400},
                    },
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {"audiolanguage": "en-US"},
                    },
                ]
            }
        }
        config = {}

        result = map_audio_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].language == "en-US"

    def test_returns_empty_list_when_no_source_materials(self):
        """Returns empty list when no source materials."""
        raw_metadata = {"title": "Test Content"}
        config = {}

        result = map_audio_attributes(raw_metadata, config)

        assert result == []

    def test_handles_single_component_dict(self):
        """Handles single component as dict (not list)."""
        raw_metadata = {
            "source_materials": {
                "component": {
                    "@componenttype": "Audio",
                    "audioattributes": {"audiolanguage": "en-US"},
                }
            }
        }
        config = {}

        result = map_audio_attributes(raw_metadata, config)

        assert len(result) == 1

    def test_uses_custom_field_names(self):
        """Uses custom field names from config."""
        raw_metadata = {
            "materials": {
                "track": [
                    {
                        "type": "Audio",
                        "audio_info": {"lang": "en-US"},
                    }
                ]
            }
        }
        config = {
            "source_materials_field": "materials",
            "component_field": "track",
            "component_type_attr": "type",
            "audio_attributes_container": "audio_info",
            "audio_language_attr": "lang",
        }

        result = map_audio_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].language == "en-US"


@pytest.mark.unit
class TestMapSubtitleTrack:
    """Tests for map_subtitle_track function"""

    def test_maps_subtitle_language(self):
        """Maps subtitle language correctly."""
        subtitle_data = {"language": "en-US"}
        config = {}

        result = map_subtitle_track(subtitle_data, config)

        assert result is not None
        assert result.language == "en-US"

    def test_sets_cc_type_for_closed_captions(self):
        """Sets CC type for closed caption tracks."""
        subtitle_data = {"language": "en-US"}
        config = {}

        result = map_subtitle_track(subtitle_data, config, is_closed_caption=True)

        assert result is not None
        assert result.type == "CC"

    def test_maps_subtitle_type(self):
        """Maps subtitle type from data."""
        subtitle_data = {"language": "en-US", "type": "SDH"}
        config = {}

        result = map_subtitle_track(subtitle_data, config)

        assert result is not None
        assert result.type == "SDH"

    def test_returns_none_for_missing_language(self):
        """Returns None when language is missing."""
        subtitle_data = {"type": "CC"}
        config = {}

        result = map_subtitle_track(subtitle_data, config)

        assert result is None

    def test_returns_none_for_empty_data(self):
        """Returns None for empty subtitle data."""
        result = map_subtitle_track({}, {})

        assert result is None

    def test_returns_none_for_none_data(self):
        """Returns None for None subtitle data."""
        result = map_subtitle_track(None, {})

        assert result is None

    def test_to_dict_serialization(self):
        """Verifies SubtitleAttributes to_dict works correctly."""
        subtitle_data = {"language": "en-US"}
        config = {}

        result = map_subtitle_track(subtitle_data, config, is_closed_caption=True)

        assert result is not None
        dict_result = result.to_dict()
        assert dict_result["Language"] == "en-US"
        assert dict_result["Type"] == "CC"


@pytest.mark.unit
class TestMapSubtitleAttributes:
    """Tests for map_subtitle_attributes function"""

    def test_extracts_closed_captions_from_source_materials(self):
        """Extracts closed captions from source materials."""
        raw_metadata = {
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Closed Captions",
                        "closedcaptionsattributes": {"language": "en-US"},
                    }
                ]
            }
        }
        config = {}

        result = map_subtitle_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].language == "en-US"
        assert result[0].type == "CC"

    def test_extracts_subtitles_from_source_materials(self):
        """Extracts subtitles from source materials."""
        raw_metadata = {
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Subtitle",
                        "subtitleattributes": {"language": "es-419"},
                    }
                ]
            }
        }
        config = {}

        result = map_subtitle_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].language == "es-419"

    def test_extracts_both_cc_and_subtitles(self):
        """Extracts both closed captions and subtitles."""
        raw_metadata = {
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Closed Captions",
                        "closedcaptionsattributes": {"language": "en-US"},
                    },
                    {
                        "@componenttype": "Subtitle",
                        "subtitleattributes": {"language": "es-419"},
                    },
                ]
            }
        }
        config = {}

        result = map_subtitle_attributes(raw_metadata, config)

        assert len(result) == 2
        languages = {s.language for s in result}
        assert "en-US" in languages
        assert "es-419" in languages

    def test_handles_forced_narrative_flag(self):
        """Handles forced_narrative flag at top level."""
        raw_metadata = {
            "forced_narrative": "true",
            "language": "en-US",
        }
        config = {}

        result = map_subtitle_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].type == "Forced"
        assert result[0].language == "en-US"

    def test_adds_forced_subtitle_when_flag_true(self):
        """Adds forced subtitle when flag is true and not already present."""
        raw_metadata = {
            "forced_narrative": "true",
            "language": "en-US",
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Closed Captions",
                        "closedcaptionsattributes": {"language": "en-US"},
                    }
                ]
            },
        }
        config = {}

        result = map_subtitle_attributes(raw_metadata, config)

        # Should have CC and Forced subtitle
        assert len(result) == 2
        types = {s.type for s in result}
        assert "CC" in types
        assert "Forced" in types

    def test_returns_empty_list_when_no_subtitles(self):
        """Returns empty list when no subtitle data."""
        raw_metadata = {"title": "Test Content"}
        config = {}

        result = map_subtitle_attributes(raw_metadata, config)

        assert result == []

    def test_uses_custom_field_names(self):
        """Uses custom field names from config."""
        raw_metadata = {
            "materials": {
                "track": [
                    {
                        "type": "CC",
                        "cc_info": {"lang": "en-US"},
                    }
                ]
            }
        }
        config = {
            "source_materials_field": "materials",
            "component_field": "track",
            "component_type_attr": "type",
            "cc_component_type": "CC",
            "cc_attributes_container": "cc_info",
            "subtitle_language_attr": "lang",
        }

        result = map_subtitle_attributes(raw_metadata, config)

        assert len(result) == 1
        assert result[0].language == "en-US"


@pytest.mark.unit
class TestMapAllTechnical:
    """Tests for map_all_technical function"""

    def test_returns_all_technical_metadata(self):
        """Returns dictionary with all technical metadata."""
        raw_metadata = {
            "frame_rate": 2400,
            "video_dar": "16:9",
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {"audiolanguage": "en-US"},
                    },
                    {
                        "@componenttype": "Closed Captions",
                        "closedcaptionsattributes": {"language": "en-US"},
                    },
                ]
            },
        }
        config = {}

        result = map_all_technical(raw_metadata, config)

        assert "video_attributes" in result
        assert "audio_attributes" in result
        assert "subtitle_attributes" in result

        assert result["video_attributes"] is not None
        assert result["video_attributes"].frame_rate == "24.00"

        assert len(result["audio_attributes"]) == 1
        assert result["audio_attributes"][0].language == "en-US"

        assert len(result["subtitle_attributes"]) == 1
        assert result["subtitle_attributes"][0].language == "en-US"

    def test_handles_empty_metadata(self):
        """Handles empty metadata gracefully."""
        raw_metadata = {}
        config = {}

        result = map_all_technical(raw_metadata, config)

        assert result["video_attributes"] is None
        assert result["audio_attributes"] == []
        assert result["subtitle_attributes"] == []

    def test_comprehensive_technical_example(self):
        """Tests with comprehensive technical data matching sample patterns."""
        raw_metadata = {
            "frame_rate": 2400,
            "video_dar": "16:9",
            "in_color_flag": "Y",
            "resolution": "1920x1080",
            "source_materials": {
                "component": [
                    {
                        "@componenttype": "Video",
                        "videoattributes": {
                            "framerate": 2400,
                            "aspectratio": "1.78",
                            "videocodec": "Apple Pro Res",
                        },
                    },
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {
                            "audiolanguage": "en-US",
                            "audiodescription": "Surround Front",
                            "fileposition": "1",
                        },
                    },
                    {
                        "@componenttype": "Audio",
                        "audioattributes": {
                            "audiolanguage": "en-US",
                            "DVS": "true",
                            "fileposition": "3",
                        },
                    },
                    {
                        "@componenttype": "Closed Captions",
                        "closedcaptionsattributes": {"language": "en-US"},
                    },
                    {
                        "@componenttype": "Subtitle",
                        "subtitleattributes": {"language": "es-419"},
                    },
                ]
            },
        }
        config = {}

        result = map_all_technical(raw_metadata, config)

        # Video
        assert result["video_attributes"] is not None
        assert result["video_attributes"].frame_rate == "24.00"
        assert result["video_attributes"].aspect_ratio == "16:9"
        assert result["video_attributes"].color_type == "Color"
        assert result["video_attributes"].width_pixels == 1920
        assert result["video_attributes"].height_pixels == 1080

        # Audio - should have 2 tracks
        assert len(result["audio_attributes"]) == 2
        # One should be DVS
        dvs_tracks = [
            a for a in result["audio_attributes"] if a.type == "VisuallyImpaired"
        ]
        assert len(dvs_tracks) == 1

        # Subtitles - should have CC and subtitle
        assert len(result["subtitle_attributes"]) == 2
        cc_tracks = [s for s in result["subtitle_attributes"] if s.type == "CC"]
        assert len(cc_tracks) == 1
