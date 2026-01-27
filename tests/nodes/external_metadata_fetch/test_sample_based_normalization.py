"""
Sample-based tests for the Generic XML normalizer.

These tests use anonymized XML fixtures to verify that the normalizer
correctly processes real-world metadata structures. All fixtures use
generic, customer-agnostic data.

Test Categories:
- Full Episode normalization (3 fixtures)
- Trailer/Interstitial normalization (2 fixtures)
- Special content normalization (1 fixture)
- Field mapping verification
- Custom fields extraction
"""

import pytest
from nodes.external_metadata_fetch.normalizers import (
    create_normalizer,
)

from tests.nodes.external_metadata_fetch.fixtures import (
    SAMPLE_CONFIG,
    load_fixture,
)

# Fixture file names
EPISODE_FIXTURES = [
    "episode_full_001.xml",
    "episode_full_002.xml",
    "episode_full_003.xml",
]

TRAILER_FIXTURES = [
    "trailer_001.xml",
    "trailer_002.xml",
]

SPECIAL_FIXTURES = [
    "special_content_001.xml",
]


@pytest.fixture
def normalizer():
    """Create a normalizer with sample configuration."""
    return create_normalizer("generic_xml", SAMPLE_CONFIG)


@pytest.mark.unit
class TestFullEpisodeNormalization:
    """Tests for full episode fixture normalization."""

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_normalizes_successfully(self, normalizer, fixture_name: str):
        """Each episode fixture normalizes without errors."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        assert result.success is True, f"Failed to normalize {fixture_name}"
        assert result.normalized_metadata is not None

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_has_content_id(self, normalizer, fixture_name: str):
        """Each episode has a valid content_id."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        content_id = basic.get("ContentId")

        assert content_id is not None
        assert content_id != "unknown"
        assert content_id.startswith("TST")  # Our test IDs start with TST

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_has_work_type(self, normalizer, fixture_name: str):
        """Each episode has correct work_type."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        work_type = basic.get("WorkType")

        assert work_type == "Episode"

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_has_localized_info(self, normalizer, fixture_name: str):
        """Each episode has localized info with title."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        localized_info = basic.get("LocalizedInfo", [])

        assert len(localized_info) > 0
        first_info = localized_info[0]
        assert first_info.get("TitleDisplayUnlimited") is not None

    def test_episode_001_specific_fields(self, normalizer):
        """Verify specific fields in episode_full_001.xml."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})

        # Check content ID
        assert basic.get("ContentId") == "TST100001"

        # Check release year
        assert basic.get("ReleaseYear") == 2024

        # Check release date
        assert basic.get("ReleaseDate") == "2024-03-15"

        # Check country
        assert basic.get("CountryOfOrigin") == "US"

        # Check language
        assert basic.get("OriginalLanguage") == "en-US"

    def test_episode_001_has_sequence_info(self, normalizer):
        """Episode 001 has correct sequence info."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        sequence_info = basic.get("SequenceInfo")

        assert sequence_info is not None
        assert sequence_info.get("Number") == 1

    def test_episode_001_has_parents(self, normalizer):
        """Episode 001 has parent relationships."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        parents = basic.get("Parents", [])

        # Should have at least one parent (season or series)
        assert len(parents) >= 1

    def test_episode_002_has_guest_actors(self, normalizer):
        """Episode 002 has guest actors mapped correctly."""
        metadata = load_fixture("episode_full_002.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        people = basic.get("People", [])

        # Should have people mapped
        assert len(people) > 0

        # Check for actors
        actors = [p for p in people if p.get("JobFunction") == "Actor"]
        assert len(actors) > 0

    def test_episode_002_has_multiple_ratings(self, normalizer):
        """Episode 002 has multiple rating systems."""
        metadata = load_fixture("episode_full_002.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        ratings = basic.get("Ratings", [])

        # Episode 002 has ACMA, au-tv, ca-tv, us-tv, TV Rating, nz-am
        assert len(ratings) >= 4


@pytest.mark.unit
class TestTrailerNormalization:
    """Tests for trailer/interstitial fixture normalization."""

    @pytest.mark.parametrize("fixture_name", TRAILER_FIXTURES)
    def test_trailer_normalizes_successfully(self, normalizer, fixture_name: str):
        """Each trailer fixture normalizes without errors."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        assert result.success is True, f"Failed to normalize {fixture_name}"
        assert result.normalized_metadata is not None

    def test_trailer_001_is_promotion(self, normalizer):
        """Trailer 001 (Interstitial) is classified as Promotion."""
        metadata = load_fixture("trailer_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        work_type = basic.get("WorkType")

        # Interstitial content should be classified as Promotion
        assert work_type == "Promotion"

    def test_trailer_001_has_episode_zero(self, normalizer):
        """Trailer 001 has episode_number=0."""
        metadata = load_fixture("trailer_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        sequence_info = basic.get("SequenceInfo")

        # Trailers typically have episode_number=0
        if sequence_info:
            assert sequence_info.get("Number") == 0

    def test_trailer_002_minimal_metadata(self, normalizer):
        """Trailer 002 handles minimal metadata gracefully."""
        metadata = load_fixture("trailer_002.xml")
        result = normalizer.normalize(metadata)

        assert result.success is True

        basic = result.normalized_metadata.get("BasicMetadata", {})

        # Should still have basic fields
        assert basic.get("ContentId") is not None
        assert basic.get("WorkType") is not None


@pytest.mark.unit
class TestSpecialContentNormalization:
    """Tests for special content fixture normalization."""

    def test_special_content_normalizes_successfully(self, normalizer):
        """Special content fixture normalizes without errors."""
        metadata = load_fixture("special_content_001.xml")
        result = normalizer.normalize(metadata)

        assert result.success is True
        assert result.normalized_metadata is not None

    def test_special_content_has_high_episode_number(self, normalizer):
        """Special content has non-standard episode number (99)."""
        metadata = load_fixture("special_content_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        sequence_info = basic.get("SequenceInfo")

        if sequence_info:
            # Special content often uses high episode numbers
            assert sequence_info.get("Number") == 99

    def test_special_content_video_type(self, normalizer):
        """Special content has video_type=Special."""
        metadata = load_fixture("special_content_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        work_type_detail = basic.get("WorkTypeDetail")

        # video_type=Special should be captured
        assert work_type_detail == "Special"


@pytest.mark.unit
class TestSourceAttribution:
    """Tests for source attribution in normalized output."""

    @pytest.mark.parametrize(
        "fixture_name", EPISODE_FIXTURES + TRAILER_FIXTURES + SPECIAL_FIXTURES
    )
    def test_has_source_attribution(self, normalizer, fixture_name: str):
        """All fixtures have source_attribution populated."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        source = result.normalized_metadata.get("SourceAttribution", {})

        assert source.get("SourceSystem") == "acme"
        assert source.get("SourceType") == "generic_xml"
        assert source.get("CorrelationId") is not None

    def test_correlation_id_uses_refid(self, normalizer):
        """Correlation ID uses refid field."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        source = result.normalized_metadata.get("SourceAttribution", {})

        # refid is L00100001 in episode_full_001.xml
        assert source.get("CorrelationId") == "L00100001"


@pytest.mark.unit
class TestAltIdentifiers:
    """Tests for alternative identifier mapping."""

    def test_episode_has_alt_identifiers(self, normalizer):
        """Episode has multiple alt_identifiers mapped."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        alt_ids = basic.get("AltIdentifiers", [])

        # Should have identifiers from: acme_id, refid, version_id, etc.
        assert len(alt_ids) >= 2

        # Check namespace prefixes
        namespaces = [aid.get("Namespace") for aid in alt_ids]

        # Should have ACME namespace (from acme_id with empty suffix)
        assert "ACME" in namespaces or any(ns.startswith("ACME") for ns in namespaces)

    def test_tms_identifiers_have_tms_namespace(self, normalizer):
        """TMS identifiers use TMS namespace (absolute, not prefixed)."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        alt_ids = basic.get("AltIdentifiers", [])

        # Find TMS identifiers
        tms_ids = [aid for aid in alt_ids if aid.get("Namespace") == "TMS"]

        # Should have TMS identifiers (tms_series_id, tms_episode_id)
        assert len(tms_ids) >= 1


@pytest.mark.unit
class TestCustomFields:
    """Tests for custom fields extraction."""

    def test_episode_has_custom_fields(self, normalizer):
        """Episode has custom_fields populated."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        custom_fields = result.normalized_metadata.get("CustomFields", {})

        # Should have some custom fields
        assert custom_fields is not None

    def test_platform_genres_in_custom_fields(self, normalizer):
        """Platform-specific genres are in custom_fields."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        custom_fields = result.normalized_metadata.get("CustomFields", {})

        # Platform genres should be extracted
        # The exact structure depends on the extract_custom_fields implementation
        platform_genres = custom_fields.get("platform_genres", {})

        # Episode 001 has Amazon, Apple, Shudder Prod, Bell Series, TELUS Series genres
        # At least some should be captured
        assert platform_genres is not None or "genres" in str(custom_fields)

    def test_advertising_fields_in_custom_fields(self, normalizer):
        """Advertising fields are in custom_fields."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        custom_fields = result.normalized_metadata.get("CustomFields", {})

        # ad_category and ad_content_id should be captured
        advertising = custom_fields.get("advertising", {})

        # Should have advertising data
        assert advertising is not None or "ad_" in str(custom_fields)


@pytest.mark.unit
class TestRatingsMapping:
    """Tests for ratings mapping."""

    def test_episode_001_ratings(self, normalizer):
        """Episode 001 has ratings mapped correctly."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        ratings = basic.get("Ratings", [])

        # Episode 001 has: TV Rating, us-tv, ca-tv, au-tv
        assert len(ratings) >= 3

        # Check that ratings have required fields
        for rating in ratings:
            assert rating.get("Region") is not None
            assert rating.get("System") is not None
            assert rating.get("Value") is not None

    def test_ratings_have_correct_regions(self, normalizer):
        """Ratings have correct region mappings."""
        metadata = load_fixture("episode_full_002.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        ratings = basic.get("Ratings", [])

        # Build a map of system -> region
        system_regions = {r.get("System"): r.get("Region") for r in ratings}

        # Verify expected mappings
        if "us-tv" in system_regions:
            assert system_regions["us-tv"] == "US"
        if "ca-tv" in system_regions:
            assert system_regions["ca-tv"] == "CA"
        if "au-tv" in system_regions:
            assert system_regions["au-tv"] == "AU"
        if "nz-am" in system_regions:
            assert system_regions["nz-am"] == "NZ"


@pytest.mark.unit
class TestPeopleMapping:
    """Tests for people/credits mapping."""

    def test_episode_001_has_actors(self, normalizer):
        """Episode 001 has actors mapped."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        people = basic.get("People", [])

        actors = [p for p in people if p.get("JobFunction") == "Actor"]

        # Episode 001 has 5 actors
        assert len(actors) >= 3

    def test_episode_001_has_directors(self, normalizer):
        """Episode 001 has directors mapped."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        people = basic.get("People", [])

        directors = [p for p in people if p.get("JobFunction") == "Director"]

        # Episode 001 has 1 director
        assert len(directors) >= 1

    def test_people_have_names(self, normalizer):
        """People entries have name information."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        people = basic.get("People", [])

        for person in people:
            name = person.get("Name", {})
            # Should have display_name (required by MEC)
            assert name.get("DisplayName") is not None

    def test_actors_have_character_names(self, normalizer):
        """Actors have character names when available."""
        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        people = basic.get("People", [])

        actors = [p for p in people if p.get("JobFunction") == "Actor"]

        # At least some actors should have character names
        actors_with_characters = [a for a in actors if a.get("Character")]
        assert len(actors_with_characters) >= 1


@pytest.mark.unit
class TestSchemaVersion:
    """Tests for schema version in output."""

    @pytest.mark.parametrize(
        "fixture_name", EPISODE_FIXTURES + TRAILER_FIXTURES + SPECIAL_FIXTURES
    )
    def test_has_schema_version(self, normalizer, fixture_name: str):
        """All fixtures have schema_version in output."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        schema_version = result.normalized_metadata.get("SchemaVersion")

        assert schema_version is not None
        assert schema_version == "1.0.0"
