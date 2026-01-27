"""
Unit tests for the custom fields extraction module.

These tests verify that:
- Platform-specific genres are extracted with platform prefix
- Ad-related fields are captured
- Timing/segment data is preserved
- AFD and other technical fields are captured
- All field names are configuration-driven
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.extract_custom_fields import (
    extract,
    extract_advertising_fields,
    extract_category_fields,
    extract_field_value,
    extract_other_custom_fields,
    extract_rights_custom_fields,
    extract_technical_custom_fields,
    extract_timing_fields,
)


@pytest.mark.unit
class TestExtractFieldValue:
    """Tests for extract_field_value helper function"""

    def test_returns_string_value(self):
        """Returns string value when present."""
        raw = {"ad_category": "Entertainment:General"}
        result = extract_field_value(raw, "ad_category")
        assert result == "Entertainment:General"

    def test_returns_dict_value(self):
        """Returns dict value preserving structure."""
        raw = {"timelines": {"segment": [{"start": "00:00:00"}]}}
        result = extract_field_value(raw, "timelines")
        assert result == {"segment": [{"start": "00:00:00"}]}

    def test_returns_list_value(self):
        """Returns list value preserving structure."""
        raw = {"markers": [{"type": "End Credit", "time": "00:45:00"}]}
        result = extract_field_value(raw, "markers")
        assert result == [{"type": "End Credit", "time": "00:45:00"}]

    def test_returns_boolean_value(self):
        """Returns boolean value."""
        raw = {"needs_watermark": False}
        result = extract_field_value(raw, "needs_watermark")
        assert result is False

    def test_returns_numeric_value(self):
        """Returns numeric value."""
        raw = {"AFD": 10}
        result = extract_field_value(raw, "AFD")
        assert result == 10

    def test_returns_none_for_missing_field(self):
        """Returns None when field is not present."""
        raw = {"other_field": "value"}
        result = extract_field_value(raw, "ad_category")
        assert result is None

    def test_returns_none_for_none_value(self):
        """Returns None when field value is None."""
        raw = {"ad_category": None}
        result = extract_field_value(raw, "ad_category")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when field value is empty string."""
        raw = {"ad_category": ""}
        result = extract_field_value(raw, "ad_category")
        assert result is None

    def test_returns_none_for_whitespace_string(self):
        """Returns None when field value is whitespace only."""
        raw = {"ad_category": "   "}
        result = extract_field_value(raw, "ad_category")
        assert result is None

    def test_returns_none_for_empty_list(self):
        """Returns None when field value is empty list."""
        raw = {"markers": []}
        result = extract_field_value(raw, "markers")
        assert result is None

    def test_returns_none_for_empty_dict(self):
        """Returns None when field value is empty dict."""
        raw = {"timelines": {}}
        result = extract_field_value(raw, "timelines")
        assert result is None


@pytest.mark.unit
class TestExtractCategoryFields:
    """Tests for extract_category_fields function"""

    def test_extracts_multiple_fields(self):
        """Extracts multiple fields for a category."""
        raw = {
            "ad_category": "Entertainment:General",
            "ad_content_id": "L01039285",
            "other_field": "ignored",
        }
        field_names = ["ad_category", "ad_content_id"]
        result = extract_category_fields(raw, field_names)
        assert result == {
            "ad_category": "Entertainment:General",
            "ad_content_id": "L01039285",
        }

    def test_skips_missing_fields(self):
        """Skips fields that are not present."""
        raw = {"ad_category": "Entertainment:General"}
        field_names = ["ad_category", "ad_content_id", "cue_points"]
        result = extract_category_fields(raw, field_names)
        assert result == {"ad_category": "Entertainment:General"}

    def test_skips_empty_values(self):
        """Skips fields with empty values."""
        raw = {
            "ad_category": "Entertainment:General",
            "ad_content_id": "",
            "cue_points": [],
        }
        field_names = ["ad_category", "ad_content_id", "cue_points"]
        result = extract_category_fields(raw, field_names)
        assert result == {"ad_category": "Entertainment:General"}

    def test_returns_empty_dict_when_no_fields_found(self):
        """Returns empty dict when no fields are found."""
        raw = {"other_field": "value"}
        field_names = ["ad_category", "ad_content_id"]
        result = extract_category_fields(raw, field_names)
        assert result == {}

    def test_preserves_complex_structures(self):
        """Preserves complex nested structures."""
        raw = {
            "timelines": {
                "segments": {
                    "segment": [
                        {"segmentnumber": 1, "start": "00:59:59:22"},
                        {"segmentnumber": 2, "start": "01:11:15:22"},
                    ]
                }
            }
        }
        field_names = ["timelines"]
        result = extract_category_fields(raw, field_names)
        assert "timelines" in result
        assert result["timelines"]["segments"]["segment"][0]["segmentnumber"] == 1


