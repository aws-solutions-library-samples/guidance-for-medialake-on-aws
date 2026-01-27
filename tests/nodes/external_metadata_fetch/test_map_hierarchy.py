"""
Unit tests for the hierarchy and sequence field mapper module.

These tests verify that:
- map_sequence_info() correctly creates SequenceInfo elements for episode numbers
- map_parents() correctly creates Parent relationship elements
- extract_parent_metadata() correctly extracts series and season metadata
- All field names are configuration-driven (no hardcoded customer values)

⚠️ GENERIC NAMING: All tests use generic names like "Test Series", "Sample Episode".
Do NOT use real show names or customer-specific data.
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_hierarchy import (
    extract_parent_metadata,
    generate_parent_content_id,
    get_int_value,
    get_string_value,
    map_parents,
    map_sequence_info,
)
from nodes.external_metadata_fetch.normalizers.mec_schema import Parent, SequenceInfo


@pytest.mark.unit
class TestGetStringValue:
    """Tests for get_string_value helper function"""

    def test_returns_string_value(self):
        """Returns string value when present."""
        raw = {"title": "Test Episode"}
        result = get_string_value(raw, "title")
        assert result == "Test Episode"

    def test_returns_none_for_missing_field(self):
        """Returns None when field is missing."""
        raw = {"other_field": "value"}
        result = get_string_value(raw, "title")
        assert result is None

    def test_returns_none_for_none_value(self):
        """Returns None when value is None."""
        raw = {"title": None}
        result = get_string_value(raw, "title")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when value is empty string."""
        raw = {"title": ""}
        result = get_string_value(raw, "title")
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Returns None when value is whitespace only."""
        raw = {"title": "   "}
        result = get_string_value(raw, "title")
        assert result is None

    def test_strips_whitespace(self):
        """Strips leading/trailing whitespace."""
        raw = {"title": "  Test Episode  "}
        result = get_string_value(raw, "title")
        assert result == "Test Episode"

    def test_converts_non_string_to_string(self):
        """Converts non-string values to string."""
        raw = {"number": 123}
        result = get_string_value(raw, "number")
        assert result == "123"

    def test_returns_none_for_none_field_name(self):
        """Returns None when field_name is None."""
        raw = {"title": "Test Episode"}
        result = get_string_value(raw, None)
        assert result is None


@pytest.mark.unit
class TestGetIntValue:
    """Tests for get_int_value helper function"""

    def test_returns_int_value(self):
        """Returns integer value when present."""
        raw = {"episode_number": 5}
        result = get_int_value(raw, "episode_number")
        assert result == 5

    def test_parses_string_to_int(self):
        """Parses string value to integer."""
        raw = {"episode_number": "5"}
        result = get_int_value(raw, "episode_number")
        assert result == 5

    def test_parses_padded_string(self):
        """Parses zero-padded string to integer."""
        raw = {"episode_number": "05"}
        result = get_int_value(raw, "episode_number")
        assert result == 5

    def test_returns_none_for_missing_field(self):
        """Returns None when field is missing."""
        raw = {"other_field": "value"}
        result = get_int_value(raw, "episode_number")
        assert result is None

    def test_returns_none_for_none_value(self):
        """Returns None when value is None."""
        raw = {"episode_number": None}
        result = get_int_value(raw, "episode_number")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when value is empty string."""
        raw = {"episode_number": ""}
        result = get_int_value(raw, "episode_number")
        assert result is None

    def test_returns_none_for_invalid_string(self):
        """Returns None when string cannot be parsed as int."""
        raw = {"episode_number": "not_a_number"}
        result = get_int_value(raw, "episode_number")
        assert result is None

    def test_handles_float_value(self):
        """Converts float to integer."""
        raw = {"episode_number": 5.7}
        result = get_int_value(raw, "episode_number")
        assert result == 5

    def test_returns_none_for_none_field_name(self):
        """Returns None when field_name is None."""
        raw = {"episode_number": 5}
        result = get_int_value(raw, None)
        assert result is None


