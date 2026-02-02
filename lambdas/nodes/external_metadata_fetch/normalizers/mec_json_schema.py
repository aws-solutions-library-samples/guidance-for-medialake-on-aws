"""MovieLabs MEC v2.25 JSON Schema for validation.

This module defines a JSON schema that validates normalized metadata output
against the MovieLabs Media Entertainment Core (MEC) v2.25 specification.

The schema validates:
- Required fields (ContentId, WorkType, etc.)
- Optional fields with correct types
- Nested structures (LocalizedInfo, Ratings, People, etc.)
- Value constraints where applicable

Note: This is a one-way transformation validation (source XML → internal JSON).
There is no requirement to serialize back to MovieLabs-compliant XML format.

Reference: MovieLabs MEC v2.25 (December 2025)
https://movielabs.com/md/
"""

from typing import Any

# JSON Schema for PersonName structure
PERSON_NAME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["DisplayName"],
    "properties": {
        "DisplayName": {
            "type": "string",
            "minLength": 1,
            "description": "Full display name (REQUIRED by MEC v2.25)",
        },
        "SortName": {
            "type": "string",
            "description": "Name formatted for sorting",
        },
        "FirstGivenName": {
            "type": "string",
            "description": "First/given name (MEC FirstGivenName element)",
        },
        "SecondGivenName": {
            "type": "string",
            "description": "Middle name (MEC SecondGivenName element)",
        },
        "FamilyName": {
            "type": "string",
            "description": "Last/family name (MEC FamilyName element)",
        },
        "Suffix": {
            "type": "string",
            "description": "Name suffix (e.g., Jr., III)",
        },
        "Moniker": {
            "type": "string",
            "description": "Stage name or nickname",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for Job (People) structure
JOB_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["JobFunction", "Name"],
    "properties": {
        "JobFunction": {
            "type": "string",
            "enum": [
                "Actor",
                "Director",
                "Writer",
                "Producer",
                "ExecutiveProducer",
                "Creator",
                "Composer",
                "Editor",
                "Cinematographer",
                "ProductionDesigner",
                "CostumeDesigner",
                "Choreographer",
                "Narrator",
                "Host",
                "Presenter",
            ],
            "description": "Job function/role (MEC JobFunction element)",
        },
        "Name": PERSON_NAME_SCHEMA,
        "JobDisplay": {
            "type": "string",
            "description": "Localized job title for display",
        },
        "BillingBlockOrder": {
            "type": "integer",
            "minimum": 0,
            "description": "Credit sequencing order (MEC BillingBlockOrder element)",
        },
        "Character": {
            "type": "string",
            "description": "Character name for actors",
        },
        "Guest": {
            "type": "boolean",
            "description": "True for guest appearances (MEC Guest element)",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for Rating structure
RATING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Region", "System", "Value"],
    "properties": {
        "Region": {
            "type": "string",
            "minLength": 2,
            "maxLength": 3,
            "description": "Country code (REQUIRED by MEC v2.25)",
        },
        "System": {
            "type": "string",
            "minLength": 1,
            "description": "Rating system identifier (REQUIRED)",
        },
        "Value": {
            "type": "string",
            "minLength": 1,
            "description": "Rating value (REQUIRED)",
        },
        "Reason": {
            "type": "string",
            "description": "Content descriptors (e.g., LSV, V, L)",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for LocalizedInfo structure
LOCALIZED_INFO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Language"],
    "properties": {
        "Language": {
            "type": "string",
            "pattern": "^[a-z]{2}(-[A-Z]{2})?$",
            "description": "Language code (e.g., en-US, es)",
        },
        "TitleDisplayUnlimited": {
            "type": "string",
            "description": "Full title without length restriction",
        },
        "TitleDisplay19": {
            "type": "string",
            "maxLength": 19,
            "description": "Short title up to 19 characters",
        },
        "TitleInternalAlias": {
            "type": "string",
            "description": "Internal reference title",
        },
        "Summary190": {
            "type": "string",
            "description": "Short summary (~190 characters)",
        },
        "Summary400": {
            "type": "string",
            "description": "Medium summary (~400 characters)",
        },
        "Summary4000": {
            "type": "string",
            "description": "Full description (up to 4000 characters)",
        },
        "Genres": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of genre strings",
        },
        "Keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of keyword strings",
        },
        "CopyrightLine": {
            "type": "string",
            "description": "Copyright notice",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for SequenceInfo structure
SEQUENCE_INFO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Number"],
    "properties": {
        "Number": {
            "type": "integer",
            "minimum": 0,
            "description": "Sequence number (episode/season number)",
        },
        "DistributionNumber": {
            "type": "string",
            "description": "Alternative distribution number",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for Parent relationship structure
PARENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["RelationshipType", "ParentContentId"],
    "properties": {
        "RelationshipType": {
            "type": "string",
            "enum": ["isepisodeof", "isseasonof", "ispartof"],
            "description": "Type of parent relationship",
        },
        "ParentContentId": {
            "type": "string",
            "minLength": 1,
            "description": "Content ID of the parent entity",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for AltIdentifier structure
ALT_IDENTIFIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Namespace", "Identifier"],
    "properties": {
        "Namespace": {
            "type": "string",
            "minLength": 1,
            "description": "Identifier namespace",
        },
        "Identifier": {
            "type": "string",
            "minLength": 1,
            "description": "Identifier value",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for AssociatedOrg structure
ASSOCIATED_ORG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Role", "DisplayName"],
    "properties": {
        "Role": {
            "type": "string",
            "enum": ["network", "studio", "distributor", "producer"],
            "description": "Organization role",
        },
        "DisplayName": {
            "type": "string",
            "minLength": 1,
            "description": "Organization display name",
        },
        "OrganizationId": {
            "type": "string",
            "description": "Optional organization identifier",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for VideoAttributes structure
VIDEO_ATTRIBUTES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "FrameRate": {
            "type": "string",
            "description": "Video frame rate (e.g., 23.976, 29.97)",
        },
        "AspectRatio": {
            "type": "string",
            "description": "Display aspect ratio (e.g., 16:9, 4:3)",
        },
        "WidthPixels": {
            "type": "integer",
            "minimum": 1,
            "description": "Horizontal resolution",
        },
        "HeightPixels": {
            "type": "integer",
            "minimum": 1,
            "description": "Vertical resolution",
        },
        "ActiveWidthPixels": {
            "type": "integer",
            "minimum": 1,
            "description": "Active picture width",
        },
        "ActiveHeightPixels": {
            "type": "integer",
            "minimum": 1,
            "description": "Active picture height",
        },
        "ColorType": {
            "type": "string",
            "description": "Color type (e.g., Color, BlackAndWhite)",
        },
        "Codec": {
            "type": "string",
            "description": "Video codec (e.g., H.264, HEVC)",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for AudioAttributes structure
AUDIO_ATTRIBUTES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Language"],
    "properties": {
        "Language": {
            "type": "string",
            "description": "Audio language code",
        },
        "Type": {
            "type": "string",
            "description": "Audio type (e.g., VisuallyImpaired for DVS)",
        },
        "SubType": {
            "type": "string",
            "description": "Audio sub-type for additional classification",
        },
        "InternalTrackReference": {
            "type": "string",
            "description": "Track reference identifier",
        },
        "Channels": {
            "type": "integer",
            "minimum": 1,
            "description": "Number of audio channels",
        },
        "Codec": {
            "type": "string",
            "description": "Audio codec (e.g., AAC, AC3)",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for SubtitleAttributes structure
SUBTITLE_ATTRIBUTES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Language"],
    "properties": {
        "Language": {
            "type": "string",
            "description": "Subtitle language code",
        },
        "Type": {
            "type": "string",
            "enum": ["CC", "SDH", "Forced", "Normal"],
            "description": "Subtitle type",
        },
        "Format": {
            "type": "string",
            "description": "Subtitle format (e.g., SRT, WebVTT)",
        },
    },
    "additionalProperties": False,
}


# JSON Schema for BasicMetadata structure
BASIC_METADATA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ContentId", "WorkType"],
    "properties": {
        "ContentId": {
            "type": "string",
            "minLength": 1,
            "description": "Unique content identifier (REQUIRED)",
        },
        "WorkType": {
            "type": "string",
            "enum": ["Movie", "Episode", "Season", "Series", "Promotion", "Short"],
            "description": "Content type classification (REQUIRED)",
        },
        "WorkTypeDetail": {
            "type": "string",
            "description": "Additional type detail (e.g., Full Episode, Special)",
        },
        "LocalizedInfo": {
            "type": "array",
            "items": LOCALIZED_INFO_SCHEMA,
            "description": "Language-specific content information",
        },
        "ReleaseYear": {
            "type": "integer",
            "minimum": 1800,
            "maximum": 2100,
            "description": "Year of release",
        },
        "ReleaseDate": {
            "type": "string",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            "description": "Full release date in ISO format (YYYY-MM-DD)",
        },
        "Ratings": {
            "type": "array",
            "items": RATING_SCHEMA,
            "description": "Content ratings from various systems",
        },
        "People": {
            "type": "array",
            "items": JOB_SCHEMA,
            "description": "Cast and crew information",
        },
        "CountryOfOrigin": {
            "type": "string",
            "minLength": 2,
            "maxLength": 3,
            "description": "Country code of origin",
        },
        "OriginalLanguage": {
            "type": "string",
            "description": "Original language code",
        },
        "SequenceInfo": SEQUENCE_INFO_SCHEMA,
        "Parents": {
            "type": "array",
            "items": PARENT_SCHEMA,
            "description": "Hierarchical parent relationships",
        },
        "AltIdentifiers": {
            "type": "array",
            "items": ALT_IDENTIFIER_SCHEMA,
            "description": "External system identifiers",
        },
        "AssociatedOrgs": {
            "type": "array",
            "items": ASSOCIATED_ORG_SCHEMA,
            "description": "Associated organizations (networks, studios)",
        },
        "VideoAttributes": VIDEO_ATTRIBUTES_SCHEMA,
        "AudioAttributes": {
            "type": "array",
            "items": AUDIO_ATTRIBUTES_SCHEMA,
            "description": "Audio track information",
        },
        "SubtitleAttributes": {
            "type": "array",
            "items": SUBTITLE_ATTRIBUTES_SCHEMA,
            "description": "Subtitle/caption information",
        },
        "RunLength": {
            "type": "string",
            "pattern": "^PT(\\d+H)?(\\d+M)?(\\d+S)?$",
            "description": "Duration in ISO 8601 format (e.g., PT45M)",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for SourceAttribution structure
SOURCE_ATTRIBUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["SourceSystem", "SourceType", "CorrelationId"],
    "properties": {
        "SourceSystem": {
            "type": "string",
            "minLength": 1,
            "description": "Source system identifier (REQUIRED)",
        },
        "SourceType": {
            "type": "string",
            "minLength": 1,
            "description": "Normalizer type used (REQUIRED)",
        },
        "CorrelationId": {
            "type": "string",
            "minLength": 1,
            "description": "ID for lookup in external system (REQUIRED)",
        },
        "NormalizedAt": {
            "type": "string",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}",
            "description": "ISO 8601 timestamp when normalization occurred",
        },
    },
    "additionalProperties": False,
}

# JSON Schema for the complete NormalizedMetadata structure
NORMALIZED_METADATA_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MEC Normalized Metadata",
    "description": "MovieLabs MEC v2.25 compliant normalized metadata output",
    "type": "object",
    "required": ["BasicMetadata", "SchemaVersion"],
    "properties": {
        "BasicMetadata": BASIC_METADATA_SCHEMA,
        "CustomFields": {
            "type": "object",
            "description": "Unmapped source fields organized by category",
            "additionalProperties": True,
        },
        "ParentMetadata": {
            "type": "object",
            "description": "Denormalized parent entity information",
            "additionalProperties": True,
        },
        "SourceAttribution": SOURCE_ATTRIBUTION_SCHEMA,
        "SchemaVersion": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Version of the normalization schema",
        },
    },
    "additionalProperties": False,
}


def get_mec_schema() -> dict[str, Any]:
    """Get the complete MEC JSON schema for validation.

    Returns:
        JSON schema dictionary for validating normalized metadata output.
    """
    return NORMALIZED_METADATA_SCHEMA


def get_basic_metadata_schema() -> dict[str, Any]:
    """Get the BasicMetadata JSON schema for validation.

    Returns:
        JSON schema dictionary for validating BasicMetadata structure.
    """
    return BASIC_METADATA_SCHEMA


def get_component_schemas() -> dict[str, dict[str, Any]]:
    """Get all component schemas for reference.

    Returns:
        Dictionary mapping component names to their schemas.
    """
    return {
        "PersonName": PERSON_NAME_SCHEMA,
        "Job": JOB_SCHEMA,
        "Rating": RATING_SCHEMA,
        "LocalizedInfo": LOCALIZED_INFO_SCHEMA,
        "SequenceInfo": SEQUENCE_INFO_SCHEMA,
        "Parent": PARENT_SCHEMA,
        "AltIdentifier": ALT_IDENTIFIER_SCHEMA,
        "AssociatedOrg": ASSOCIATED_ORG_SCHEMA,
        "VideoAttributes": VIDEO_ATTRIBUTES_SCHEMA,
        "AudioAttributes": AUDIO_ATTRIBUTES_SCHEMA,
        "SubtitleAttributes": SUBTITLE_ATTRIBUTES_SCHEMA,
        "BasicMetadata": BASIC_METADATA_SCHEMA,
        "SourceAttribution": SOURCE_ATTRIBUTION_SCHEMA,
        "NormalizedMetadata": NORMALIZED_METADATA_SCHEMA,
    }
