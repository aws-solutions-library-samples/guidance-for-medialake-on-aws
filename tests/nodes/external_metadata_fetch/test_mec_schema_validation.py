"""
Tests for MEC JSON schema validation.

These tests verify that:
- Normalized metadata output validates against the MEC JSON schema
- Required MEC elements are present when source data is available
- Schema correctly rejects invalid structures
- Sample outputs pass validation

Note: This is a one-way transformation validation (source XML → internal JSON).
No XML export or round-trip validation is required.
"""

import pytest
from jsonschema import ValidationError, validate
from nodes.external_metadata_fetch.normalizers import create_normalizer
from nodes.external_metadata_fetch.normalizers.mec_json_schema import (
    ALT_IDENTIFIER_SCHEMA,
    JOB_SCHEMA,
    LOCALIZED_INFO_SCHEMA,
    PARENT_SCHEMA,
    PERSON_NAME_SCHEMA,
    RATING_SCHEMA,
    SEQUENCE_INFO_SCHEMA,
    get_basic_metadata_schema,
    get_component_schemas,
    get_mec_schema,
)

from tests.nodes.external_metadata_fetch.fixtures import (
    SAMPLE_CONFIG,
    load_fixture,
)

# Fixture file names for sample-based validation
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

ALL_FIXTURES = EPISODE_FIXTURES + TRAILER_FIXTURES + SPECIAL_FIXTURES


@pytest.fixture
def mec_schema():
    """Get the complete MEC JSON schema."""
    return get_mec_schema()


@pytest.fixture
def basic_metadata_schema():
    """Get the BasicMetadata JSON schema."""
    return get_basic_metadata_schema()


@pytest.fixture
def normalizer():
    """Create a normalizer with sample configuration."""
    return create_normalizer("generic_xml", SAMPLE_CONFIG)


@pytest.mark.unit
class TestSchemaStructure:
    """Tests for schema structure and availability."""

    def test_mec_schema_has_required_fields(self, mec_schema):
        """MEC schema defines required fields."""
        assert "required" in mec_schema
        assert "BasicMetadata" in mec_schema["required"]
        assert "SchemaVersion" in mec_schema["required"]

    def test_mec_schema_has_properties(self, mec_schema):
        """MEC schema defines expected properties."""
        props = mec_schema["properties"]
        assert "BasicMetadata" in props
        assert "CustomFields" in props
        assert "ParentMetadata" in props
        assert "SourceAttribution" in props
        assert "SchemaVersion" in props

    def test_basic_metadata_schema_has_required_fields(self, basic_metadata_schema):
        """BasicMetadata schema defines required fields."""
        assert "required" in basic_metadata_schema
        assert "ContentId" in basic_metadata_schema["required"]
        assert "WorkType" in basic_metadata_schema["required"]

    def test_component_schemas_available(self):
        """All component schemas are available."""
        schemas = get_component_schemas()
        expected_components = [
            "PersonName",
            "Job",
            "Rating",
            "LocalizedInfo",
            "SequenceInfo",
            "Parent",
            "AltIdentifier",
            "AssociatedOrg",
            "VideoAttributes",
            "AudioAttributes",
            "SubtitleAttributes",
            "BasicMetadata",
            "SourceAttribution",
            "NormalizedMetadata",
        ]
        for component in expected_components:
            assert component in schemas


@pytest.mark.unit
class TestPersonNameValidation:
    """Tests for PersonName schema validation."""

    def test_valid_person_name_minimal(self):
        """Valid PersonName with only required DisplayName."""
        data = {"DisplayName": "John Actor"}
        validate(data, PERSON_NAME_SCHEMA)

    def test_valid_person_name_full(self):
        """Valid PersonName with all fields."""
        data = {
            "DisplayName": "John Actor",
            "SortName": "Actor, John",
            "FirstGivenName": "John",
            "SecondGivenName": "Michael",
            "FamilyName": "Actor",
            "Suffix": "Jr.",
            "Moniker": "Johnny",
        }
        validate(data, PERSON_NAME_SCHEMA)

    def test_invalid_person_name_missing_display_name(self):
        """PersonName without DisplayName is invalid."""
        data = {"FirstGivenName": "John", "FamilyName": "Actor"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, PERSON_NAME_SCHEMA)
        assert "DisplayName" in str(exc_info.value)

    def test_invalid_person_name_empty_display_name(self):
        """PersonName with empty DisplayName is invalid."""
        data = {"DisplayName": ""}
        with pytest.raises(ValidationError):
            validate(data, PERSON_NAME_SCHEMA)


