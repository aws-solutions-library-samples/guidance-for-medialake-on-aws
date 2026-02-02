"""MovieLabs Media Entertainment Core (MEC) v2.25 schema models.

This module defines dataclass models representing the MEC output structure.
These models use MEC-compatible field naming conventions (snake_case in Python,
corresponding to PascalCase MEC element names).

Field Name Mapping:
    Python snake_case → MEC PascalCase → DynamoDB CamelCase
    display_name → DisplayName → DisplayName
    first_given_name → FirstGivenName → FirstGivenName
    family_name → FamilyName → FamilyName
    job_function → JobFunction → JobFunction
    billing_block_order → BillingBlockOrder → BillingBlockOrder

Note: The to_dict() methods convert snake_case Python field names to CamelCase
for consistency with MediaLake's DynamoDB schema conventions (matching
EmbeddedMetadata, Consolidated, and other metadata structures).

Reference: MovieLabs MEC v2.25 (December 2025)
https://movielabs.com/md/
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AltIdentifier:
    """MEC AltIdentifier element for external system identifiers.

    Represents an identifier from an external system with its namespace.

    Attributes:
        namespace: Identifier namespace (e.g., "CUSTOMER", "TMS", "CUSTOMER-REF")
        identifier: The actual identifier value
    """

    namespace: str
    identifier: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for serialization with CamelCase keys."""
        return {"Namespace": self.namespace, "Identifier": self.identifier}


@dataclass
class PersonName:
    """MEC Person Name structure (PersonName-type in schema).

    IMPORTANT MEC v2.25 Schema Notes:
    - DisplayName is REQUIRED
    - Use FirstGivenName (not FirstName) and FamilyName (not LastName)

    Attributes:
        display_name: REQUIRED - Full display name with language attribute
        sort_name: Name formatted for sorting (e.g., "Anderson, Jacob")
        first_given_name: First/given name (FirstGivenName element)
        second_given_name: Middle name (SecondGivenName element)
        family_name: Last/family name (FamilyName element)
        suffix: Name suffix (e.g., "Jr.", "III")
        moniker: Stage name or nickname
    """

    display_name: str  # REQUIRED by MEC schema
    sort_name: str | None = None
    first_given_name: str | None = None
    second_given_name: str | None = None
    family_name: str | None = None
    suffix: str | None = None
    moniker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {"DisplayName": self.display_name}
        if self.sort_name is not None:
            result["SortName"] = self.sort_name
        if self.first_given_name is not None:
            result["FirstGivenName"] = self.first_given_name
        if self.second_given_name is not None:
            result["SecondGivenName"] = self.second_given_name
        if self.family_name is not None:
            result["FamilyName"] = self.family_name
        if self.suffix is not None:
            result["Suffix"] = self.suffix
        if self.moniker is not None:
            result["Moniker"] = self.moniker
        return result


@dataclass
class Job:
    """MEC Job element for People (BasicMetadataJob-type in schema).

    IMPORTANT MEC v2.25 Schema Notes:
    - JobFunction and BillingBlockOrder are ELEMENTS, not attributes
    - Guest is a boolean ELEMENT for guest appearances

    Attributes:
        job_function: JobFunction ELEMENT - Actor, Director, Writer, Producer, etc.
        name: PersonName structure with display_name (REQUIRED)
        job_display: Localized job title for display
        billing_block_order: BillingBlockOrder ELEMENT for credit sequencing
        character: Character name (simple string) for actors
        guest: Guest ELEMENT - True for guest appearances
    """

    job_function: str  # Actor, Director, Writer, Producer, ExecutiveProducer, Creator
    name: PersonName
    job_display: str | None = None
    billing_block_order: int | None = None
    character: str | None = None
    guest: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {
            "JobFunction": self.job_function,
            "Name": self.name.to_dict(),
        }
        if self.job_display is not None:
            result["JobDisplay"] = self.job_display
        if self.billing_block_order is not None:
            result["BillingBlockOrder"] = self.billing_block_order
        if self.character is not None:
            result["Character"] = self.character
        if self.guest is not None:
            result["Guest"] = self.guest
        return result


