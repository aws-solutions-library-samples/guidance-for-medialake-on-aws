"""
Unit tests for the MEC schema models.

These tests verify that the MEC schema dataclasses:
- Can be instantiated with required and optional fields
- Correctly serialize to dictionaries
- Exclude None/empty values from serialization
"""

import pytest

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.normalizers.mec_schema import (
    AltIdentifier,
    AssociatedOrg,
    AudioAttributes,
    BasicMetadata,
    Job,
    LocalizedInfo,
    NormalizedMetadata,
    Parent,
    PersonName,
    Rating,
    SequenceInfo,
    SourceAttribution,
    SubtitleAttributes,
    VideoAttributes,
)


@pytest.mark.unit
class TestAltIdentifier:
    """Tests for AltIdentifier dataclass"""

    def test_create_identifier(self):
        """Creates an identifier with namespace and value."""
        alt_id = AltIdentifier(namespace="CUSTOMER", identifier="ID123456")

        assert alt_id.namespace == "CUSTOMER"
        assert alt_id.identifier == "ID123456"

    def test_to_dict(self):
        """to_dict returns correct structure."""
        alt_id = AltIdentifier(namespace="TMS", identifier="EP043931170004")

        result = alt_id.to_dict()

        assert result == {"Namespace": "TMS", "Identifier": "EP043931170004"}


@pytest.mark.unit
class TestPersonName:
    """Tests for PersonName dataclass"""

    def test_create_with_display_name_only(self):
        """Creates name with only required display_name."""
        name = PersonName(display_name="Jacob Anderson")

        assert name.display_name == "Jacob Anderson"
        assert name.first_given_name is None
        assert name.family_name is None

    def test_create_with_all_fields(self):
        """Creates name with all fields populated."""
        name = PersonName(
            display_name="Jacob Anderson",
            sort_name="Anderson, Jacob",
            first_given_name="Jacob",
            family_name="Anderson",
            suffix="Jr.",
        )

        assert name.display_name == "Jacob Anderson"
        assert name.sort_name == "Anderson, Jacob"
        assert name.first_given_name == "Jacob"
        assert name.family_name == "Anderson"
        assert name.suffix == "Jr."

    def test_to_dict_excludes_none_values(self):
        """to_dict excludes None values."""
        name = PersonName(
            display_name="Jacob Anderson",
            first_given_name="Jacob",
        )

        result = name.to_dict()

        assert result == {
            "DisplayName": "Jacob Anderson",
            "FirstGivenName": "Jacob",
        }
        assert "FamilyName" not in result
        assert "SortName" not in result


@pytest.mark.unit
class TestJob:
    """Tests for Job dataclass"""

    def test_create_actor_job(self):
        """Creates an actor job with character."""
        name = PersonName(display_name="Jacob Anderson")
        job = Job(
            job_function="Actor",
            name=name,
            billing_block_order=1,
            character="John Protagonist",
        )

        assert job.job_function == "Actor"
        assert job.name.display_name == "Jacob Anderson"
        assert job.billing_block_order == 1
        assert job.character == "John Protagonist"

    def test_create_guest_actor(self):
        """Creates a guest actor job."""
        name = PersonName(display_name="Guest Star")
        job = Job(
            job_function="Actor",
            name=name,
            guest=True,
        )

        assert job.guest is True

    def test_to_dict_includes_nested_name(self):
        """to_dict includes nested name structure."""
        name = PersonName(
            display_name="John Director",
            first_given_name="John",
            family_name="Director",
        )
        job = Job(job_function="Director", name=name)

        result = job.to_dict()

        assert result["JobFunction"] == "Director"
        assert result["Name"]["DisplayName"] == "John Director"
        assert result["Name"]["FirstGivenName"] == "John"


@pytest.mark.unit
class TestRating:
    """Tests for Rating dataclass"""

    def test_create_rating_with_reason(self):
        """Creates a rating with content descriptors."""
        rating = Rating(
            region="US",
            system="us-tv",
            value="TV-MA",
            reason="LSV",
        )

        assert rating.region == "US"
        assert rating.system == "us-tv"
        assert rating.value == "TV-MA"
        assert rating.reason == "LSV"

    def test_create_rating_without_reason(self):
        """Creates a rating without content descriptors."""
        rating = Rating(region="CA", system="ca-tv", value="18+")

        assert rating.reason is None

    def test_to_dict_excludes_none_reason(self):
        """to_dict excludes reason when None."""
        rating = Rating(region="US", system="us-tv", value="TV-14")

        result = rating.to_dict()

        assert result == {"Region": "US", "System": "us-tv", "Value": "TV-14"}
        assert "Reason" not in result