@pytest.mark.unit
class TestJobValidation:
    """Tests for Job (People) schema validation."""

    def test_valid_job_minimal(self):
        """Valid Job with required fields only."""
        data = {
            "JobFunction": "Actor",
            "Name": {"DisplayName": "John Actor"},
        }
        validate(data, JOB_SCHEMA)

    def test_valid_job_full(self):
        """Valid Job with all fields."""
        data = {
            "JobFunction": "Actor",
            "Name": {
                "DisplayName": "John Actor",
                "FirstGivenName": "John",
                "FamilyName": "Actor",
            },
            "JobDisplay": "Lead Actor",
            "BillingBlockOrder": 1,
            "Character": "Hero",
            "Guest": False,
        }
        validate(data, JOB_SCHEMA)

    def test_valid_job_guest_actor(self):
        """Valid guest actor Job."""
        data = {
            "JobFunction": "Actor",
            "Name": {"DisplayName": "Guest Star"},
            "Guest": True,
        }
        validate(data, JOB_SCHEMA)

    def test_invalid_job_missing_function(self):
        """Job without JobFunction is invalid."""
        data = {"Name": {"DisplayName": "John Actor"}}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, JOB_SCHEMA)
        assert "JobFunction" in str(exc_info.value)

    def test_invalid_job_unknown_function(self):
        """Job with unknown JobFunction is invalid."""
        data = {
            "JobFunction": "UnknownRole",
            "Name": {"DisplayName": "John Actor"},
        }
        with pytest.raises(ValidationError):
            validate(data, JOB_SCHEMA)


@pytest.mark.unit
class TestRatingValidation:
    """Tests for Rating schema validation."""

    def test_valid_rating_minimal(self):
        """Valid Rating with required fields only."""
        data = {
            "Region": "US",
            "System": "us-tv",
            "Value": "TV-MA",
        }
        validate(data, RATING_SCHEMA)

    def test_valid_rating_with_reason(self):
        """Valid Rating with content descriptors."""
        data = {
            "Region": "US",
            "System": "us-tv",
            "Value": "TV-MA",
            "Reason": "LSV",
        }
        validate(data, RATING_SCHEMA)

    def test_invalid_rating_missing_region(self):
        """Rating without Region is invalid."""
        data = {"System": "us-tv", "Value": "TV-MA"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, RATING_SCHEMA)
        assert "Region" in str(exc_info.value)

    def test_invalid_rating_missing_system(self):
        """Rating without System is invalid."""
        data = {"Region": "US", "Value": "TV-MA"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, RATING_SCHEMA)
        assert "System" in str(exc_info.value)

    def test_invalid_rating_missing_value(self):
        """Rating without Value is invalid."""
        data = {"Region": "US", "System": "us-tv"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, RATING_SCHEMA)
        assert "Value" in str(exc_info.value)


@pytest.mark.unit
class TestLocalizedInfoValidation:
    """Tests for LocalizedInfo schema validation."""

    def test_valid_localized_info_minimal(self):
        """Valid LocalizedInfo with required Language only."""
        data = {"Language": "en-US"}
        validate(data, LOCALIZED_INFO_SCHEMA)

    def test_valid_localized_info_full(self):
        """Valid LocalizedInfo with all fields."""
        data = {
            "Language": "en-US",
            "TitleDisplayUnlimited": "Full Episode Title",
            "TitleDisplay19": "Short Title",
            "TitleInternalAlias": "Internal Ref",
            "Summary190": "Short summary",
            "Summary400": "Medium summary",
            "Summary4000": "Full description",
            "Genres": ["Drama", "Horror"],
            "Keywords": ["adventure", "mystery"],
            "CopyrightLine": "© 2024 Example Studios",
        }
        validate(data, LOCALIZED_INFO_SCHEMA)

    def test_invalid_localized_info_missing_language(self):
        """LocalizedInfo without Language is invalid."""
        data = {"TitleDisplayUnlimited": "Title"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, LOCALIZED_INFO_SCHEMA)
        assert "Language" in str(exc_info.value)

    def test_invalid_localized_info_bad_language_format(self):
        """LocalizedInfo with invalid language format is invalid."""
        data = {"Language": "english"}
        with pytest.raises(ValidationError):
            validate(data, LOCALIZED_INFO_SCHEMA)


