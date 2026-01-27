"""
Unit tests for the Generic XML normalizer.

These tests verify that:
- GenericXmlNormalizer correctly implements SourceNormalizer interface
- get_source_type() returns "generic_xml"
- validate_input() validates using configured field names
- normalize() orchestrates all field mappers with config
- Content ID generation uses configured primary_id_field and ref_id_field
- All field name lookups use config - no hardcoded customer field names
"""

from typing import Any

import pytest
from nodes.external_metadata_fetch.normalizers import (
    GenericXmlNormalizer,
    NormalizationResult,
    SourceNormalizer,
    ValidationResult,
    create_normalizer,
)


def create_sample_config() -> dict[str, Any]:
    """Create a sample configuration for testing."""
    return {
        "source_namespace_prefix": "ACME",
        "default_language": "en-US",
        "primary_id_field": "content_id",
        "ref_id_field": "reference_id",
        "include_raw_source": False,
        "premiere_year_field": "release_year",
        "original_air_date_field": "air_date",
        "country_code_field": "country",
        "language_field": "original_language",
        "run_length_field": "duration",
        "title_mappings": {
            "title_field": "title",
            "title_brief_field": "short_title",
            "description_field": "description",
            "description_short_field": "short_description",
        },
        "identifier_mappings": {
            "content_id": "",
            "reference_id": "-REF",
        },
        "classification_mappings": {
            "is_movie_field": "is_movie",
            "content_type_field": "content_type",
            "video_type_field": "video_type",
            "genre_field": "genre",
        },
        "hierarchy_mappings": {
            "episode_number_field": "episode_number",
            "season_number_field": "season_number",
            "series_title_field": "series_title",
        },
        # people_field_mappings: field_name -> JobFunction
        "people_field_mappings": {
            "actors": "Actor",
            "directors": "Director",
        },
        "person_first_name_attr": "first_name",
        "person_last_name_attr": "last_name",
        "person_order_attr": "order",
        "person_role_attr": "role",
        "rating_system_mappings": {
            "US-TV": {"region": "US", "system": "TVPG"},
            "MPAA": {"region": "US", "system": "MPAA"},
        },
        # custom_field_categories: category -> list of field names
        "custom_field_categories": {
            "platform_genres": [],
            "advertising": ["ad_category", "ad_content_id"],
            "timing": ["timelines", "segments"],
        },
    }


def create_sample_metadata() -> dict[str, Any]:
    """Create sample raw metadata for testing.

    The structure matches what xmltodict produces from XML:
    - Nested containers for lists (e.g., actors/actor)
    - @ prefix for XML attributes
    - #text for text content
    """
    return {
        "content_id": "ACME123456",
        "reference_id": "REF789",
        "title": "Test Episode Title",
        "short_title": "Test Ep",
        "description": "A sample episode for testing the normalizer.",
        "short_description": "Sample episode",
        "release_year": 2024,
        "air_date": "2024-03-15",
        "country": "US",
        "original_language": "en",
        "duration": "PT45M",
        "is_movie": False,
        "content_type": "Episode",
        "video_type": "Full Episode",
        "genre": "Drama",
        "episode_number": 5,
        "season_number": 2,
        "series_title": "Test Series",
        # Nested structure matching XML-to-dict conversion
        "actors": {
            "actor": [
                {
                    "#text": "John Actor",
                    "first_name": "John",
                    "last_name": "Actor",
                    "order": "1",
                },
                {
                    "#text": "Jane Performer",
                    "first_name": "Jane",
                    "last_name": "Performer",
                    "order": "2",
                },
            ]
        },
        "directors": {
            "director": [
                {"#text": "Sam Director", "first_name": "Sam", "last_name": "Director"},
            ]
        },
        # Ratings with nested structure
        "rating": {
            "Rating": [
                {"@Type": "US-TV", "#text": "TV-14", "@Descriptor": "V"},
            ]
        },
    }