@pytest.mark.unit
class TestLocalizedInfo:
    """Tests for LocalizedInfo dataclass"""

    def test_create_with_defaults(self):
        """Creates localized info with default language."""
        info = LocalizedInfo()

        assert info.language == "en-US"
        assert info.genres == []
        assert info.keywords == []

    def test_create_with_all_fields(self):
        """Creates localized info with all fields."""
        info = LocalizedInfo(
            language="en-US",
            title_display_unlimited="Full Episode Title",
            title_display_19="Short Title",
            summary_190="Short summary",
            summary_400="Medium summary for display",
            summary_4000="Full description",
            genres=["Drama", "Horror"],
            keywords=["adventure", "mystery"],
            copyright_line="© 2022 Example Studios",
        )

        assert info.title_display_unlimited == "Full Episode Title"
        assert info.summary_400 == "Medium summary for display"
        assert info.genres == ["Drama", "Horror"]

    def test_to_dict_excludes_empty_lists(self):
        """to_dict excludes empty lists."""
        info = LocalizedInfo(
            title_display_unlimited="Title",
        )

        result = info.to_dict()

        assert "genres" not in result
        assert "keywords" not in result

    def test_to_dict_includes_non_empty_lists(self):
        """to_dict includes non-empty lists."""
        info = LocalizedInfo(genres=["Drama"])

        result = info.to_dict()

        assert result["Genres"] == ["Drama"]

    def test_to_dict_includes_summary_400(self):
        """to_dict includes summary_400 when present."""
        info = LocalizedInfo(
            summary_190="Short",
            summary_400="Medium length summary",
            summary_4000="Full description",
        )

        result = info.to_dict()

        assert result["Summary190"] == "Short"
        assert result["Summary400"] == "Medium length summary"
        assert result["Summary4000"] == "Full description"


@pytest.mark.unit
class TestSequenceInfo:
    """Tests for SequenceInfo dataclass"""

    def test_create_episode_sequence(self):
        """Creates sequence info for an episode."""
        seq = SequenceInfo(number=5)

        assert seq.number == 5
        assert seq.distribution_number is None

    def test_to_dict(self):
        """to_dict returns correct structure."""
        seq = SequenceInfo(number=3, distribution_number="S01E03")

        result = seq.to_dict()

        assert result == {"Number": 3, "DistributionNumber": "S01E03"}


@pytest.mark.unit
class TestParent:
    """Tests for Parent dataclass"""

    def test_create_episode_parent(self):
        """Creates parent relationship for episode."""
        parent = Parent(
            relationship_type="isepisodeof",
            parent_content_id="RLS25733",
        )

        assert parent.relationship_type == "isepisodeof"
        assert parent.parent_content_id == "RLS25733"

    def test_to_dict(self):
        """to_dict returns correct structure."""
        parent = Parent(
            relationship_type="isseasonof",
            parent_content_id="SER12345",
        )

        result = parent.to_dict()

        assert result == {
            "RelationshipType": "isseasonof",
            "ParentContentId": "SER12345",
        }


@pytest.mark.unit
class TestVideoAttributes:
    """Tests for VideoAttributes dataclass"""

    def test_create_with_resolution(self):
        """Creates video attributes with resolution."""
        video = VideoAttributes(
            frame_rate="23.976",
            aspect_ratio="16:9",
            width_pixels=1920,
            height_pixels=1080,
        )

        assert video.frame_rate == "23.976"
        assert video.width_pixels == 1920
        assert video.height_pixels == 1080

    def test_to_dict_excludes_none_values(self):
        """to_dict excludes None values."""
        video = VideoAttributes(frame_rate="29.97")

        result = video.to_dict()

        assert result == {"FrameRate": "29.97"}
        assert "WidthPixels" not in result


@pytest.mark.unit
class TestAudioAttributes:
    """Tests for AudioAttributes dataclass"""

    def test_create_audio_track(self):
        """Creates audio attributes for a track."""
        audio = AudioAttributes(
            language="en",
            type="VisuallyImpaired",
            channels=2,
        )

        assert audio.language == "en"
        assert audio.type == "VisuallyImpaired"
        assert audio.channels == 2

    def test_to_dict(self):
        """to_dict returns correct structure."""
        audio = AudioAttributes(language="es")

        result = audio.to_dict()

        assert result == {"Language": "es"}