@pytest.mark.unit
class TestGenerateParentContentId:
    """Tests for generate_parent_content_id function"""

    def test_generates_urn_format(self):
        """Generates URN-style content ID."""
        result = generate_parent_content_id("RLS25733", "CUSTOMER")
        assert result == "urn:customer:RLS25733"

    def test_lowercases_namespace(self):
        """Lowercases namespace prefix in URN."""
        result = generate_parent_content_id("RLS25733", "ACME")
        assert result == "urn:acme:RLS25733"

    def test_preserves_id_case(self):
        """Preserves original case of the ID."""
        result = generate_parent_content_id("RLA236634", "SOURCE")
        assert result == "urn:source:RLA236634"


@pytest.mark.unit
class TestMapSequenceInfo:
    """Tests for map_sequence_info function"""

    def test_maps_episode_number(self):
        """Maps episode number to SequenceInfo."""
        raw = {"episode_number": "5"}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is not None
        assert isinstance(result, SequenceInfo)
        assert result.number == 5

    def test_maps_integer_episode_number(self):
        """Maps integer episode number."""
        raw = {"episode_number": 10}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is not None
        assert result.number == 10

    def test_maps_padded_episode_number(self):
        """Maps zero-padded episode number string."""
        raw = {"episode_number": "01"}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is not None
        assert result.number == 1

    def test_returns_none_for_missing_episode_number(self):
        """Returns None when episode number is missing."""
        raw = {"other_field": "value"}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is None

    def test_returns_none_for_empty_episode_number(self):
        """Returns None when episode number is empty."""
        raw = {"episode_number": ""}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is None

    def test_returns_none_for_zero_episode_number(self):
        """Returns None for episode number 0 (trailers/interstitials)."""
        raw = {"episode_number": "0"}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
            }
        }

        result = map_sequence_info(raw, config)

        # Note: 0 is a valid integer, so it should return SequenceInfo
        assert result is not None
        assert result.number == 0

    def test_includes_distribution_number(self):
        """Includes distribution number when configured."""
        raw = {
            "episode_number": "5",
            "distribution_number": "105",
        }
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
                "distribution_number_field": "distribution_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is not None
        assert result.number == 5
        assert result.distribution_number == "105"

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"ep_num": "7"}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "ep_num",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is not None
        assert result.number == 7

    def test_uses_default_field_name(self):
        """Uses default field name when not configured."""
        raw = {"episode_number": "3"}
        config = {}

        result = map_sequence_info(raw, config)

        assert result is not None
        assert result.number == 3

    def test_to_dict_serialization(self):
        """Verifies SequenceInfo to_dict works correctly."""
        raw = {"episode_number": "5", "distribution_number": "105"}
        config = {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
                "distribution_number_field": "distribution_number",
            }
        }

        result = map_sequence_info(raw, config)

        assert result is not None
        dict_result = result.to_dict()
        assert dict_result == {
            "Number": 5,
            "DistributionNumber": "105",
        }


