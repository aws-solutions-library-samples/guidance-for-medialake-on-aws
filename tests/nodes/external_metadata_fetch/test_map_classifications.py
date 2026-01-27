"""
Unit tests for the content classification field mapper module.

These tests verify that:
- get_work_type() correctly determines WorkType (Movie, Episode, Promotion)
- WorkTypeDetail is correctly extracted from video_type field
- Primary genre is correctly extracted
- Platform-specific genres are extracted to custom fields
- All field names are configuration-driven
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_classifications import (
    determine_work_type,
    extract_default_genres_from_genres_field,
    extract_genres_list,
    extract_platform_genres,
    extract_primary_genre,
    get_string_value,
    get_work_type,
    map_all_genres,
)


@pytest.mark.unit
class TestGetStringValue:
    """Tests for get_string_value helper function"""

    def test_returns_value_for_valid_string(self):
        """Returns the string value when present."""
        raw = {"content_type": "Series"}
        result = get_string_value(raw, "content_type")
        assert result == "Series"

    def test_returns_none_for_none_field_name(self):
        """Returns None when field_name is None."""
        raw = {"content_type": "Series"}
        result = get_string_value(raw, None)
        assert result is None

    def test_returns_none_for_missing_field(self):
        """Returns None when field is not in metadata."""
        raw = {"other_field": "value"}
        result = get_string_value(raw, "content_type")
        assert result is None

    def test_returns_none_for_none_value(self):
        """Returns None when field value is None."""
        raw = {"content_type": None}
        result = get_string_value(raw, "content_type")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when field value is empty string."""
        raw = {"content_type": ""}
        result = get_string_value(raw, "content_type")
        assert result is None

    def test_strips_whitespace(self):
        """Strips leading and trailing whitespace."""
        raw = {"content_type": "  Series  "}
        result = get_string_value(raw, "content_type")
        assert result == "Series"


@pytest.mark.unit
class TestDetermineWorkType:
    """Tests for determine_work_type function"""

    def test_returns_movie_for_true_is_movie(self):
        """Returns 'Movie' when is_movie is TRUE."""
        result = determine_work_type("TRUE", None, {})
        assert result == "Movie"

    def test_returns_movie_for_lowercase_true(self):
        """Returns 'Movie' when is_movie is 'true'."""
        result = determine_work_type("true", None, {})
        assert result == "Movie"

    def test_returns_movie_for_numeric_one(self):
        """Returns 'Movie' when is_movie is '1'."""
        result = determine_work_type("1", None, {})
        assert result == "Movie"

    def test_returns_movie_for_yes(self):
        """Returns 'Movie' when is_movie is 'yes'."""
        result = determine_work_type("yes", None, {})
        assert result == "Movie"

    def test_returns_promotion_for_interstitial(self):
        """Returns 'Promotion' when content_type is 'Interstitial'."""
        result = determine_work_type("FALSE", "Interstitial", {})
        assert result == "Promotion"

    def test_returns_promotion_for_trailer(self):
        """Returns 'Promotion' when content_type is 'Trailer'."""
        result = determine_work_type(None, "Trailer", {})
        assert result == "Promotion"

    def test_returns_promotion_for_promo(self):
        """Returns 'Promotion' when content_type is 'Promo'."""
        result = determine_work_type(None, "Promo", {})
        assert result == "Promotion"

    def test_returns_episode_for_series(self):
        """Returns 'Episode' when content_type is 'Series'."""
        result = determine_work_type("FALSE", "Series", {})
        assert result == "Episode"

    def test_returns_episode_for_episode_content_type(self):
        """Returns 'Episode' when content_type is 'Episode'."""
        result = determine_work_type(None, "Episode", {})
        assert result == "Episode"

    def test_returns_episode_as_default(self):
        """Returns 'Episode' as default when no matching values."""
        result = determine_work_type(None, None, {})
        assert result == "Episode"

    def test_returns_episode_for_false_is_movie(self):
        """Returns 'Episode' when is_movie is FALSE."""
        result = determine_work_type("FALSE", None, {})
        assert result == "Episode"

    def test_movie_takes_precedence_over_content_type(self):
        """Movie determination takes precedence over content_type."""
        result = determine_work_type("TRUE", "Series", {})
        assert result == "Movie"

    def test_uses_custom_movie_values_from_config(self):
        """Uses custom movie values from configuration."""
        config = {
            "work_type_mappings": {
                "movie_values": ["FILM", "film"],
            }
        }
        result = determine_work_type("FILM", None, config)
        assert result == "Movie"

    def test_uses_custom_promotion_types_from_config(self):
        """Uses custom promotion content types from configuration."""
        config = {
            "work_type_mappings": {
                "promotion_content_types": ["Commercial", "Ad"],
            }
        }
        result = determine_work_type(None, "Commercial", config)
        assert result == "Promotion"