@pytest.mark.unit
class TestSubtitleAttributes:
    """Tests for SubtitleAttributes dataclass"""

    def test_create_subtitle(self):
        """Creates subtitle attributes."""
        subtitle = SubtitleAttributes(
            language="en",
            type="CC",
        )

        assert subtitle.language == "en"
        assert subtitle.type == "CC"

    def test_to_dict(self):
        """to_dict returns correct structure."""
        subtitle = SubtitleAttributes(language="es", type="SDH")

        result = subtitle.to_dict()

        assert result == {"Language": "es", "Type": "SDH"}


@pytest.mark.unit
class TestAssociatedOrg:
    """Tests for AssociatedOrg dataclass"""

    def test_create_network(self):
        """Creates an associated organization for a network."""
        org = AssociatedOrg(
            role="network",
            display_name="Test Network Plus",
        )

        assert org.role == "network"
        assert org.display_name == "Test Network Plus"
        assert org.organization_id is None

    def test_create_studio_with_id(self):
        """Creates an associated organization for a studio with ID."""
        org = AssociatedOrg(
            role="studio",
            display_name="Example Studios",
            organization_id="STUDIO123",
        )

        assert org.role == "studio"
        assert org.display_name == "Example Studios"
        assert org.organization_id == "STUDIO123"

    def test_to_dict_excludes_none_id(self):
        """to_dict excludes organization_id when None."""
        org = AssociatedOrg(role="network", display_name="Test Network")

        result = org.to_dict()

        assert result == {"Role": "network", "DisplayName": "Test Network"}
        assert "OrganizationId" not in result

    def test_to_dict_includes_id(self):
        """to_dict includes organization_id when present."""
        org = AssociatedOrg(
            role="distributor",
            display_name="Test Distributor",
            organization_id="DIST456",
        )

        result = org.to_dict()

        assert result == {
            "Role": "distributor",
            "DisplayName": "Test Distributor",
            "OrganizationId": "DIST456",
        }


@pytest.mark.unit
class TestBasicMetadata:
    """Tests for BasicMetadata dataclass"""

    def test_create_minimal_metadata(self):
        """Creates metadata with only required fields."""
        metadata = BasicMetadata(
            content_id="RLA236635",
            work_type="Episode",
        )

        assert metadata.content_id == "RLA236635"
        assert metadata.work_type == "Episode"
        assert metadata.localized_info == []
        assert metadata.ratings == []
        assert metadata.people == []

    def test_create_full_metadata(self):
        """Creates metadata with all fields populated."""
        localized = LocalizedInfo(
            title_display_unlimited="Episode Title",
            genres=["Drama"],
        )
        rating = Rating(region="US", system="us-tv", value="TV-MA")
        name = PersonName(display_name="Actor Name")
        job = Job(job_function="Actor", name=name)
        seq = SequenceInfo(number=1)
        parent = Parent(relationship_type="isepisodeof", parent_content_id="SEASON1")
        alt_id = AltIdentifier(namespace="CUSTOMER", identifier="ID123456")

        metadata = BasicMetadata(
            content_id="RLA236635",
            work_type="Episode",
            work_type_detail="Full Episode",
            localized_info=[localized],
            release_year=2022,
            release_date="2022-10-02",
            ratings=[rating],
            people=[job],
            country_of_origin="US",
            original_language="en-US",
            sequence_info=seq,
            parents=[parent],
            alt_identifiers=[alt_id],
        )

        assert metadata.work_type_detail == "Full Episode"
        assert len(metadata.localized_info) == 1
        assert len(metadata.ratings) == 1
        assert len(metadata.people) == 1

    def test_to_dict_minimal(self):
        """to_dict with minimal fields."""
        metadata = BasicMetadata(content_id="123", work_type="Movie")

        result = metadata.to_dict()

        assert result == {"ContentId": "123", "WorkType": "Movie"}
        assert "LocalizedInfo" not in result
        assert "Ratings" not in result

    def test_to_dict_with_nested_structures(self):
        """to_dict correctly serializes nested structures."""
        localized = LocalizedInfo(title_display_unlimited="Title")
        rating = Rating(region="US", system="us-tv", value="TV-14")

        metadata = BasicMetadata(
            content_id="123",
            work_type="Episode",
            localized_info=[localized],
            ratings=[rating],
        )

        result = metadata.to_dict()

        assert result["LocalizedInfo"][0]["TitleDisplayUnlimited"] == "Title"
        assert result["Ratings"][0]["Value"] == "TV-14"

    def test_to_dict_with_associated_orgs(self):
        """to_dict correctly serializes associated organizations."""
        network = AssociatedOrg(role="network", display_name="Test Network Plus")
        studio = AssociatedOrg(
            role="studio", display_name="Example Studios", organization_id="STUDIO123"
        )

        metadata = BasicMetadata(
            content_id="123",
            work_type="Episode",
            associated_orgs=[network, studio],
        )

        result = metadata.to_dict()

        assert len(result["AssociatedOrgs"]) == 2
        assert result["AssociatedOrgs"][0]["Role"] == "network"
        assert result["AssociatedOrgs"][0]["DisplayName"] == "Test Network Plus"
        assert result["AssociatedOrgs"][1]["Role"] == "studio"
        assert result["AssociatedOrgs"][1]["OrganizationId"] == "STUDIO123"