@pytest.mark.unit
class TestGenericXmlNormalizerInterface:
    """Tests for GenericXmlNormalizer interface implementation"""

    def test_inherits_from_source_normalizer(self):
        """GenericXmlNormalizer inherits from SourceNormalizer."""
        normalizer = GenericXmlNormalizer()
        assert isinstance(normalizer, SourceNormalizer)

    def test_get_source_type_returns_generic_xml(self):
        """get_source_type() returns 'generic_xml'."""
        normalizer = GenericXmlNormalizer()
        assert normalizer.get_source_type() == "generic_xml"

    def test_factory_creates_generic_xml_normalizer(self):
        """Factory creates GenericXmlNormalizer for 'generic_xml' type."""
        normalizer = create_normalizer("generic_xml")
        assert isinstance(normalizer, GenericXmlNormalizer)

    def test_factory_passes_config_to_normalizer(self):
        """Factory passes config to GenericXmlNormalizer."""
        config = {"source_namespace_prefix": "TEST"}
        normalizer = create_normalizer("generic_xml", config)
        assert normalizer.config == config


@pytest.mark.unit
class TestGenericXmlNormalizerConfig:
    """Tests for GenericXmlNormalizer configuration handling"""

    def test_default_config_values(self):
        """Uses default values when config not provided."""
        normalizer = GenericXmlNormalizer()

        assert normalizer._source_namespace_prefix == "SOURCE"
        assert normalizer._default_language == "en-US"
        assert normalizer._primary_id_field == "id"
        assert normalizer._ref_id_field == "ref_id"
        assert normalizer._include_raw_source is False

    def test_custom_config_values(self):
        """Uses custom values from config."""
        config = {
            "source_namespace_prefix": "ACME",
            "default_language": "es-ES",
            "primary_id_field": "acme_id",
            "ref_id_field": "acme_ref",
            "include_raw_source": True,
        }
        normalizer = GenericXmlNormalizer(config)

        assert normalizer._source_namespace_prefix == "ACME"
        assert normalizer._default_language == "es-ES"
        assert normalizer._primary_id_field == "acme_id"
        assert normalizer._ref_id_field == "acme_ref"
        assert normalizer._include_raw_source is True

    def test_partial_config_uses_defaults(self):
        """Uses defaults for missing config values."""
        config = {"source_namespace_prefix": "PARTIAL"}
        normalizer = GenericXmlNormalizer(config)

        assert normalizer._source_namespace_prefix == "PARTIAL"
        assert normalizer._default_language == "en-US"  # Default
        assert normalizer._primary_id_field == "id"  # Default


@pytest.mark.unit
class TestGenericXmlNormalizerValidation:
    """Tests for GenericXmlNormalizer.validate_input()"""

    def test_validates_empty_metadata(self):
        """Returns error for empty metadata."""
        normalizer = GenericXmlNormalizer()
        result = normalizer.validate_input({})

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Empty metadata" in result.errors[0].message

    def test_validates_none_metadata(self):
        """Returns error for None metadata."""
        normalizer = GenericXmlNormalizer()
        result = normalizer.validate_input(None)  # type: ignore

        assert result.is_valid is False

    def test_warns_when_no_identifier(self):
        """Adds warning when no identifier found."""
        config = {
            "primary_id_field": "content_id",
            "ref_id_field": "reference_id",
        }
        normalizer = GenericXmlNormalizer(config)
        result = normalizer.validate_input({"title": "Test"})

        assert result.is_valid is True  # Warnings don't invalidate
        assert len(result.warnings) >= 1
        # Check for identifier warning
        id_warnings = [w for w in result.warnings if "identifier" in w.message.lower()]
        assert len(id_warnings) >= 1

    def test_warns_when_no_title(self):
        """Adds warning when no title found."""
        config = {
            "primary_id_field": "content_id",
            "title_mappings": {
                "title_field": "title",
                "title_brief_field": "short_title",
            },
        }
        normalizer = GenericXmlNormalizer(config)
        result = normalizer.validate_input({"content_id": "123"})

        assert result.is_valid is True  # Warnings don't invalidate
        assert len(result.warnings) >= 1
        # Check for title warning
        title_warnings = [w for w in result.warnings if "title" in w.message.lower()]
        assert len(title_warnings) >= 1

    def test_valid_metadata_passes(self):
        """Valid metadata passes validation."""
        config = create_sample_config()
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.validate_input(metadata)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_uses_configured_field_names(self):
        """Uses configured field names for validation."""
        config = {
            "primary_id_field": "custom_id",
            "ref_id_field": "custom_ref",
            "title_mappings": {
                "title_field": "custom_title",
                "title_brief_field": "custom_brief",
            },
        }
        normalizer = GenericXmlNormalizer(config)

        # Metadata with custom field names
        metadata = {
            "custom_id": "123",
            "custom_title": "Test Title",
        }
        result = normalizer.validate_input(metadata)

        assert result.is_valid is True