@pytest.mark.unit
class TestGetWorkType:
    """Tests for get_work_type function"""

    def test_returns_movie_work_type(self):
        """Returns Movie work type for movie content."""
        raw = {"is_movie": "TRUE", "content_type": "Movie"}
        config = {
            "classification_mappings": {
                "is_movie_field": "is_movie",
                "content_type_field": "content_type",
            }
        }
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Movie"

    def test_returns_episode_work_type(self):
        """Returns Episode work type for series content."""
        raw = {"is_movie": "FALSE", "content_type": "Series"}
        config = {
            "classification_mappings": {
                "is_movie_field": "is_movie",
                "content_type_field": "content_type",
            }
        }
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Episode"

    def test_returns_promotion_work_type(self):
        """Returns Promotion work type for interstitial content."""
        raw = {"is_movie": "FALSE", "content_type": "Interstitial"}
        config = {
            "classification_mappings": {
                "is_movie_field": "is_movie",
                "content_type_field": "content_type",
            }
        }
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Promotion"

    def test_extracts_work_type_detail(self):
        """Extracts WorkTypeDetail from video_type field."""
        raw = {
            "is_movie": "FALSE",
            "content_type": "Series",
            "video_type": "Full Episode",
        }
        config = {
            "classification_mappings": {
                "is_movie_field": "is_movie",
                "content_type_field": "content_type",
                "video_type_field": "video_type",
            }
        }
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Episode"
        assert detail == "Full Episode"

    def test_returns_none_detail_when_missing(self):
        """Returns None for WorkTypeDetail when video_type is missing."""
        raw = {"is_movie": "FALSE", "content_type": "Series"}
        config = {
            "classification_mappings": {
                "is_movie_field": "is_movie",
                "content_type_field": "content_type",
                "video_type_field": "video_type",
            }
        }
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Episode"
        assert detail is None

    def test_uses_custom_field_names(self):
        """Uses custom field names from configuration."""
        raw = {
            "movie_flag": "TRUE",
            "type": "Movie",
            "subtype": "Feature Film",
        }
        config = {
            "classification_mappings": {
                "is_movie_field": "movie_flag",
                "content_type_field": "type",
                "video_type_field": "subtype",
            }
        }
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Movie"
        assert detail == "Feature Film"

    def test_uses_default_field_names(self):
        """Uses default field names when not configured."""
        raw = {
            "is_movie": "FALSE",
            "content_type": "Series",
            "video_type": "Full Episode",
        }
        config = {}
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Episode"
        assert detail == "Full Episode"

    def test_handles_empty_config(self):
        """Works with empty configuration using defaults."""
        raw = {"is_movie": "TRUE"}
        config = {}
        work_type, detail = get_work_type(raw, config)
        assert work_type == "Movie"


@pytest.mark.unit
class TestExtractPrimaryGenre:
    """Tests for extract_primary_genre function"""

    def test_extracts_primary_genre(self):
        """Extracts primary genre from configured field."""
        raw = {"genre": "Drama"}
        config = {"classification_mappings": {"genre_field": "genre"}}
        result = extract_primary_genre(raw, config)
        assert result == "Drama"

    def test_uses_custom_field_name(self):
        """Uses custom field name from configuration."""
        raw = {"primary_genre": "Horror"}
        config = {"classification_mappings": {"genre_field": "primary_genre"}}
        result = extract_primary_genre(raw, config)
        assert result == "Horror"

    def test_uses_default_field_name(self):
        """Uses 'genre' as default field name."""
        raw = {"genre": "Comedy"}
        config = {}
        result = extract_primary_genre(raw, config)
        assert result == "Comedy"

    def test_returns_none_for_missing_field(self):
        """Returns None when genre field is missing."""
        raw = {"other_field": "value"}
        config = {"classification_mappings": {"genre_field": "genre"}}
        result = extract_primary_genre(raw, config)
        assert result is None

    def test_returns_none_for_empty_value(self):
        """Returns None when genre value is empty."""
        raw = {"genre": ""}
        config = {"classification_mappings": {"genre_field": "genre"}}
        result = extract_primary_genre(raw, config)
        assert result is None