@pytest.mark.unit
class TestSequenceInfoValidation:
    """Tests for SequenceInfo schema validation."""

    def test_valid_sequence_info_minimal(self):
        """Valid SequenceInfo with required Number only."""
        data = {"Number": 1}
        validate(data, SEQUENCE_INFO_SCHEMA)

    def test_valid_sequence_info_full(self):
        """Valid SequenceInfo with all fields."""
        data = {"Number": 5, "DistributionNumber": "S01E05"}
        validate(data, SEQUENCE_INFO_SCHEMA)

    def test_valid_sequence_info_zero(self):
        """SequenceInfo with Number=0 is valid (for trailers)."""
        data = {"Number": 0}
        validate(data, SEQUENCE_INFO_SCHEMA)

    def test_invalid_sequence_info_missing_number(self):
        """SequenceInfo without Number is invalid."""
        data = {"DistributionNumber": "S01E05"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, SEQUENCE_INFO_SCHEMA)
        assert "Number" in str(exc_info.value)

    def test_invalid_sequence_info_negative_number(self):
        """SequenceInfo with negative Number is invalid."""
        data = {"Number": -1}
        with pytest.raises(ValidationError):
            validate(data, SEQUENCE_INFO_SCHEMA)


@pytest.mark.unit
class TestParentValidation:
    """Tests for Parent relationship schema validation."""

    def test_valid_parent_episode(self):
        """Valid Parent for episode relationship."""
        data = {
            "RelationshipType": "isepisodeof",
            "ParentContentId": "SEASON123",
        }
        validate(data, PARENT_SCHEMA)

    def test_valid_parent_season(self):
        """Valid Parent for season relationship."""
        data = {
            "RelationshipType": "isseasonof",
            "ParentContentId": "SERIES456",
        }
        validate(data, PARENT_SCHEMA)

    def test_invalid_parent_missing_type(self):
        """Parent without RelationshipType is invalid."""
        data = {"ParentContentId": "SEASON123"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, PARENT_SCHEMA)
        assert "RelationshipType" in str(exc_info.value)

    def test_invalid_parent_unknown_type(self):
        """Parent with unknown RelationshipType is invalid."""
        data = {
            "RelationshipType": "unknownrelation",
            "ParentContentId": "PARENT123",
        }
        with pytest.raises(ValidationError):
            validate(data, PARENT_SCHEMA)


@pytest.mark.unit
class TestAltIdentifierValidation:
    """Tests for AltIdentifier schema validation."""

    def test_valid_alt_identifier(self):
        """Valid AltIdentifier with all required fields."""
        data = {"Namespace": "ACME", "Identifier": "ID123456"}
        validate(data, ALT_IDENTIFIER_SCHEMA)

    def test_invalid_alt_identifier_missing_namespace(self):
        """AltIdentifier without Namespace is invalid."""
        data = {"Identifier": "ID123456"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, ALT_IDENTIFIER_SCHEMA)
        assert "Namespace" in str(exc_info.value)

    def test_invalid_alt_identifier_empty_identifier(self):
        """AltIdentifier with empty Identifier is invalid."""
        data = {"Namespace": "ACME", "Identifier": ""}
        with pytest.raises(ValidationError):
            validate(data, ALT_IDENTIFIER_SCHEMA)