@pytest.mark.unit
class TestGenericXmlNormalizerContentId:
    """Tests for content ID generation"""

    def test_uses_primary_id_field(self):
        """Uses configured primary_id_field for content_id."""
        config = {
            "primary_id_field": "my_id",
            "ref_id_field": "my_ref",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {"my_id": "PRIMARY123", "my_ref": "REF456"}

        content_id = normalizer._generate_content_id(metadata)

        assert content_id == "PRIMARY123"

    def test_falls_back_to_ref_id(self):
        """Falls back to ref_id when primary_id is missing."""
        config = {
            "primary_id_field": "my_id",
            "ref_id_field": "my_ref",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {"my_ref": "REF456"}

        content_id = normalizer._generate_content_id(metadata)

        assert content_id == "REF456"

    def test_returns_unknown_when_no_id(self):
        """Returns 'unknown' when no identifier found."""
        config = {
            "primary_id_field": "my_id",
            "ref_id_field": "my_ref",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {"other_field": "value"}

        content_id = normalizer._generate_content_id(metadata)

        assert content_id == "unknown"

    def test_strips_whitespace_from_id(self):
        """Strips whitespace from identifier values."""
        config = {"primary_id_field": "id"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"id": "  TRIMMED123  "}

        content_id = normalizer._generate_content_id(metadata)

        assert content_id == "TRIMMED123"

    def test_skips_empty_primary_id(self):
        """Skips empty primary_id and uses ref_id."""
        config = {
            "primary_id_field": "my_id",
            "ref_id_field": "my_ref",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {"my_id": "", "my_ref": "REF456"}

        content_id = normalizer._generate_content_id(metadata)

        assert content_id == "REF456"


@pytest.mark.unit
class TestGenericXmlNormalizerCorrelationId:
    """Tests for correlation ID generation"""

    def test_prefers_ref_id_for_correlation(self):
        """Prefers ref_id over primary_id for correlation."""
        config = {
            "primary_id_field": "my_id",
            "ref_id_field": "my_ref",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {"my_id": "PRIMARY123", "my_ref": "REF456"}

        correlation_id = normalizer._get_correlation_id(metadata)

        assert correlation_id == "REF456"

    def test_falls_back_to_primary_id(self):
        """Falls back to primary_id when ref_id is missing."""
        config = {
            "primary_id_field": "my_id",
            "ref_id_field": "my_ref",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {"my_id": "PRIMARY123"}

        correlation_id = normalizer._get_correlation_id(metadata)

        assert correlation_id == "PRIMARY123"


@pytest.mark.unit
class TestGenericXmlNormalizerExtractors:
    """Tests for field extraction helper methods"""

    def test_extract_year_valid(self):
        """Extracts valid year from configured field."""
        config = {"premiere_year_field": "year"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"year": 2024}

        result = normalizer._extract_year(metadata)

        assert result == 2024

    def test_extract_year_string(self):
        """Extracts year from string value."""
        config = {"premiere_year_field": "year"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"year": "2024"}

        result = normalizer._extract_year(metadata)

        assert result == 2024

    def test_extract_year_invalid(self):
        """Returns None for invalid year."""
        config = {"premiere_year_field": "year"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"year": "not-a-year"}

        result = normalizer._extract_year(metadata)

        assert result is None

    def test_extract_year_missing(self):
        """Returns None when year field is missing."""
        config = {"premiere_year_field": "year"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"other": "value"}

        result = normalizer._extract_year(metadata)

        assert result is None

    def test_extract_date_valid(self):
        """Extracts valid date from configured field."""
        config = {"original_air_date_field": "air_date"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"air_date": "2024-03-15"}

        result = normalizer._extract_date(metadata)

        assert result == "2024-03-15"

    def test_extract_date_missing(self):
        """Returns None when date field is missing."""
        config = {"original_air_date_field": "air_date"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"other": "value"}

        result = normalizer._extract_date(metadata)

        assert result is None

    def test_extract_country_valid(self):
        """Extracts valid country from configured field."""
        config = {"country_code_field": "country"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"country": "US"}

        result = normalizer._extract_country(metadata)

        assert result == "US"

    def test_extract_language_valid(self):
        """Extracts valid language from configured field."""
        config = {"language_field": "lang"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"lang": "en-US"}

        result = normalizer._extract_language(metadata)

        assert result == "en-US"

    def test_extract_run_length_iso_format(self):
        """Preserves ISO 8601 duration format."""
        config = {"run_length_field": "duration"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"duration": "PT45M"}

        result = normalizer._extract_run_length(metadata)

        assert result == "PT45M"

    def test_extract_run_length_seconds(self):
        """Converts seconds to ISO 8601 format."""
        config = {"run_length_field": "duration"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"duration": "3600"}  # 1 hour in seconds

        result = normalizer._extract_run_length(metadata)

        assert result == "PT1H"

    def test_extract_run_length_with_minutes_and_seconds(self):
        """Converts seconds to ISO 8601 with minutes and seconds."""
        config = {"run_length_field": "duration"}
        normalizer = GenericXmlNormalizer(config)
        metadata = {"duration": "2705"}  # 45 minutes 5 seconds

        result = normalizer._extract_run_length(metadata)

        assert result == "PT45M5S"


@pytest.mark.unit
class TestGenericXmlNormalizerNormalize:
    """Tests for GenericXmlNormalizer.normalize()"""

    def test_normalize_returns_success_for_valid_input(self):
        """Returns successful result for valid input."""
        config = create_sample_config()
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.normalize(metadata)

        assert result.success is True
        assert result.normalized_metadata is not None

    def test_normalize_returns_failure_for_empty_input(self):
        """Returns failure for empty input."""
        normalizer = GenericXmlNormalizer()

        result = normalizer.normalize({})

        assert result.success is False
        assert result.normalized_metadata is None
        assert result.validation.is_valid is False

    def test_normalize_includes_content_id(self):
        """Normalized output includes content_id."""
        config = create_sample_config()
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.normalize(metadata)

        assert result.success is True
        assert result.normalized_metadata is not None
        basic = result.normalized_metadata.get("BasicMetadata", {})
        assert basic.get("ContentId") == "ACME123456"

    def test_normalize_includes_source_attribution(self):
        """Normalized output includes source_attribution."""
        config = create_sample_config()
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.normalize(metadata)

        assert result.success is True
        assert result.normalized_metadata is not None
        source = result.normalized_metadata.get("SourceAttribution", {})
        assert source.get("SourceSystem") == "acme"
        assert source.get("SourceType") == "generic_xml"
        assert source.get("CorrelationId") == "REF789"

    def test_normalize_includes_raw_source_when_configured(self):
        """Includes raw_source when include_raw_source is True."""
        config = create_sample_config()
        config["include_raw_source"] = True
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.normalize(metadata)

        assert result.success is True
        assert result.raw_source == metadata

    def test_normalize_excludes_raw_source_by_default(self):
        """Excludes raw_source by default."""
        config = create_sample_config()
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.normalize(metadata)

        assert result.success is True
        assert result.raw_source is None

    def test_normalize_handles_exception(self):
        """Handles exceptions during normalization gracefully."""
        # Create a config that will cause an error in field mappers
        config = {"source_namespace_prefix": "TEST"}
        normalizer = GenericXmlNormalizer(config)

        # Metadata that might cause issues
        metadata = {"content_id": "123", "title": "Test"}

        # Should not raise, should return failure result
        result = normalizer.normalize(metadata)

        # The result depends on whether field mappers handle missing config
        # gracefully - this tests the exception handling path
        assert isinstance(result, NormalizationResult)

    def test_normalize_validation_result_included(self):
        """Validation result is included in normalization result."""
        config = create_sample_config()
        normalizer = GenericXmlNormalizer(config)
        metadata = create_sample_metadata()

        result = normalizer.normalize(metadata)

        assert result.validation is not None
        assert isinstance(result.validation, ValidationResult)


@pytest.mark.unit
class TestGenericXmlNormalizerMinimalConfig:
    """Tests with minimal configuration to verify defaults work"""

    def test_normalizes_with_minimal_config(self):
        """Can normalize with minimal configuration."""
        config = {
            "source_namespace_prefix": "TEST",
            "primary_id_field": "id",
        }
        normalizer = GenericXmlNormalizer(config)
        metadata = {
            "id": "TEST123",
            "title": "Test Content",
        }

        result = normalizer.normalize(metadata)

        # Should succeed even with minimal config
        assert isinstance(result, NormalizationResult)

    def test_normalizes_with_empty_config(self):
        """Can normalize with empty configuration using defaults."""
        normalizer = GenericXmlNormalizer({})
        metadata = {
            "id": "DEFAULT123",
            "title": "Default Test",
        }

        result = normalizer.normalize(metadata)

        assert isinstance(result, NormalizationResult)