@pytest.mark.unit
class TestExtractGenresList:
    """Tests for extract_genres_list function"""

    def test_extracts_primary_genre(self):
        """Extracts primary genre into list."""
        raw = {"genre": "Drama"}
        config = {"classification_mappings": {"genre_field": "genre"}}
        result = extract_genres_list(raw, config)
        assert result == ["Drama"]

    def test_extracts_primary_and_subgenre(self):
        """Extracts both primary genre and subgenre."""
        raw = {"genre": "Drama", "subgenre": "Horror"}
        config = {
            "classification_mappings": {
                "genre_field": "genre",
                "subgenre_field": "subgenre",
            }
        }
        result = extract_genres_list(raw, config)
        assert result == ["Drama", "Horror"]

    def test_avoids_duplicate_genres(self):
        """Avoids adding duplicate genres."""
        raw = {"genre": "Drama", "subgenre": "Drama"}
        config = {
            "classification_mappings": {
                "genre_field": "genre",
                "subgenre_field": "subgenre",
            }
        }
        result = extract_genres_list(raw, config)
        assert result == ["Drama"]

    def test_returns_empty_list_when_no_genres(self):
        """Returns empty list when no genres found."""
        raw = {"other_field": "value"}
        config = {"classification_mappings": {"genre_field": "genre"}}
        result = extract_genres_list(raw, config)
        assert result == []


@pytest.mark.unit
class TestExtractPlatformGenres:
    """Tests for extract_platform_genres function"""

    def test_extracts_amazon_genres(self):
        """Extracts Amazon platform-specific genres."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "Amazon", "#text": "Drama - Crime"},
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
        result = extract_platform_genres(raw, config)
        assert "amazon" in result
        assert result["amazon"] == ["Drama - Crime"]

    def test_extracts_multiple_platform_genres(self):
        """Extracts genres from multiple platforms."""
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
        result = extract_platform_genres(raw, config)
        assert "amazon" in result
        assert "apple" in result
        assert "roku" in result

    def test_normalizes_platform_names(self):
        """Normalizes platform names to lowercase with underscores."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "SN Series", "#text": "Drama"},
                    {"@type": "Bell Series", "#text": "Drama"},
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
        result = extract_platform_genres(raw, config)
        assert "sn_series" in result
        assert "bell_series" in result

    def test_excludes_default_and_subgenre_types(self):
        """Excludes default and subgenre types from platform genres."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "subgenre", "#text": "Horror"},
                    {"@type": "Amazon", "#text": "Drama - Crime"},
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
        result = extract_platform_genres(raw, config)
        assert "default" not in result
        assert "subgenre" not in result
        assert "amazon" in result

    def test_handles_single_genre_entry(self):
        """Handles single genre entry (not a list)."""
        raw = {"genres": {"genre": {"@type": "Amazon", "#text": "Drama"}}}
        config = {
            "classification_mappings": {
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            }
        }
        result = extract_platform_genres(raw, config)
        assert "amazon" in result
        assert result["amazon"] == ["Drama"]

    def test_returns_empty_dict_when_no_genres(self):
        """Returns empty dict when no genres field."""
        raw = {"other_field": "value"}
        config = {"classification_mappings": {"genres_field": "genres"}}
        result = extract_platform_genres(raw, config)
        assert result == {}

    def test_skips_empty_genre_text(self):
        """Skips genres with empty text."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "Amazon", "#text": ""},
                    {"@type": "Apple", "#text": "Drama"},
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
        result = extract_platform_genres(raw, config)
        assert "amazon" not in result
        assert "apple" in result

    def test_avoids_duplicate_genres_per_platform(self):
        """Avoids adding duplicate genres for the same platform."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "Amazon", "#text": "Drama"},
                    {"@type": "Amazon", "#text": "Drama"},
                    {"@type": "Amazon", "#text": "Horror"},
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
        result = extract_platform_genres(raw, config)
        assert result["amazon"] == ["Drama", "Horror"]


@pytest.mark.unit
class TestExtractDefaultGenresFromGenresField:
    """Tests for extract_default_genres_from_genres_field function"""

    def test_extracts_default_genre(self):
        """Extracts genre with type 'default'."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
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
        result = extract_default_genres_from_genres_field(raw, config)
        assert result == ["Drama"]

    def test_extracts_subgenre(self):
        """Extracts genre with type 'subgenre'."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "subgenre", "#text": "Horror"},
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
        result = extract_default_genres_from_genres_field(raw, config)
        assert result == ["Horror"]

    def test_extracts_both_default_and_subgenre(self):
        """Extracts both default and subgenre types."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "subgenre", "#text": "Horror"},
                    {"@type": "Amazon", "#text": "Drama - Crime"},
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
        result = extract_default_genres_from_genres_field(raw, config)
        assert "Drama" in result
        assert "Horror" in result
        assert "Drama - Crime" not in result

    def test_excludes_platform_genres(self):
        """Excludes platform-specific genres."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "Amazon", "#text": "Drama - Crime"},
                    {"@type": "Apple", "#text": "Drama"},
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
        result = extract_default_genres_from_genres_field(raw, config)
        assert result == []

    def test_avoids_duplicate_genres(self):
        """Avoids adding duplicate genres."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "subgenre", "#text": "Drama"},
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
        result = extract_default_genres_from_genres_field(raw, config)
        assert result == ["Drama"]