@pytest.mark.unit
class TestExtractAdvertisingFields:
    """Tests for extract_advertising_fields function"""

    def test_extracts_ad_category(self):
        """Extracts ad_category field."""
        raw = {"ad_category": "Entertainment:General"}
        config = {}
        result = extract_advertising_fields(raw, config)
        assert result["ad_category"] == "Entertainment:General"

    def test_extracts_ad_content_id(self):
        """Extracts ad_content_id field."""
        raw = {"ad_content_id": "L01039285"}
        config = {}
        result = extract_advertising_fields(raw, config)
        assert result["ad_content_id"] == "L01039285"

    def test_extracts_cue_points(self):
        """Extracts cue_points field."""
        raw = {"cue_points": [{"time": "00:15:00"}, {"time": "00:30:00"}]}
        config = {}
        result = extract_advertising_fields(raw, config)
        assert result["cue_points"] == [{"time": "00:15:00"}, {"time": "00:30:00"}]

    def test_extracts_adopportunitiesmarkers(self):
        """Extracts adopportunitiesmarkers field."""
        raw = {"adopportunitiesmarkers": [{"marker": "ad1"}]}
        config = {}
        result = extract_advertising_fields(raw, config)
        assert result["adopportunitiesmarkers"] == [{"marker": "ad1"}]

    def test_uses_custom_field_names_from_config(self):
        """Uses custom field names from configuration."""
        raw = {"custom_ad_field": "custom_value"}
        config = {
            "custom_field_categories": {
                "advertising": ["custom_ad_field"],
            }
        }
        result = extract_advertising_fields(raw, config)
        assert result["custom_ad_field"] == "custom_value"

    def test_returns_empty_dict_when_no_ad_fields(self):
        """Returns empty dict when no advertising fields present."""
        raw = {"other_field": "value"}
        config = {}
        result = extract_advertising_fields(raw, config)
        assert result == {}


@pytest.mark.unit
class TestExtractTimingFields:
    """Tests for extract_timing_fields function"""

    def test_extracts_timelines(self):
        """Extracts timelines field with segment data."""
        raw = {
            "timelines": {
                "segments": {
                    "segment": [
                        {
                            "segmentnumber": 1,
                            "start": "00:59:59:22",
                            "end": "01:11:15:22",
                        },
                    ]
                }
            }
        }
        config = {}
        result = extract_timing_fields(raw, config)
        assert "timelines" in result
        assert result["timelines"]["segments"]["segment"][0]["segmentnumber"] == 1

    def test_extracts_timelines_df30(self):
        """Extracts timelines_df30 (drop-frame) field."""
        raw = {
            "timelines_df30": {
                "segments": {
                    "segment": [
                        {"segmentnumber": 1, "start": "00;59;59;22"},
                    ]
                }
            }
        }
        config = {}
        result = extract_timing_fields(raw, config)
        assert "timelines_df30" in result

    def test_extracts_markers(self):
        """Extracts markers field."""
        raw = {
            "markers": {
                "marker": [
                    {"@type": "Segment", "#text": "End Credit"},
                ]
            }
        }
        config = {}
        result = extract_timing_fields(raw, config)
        assert "markers" in result
        assert result["markers"]["marker"][0]["#text"] == "End Credit"

    def test_extracts_segments(self):
        """Extracts standalone segments field."""
        raw = {
            "segments": [
                {"number": 1, "start": "00:00:00", "end": "00:15:00"},
            ]
        }
        config = {}
        result = extract_timing_fields(raw, config)
        assert "segments" in result

    def test_uses_custom_field_names_from_config(self):
        """Uses custom field names from configuration."""
        raw = {"custom_timing_field": {"data": "value"}}
        config = {
            "custom_field_categories": {
                "timing": ["custom_timing_field"],
            }
        }
        result = extract_timing_fields(raw, config)
        assert result["custom_timing_field"] == {"data": "value"}

    def test_returns_empty_dict_when_no_timing_fields(self):
        """Returns empty dict when no timing fields present."""
        raw = {"other_field": "value"}
        config = {}
        result = extract_timing_fields(raw, config)
        assert result == {}