@pytest.mark.unit
class TestSourceAttribution:
    """Tests for SourceAttribution dataclass"""

    def test_create_attribution(self):
        """Creates source attribution."""
        attr = SourceAttribution(
            source_system="customer_a",
            source_type="generic_xml",
            correlation_id="CORR123456",
            normalized_at="2026-01-12T10:30:00Z",
        )

        assert attr.source_system == "customer_a"
        assert attr.source_type == "generic_xml"
        assert attr.correlation_id == "CORR123456"

    def test_to_dict_excludes_none_timestamp(self):
        """to_dict excludes normalized_at when None."""
        attr = SourceAttribution(
            source_system="test",
            source_type="test_type",
            correlation_id="123",
        )

        result = attr.to_dict()

        assert "normalized_at" not in result


@pytest.mark.unit
class TestNormalizedMetadata:
    """Tests for NormalizedMetadata dataclass"""

    def test_create_normalized_metadata(self):
        """Creates complete normalized metadata structure."""
        basic = BasicMetadata(content_id="123", work_type="Episode")
        attr = SourceAttribution(
            source_system="customer_a",
            source_type="generic_xml",
            correlation_id="123",
        )

        normalized = NormalizedMetadata(
            basic_metadata=basic,
            custom_fields={"platform_genres": {"amazon": ["Drama"]}},
            source_attribution=attr,
        )

        assert normalized.basic_metadata.content_id == "123"
        assert normalized.custom_fields["platform_genres"]["amazon"] == ["Drama"]
        assert normalized.schema_version == "1.0.0"

    def test_to_dict_structure(self):
        """to_dict returns correct top-level structure."""
        basic = BasicMetadata(content_id="123", work_type="Movie")
        attr = SourceAttribution(
            source_system="test",
            source_type="test_type",
            correlation_id="456",
        )

        normalized = NormalizedMetadata(
            basic_metadata=basic,
            source_attribution=attr,
        )

        result = normalized.to_dict()

        assert "BasicMetadata" in result
        assert "SchemaVersion" in result
        assert "SourceAttribution" in result
        assert result["SchemaVersion"] == "1.0.0"
        # Verify nested basic_metadata uses CamelCase
        assert "ContentId" in result["BasicMetadata"]
        assert "WorkType" in result["BasicMetadata"]

    def test_to_dict_excludes_empty_custom_fields(self):
        """to_dict excludes empty custom_fields."""
        basic = BasicMetadata(content_id="123", work_type="Movie")

        normalized = NormalizedMetadata(basic_metadata=basic)

        result = normalized.to_dict()

        assert "custom_fields" not in result

    def test_to_dict_includes_non_empty_custom_fields(self):
        """to_dict includes non-empty custom_fields."""
        basic = BasicMetadata(content_id="123", work_type="Movie")

        normalized = NormalizedMetadata(
            basic_metadata=basic,
            custom_fields={"key": "value"},
        )

        result = normalized.to_dict()

        assert result["CustomFields"] == {"key": "value"}
        # Verify nested basic_metadata uses CamelCase
        assert result["BasicMetadata"]["ContentId"] == "123"

    def test_to_dict_includes_parent_metadata(self):
        """to_dict includes parent_metadata when present."""
        basic = BasicMetadata(content_id="123", work_type="Episode")

        normalized = NormalizedMetadata(
            basic_metadata=basic,
            parent_metadata={"series_name": "Test Series"},
        )

        result = normalized.to_dict()

        assert result["ParentMetadata"] == {"series_name": "Test Series"}
        # Verify nested basic_metadata uses CamelCase
        assert result["BasicMetadata"]["ContentId"] == "123"
        assert result["BasicMetadata"]["WorkType"] == "Episode"