@pytest.mark.unit
class TestMapAllGenres:
    """Tests for map_all_genres function"""

    def test_combines_simple_and_structured_genres(self):
        """Combines genres from simple field and structured genres field."""
        raw = {
            "genre": "Drama",
            "genres": {
                "genre": [
                    {"@type": "subgenre", "#text": "Horror"},
                ]
            },
        }
        config = {
            "classification_mappings": {
                "genre_field": "genre",
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            }
        }
        result = map_all_genres(raw, config)
        assert "Drama" in result
        assert "Horror" in result

    def test_avoids_duplicates_across_sources(self):
        """Avoids duplicate genres from different sources."""
        raw = {
            "genre": "Drama",
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "subgenre", "#text": "Horror"},
                ]
            },
        }
        config = {
            "classification_mappings": {
                "genre_field": "genre",
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            }
        }
        result = map_all_genres(raw, config)
        assert result.count("Drama") == 1
        assert "Horror" in result

    def test_returns_empty_list_when_no_genres(self):
        """Returns empty list when no genres found."""
        raw = {"other_field": "value"}
        config = {}
        result = map_all_genres(raw, config)
        assert result == []

    def test_handles_only_simple_genre(self):
        """Handles case with only simple genre field."""
        raw = {"genre": "Comedy"}
        config = {"classification_mappings": {"genre_field": "genre"}}
        result = map_all_genres(raw, config)
        assert result == ["Comedy"]

    def test_handles_only_structured_genres(self):
        """Handles case with only structured genres field."""
        raw = {
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Action"},
                    {"@type": "subgenre", "#text": "Adventure"},
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
        result = map_all_genres(raw, config)
        assert "Action" in result
        assert "Adventure" in result

    def test_comprehensive_genre_mapping(self):
        """Tests comprehensive genre mapping scenario."""
        raw = {
            "genre": "Drama",
            "subgenre": "Horror",
            "genres": {
                "genre": [
                    {"@type": "default", "#text": "Drama"},
                    {"@type": "subgenre", "#text": "Horror"},
                    {"@type": "Amazon", "#text": "Drama - Crime"},
                    {"@type": "Apple", "#text": "Drama"},
                ]
            },
        }
        config = {
            "classification_mappings": {
                "genre_field": "genre",
                "subgenre_field": "subgenre",
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            }
        }
        result = map_all_genres(raw, config)

        # Should include Drama and Horror (no duplicates)
        assert "Drama" in result
        assert "Horror" in result
        assert result.count("Drama") == 1
        assert result.count("Horror") == 1

        # Should NOT include platform-specific genres
        assert "Drama - Crime" not in result