@pytest.mark.unit
class TestExtractTechnicalCustomFields:
    """Tests for extract_technical_custom_fields function"""

    def test_extracts_afd(self):
        """Extracts AFD (Active Format Description) field."""
        raw = {"AFD": "10"}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["AFD"] == "10"

    def test_extracts_afd_as_numeric(self):
        """Extracts AFD as numeric value."""
        raw = {"AFD": 10}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["AFD"] == 10

    def test_extracts_needs_watermark(self):
        """Extracts needs_watermark flag."""
        raw = {"needs_watermark": False}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["needs_watermark"] is False

    def test_extracts_needs_watermark_true(self):
        """Extracts needs_watermark flag when true."""
        raw = {"needs_watermark": True}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["needs_watermark"] is True

    def test_extracts_semitextless(self):
        """Extracts semitextless flag."""
        raw = {"semitextless": False}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["semitextless"] is False

    def test_extracts_conform_materials_list(self):
        """Extracts conform_materials_list field."""
        raw = {"conform_materials_list": "L01039285"}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["conform_materials_list"] == "L01039285"

    def test_extracts_format(self):
        """Extracts format field."""
        raw = {"format": "HD"}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result["format"] == "HD"

    def test_uses_custom_field_names_from_config(self):
        """Uses custom field names from configuration."""
        raw = {"custom_tech_field": "value"}
        config = {
            "custom_field_categories": {
                "technical": ["custom_tech_field"],
            }
        }
        result = extract_technical_custom_fields(raw, config)
        assert result["custom_tech_field"] == "value"

    def test_returns_empty_dict_when_no_technical_fields(self):
        """Returns empty dict when no technical fields present."""
        raw = {"other_field": "value"}
        config = {}
        result = extract_technical_custom_fields(raw, config)
        assert result == {}


@pytest.mark.unit
class TestExtractRightsCustomFields:
    """Tests for extract_rights_custom_fields function"""

    def test_extracts_platform_rights(self):
        """Extracts platform_rights field."""
        raw = {"platform_rights": "exclusive"}
        config = {}
        result = extract_rights_custom_fields(raw, config)
        assert result["platform_rights"] == "exclusive"

    def test_extracts_carousel(self):
        """Extracts carousel field."""
        raw = {"carousel": "featured"}
        config = {}
        result = extract_rights_custom_fields(raw, config)
        assert result["carousel"] == "featured"

    def test_uses_custom_field_names_from_config(self):
        """Uses custom field names from configuration."""
        raw = {"custom_rights_field": "value"}
        config = {
            "custom_field_categories": {
                "rights": ["custom_rights_field"],
            }
        }
        result = extract_rights_custom_fields(raw, config)
        assert result["custom_rights_field"] == "value"

    def test_returns_empty_dict_when_no_rights_fields(self):
        """Returns empty dict when no rights fields present."""
        raw = {"other_field": "value"}
        config = {}
        result = extract_rights_custom_fields(raw, config)
        assert result == {}


@pytest.mark.unit
class TestExtractOtherCustomFields:
    """Tests for extract_other_custom_fields function"""

    def test_extracts_placement(self):
        """Extracts placement field with complex structure."""
        raw = {
            "placement": {
                "placementplaylistevent": [
                    {
                        "@Index": "1",
                        "material_title": "Test Title",
                        "material_type": "Episode",
                    }
                ]
            }
        }
        config = {}
        result = extract_other_custom_fields(raw, config)
        assert "placement" in result
        assert result["placement"]["placementplaylistevent"][0]["@Index"] == "1"

    def test_uses_custom_field_names_from_config(self):
        """Uses custom field names from configuration."""
        raw = {"custom_other_field": "value"}
        config = {
            "custom_field_categories": {
                "other": ["custom_other_field"],
            }
        }
        result = extract_other_custom_fields(raw, config)
        assert result["custom_other_field"] == "value"

    def test_returns_empty_dict_when_no_other_fields(self):
        """Returns empty dict when no other fields present."""
        raw = {"different_field": "value"}
        config = {}
        result = extract_other_custom_fields(raw, config)
        assert result == {}