@pytest.mark.unit
class TestNormalizedMetadataValidation:
    """Tests for complete NormalizedMetadata schema validation."""

    def test_valid_normalized_metadata_minimal(self, mec_schema):
        """Valid NormalizedMetadata with minimal required fields."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST100001",
                "WorkType": "Episode",
            },
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)

    def test_valid_normalized_metadata_full(self, mec_schema):
        """Valid NormalizedMetadata with all fields populated."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST100001",
                "WorkType": "Episode",
                "WorkTypeDetail": "Full Episode",
                "LocalizedInfo": [
                    {
                        "Language": "en-US",
                        "TitleDisplayUnlimited": "Test Episode Title",
                        "Summary190": "Short summary",
                        "Genres": ["Drama"],
                    }
                ],
                "ReleaseYear": 2024,
                "ReleaseDate": "2024-03-15",
                "Ratings": [
                    {
                        "Region": "US",
                        "System": "us-tv",
                        "Value": "TV-MA",
                        "Reason": "LSV",
                    }
                ],
                "People": [
                    {
                        "JobFunction": "Actor",
                        "Name": {"DisplayName": "John Actor"},
                        "BillingBlockOrder": 1,
                        "Character": "Hero",
                    }
                ],
                "CountryOfOrigin": "US",
                "OriginalLanguage": "en-US",
                "SequenceInfo": {"Number": 1},
                "Parents": [
                    {"RelationshipType": "isepisodeof", "ParentContentId": "SEASON1"}
                ],
                "AltIdentifiers": [{"Namespace": "ACME", "Identifier": "TST100001"}],
            },
            "CustomFields": {"platform_genres": {"amazon": ["Drama"]}},
            "SourceAttribution": {
                "SourceSystem": "acme",
                "SourceType": "generic_xml",
                "CorrelationId": "L00100001",
                "NormalizedAt": "2024-03-15T10:30:00Z",
            },
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)

    def test_invalid_normalized_metadata_missing_basic(self, mec_schema):
        """NormalizedMetadata without BasicMetadata is invalid."""
        data = {"SchemaVersion": "1.0.0"}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, mec_schema)
        assert "BasicMetadata" in str(exc_info.value)

    def test_invalid_normalized_metadata_missing_version(self, mec_schema):
        """NormalizedMetadata without SchemaVersion is invalid."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST100001",
                "WorkType": "Episode",
            }
        }
        with pytest.raises(ValidationError) as exc_info:
            validate(data, mec_schema)
        assert "SchemaVersion" in str(exc_info.value)

    def test_invalid_normalized_metadata_bad_work_type(self, mec_schema):
        """NormalizedMetadata with invalid WorkType is invalid."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST100001",
                "WorkType": "InvalidType",
            },
            "SchemaVersion": "1.0.0",
        }
        with pytest.raises(ValidationError):
            validate(data, mec_schema)


@pytest.mark.unit
class TestSampleOutputValidation:
    """Tests that validate sample normalizer outputs against the schema."""

    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    def test_sample_output_validates(self, normalizer, mec_schema, fixture_name: str):
        """Each sample fixture output validates against MEC schema."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        assert result.success is True, f"Normalization failed for {fixture_name}"
        assert result.normalized_metadata is not None

        # Validate against schema
        validate(result.normalized_metadata, mec_schema)

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_has_required_mec_elements(self, normalizer, fixture_name: str):
        """Episode fixtures have required MEC elements when source data available."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})

        # Required fields
        assert basic.get("ContentId") is not None
        assert basic.get("WorkType") == "Episode"

        # Expected fields for episodes with full metadata
        assert basic.get("LocalizedInfo") is not None
        assert len(basic.get("LocalizedInfo", [])) > 0

        # Episodes should have sequence info
        assert basic.get("SequenceInfo") is not None

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_localized_info_has_title(self, normalizer, fixture_name: str):
        """Episode LocalizedInfo has title when source data available."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        localized_info = basic.get("LocalizedInfo", [])

        assert len(localized_info) > 0
        first_info = localized_info[0]

        # Should have at least one title field
        has_title = (
            first_info.get("TitleDisplayUnlimited") is not None
            or first_info.get("TitleDisplay19") is not None
            or first_info.get("TitleInternalAlias") is not None
        )
        assert has_title, f"No title found in {fixture_name}"

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_ratings_have_required_fields(self, normalizer, fixture_name: str):
        """Episode ratings have all required MEC fields."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        ratings = basic.get("Ratings", [])

        for rating in ratings:
            # All required fields must be present
            assert rating.get("Region") is not None, "Rating missing Region"
            assert rating.get("System") is not None, "Rating missing System"
            assert rating.get("Value") is not None, "Rating missing Value"

    @pytest.mark.parametrize("fixture_name", EPISODE_FIXTURES)
    def test_episode_people_have_required_fields(self, normalizer, fixture_name: str):
        """Episode people entries have all required MEC fields."""
        metadata = load_fixture(fixture_name)
        result = normalizer.normalize(metadata)

        basic = result.normalized_metadata.get("BasicMetadata", {})
        people = basic.get("People", [])

        for person in people:
            # JobFunction is required
            assert person.get("JobFunction") is not None, "Person missing JobFunction"

            # Name with DisplayName is required
            name = person.get("Name", {})
            assert name.get("DisplayName") is not None, "Person missing DisplayName"