@dataclass
class Rating:
    """MEC Rating element (ContentRatingDetail-type in schema).

    IMPORTANT MEC v2.25 Schema Notes:
    - Region is REQUIRED and contains a country child element
    - System and Value are also REQUIRED

    Attributes:
        region: REQUIRED - Region containing country code (e.g., "US", "CA")
        system: REQUIRED - Rating system identifier (e.g., "us-tv", "ca-tv")
        value: REQUIRED - Rating value (e.g., "TV-MA", "TV-14")
        reason: Content descriptors (e.g., "LSV", "V", "L")
    """

    region: str  # REQUIRED - country code
    system: str  # REQUIRED - rating system
    value: str  # REQUIRED - rating value
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {
            "Region": self.region,
            "System": self.system,
            "Value": self.value,
        }
        if self.reason is not None:
            result["Reason"] = self.reason
        return result


@dataclass
class LocalizedInfo:
    """MEC LocalizedInfo element for language-specific content.

    Contains titles, descriptions, genres, and keywords for a specific language.

    Attributes:
        language: Language code (e.g., "en-US") - REQUIRED
        title_display_unlimited: Full title (TitleDisplayUnlimited)
        title_display_19: Short title up to 19 chars (TitleDisplay19)
        title_internal_alias: Internal reference title (TitleInternalAlias)
        summary_190: Short summary ~190 chars (Summary190)
        summary_400: Medium summary ~400 chars (Summary400)
        summary_4000: Full description up to 4000 chars (Summary4000)
        genres: List of genre strings
        keywords: List of keyword strings
        copyright_line: Copyright notice (CopyrightLine)
    """

    language: str = "en-US"
    title_display_unlimited: str | None = None
    title_display_19: str | None = None
    title_internal_alias: str | None = None
    summary_190: str | None = None
    summary_400: str | None = None  # MEC Summary400 (between 190 and 4000)
    summary_4000: str | None = None
    genres: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    copyright_line: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None/empty values."""
        result: dict[str, Any] = {"Language": self.language}
        if self.title_display_unlimited is not None:
            result["TitleDisplayUnlimited"] = self.title_display_unlimited
        if self.title_display_19 is not None:
            result["TitleDisplay19"] = self.title_display_19
        if self.title_internal_alias is not None:
            result["TitleInternalAlias"] = self.title_internal_alias
        if self.summary_190 is not None:
            result["Summary190"] = self.summary_190
        if self.summary_400 is not None:
            result["Summary400"] = self.summary_400
        if self.summary_4000 is not None:
            result["Summary4000"] = self.summary_4000
        if self.genres:
            result["Genres"] = self.genres
        if self.keywords:
            result["Keywords"] = self.keywords
        if self.copyright_line is not None:
            result["CopyrightLine"] = self.copyright_line
        return result


@dataclass
class SequenceInfo:
    """MEC SequenceInfo element for episode/season numbering.

    Attributes:
        number: Sequence number (episode number, season number)
        distribution_number: Alternative distribution number
    """

    number: int
    distribution_number: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {"Number": self.number}
        if self.distribution_number is not None:
            result["DistributionNumber"] = self.distribution_number
        return result


@dataclass
class Parent:
    """MEC Parent relationship element.

    Represents hierarchical relationships between content entities.

    Attributes:
        relationship_type: Type of relationship (isepisodeof, isseasonof)
        parent_content_id: Content ID of the parent entity
    """

    relationship_type: str  # isepisodeof, isseasonof
    parent_content_id: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary with CamelCase keys."""
        return {
            "RelationshipType": self.relationship_type,
            "ParentContentId": self.parent_content_id,
        }


@dataclass
class VideoAttributes:
    """MEC Video technical attributes.

    Note: Resolution uses WidthPixels/HeightPixels (not Width/Height).
    video_definition (HD/SD/UHD) is derived from resolution, not a direct MEC element.

    Attributes:
        frame_rate: Video frame rate (e.g., "23.976", "29.97")
        aspect_ratio: Display aspect ratio (e.g., "16:9", "4:3")
        width_pixels: Horizontal resolution (WidthPixels element)
        height_pixels: Vertical resolution (HeightPixels element)
        active_width_pixels: Active picture width (ActiveWidthPixels)
        active_height_pixels: Active picture height (ActiveHeightPixels)
        color_type: Color type (e.g., "Color", "BlackAndWhite")
        codec: Video codec (e.g., "H.264", "HEVC")
    """

    frame_rate: str | None = None
    aspect_ratio: str | None = None
    width_pixels: int | None = None
    height_pixels: int | None = None
    active_width_pixels: int | None = None
    active_height_pixels: int | None = None
    color_type: str | None = None
    codec: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {}
        if self.frame_rate is not None:
            result["FrameRate"] = self.frame_rate
        if self.aspect_ratio is not None:
            result["AspectRatio"] = self.aspect_ratio
        if self.width_pixels is not None:
            result["WidthPixels"] = self.width_pixels
        if self.height_pixels is not None:
            result["HeightPixels"] = self.height_pixels
        if self.active_width_pixels is not None:
            result["ActiveWidthPixels"] = self.active_width_pixels
        if self.active_height_pixels is not None:
            result["ActiveHeightPixels"] = self.active_height_pixels
        if self.color_type is not None:
            result["ColorType"] = self.color_type
        if self.codec is not None:
            result["Codec"] = self.codec
        return result


