"""
Unit tests for the ratings field mapper module.

These tests verify that:
- map_rating() correctly creates Rating elements
- Each rating system is correctly identified using config
- Content descriptors are mapped to Reason field
- Multiple ratings per asset are handled correctly
- Empty/null values are skipped
- Rating values are preserved without modification
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_ratings import (
    DEFAULT_RATING_SYSTEM_MAPPINGS,
    extract_ratings_list,
    map_hierarchical_ratings,
    map_rating,
    map_ratings,
)
from nodes.external_metadata_fetch.normalizers.mec_schema import Rating


@pytest.mark.unit
class TestMapRating:
    """Tests for map_rating function"""

    def test_creates_rating_with_valid_data(self):
        """Creates Rating with valid data and config."""
        rating_data = {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"}
        config = {
            "rating_system_mappings": {"us-tv": {"system": "us-tv", "region": "US"}}
        }

        result = map_rating(rating_data, config)

        assert result is not None
        assert isinstance(result, Rating)
        assert result.region == "US"
        assert result.system == "us-tv"
        assert result.value == "TV-MA"
        assert result.reason == "LSV"

    def test_returns_none_for_empty_data(self):
        """Returns None when rating data is empty."""
        result = map_rating({}, {})

        assert result is None

    def test_returns_none_for_none_data(self):
        """Returns None when rating data is None."""
        result = map_rating(None, {})

        assert result is None

    def test_returns_none_for_empty_value(self):
        """Returns None when rating value is empty."""
        rating_data = {"@Type": "us-tv", "#text": ""}
        config = {}

        result = map_rating(rating_data, config)

        assert result is None

    def test_returns_none_for_whitespace_value(self):
        """Returns None when rating value is whitespace only."""
        rating_data = {"@Type": "us-tv", "#text": "   "}
        config = {}

        result = map_rating(rating_data, config)

        assert result is None

    def test_strips_whitespace_from_value(self):
        """Strips leading/trailing whitespace from rating value."""
        rating_data = {"@Type": "us-tv", "#text": "  TV-MA  "}
        config = {
            "rating_system_mappings": {"us-tv": {"system": "us-tv", "region": "US"}}
        }

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.value == "TV-MA"

    def test_handles_missing_descriptor(self):
        """Handles ratings without content descriptors."""
        rating_data = {"@Type": "ca-tv", "#text": "18+"}
        config = {
            "rating_system_mappings": {"ca-tv": {"system": "ca-tv", "region": "CA"}}
        }

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.value == "18+"
        assert result.reason is None

    def test_uses_default_mappings_when_not_configured(self):
        """Uses default rating system mappings when not in config."""
        rating_data = {"@Type": "us-tv", "#text": "TV-14"}
        config = {}  # No rating_system_mappings

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.system == "us-tv"
        assert result.region == "US"

    def test_handles_unknown_rating_type(self):
        """Handles unknown rating types gracefully."""
        rating_data = {"@Type": "unknown-system", "#text": "R"}
        config = {}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.system == "unknown-system"
        assert result.region == "US"  # Default region
        assert result.value == "R"

    def test_custom_attribute_names(self):
        """Uses custom attribute names from config."""
        rating_data = {"type": "us-tv", "value": "TV-MA", "descriptor": "V"}
        config = {
            "rating_type_attr": "type",
            "rating_value_attr": "value",
            "rating_descriptor_attr": "descriptor",
            "rating_system_mappings": {"us-tv": {"system": "us-tv", "region": "US"}},
        }

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.value == "TV-MA"
        assert result.reason == "V"


@pytest.mark.unit
class TestRatingSystemMappings:
    """Tests for rating system to region mappings"""

    def test_us_tv_rating_maps_to_us_region(self):
        """US TV rating maps to US region."""
        rating_data = {"@Type": "us-tv", "#text": "TV-MA"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "US"
        assert result.system == "us-tv"

    def test_tv_rating_generic_maps_to_us_region(self):
        """Generic TV Rating maps to US region."""
        rating_data = {"@Type": "TV Rating", "#text": "TV-14"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "US"
        assert result.system == "us-tv"

    def test_ca_tv_rating_maps_to_ca_region(self):
        """Canadian TV rating maps to CA region."""
        rating_data = {"@Type": "ca-tv", "#text": "18+"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "CA"
        assert result.system == "ca-tv"

    def test_au_tv_rating_maps_to_au_region(self):
        """Australian TV rating maps to AU region."""
        rating_data = {"@Type": "au-tv", "#text": "MA15+"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "AU"
        assert result.system == "au-tv"

    def test_acma_rating_maps_to_au_region(self):
        """ACMA rating maps to AU region."""
        rating_data = {"@Type": "ACMA", "#text": "MA15"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "AU"
        assert result.system == "ACMA"

    def test_dmec_rating_maps_to_mx_region(self):
        """Mexican DMEC rating maps to MX region."""
        rating_data = {"@Type": "DMEC", "#text": "A"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "MX"
        assert result.system == "DMEC"

    def test_in_tv_rating_maps_to_in_region(self):
        """Indian TV rating maps to IN region."""
        rating_data = {"@Type": "in-tv", "#text": "A"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "IN"
        assert result.system == "in-tv"

    def test_nz_tv_rating_maps_to_nz_region(self):
        """New Zealand TV rating maps to NZ region."""
        rating_data = {"@Type": "nz-tv", "#text": "16"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "NZ"
        assert result.system == "nz-tv"

    def test_nz_am_rating_maps_to_nz_region(self):
        """New Zealand nz-am rating maps to NZ region."""
        rating_data = {"@Type": "nz-am", "#text": "16"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.region == "NZ"
        assert result.system == "nz-am"


@pytest.mark.unit
class TestContentDescriptors:
    """Tests for content descriptor (Reason) mapping"""

    def test_maps_single_descriptor_to_reason(self):
        """Maps single content descriptor to Reason field."""
        rating_data = {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "V"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.reason == "V"

    def test_maps_multiple_descriptors_to_reason(self):
        """Maps multiple content descriptors to Reason field."""
        rating_data = {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.reason == "LSV"

    def test_maps_detailed_descriptors(self):
        """Maps detailed Australian-style descriptors."""
        rating_data = {"@Type": "ACMA", "#text": "MA15", "@Descriptor": "DHNSSLV"}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.reason == "DHNSSLV"

    def test_strips_whitespace_from_descriptor(self):
        """Strips whitespace from content descriptors."""
        rating_data = {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "  LSV  "}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_rating(rating_data, config)

        assert result is not None
        assert result.reason == "LSV"


@pytest.mark.unit
class TestExtractRatingsList:
    """Tests for extract_ratings_list function"""

    def test_extracts_list_from_nested_structure(self):
        """Extracts ratings list from nested container structure."""
        raw_metadata = {
            "rating": {
                "Rating": [
                    {"@Type": "us-tv", "#text": "TV-MA"},
                    {"@Type": "ca-tv", "#text": "18+"},
                ]
            }
        }
        config = {}

        result = extract_ratings_list(raw_metadata, config)

        assert len(result) == 2

    def test_extracts_single_rating_as_list(self):
        """Extracts single rating dict as list."""
        raw_metadata = {"rating": {"Rating": {"@Type": "us-tv", "#text": "TV-MA"}}}
        config = {}

        result = extract_ratings_list(raw_metadata, config)

        assert len(result) == 1
        assert result[0]["@Type"] == "us-tv"

    def test_returns_empty_list_when_no_ratings(self):
        """Returns empty list when no ratings field."""
        raw_metadata = {}
        config = {}

        result = extract_ratings_list(raw_metadata, config)

        assert result == []

    def test_uses_custom_field_names(self):
        """Uses custom field names from config."""
        raw_metadata = {
            "content_ratings": {"RatingEntry": [{"@Type": "us-tv", "#text": "TV-MA"}]}
        }
        config = {"rating_field": "content_ratings", "rating_container": "RatingEntry"}

        result = extract_ratings_list(raw_metadata, config)

        assert len(result) == 1


@pytest.mark.unit
class TestMapRatings:
    """Tests for map_ratings function"""

    def test_maps_multiple_ratings(self):
        """Maps multiple ratings from source metadata."""
        raw_metadata = {
            "rating": {
                "Rating": [
                    {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"},
                    {"@Type": "ca-tv", "#text": "18+"},
                    {"@Type": "au-tv", "#text": "MA15+"},
                ]
            }
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_ratings(raw_metadata, config)

        assert len(result) == 3

        # Check regions
        regions = {r.region for r in result}
        assert "US" in regions
        assert "CA" in regions
        assert "AU" in regions

    def test_skips_empty_ratings(self):
        """Skips ratings with empty values."""
        raw_metadata = {
            "rating": {
                "Rating": [
                    {"@Type": "us-tv", "#text": "TV-MA"},
                    {"@Type": "ca-tv", "#text": ""},  # Empty value
                    {"@Type": "au-tv", "#text": "MA15+"},
                ]
            }
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_ratings(raw_metadata, config)

        assert len(result) == 2

    def test_returns_empty_list_when_no_ratings(self):
        """Returns empty list when no ratings in metadata."""
        raw_metadata = {"title": "Test Content"}
        config = {}

        result = map_ratings(raw_metadata, config)

        assert result == []

    def test_handles_single_rating(self):
        """Handles single rating (not in list)."""
        raw_metadata = {"rating": {"Rating": {"@Type": "us-tv", "#text": "TV-14"}}}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_ratings(raw_metadata, config)

        assert len(result) == 1
        assert result[0].value == "TV-14"

    def test_comprehensive_rating_example(self):
        """Tests with comprehensive rating data matching sample patterns."""
        raw_metadata = {
            "rating": {
                "Rating": [
                    {"@Type": "TV Rating", "#text": "TV-MA", "@Descriptor": "LSV"},
                    {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"},
                    {"@Type": "ca-tv", "#text": "18+"},
                    {"@Type": "au-tv", "#text": "MA15+"},
                    {"@Type": "ACMA", "#text": "MA15", "@Descriptor": "DHNSSLV"},
                    {"@Type": "DMEC", "#text": "A"},
                    {"@Type": "in-tv", "#text": "A"},
                    {"@Type": "nz-tv", "#text": "16"},
                    {"@Type": "nz-am", "#text": "16"},
                ]
            }
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_ratings(raw_metadata, config)

        assert len(result) == 9

        # Verify all regions are represented
        regions = {r.region for r in result}
        assert "US" in regions
        assert "CA" in regions
        assert "AU" in regions
        assert "MX" in regions
        assert "IN" in regions
        assert "NZ" in regions

    def test_to_dict_serialization(self):
        """Verifies Rating to_dict works correctly."""
        raw_metadata = {
            "rating": {
                "Rating": {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"}
            }
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_ratings(raw_metadata, config)

        assert len(result) == 1
        dict_result = result[0].to_dict()
        assert dict_result == {
            "Region": "US",
            "System": "us-tv",
            "Value": "TV-MA",
            "Reason": "LSV",
        }


@pytest.mark.unit
class TestMapHierarchicalRatings:
    """Tests for map_hierarchical_ratings function"""

    def test_maps_episode_level_ratings(self):
        """Maps episode-level ratings."""
        raw_metadata = {"rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-MA"}]}}
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_hierarchical_ratings(raw_metadata, config)

        assert len(result["episode"]) == 1
        assert result["episode"][0].value == "TV-MA"
        assert result["season"] == []
        assert result["series"] == []

    def test_maps_season_level_ratings(self):
        """Maps season-level ratings."""
        raw_metadata = {
            "rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-MA"}]},
            "season_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-14"}]},
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_hierarchical_ratings(raw_metadata, config)

        assert len(result["episode"]) == 1
        assert len(result["season"]) == 1
        assert result["season"][0].value == "TV-14"

    def test_maps_series_level_ratings(self):
        """Maps series-level ratings."""
        raw_metadata = {
            "rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-MA"}]},
            "series_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-14"}]},
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_hierarchical_ratings(raw_metadata, config)

        assert len(result["episode"]) == 1
        assert len(result["series"]) == 1
        assert result["series"][0].value == "TV-14"

    def test_maps_all_hierarchy_levels(self):
        """Maps ratings at all hierarchy levels."""
        raw_metadata = {
            "rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-MA"}]},
            "season_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-14"}]},
            "series_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-PG"}]},
        }
        config = {"rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS}

        result = map_hierarchical_ratings(raw_metadata, config)

        assert len(result["episode"]) == 1
        assert len(result["season"]) == 1
        assert len(result["series"]) == 1
        assert result["episode"][0].value == "TV-MA"
        assert result["season"][0].value == "TV-14"
        assert result["series"][0].value == "TV-PG"

    def test_uses_custom_field_names(self):
        """Uses custom field names from config."""
        raw_metadata = {
            "content_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-MA"}]},
            "season_content_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-14"}]},
        }
        config = {
            "rating_field": "content_rating",
            "season_rating_field": "season_content_rating",
            "rating_system_mappings": DEFAULT_RATING_SYSTEM_MAPPINGS,
        }

        result = map_hierarchical_ratings(raw_metadata, config)

        assert len(result["episode"]) == 1
        assert len(result["season"]) == 1