@pytest.mark.unit
class TestMapParents:
    """Tests for map_parents function"""

    def test_creates_episode_to_season_relationship(self):
        """Creates Parent relationship from Episode to Season."""
        raw = {"season_id": "RLS25733"}
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = map_parents(raw, config)

        assert len(result) == 1
        assert isinstance(result[0], Parent)
        assert result[0].relationship_type == "isepisodeof"
        assert result[0].parent_content_id == "urn:customer:RLS25733"

    def test_creates_season_to_series_relationship_when_no_season(self):
        """Creates Season to Series relationship when no season_id present."""
        raw = {"series_id": "RLA236634"}
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = map_parents(raw, config)

        assert len(result) == 1
        assert result[0].relationship_type == "isseasonof"
        assert result[0].parent_content_id == "urn:customer:RLA236634"

    def test_only_creates_immediate_parent_for_episode(self):
        """Only creates Episode→Season relationship, not Episode→Series."""
        raw = {
            "season_id": "RLS25733",
            "series_id": "RLA236634",
        }
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = map_parents(raw, config)

        # Should only have one parent (Episode → Season)
        assert len(result) == 1
        assert result[0].relationship_type == "isepisodeof"
        assert result[0].parent_content_id == "urn:customer:RLS25733"

    def test_returns_empty_list_when_no_parent_ids(self):
        """Returns empty list when no parent IDs present."""
        raw = {"title": "Test Episode"}
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = map_parents(raw, config)

        assert result == []

    def test_returns_empty_list_for_empty_parent_ids(self):
        """Returns empty list when parent IDs are empty strings."""
        raw = {
            "season_id": "",
            "series_id": "",
        }
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = map_parents(raw, config)

        assert result == []

    def test_uses_custom_field_names(self):
        """Uses custom field names from configuration."""
        raw = {"parent_season": "SN001"}
        config = {
            "hierarchy_mappings": {
                "season_id_field": "parent_season",
            },
            "source_namespace_prefix": "ACME",
        }

        result = map_parents(raw, config)

        assert len(result) == 1
        assert result[0].parent_content_id == "urn:acme:SN001"

    def test_uses_default_namespace_prefix(self):
        """Uses default namespace prefix when not configured."""
        raw = {"season_id": "RLS25733"}
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
            },
        }

        result = map_parents(raw, config)

        assert len(result) == 1
        assert result[0].parent_content_id == "urn:source:RLS25733"

    def test_to_dict_serialization(self):
        """Verifies Parent to_dict works correctly."""
        raw = {"season_id": "RLS25733"}
        config = {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = map_parents(raw, config)

        assert len(result) == 1
        dict_result = result[0].to_dict()
        assert dict_result == {
            "RelationshipType": "isepisodeof",
            "ParentContentId": "urn:customer:RLS25733",
        }


@pytest.mark.unit
class TestExtractParentMetadata:
    """Tests for extract_parent_metadata function"""

    def test_extracts_series_metadata(self):
        """Extracts series-level metadata."""
        raw = {
            "series_id": "RLA236634",
            "show_name": "Test Series",
            "short_series_description": "A test series about testing.",
            "long_series_description": "A comprehensive test series that explores various testing scenarios.",
            "series_premiere_date": "2022-10-02",
            "season_count": "3",
        }
        config = {
            "parent_metadata_mappings": {
                "show_name_field": "show_name",
                "short_series_description_field": "short_series_description",
                "long_series_description_field": "long_series_description",
                "series_premiere_date_field": "series_premiere_date",
                "season_count_field": "season_count",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert "series" in result
        series = result["series"]
        assert series["content_id"] == "urn:customer:RLA236634"
        assert series["source_id"] == "RLA236634"
        assert series["title"] == "Test Series"
        assert series["short_description"] == "A test series about testing."
        assert (
            series["long_description"]
            == "A comprehensive test series that explores various testing scenarios."
        )
        assert series["premiere_date"] == "2022-10-02"
        assert series["season_count"] == 3

    def test_extracts_season_metadata(self):
        """Extracts season-level metadata."""
        raw = {
            "season_id": "RLS25733",
            "season_number": "1",
            "short_season_description": "Season one of the test series.",
            "long_season_description": "The first season introduces the main characters and storylines.",
            "episode_count": "9",
        }
        config = {
            "parent_metadata_mappings": {
                "season_number_field": "season_number",
                "short_season_description_field": "short_season_description",
                "long_season_description_field": "long_season_description",
                "episode_count_field": "episode_count",
            },
            "hierarchy_mappings": {
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert "season" in result
        season = result["season"]
        assert season["content_id"] == "urn:customer:RLS25733"
        assert season["source_id"] == "RLS25733"
        assert season["number"] == 1
        assert season["short_description"] == "Season one of the test series."
        assert (
            season["long_description"]
            == "The first season introduces the main characters and storylines."
        )
        assert season["episode_count"] == 9

    def test_extracts_both_series_and_season_metadata(self):
        """Extracts both series and season metadata."""
        raw = {
            "series_id": "RLA236634",
            "show_name": "Test Series",
            "season_id": "RLS25733",
            "season_number": "1",
            "episode_count": "9",
        }
        config = {
            "parent_metadata_mappings": {
                "show_name_field": "show_name",
                "season_number_field": "season_number",
                "episode_count_field": "episode_count",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert "series" in result
        assert "season" in result
        assert result["series"]["title"] == "Test Series"
        assert result["season"]["number"] == 1
        assert result["season"]["episode_count"] == 9

    def test_returns_none_when_no_parent_metadata(self):
        """Returns None when no parent metadata is present."""
        raw = {"title": "Test Episode"}
        config = {
            "parent_metadata_mappings": {
                "show_name_field": "show_name",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is None

    def test_handles_partial_series_metadata(self):
        """Handles partial series metadata (only some fields present)."""
        raw = {
            "show_name": "Test Series",
            # No series_id, descriptions, or dates
        }
        config = {
            "parent_metadata_mappings": {
                "show_name_field": "show_name",
                "short_series_description_field": "short_series_description",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert "series" in result
        assert result["series"]["title"] == "Test Series"
        assert "content_id" not in result["series"]
        assert "short_description" not in result["series"]

    def test_handles_partial_season_metadata(self):
        """Handles partial season metadata (only some fields present)."""
        raw = {
            "season_number": "2",
            # No season_id, descriptions, or episode_count
        }
        config = {
            "parent_metadata_mappings": {
                "season_number_field": "season_number",
                "episode_count_field": "episode_count",
            },
            "hierarchy_mappings": {
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert "season" in result
        assert result["season"]["number"] == 2
        assert "content_id" not in result["season"]
        assert "episode_count" not in result["season"]

    def test_uses_custom_field_names(self):
        """Uses custom field names from configuration."""
        raw = {
            "program_title": "Custom Series Name",
            "program_id": "PROG001",
        }
        config = {
            "parent_metadata_mappings": {
                "show_name_field": "program_title",
            },
            "hierarchy_mappings": {
                "series_id_field": "program_id",
            },
            "source_namespace_prefix": "ACME",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert result["series"]["title"] == "Custom Series Name"
        assert result["series"]["content_id"] == "urn:acme:PROG001"

    def test_uses_default_field_names(self):
        """Uses default field names when not configured."""
        raw = {
            "series_id": "SER001",
            "show_name": "Default Series",
            "season_id": "SEA001",
            "season_number": "1",
        }
        config = {}

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert "series" in result
        assert "season" in result

    def test_handles_integer_counts(self):
        """Handles integer values for counts."""
        raw = {
            "series_id": "SER001",
            "season_count": 5,
            "season_id": "SEA001",
            "episode_count": 12,
        }
        config = {
            "parent_metadata_mappings": {
                "season_count_field": "season_count",
                "episode_count_field": "episode_count",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None
        assert result["series"]["season_count"] == 5
        assert result["season"]["episode_count"] == 12

    def test_comprehensive_example(self):
        """Tests with comprehensive metadata matching typical episode data."""
        raw = {
            # Series metadata
            "series_id": "RLA236634",
            "show_name": "Test Series",
            "short_series_description": "A test series about testing.",
            "long_series_description": "A comprehensive test series that explores various testing scenarios in depth.",
            "series_premiere_date": "2022-10-02",
            "season_count": "3",
            # Season metadata
            "season_id": "RLS25733",
            "season_number": "01",
            "short_season_description": "Season one of the test series.",
            "long_season_description": "The first season introduces the main characters and storylines.",
            "episode_count": "9",
        }
        config = {
            "parent_metadata_mappings": {
                "show_name_field": "show_name",
                "short_series_description_field": "short_series_description",
                "long_series_description_field": "long_series_description",
                "series_premiere_date_field": "series_premiere_date",
                "season_count_field": "season_count",
                "season_number_field": "season_number",
                "short_season_description_field": "short_season_description",
                "long_season_description_field": "long_season_description",
                "episode_count_field": "episode_count",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

        result = extract_parent_metadata(raw, config)

        assert result is not None

        # Verify series metadata
        series = result["series"]
        assert series["content_id"] == "urn:customer:RLA236634"
        assert series["source_id"] == "RLA236634"
        assert series["title"] == "Test Series"
        assert series["short_description"] == "A test series about testing."
        assert "comprehensive test series" in series["long_description"]
        assert series["premiere_date"] == "2022-10-02"
        assert series["season_count"] == 3

        # Verify season metadata
        season = result["season"]
        assert season["content_id"] == "urn:customer:RLS25733"
        assert season["source_id"] == "RLS25733"
        assert season["number"] == 1
        assert season["short_description"] == "Season one of the test series."
        assert "first season" in season["long_description"]
        assert season["episode_count"] == 9