@dataclass
class AudioAttributes:
    """MEC Audio technical attributes.

    Attributes:
        language: Audio language code (e.g., "en", "es")
        type: Audio type (e.g., "VisuallyImpaired" for DVS)
        sub_type: Audio sub-type for additional classification
        internal_track_reference: Track reference identifier
        channels: Number of audio channels
        codec: Audio codec (e.g., "AAC", "AC3")
    """

    language: str
    type: str | None = None
    sub_type: str | None = None
    internal_track_reference: str | None = None
    channels: int | None = None
    codec: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {"Language": self.language}
        if self.type is not None:
            result["Type"] = self.type
        if self.sub_type is not None:
            result["SubType"] = self.sub_type
        if self.internal_track_reference is not None:
            result["InternalTrackReference"] = self.internal_track_reference
        if self.channels is not None:
            result["Channels"] = self.channels
        if self.codec is not None:
            result["Codec"] = self.codec
        return result


@dataclass
class SubtitleAttributes:
    """MEC Subtitle/Caption attributes.

    Note: Forced narrative subtitles are indicated by setting type="Forced"

    Attributes:
        language: Subtitle language code
        type: Subtitle type (CC, SDH, Forced, etc.)
        format: Subtitle format (e.g., "SRT", "WebVTT")
    """

    language: str
    type: str | None = None
    format: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {"Language": self.language}
        if self.type is not None:
            result["Type"] = self.type
        if self.format is not None:
            result["Format"] = self.format
        return result


@dataclass
class AssociatedOrg:
    """MEC AssociatedOrg element for network/studio information.

    Represents organizations associated with the content such as
    networks, studios, or distributors.

    Attributes:
        role: Organization role (e.g., "network", "studio", "distributor")
        display_name: Organization display name
        organization_id: Optional organization identifier
    """

    role: str  # network, studio, distributor
    display_name: str
    organization_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {
            "Role": self.role,
            "DisplayName": self.display_name,
        }
        if self.organization_id is not None:
            result["OrganizationId"] = self.organization_id
        return result