@pytest.mark.unit
class TestExtract:
    """Tests for the main extract function"""

    def test_extracts_platform_genres(self):
        """Extracts platform-specific genres with platform prefix."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "Amazon", "#text": "Drama"},
                    {"@type": "Apple", "#text": "Drama"},
                    {"@type": "Roku", "#text": "Drama - Thriller"},
                ]
            }
        }
        config = {
            "classification_mappings": {
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            }
        }
        result = extract(raw, config)
        assert "platform_genres" in result
        assert "amazon" in result["platform_genres"]
        assert "apple" in result["platform_genres"]
        assert "roku" in result["platform_genres"]
        assert result["platform_genres"]["amazon"] == ["Drama"]

    def test_extracts_advertising_category(self):
        """Extracts advertising fields into advertising category."""
        raw = {
            "ad_category": "Entertainment:General",
            "ad_content_id": "L01039285",
        }
        config = {}
        result = extract(raw, config)
        assert "advertising" in result
        assert result["advertising"]["ad_category"] == "Entertainment:General"
        assert result["advertising"]["ad_content_id"] == "L01039285"

    def test_extracts_timing_category(self):
        """Extracts timing fields into timing category."""
        raw = {
            "timelines": {"segments": {"segment": [{"start": "00:00:00"}]}},
            "markers": {"marker": [{"#text": "End Credit"}]},
        }
        config = {}
        result = extract(raw, config)
        assert "timing" in result
        assert "timelines" in result["timing"]
        assert "markers" in result["timing"]

    def test_extracts_technical_category(self):
        """Extracts technical fields into technical category."""
        raw = {
            "AFD": "10",
            "needs_watermark": False,
            "semitextless": False,
        }
        config = {}
        result = extract(raw, config)
        assert "technical" in result
        assert result["technical"]["AFD"] == "10"
        assert result["technical"]["needs_watermark"] is False

    def test_extracts_rights_category(self):
        """Extracts rights fields into rights category."""
        raw = {
            "platform_rights": "exclusive",
            "carousel": "featured",
        }
        config = {}
        result = extract(raw, config)
        assert "rights" in result
        assert result["rights"]["platform_rights"] == "exclusive"

    def test_extracts_other_category(self):
        """Extracts other fields into other category."""
        raw = {
            "placement": {"data": "value"},
        }
        config = {}
        result = extract(raw, config)
        assert "other" in result
        assert result["other"]["placement"] == {"data": "value"}

    def test_omits_empty_categories(self):
        """Omits categories that have no fields."""
        raw = {"ad_category": "Entertainment:General"}
        config = {}
        result = extract(raw, config)
        assert "advertising" in result
        assert "timing" not in result
        assert "technical" not in result
        assert "rights" not in result
        assert "other" not in result
        assert "platform_genres" not in result

    def test_returns_empty_dict_when_no_custom_fields(self):
        """Returns empty dict when no custom fields present."""
        raw = {"title": "Test Title", "description": "Test Description"}
        config = {}
        result = extract(raw, config)
        assert result == {}

    def test_comprehensive_extraction(self):
        """Tests comprehensive extraction with all categories."""
        raw = {
            # Platform genres
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "Amazon", "#text": "Drama - Crime"},
                    {"@type": "Apple", "#text": "Drama"},
                ]
            },
            # Advertising
            "ad_category": "Entertainment:General",
            "ad_content_id": "L01039285",
            "cue_points": [{"time": "00:15:00"}],
            # Timing
            "timelines": {
                "segments": {
                    "segment": [
                        {
                            "segmentnumber": 1,
                            "start": "00:59:59:22",
                            "end": "01:11:15:22",
                        },
                    ]
                }
            },
            "markers": {"marker": [{"@type": "Segment", "#text": "End Credit"}]},
            # Technical
            "AFD": "10",
            "needs_watermark": False,
            "semitextless": False,
            "conform_materials_list": "L01039285",
            # Rights
            "platform_rights": "exclusive",
            # Other
            "placement": {"placementplaylistevent": [{"@Index": "1"}]},
        }
        config = {
            "classification_mappings": {
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            }
        }
        result = extract(raw, config)

        # Verify all categories present
        assert "platform_genres" in result
        assert "advertising" in result
        assert "timing" in result
        assert "technical" in result
        assert "rights" in result
        assert "other" in result

        # Verify platform genres (excludes default)
        assert "amazon" in result["platform_genres"]
        assert "apple" in result["platform_genres"]
        assert result["platform_genres"]["amazon"] == ["Drama - Crime"]

        # Verify advertising
        assert result["advertising"]["ad_category"] == "Entertainment:General"
        assert result["advertising"]["ad_content_id"] == "L01039285"
        assert result["advertising"]["cue_points"] == [{"time": "00:15:00"}]

        # Verify timing
        assert "timelines" in result["timing"]
        assert "markers" in result["timing"]

        # Verify technical
        assert result["technical"]["AFD"] == "10"
        assert result["technical"]["needs_watermark"] is False
        assert result["technical"]["semitextless"] is False
        assert result["technical"]["conform_materials_list"] == "L01039285"

        # Verify rights
        assert result["rights"]["platform_rights"] == "exclusive"

        # Verify other
        assert "placement" in result["other"]

    def test_uses_custom_config_for_all_categories(self):
        """Uses custom configuration for all field categories."""
        raw = {
            "custom_ad": "ad_value",
            "custom_timing": "timing_value",
            "custom_tech": "tech_value",
            "custom_rights": "rights_value",
            "custom_other": "other_value",
        }
        config = {
            "custom_field_categories": {
                "advertising": ["custom_ad"],
                "timing": ["custom_timing"],
                "technical": ["custom_tech"],
                "rights": ["custom_rights"],
                "other": ["custom_other"],
            }
        }
        result = extract(raw, config)

        assert result["advertising"]["custom_ad"] == "ad_value"
        assert result["timing"]["custom_timing"] == "timing_value"
        assert result["technical"]["custom_tech"] == "tech_value"
        assert result["rights"]["custom_rights"] == "rights_value"
        assert result["other"]["custom_other"] == "other_value"