@pytest.mark.unit
class TestSchemaVersionValidation:
    """Tests for schema version format validation."""

    def test_valid_schema_version_format(self, mec_schema):
        """Valid semantic version format passes validation."""
        data = {
            "BasicMetadata": {"ContentId": "TST1", "WorkType": "Movie"},
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)

    def test_valid_schema_version_higher(self, mec_schema):
        """Higher version numbers pass validation."""
        data = {
            "BasicMetadata": {"ContentId": "TST1", "WorkType": "Movie"},
            "SchemaVersion": "2.5.10",
        }
        validate(data, mec_schema)

    def test_invalid_schema_version_format(self, mec_schema):
        """Invalid version format fails validation."""
        data = {
            "BasicMetadata": {"ContentId": "TST1", "WorkType": "Movie"},
            "SchemaVersion": "v1.0",
        }
        with pytest.raises(ValidationError):
            validate(data, mec_schema)


@pytest.mark.unit
class TestSourceAttributionValidation:
    """Tests for SourceAttribution schema validation."""

    def test_valid_source_attribution_minimal(self, mec_schema):
        """Valid SourceAttribution with required fields only."""
        data = {
            "BasicMetadata": {"ContentId": "TST1", "WorkType": "Movie"},
            "SourceAttribution": {
                "SourceSystem": "acme",
                "SourceType": "generic_xml",
                "CorrelationId": "CORR123",
            },
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)

    def test_valid_source_attribution_with_timestamp(self, mec_schema):
        """Valid SourceAttribution with timestamp."""
        data = {
            "BasicMetadata": {"ContentId": "TST1", "WorkType": "Movie"},
            "SourceAttribution": {
                "SourceSystem": "acme",
                "SourceType": "generic_xml",
                "CorrelationId": "CORR123",
                "NormalizedAt": "2024-03-15T10:30:00Z",
            },
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)


@pytest.mark.unit
class TestReleaseDateValidation:
    """Tests for ReleaseDate format validation."""

    def test_valid_release_date_format(self, mec_schema):
        """Valid ISO date format passes validation."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST1",
                "WorkType": "Movie",
                "ReleaseDate": "2024-03-15",
            },
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)

    def test_invalid_release_date_format(self, mec_schema):
        """Invalid date format fails validation."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST1",
                "WorkType": "Movie",
                "ReleaseDate": "March 15, 2024",
            },
            "SchemaVersion": "1.0.0",
        }
        with pytest.raises(ValidationError):
            validate(data, mec_schema)


@pytest.mark.unit
class TestReleaseYearValidation:
    """Tests for ReleaseYear range validation."""

    def test_valid_release_year(self, mec_schema):
        """Valid release year passes validation."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST1",
                "WorkType": "Movie",
                "ReleaseYear": 2024,
            },
            "SchemaVersion": "1.0.0",
        }
        validate(data, mec_schema)

    def test_invalid_release_year_too_old(self, mec_schema):
        """Release year before 1800 fails validation."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST1",
                "WorkType": "Movie",
                "ReleaseYear": 1700,
            },
            "SchemaVersion": "1.0.0",
        }
        with pytest.raises(ValidationError):
            validate(data, mec_schema)

    def test_invalid_release_year_too_future(self, mec_schema):
        """Release year after 2100 fails validation."""
        data = {
            "BasicMetadata": {
                "ContentId": "TST1",
                "WorkType": "Movie",
                "ReleaseYear": 2200,
            },
            "SchemaVersion": "1.0.0",
        }
        with pytest.raises(ValidationError):
            validate(data, mec_schema)