@dataclass
class BasicMetadata:
    """MEC BasicMetadata structure - the core normalized output.

    This is the primary container for normalized content metadata,
    following the MovieLabs MEC v2.25 schema structure.

    Attributes:
        content_id: Unique content identifier
        work_type: Content type (Movie, Episode, Season, Series, Promotion)
        work_type_detail: Additional type detail
        localized_info: Language-specific content (titles, descriptions)
        release_year: Year of release
        release_date: Full release date (ISO format string)
        ratings: Content ratings from various systems
        people: Cast and crew information
        country_of_origin: Country code of origin
        original_language: Original language code
        sequence_info: Episode/season numbering
        parents: Hierarchical relationships
        alt_identifiers: External system identifiers
        associated_orgs: Associated organizations (networks, studios)
        video_attributes: Video technical specs
        audio_attributes: Audio track information
        subtitle_attributes: Subtitle/caption information
        run_length: Duration in ISO 8601 format (e.g., "PT45M")
    """

    content_id: str
    work_type: str  # Movie, Episode, Season, Series, Promotion
    work_type_detail: str | None = None

    # Localized content
    localized_info: list[LocalizedInfo] = field(default_factory=list)

    # Temporal
    release_year: int | None = None
    release_date: str | None = None  # ISO format date string

    # Ratings
    ratings: list[Rating] = field(default_factory=list)

    # People
    people: list[Job] = field(default_factory=list)

    # Geographic/Linguistic
    country_of_origin: str | None = None
    original_language: str | None = None

    # Hierarchy
    sequence_info: SequenceInfo | None = None
    parents: list[Parent] = field(default_factory=list)

    # Identifiers
    alt_identifiers: list[AltIdentifier] = field(default_factory=list)

    # Associated Organizations (networks, studios)
    associated_orgs: list[AssociatedOrg] = field(default_factory=list)

    # Technical (optional)
    video_attributes: VideoAttributes | None = None
    audio_attributes: list[AudioAttributes] = field(default_factory=list)
    subtitle_attributes: list[SubtitleAttributes] = field(default_factory=list)

    # Duration
    run_length: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None/empty values."""
        result: dict[str, Any] = {
            "ContentId": self.content_id,
            "WorkType": self.work_type,
        }

        if self.work_type_detail is not None:
            result["WorkTypeDetail"] = self.work_type_detail

        if self.localized_info:
            result["LocalizedInfo"] = [li.to_dict() for li in self.localized_info]

        if self.release_year is not None:
            result["ReleaseYear"] = self.release_year

        if self.release_date is not None:
            result["ReleaseDate"] = self.release_date

        if self.ratings:
            result["Ratings"] = [r.to_dict() for r in self.ratings]

        if self.people:
            result["People"] = [p.to_dict() for p in self.people]

        if self.country_of_origin is not None:
            result["CountryOfOrigin"] = self.country_of_origin

        if self.original_language is not None:
            result["OriginalLanguage"] = self.original_language

        if self.sequence_info is not None:
            result["SequenceInfo"] = self.sequence_info.to_dict()

        if self.parents:
            result["Parents"] = [p.to_dict() for p in self.parents]

        if self.alt_identifiers:
            result["AltIdentifiers"] = [ai.to_dict() for ai in self.alt_identifiers]

        if self.associated_orgs:
            result["AssociatedOrgs"] = [ao.to_dict() for ao in self.associated_orgs]

        if self.video_attributes is not None:
            result["VideoAttributes"] = self.video_attributes.to_dict()

        if self.audio_attributes:
            result["AudioAttributes"] = [aa.to_dict() for aa in self.audio_attributes]

        if self.subtitle_attributes:
            result["SubtitleAttributes"] = [
                sa.to_dict() for sa in self.subtitle_attributes
            ]

        if self.run_length is not None:
            result["RunLength"] = self.run_length

        return result


@dataclass
class SourceAttribution:
    """Attribution information for the metadata source.

    Attributes:
        source_system: Source system identifier (e.g., "customer_a", "customer_b")
        source_type: Normalizer type used (e.g., "generic_xml")
        correlation_id: ID used for lookup in the external system
        normalized_at: ISO 8601 timestamp when normalization occurred
    """

    source_system: str
    source_type: str
    correlation_id: str
    normalized_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with CamelCase keys, excluding None values."""
        result: dict[str, Any] = {
            "SourceSystem": self.source_system,
            "SourceType": self.source_type,
            "CorrelationId": self.correlation_id,
        }
        if self.normalized_at is not None:
            result["NormalizedAt"] = self.normalized_at
        return result


@dataclass
class NormalizedMetadata:
    """Complete normalized metadata output.

    This is the top-level structure stored in DynamoDB's ExternalMetadata field.

    Attributes:
        basic_metadata: Core MEC-compliant metadata
        custom_fields: Unmapped source fields organized by category
        parent_metadata: Denormalized parent entity information
        source_attribution: Source system and normalization info
        schema_version: Version of the normalization schema
    """

    basic_metadata: BasicMetadata
    custom_fields: dict[str, Any] = field(default_factory=dict)
    parent_metadata: dict[str, Any] | None = None
    source_attribution: SourceAttribution | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage with CamelCase keys.

        Returns:
            Dictionary representation suitable for storage with CamelCase keys
            matching MediaLake's DynamoDB schema conventions.
        """
        result: dict[str, Any] = {
            "BasicMetadata": self.basic_metadata.to_dict(),
            "SchemaVersion": self.schema_version,
        }

        if self.custom_fields:
            result["CustomFields"] = self.custom_fields

        if self.parent_metadata is not None:
            result["ParentMetadata"] = self.parent_metadata

        if self.source_attribution is not None:
            result["SourceAttribution"] = self.source_attribution.to_dict()

        return result
