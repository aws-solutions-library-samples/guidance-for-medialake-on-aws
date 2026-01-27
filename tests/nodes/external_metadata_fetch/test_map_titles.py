"""
Unit tests for the title and description field mapper module.

These tests verify that:
- map_localized_info() correctly creates LocalizedInfo elements
- Title fields are mapped correctly using configuration
- Description fields are mapped correctly using configuration
- Language attribute is set correctly from config
- Missing fields are handled gracefully
- Keywords are parsed correctly from various formats
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_titles import (
    get_string_value,
    map_copyright_line,
    map_keywords,
    map_localized_info,
    map_summary_190,
    map_summary_4000,
    map_title_display_19,
    map_title_display_unlimited,
    map_title_internal_alias,
    parse_keywords,
)
from nodes.external_metadata_fetch.normalizers.mec_schema import LocalizedInfo


@pytest.mark.unit
class TestGetStringValue:
    """Tests for get_string_value helper function"""

    def test_returns_value_for_valid_string(self):
        """Returns the string value when present."""
        raw = {"title": "Test Title"}
        result = get_string_value(raw, "title")
        assert result == "Test Title"

    def test_returns_none_for_none_field_name(self):
        """Returns None when field_name is None."""
        raw = {"title": "Test Title"}
        result = get_string_value(raw, None)
        assert result is None

    def test_returns_none_for_missing_field(self):
        """Returns None when field is not in metadata."""
        raw = {"other_field": "value"}
        result = get_string_value(raw, "title")
        assert result is None

    def test_returns_none_for_none_value(self):
        """Returns None when field value is None."""
        raw = {"title": None}
        result = get_string_value(raw, "title")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when field value is empty string."""
        raw = {"title": ""}
        result = get_string_value(raw, "title")
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Returns None when field value is whitespace only."""
        raw = {"title": "   "}
        result = get_string_value(raw, "title")
        assert result is None

    def test_strips_whitespace(self):
        """Strips leading and trailing whitespace."""
        raw = {"title": "  Test Title  "}
        result = get_string_value(raw, "title")
        assert result == "Test Title"

    def test_converts_non_string_to_string(self):
        """Converts non-string values to string."""
        raw = {"number": 12345}
        result = get_string_value(raw, "number")
        assert result == "12345"


@pytest.mark.unit
class TestParseKeywords:
    """Tests for parse_keywords helper function"""

    def test_parses_comma_separated_string(self):
        """Parses comma-separated keywords string."""
        raw = {"keywords": "Science Fiction, Adventure, Drama"}
        result = parse_keywords(raw, "keywords")
        assert result == ["Science Fiction", "Adventure", "Drama"]

    def test_parses_list_of_strings(self):
        """Parses list of keyword strings."""
        raw = {"keywords": ["Science Fiction", "Adventure", "Drama"]}
        result = parse_keywords(raw, "keywords")
        assert result == ["Science Fiction", "Adventure", "Drama"]

    def test_returns_empty_list_for_none_field_name(self):
        """Returns empty list when field_name is None."""
        raw = {"keywords": "Science Fiction, Adventure"}
        result = parse_keywords(raw, None)
        assert result == []

    def test_returns_empty_list_for_missing_field(self):
        """Returns empty list when field is not in metadata."""
        raw = {"other_field": "value"}
        result = parse_keywords(raw, "keywords")
        assert result == []

    def test_returns_empty_list_for_none_value(self):
        """Returns empty list when field value is None."""
        raw = {"keywords": None}
        result = parse_keywords(raw, "keywords")
        assert result == []

    def test_returns_empty_list_for_empty_string(self):
        """Returns empty list when field value is empty string."""
        raw = {"keywords": ""}
        result = parse_keywords(raw, "keywords")
        assert result == []

    def test_strips_whitespace_from_keywords(self):
        """Strips whitespace from each keyword."""
        raw = {"keywords": "  Science Fiction  ,  Adventure  ,  Drama  "}
        result = parse_keywords(raw, "keywords")
        assert result == ["Science Fiction", "Adventure", "Drama"]

    def test_filters_empty_keywords(self):
        """Filters out empty keywords from list."""
        raw = {"keywords": ["Science Fiction", "", "Adventure", None, "Drama"]}
        result = parse_keywords(raw, "keywords")
        assert result == ["Science Fiction", "Adventure", "Drama"]

    def test_handles_single_keyword(self):
        """Handles single keyword without comma."""
        raw = {"keywords": "Drama"}
        result = parse_keywords(raw, "keywords")
        assert result == ["Drama"]


@pytest.mark.unit
class TestMapTitleDisplayUnlimited:
    """Tests for map_title_display_unlimited function"""

    def test_maps_title_field(self):
        """Maps configured title field to TitleDisplayUnlimited."""
        raw = {"title": "The mysterious journey begins with unexpected discoveries..."}
        config = {"title_mappings": {"title_field": "title"}}
        result = map_title_display_unlimited(raw, config)
        assert result == "The mysterious journey begins with unexpected discoveries..."

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"episode_title": "Custom Title"}
        config = {"title_mappings": {"title_field": "episode_title"}}
        result = map_title_display_unlimited(raw, config)
        assert result == "Custom Title"

    def test_uses_default_field_name(self):
        """Uses 'title' as default field name."""
        raw = {"title": "Default Title"}
        config = {}
        result = map_title_display_unlimited(raw, config)
        assert result == "Default Title"

    def test_returns_none_for_missing_field(self):
        """Returns None when title field is missing."""
        raw = {"other_field": "value"}
        config = {"title_mappings": {"title_field": "title"}}
        result = map_title_display_unlimited(raw, config)
        assert result is None


@pytest.mark.unit
class TestMapTitleDisplay19:
    """Tests for map_title_display_19 function"""

    def test_maps_title_brief_field(self):
        """Maps configured title_brief field to TitleDisplay19."""
        raw = {"titlebrief": "Episode 101"}
        config = {"title_mappings": {"title_brief_field": "titlebrief"}}
        result = map_title_display_19(raw, config)
        assert result == "Episode 101"

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"short_title": "Short Title"}
        config = {"title_mappings": {"title_brief_field": "short_title"}}
        result = map_title_display_19(raw, config)
        assert result == "Short Title"

    def test_uses_default_field_name(self):
        """Uses 'titlebrief' as default field name."""
        raw = {"titlebrief": "Brief Title"}
        config = {}
        result = map_title_display_19(raw, config)
        assert result == "Brief Title"

    def test_returns_none_for_missing_field(self):
        """Returns None when title_brief field is missing."""
        raw = {"other_field": "value"}
        config = {"title_mappings": {"title_brief_field": "titlebrief"}}
        result = map_title_display_19(raw, config)
        assert result is None


@pytest.mark.unit
class TestMapTitleInternalAlias:
    """Tests for map_title_internal_alias function"""

    def test_maps_dedicated_internal_alias_field(self):
        """Maps dedicated internal alias field when configured."""
        raw = {"internal_title": "Internal Alias", "titlebrief": "Brief Title"}
        config = {
            "title_mappings": {
                "title_internal_alias_field": "internal_title",
                "title_brief_field": "titlebrief",
            }
        }
        result = map_title_internal_alias(raw, config)
        assert result == "Internal Alias"

    def test_falls_back_to_title_brief(self):
        """Falls back to title_brief when internal alias not configured."""
        raw = {"titlebrief": "Brief Title"}
        config = {"title_mappings": {"title_brief_field": "titlebrief"}}
        result = map_title_internal_alias(raw, config)
        assert result == "Brief Title"

    def test_respects_use_brief_as_internal_alias_false(self):
        """Does not fall back when use_brief_as_internal_alias is False."""
        raw = {"titlebrief": "Brief Title"}
        config = {
            "title_mappings": {
                "title_brief_field": "titlebrief",
                "use_brief_as_internal_alias": False,
            }
        }
        result = map_title_internal_alias(raw, config)
        assert result is None

    def test_returns_none_when_no_fields_available(self):
        """Returns None when no internal alias or brief title available."""
        raw = {"other_field": "value"}
        config = {"title_mappings": {"use_brief_as_internal_alias": False}}
        result = map_title_internal_alias(raw, config)
        assert result is None


@pytest.mark.unit
class TestMapSummary190:
    """Tests for map_summary_190 function"""

    def test_maps_short_description_field(self):
        """Maps configured short_description field to Summary190."""
        raw = {"short_description": "A protagonist embarks on an adventure..."}
        config = {
            "description_mappings": {"short_description_field": "short_description"}
        }
        result = map_summary_190(raw, config)
        assert result == "A protagonist embarks on an adventure..."

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"brief_desc": "Brief description"}
        config = {"description_mappings": {"short_description_field": "brief_desc"}}
        result = map_summary_190(raw, config)
        assert result == "Brief description"

    def test_uses_default_field_name(self):
        """Uses 'short_description' as default field name."""
        raw = {"short_description": "Default short desc"}
        config = {}
        result = map_summary_190(raw, config)
        assert result == "Default short desc"

    def test_returns_none_for_missing_field(self):
        """Returns None when short_description field is missing."""
        raw = {"other_field": "value"}
        config = {
            "description_mappings": {"short_description_field": "short_description"}
        }
        result = map_summary_190(raw, config)
        assert result is None


@pytest.mark.unit
class TestMapSummary4000:
    """Tests for map_summary_4000 function"""

    def test_maps_long_description_field(self):
        """Maps configured long_description field to Summary4000."""
        raw = {
            "long_description": "In a world of wonder, our hero discovers secrets..."
        }
        config = {
            "description_mappings": {"long_description_field": "long_description"}
        }
        result = map_summary_4000(raw, config)
        assert result == "In a world of wonder, our hero discovers secrets..."

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"full_desc": "Full description"}
        config = {"description_mappings": {"long_description_field": "full_desc"}}
        result = map_summary_4000(raw, config)
        assert result == "Full description"

    def test_uses_default_field_name(self):
        """Uses 'long_description' as default field name."""
        raw = {"long_description": "Default long desc"}
        config = {}
        result = map_summary_4000(raw, config)
        assert result == "Default long desc"

    def test_returns_none_for_missing_field(self):
        """Returns None when long_description field is missing."""
        raw = {"other_field": "value"}
        config = {
            "description_mappings": {"long_description_field": "long_description"}
        }
        result = map_summary_4000(raw, config)
        assert result is None


@pytest.mark.unit
class TestMapCopyrightLine:
    """Tests for map_copyright_line function"""

    def test_maps_copyright_field(self):
        """Maps configured copyright field to CopyrightLine."""
        raw = {"copyright_holder": "© 2022 Example Productions"}
        config = {"copyright_field": "copyright_holder"}
        result = map_copyright_line(raw, config)
        assert result == "© 2022 Example Productions"

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"copyright_notice": "© 2022 Custom"}
        config = {"copyright_field": "copyright_notice"}
        result = map_copyright_line(raw, config)
        assert result == "© 2022 Custom"

    def test_uses_default_field_name(self):
        """Uses 'copyright_holder' as default field name."""
        raw = {"copyright_holder": "Default Copyright"}
        config = {}
        result = map_copyright_line(raw, config)
        assert result == "Default Copyright"

    def test_returns_none_for_missing_field(self):
        """Returns None when copyright field is missing."""
        raw = {"other_field": "value"}
        config = {"copyright_field": "copyright_holder"}
        result = map_copyright_line(raw, config)
        assert result is None


@pytest.mark.unit
class TestMapKeywords:
    """Tests for map_keywords function"""

    def test_maps_keywords_field(self):
        """Maps configured keywords field to list of keywords."""
        raw = {"keywords": "Science Fiction, Adventure, Drama"}
        config = {"keywords_field": "keywords"}
        result = map_keywords(raw, config)
        assert result == ["Science Fiction", "Adventure", "Drama"]

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"tags": "Tag1, Tag2"}
        config = {"keywords_field": "tags"}
        result = map_keywords(raw, config)
        assert result == ["Tag1", "Tag2"]

    def test_uses_default_field_name(self):
        """Uses 'keywords' as default field name."""
        raw = {"keywords": "Default, Keywords"}
        config = {}
        result = map_keywords(raw, config)
        assert result == ["Default", "Keywords"]

    def test_returns_empty_list_for_missing_field(self):
        """Returns empty list when keywords field is missing."""
        raw = {"other_field": "value"}
        config = {"keywords_field": "keywords"}
        result = map_keywords(raw, config)
        assert result == []


@pytest.mark.unit
class TestMapLocalizedInfo:
    """Tests for map_localized_info function"""

    def test_creates_localized_info_with_all_fields(self):
        """Creates LocalizedInfo with all title and description fields."""
        raw = {
            "title": "The mysterious journey begins with unexpected discoveries...",
            "titlebrief": "Episode 101",
            "short_description": "A protagonist embarks on an adventure...",
            "long_description": "In a world of wonder, our hero discovers secrets...",
            "copyright_holder": "© 2022 Example Productions",
            "keywords": "Science Fiction, Adventure, Drama",
        }
        config = {
            "default_language": "en-US",
            "title_mappings": {
                "title_field": "title",
                "title_brief_field": "titlebrief",
            },
            "description_mappings": {
                "short_description_field": "short_description",
                "long_description_field": "long_description",
            },
            "copyright_field": "copyright_holder",
            "keywords_field": "keywords",
        }

        result = map_localized_info(raw, config)

        assert len(result) == 1
        localized = result[0]
        assert isinstance(localized, LocalizedInfo)
        assert localized.language == "en-US"
        assert (
            localized.title_display_unlimited
            == "The mysterious journey begins with unexpected discoveries..."
        )
        assert localized.title_display_19 == "Episode 101"
        assert localized.title_internal_alias == "Episode 101"  # Falls back to brief
        assert localized.summary_190 == "A protagonist embarks on an adventure..."
        assert (
            localized.summary_4000
            == "In a world of wonder, our hero discovers secrets..."
        )
        assert localized.copyright_line == "© 2022 Example Productions"
        assert localized.keywords == ["Science Fiction", "Adventure", "Drama"]

    def test_sets_language_from_config(self):
        """Sets language attribute from configuration."""
        raw = {"title": "Test Title"}
        config = {
            "default_language": "es-ES",
            "title_mappings": {"title_field": "title"},
        }

        result = map_localized_info(raw, config)

        assert len(result) == 1
        assert result[0].language == "es-ES"

    def test_uses_default_language_when_not_configured(self):
        """Uses 'en-US' as default language."""
        raw = {"title": "Test Title"}
        config = {"title_mappings": {"title_field": "title"}}

        result = map_localized_info(raw, config)

        assert len(result) == 1
        assert result[0].language == "en-US"

    def test_returns_empty_list_when_no_content(self):
        """Returns empty list when no title or description fields found."""
        raw = {"other_field": "value"}
        config = {
            "title_mappings": {"title_field": "title"},
            "description_mappings": {"short_description_field": "short_description"},
        }

        result = map_localized_info(raw, config)

        assert result == []

    def test_handles_partial_fields(self):
        """Creates LocalizedInfo with only available fields."""
        raw = {
            "title": "Test Title",
            "short_description": "Short desc",
        }
        config = {
            "title_mappings": {"title_field": "title"},
            "description_mappings": {
                "short_description_field": "short_description",
                "long_description_field": "long_description",
            },
        }

        result = map_localized_info(raw, config)

        assert len(result) == 1
        localized = result[0]
        assert localized.title_display_unlimited == "Test Title"
        assert localized.summary_190 == "Short desc"
        assert localized.summary_4000 is None
        assert localized.copyright_line is None

    def test_handles_empty_config(self):
        """Works with empty configuration using defaults."""
        raw = {
            "title": "Default Title",
            "titlebrief": "Brief",
            "short_description": "Short",
            "long_description": "Long",
        }
        config = {}

        result = map_localized_info(raw, config)

        assert len(result) == 1
        localized = result[0]
        assert localized.language == "en-US"
        assert localized.title_display_unlimited == "Default Title"
        assert localized.title_display_19 == "Brief"
        assert localized.summary_190 == "Short"
        assert localized.summary_4000 == "Long"

    def test_handles_whitespace_values(self):
        """Handles whitespace-only values as missing."""
        raw = {
            "title": "Valid Title",
            "titlebrief": "   ",  # Whitespace only
            "short_description": "",  # Empty
        }
        config = {
            "title_mappings": {
                "title_field": "title",
                "title_brief_field": "titlebrief",
            },
            "description_mappings": {
                "short_description_field": "short_description",
            },
        }

        result = map_localized_info(raw, config)

        assert len(result) == 1
        localized = result[0]
        assert localized.title_display_unlimited == "Valid Title"
        assert localized.title_display_19 is None
        assert localized.summary_190 is None

    def test_to_dict_serialization(self):
        """Verifies LocalizedInfo to_dict works correctly."""
        raw = {
            "title": "Test Title",
            "keywords": "Key1, Key2",
        }
        config = {
            "default_language": "en-US",
            "title_mappings": {"title_field": "title"},
            "keywords_field": "keywords",
        }

        result = map_localized_info(raw, config)

        assert len(result) == 1
        dict_result = result[0].to_dict()
        assert dict_result["Language"] == "en-US"
        assert dict_result["TitleDisplayUnlimited"] == "Test Title"
        assert dict_result["Keywords"] == ["Key1", "Key2"]

    def test_comprehensive_config_example(self):
        """Tests with comprehensive configuration matching generic sample."""
        raw = {
            "title": "The mysterious journey begins as our hero discovers hidden secrets",
            "titlebrief": "Episode 101",
            "short_description": "A protagonist embarks on an adventure in a distant land.",
            "long_description": "In a world of wonder, our hero discovers secrets that will change everything forever.",
            "copyright_holder": "© 2022 Example Productions, LLC",
            "keywords": "Science Fiction, Adventure, Drama, Mystery, Fantasy",
        }
        config = {
            "default_language": "en-US",
            "title_mappings": {
                "title_field": "title",
                "title_brief_field": "titlebrief",
                "use_brief_as_internal_alias": True,
            },
            "description_mappings": {
                "short_description_field": "short_description",
                "long_description_field": "long_description",
            },
            "copyright_field": "copyright_holder",
            "keywords_field": "keywords",
        }

        result = map_localized_info(raw, config)

        assert len(result) == 1
        localized = result[0]

        # Verify all fields
        assert localized.language == "en-US"
        assert "mysterious journey begins" in localized.title_display_unlimited
        assert localized.title_display_19 == "Episode 101"
        assert localized.title_internal_alias == "Episode 101"
        assert "protagonist embarks on an adventure" in localized.summary_190
        assert "world of wonder" in localized.summary_4000
        assert "© 2022 Example Productions" in localized.copyright_line
        assert len(localized.keywords) == 5
        assert "Science Fiction" in localized.keywords
        assert "Adventure" in localized.keywords

    def test_only_keywords_creates_localized_info(self):
        """Creates LocalizedInfo when only keywords are present."""
        raw = {"keywords": "Tag1, Tag2"}
        config = {"keywords_field": "keywords"}

        result = map_localized_info(raw, config)

        assert len(result) == 1
        assert result[0].keywords == ["Tag1", "Tag2"]
        assert result[0].title_display_unlimited is None

    def test_only_copyright_creates_localized_info(self):
        """Creates LocalizedInfo when only copyright is present."""
        raw = {"copyright_holder": "© 2022 Test"}
        config = {"copyright_field": "copyright_holder"}

        result = map_localized_info(raw, config)

        assert len(result) == 1
        assert result[0].copyright_line == "© 2022 Test"
        assert result[0].title_display_unlimited is None
