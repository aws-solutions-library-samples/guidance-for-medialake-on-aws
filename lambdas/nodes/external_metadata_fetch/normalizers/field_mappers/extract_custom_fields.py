"""Configuration-driven custom fields extraction for unmapped metadata.

This module provides functions to extract source metadata fields that don't map
to standard MEC elements. These fields are preserved in a structured custom_fields
container organized by category.

Custom field categories include:
- platform_genres: Platform-specific genres (Amazon, Apple, Roku, etc.)
- advertising: Ad-related fields (ad_category, ad_content_id, cue_points, etc.)
- timing: Timing/segment data (timelines, segments, markers)
- technical: Technical fields without MEC equivalents (AFD, watermark flags, etc.)
- rights: Rights/distribution fields not in MEC
- other: Miscellaneous unmapped fields

All field names are configuration-driven - NO hardcoded customer-specific values.

Example configuration:
    {
        "custom_field_categories": {
            "advertising": ["ad_category", "ad_content_id", "cue_points", "adopportunitiesmarkers"],
            "timing": ["timelines", "timelines_df30", "segments", "markers"],
            "technical": ["AFD", "needs_watermark", "semitextless", "conform_materials_list"],
            "rights": ["platform_rights", "carousel"],
            "other": ["placement"],
        },
        "classification_mappings": {
            "genres_field": "genres",
            "genre_type_attr": "@type",
            "genre_text_key": "#text",
        },
        "platform_genre_types": ["Amazon", "Apple", "Roku", "SN Series", "Bell Series"],
    }

Reference: MovieLabs MEC v2.25 - Fields without direct MEC mapping
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.field_mappers.map_classifications import (
        extract_platform_genres,
    )
except ImportError:
    from normalizers.field_mappers.map_classifications import extract_platform_genres


# Default custom field categories - can be overridden via config
DEFAULT_CUSTOM_FIELD_CATEGORIES: dict[str, list[str]] = {
    "advertising": [
        "ad_category",
        "ad_content_id",
        "cue_points",
        "adopportunitiesmarkers",
    ],
    "timing": [
        "timelines",
        "timelines_df30",
        "segments",
        "markers",
    ],
    "technical": [
        "AFD",
        "needs_watermark",
        "semitextless",
        "conform_materials_list",
        "format",
    ],
    "rights": [
        "platform_rights",
        "carousel",
    ],
    "other": [
        "placement",
    ],
}


def extract_field_value(
    raw_metadata: dict[str, Any],
    field_name: str,
) -> Any | None:
    """Extract a field value from raw metadata, preserving its structure.

    This function extracts the value as-is, preserving nested structures
    like dicts and lists. Only None values and empty strings are skipped.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        field_name: The field name to extract.

    Returns:
        The field value if present and non-empty, None otherwise.
    """
    value = raw_metadata.get(field_name)

    if value is None:
        return None

    # Skip empty strings
    if isinstance(value, str) and not value.strip():
        return None

    # Skip empty lists
    if isinstance(value, list) and len(value) == 0:
        return None

    # Skip empty dicts
    if isinstance(value, dict) and len(value) == 0:
        return None

    return value


def extract_category_fields(
    raw_metadata: dict[str, Any],
    field_names: list[str],
) -> dict[str, Any]:
    """Extract all fields for a specific category.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        field_names: List of field names to extract for this category.

    Returns:
        Dict of field_name -> value for all non-empty fields.
    """
    category_fields: dict[str, Any] = {}

    for field_name in field_names:
        value = extract_field_value(raw_metadata, field_name)
        if value is not None:
            category_fields[field_name] = value

    return category_fields


def extract_advertising_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Extract advertising-related custom fields.

    Advertising fields include ad categories, content IDs, cue points,
    and ad opportunity markers. These have no MEC equivalent.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing custom_field_categories.

    Returns:
        Dict of advertising field names to values.
    """
    custom_categories = config.get(
        "custom_field_categories", DEFAULT_CUSTOM_FIELD_CATEGORIES
    )
    advertising_fields = custom_categories.get(
        "advertising", DEFAULT_CUSTOM_FIELD_CATEGORIES["advertising"]
    )

    return extract_category_fields(raw_metadata, advertising_fields)


def extract_timing_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Extract timing and segment custom fields.

    Timing fields include timelines, segments, and markers. These belong
    in MovieLabs MMC (Media Manifest Core) spec, not MEC.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing custom_field_categories.

    Returns:
        Dict of timing field names to values.
    """
    custom_categories = config.get(
        "custom_field_categories", DEFAULT_CUSTOM_FIELD_CATEGORIES
    )
    timing_fields = custom_categories.get(
        "timing", DEFAULT_CUSTOM_FIELD_CATEGORIES["timing"]
    )

    return extract_category_fields(raw_metadata, timing_fields)


def extract_technical_custom_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Extract technical custom fields without MEC equivalents.

    Technical custom fields include AFD (Active Format Description),
    watermark flags, semi-textless flags, and conform materials.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing custom_field_categories.

    Returns:
        Dict of technical field names to values.
    """
    custom_categories = config.get(
        "custom_field_categories", DEFAULT_CUSTOM_FIELD_CATEGORIES
    )
    technical_fields = custom_categories.get(
        "technical", DEFAULT_CUSTOM_FIELD_CATEGORIES["technical"]
    )

    return extract_category_fields(raw_metadata, technical_fields)


def extract_rights_custom_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Extract rights/distribution custom fields.

    Rights fields that don't map to MEC include platform_rights and carousel.
    Full rights management belongs in MovieLabs Avails spec.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing custom_field_categories.

    Returns:
        Dict of rights field names to values.
    """
    custom_categories = config.get(
        "custom_field_categories", DEFAULT_CUSTOM_FIELD_CATEGORIES
    )
    rights_fields = custom_categories.get(
        "rights", DEFAULT_CUSTOM_FIELD_CATEGORIES["rights"]
    )

    return extract_category_fields(raw_metadata, rights_fields)


def extract_other_custom_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Extract miscellaneous custom fields.

    Other fields include placement data and any other unmapped fields
    specified in configuration.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing custom_field_categories.

    Returns:
        Dict of other field names to values.
    """
    custom_categories = config.get(
        "custom_field_categories", DEFAULT_CUSTOM_FIELD_CATEGORIES
    )
    other_fields = custom_categories.get(
        "other", DEFAULT_CUSTOM_FIELD_CATEGORIES["other"]
    )

    return extract_category_fields(raw_metadata, other_fields)


def extract(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Extract all custom fields from source metadata organized by category.

    This is the main entry point for custom field extraction. It collects
    all unmapped fields and organizes them by category for easier access.

    Categories:
    - platform_genres: Platform-specific genres (Amazon, Apple, Roku, etc.)
    - advertising: Ad-related fields
    - timing: Timing/segment data
    - technical: Technical fields without MEC equivalents
    - rights: Rights/distribution fields not in MEC
    - other: Miscellaneous unmapped fields

    NO hardcoded field names - all field names come from config["custom_field_categories"].

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - custom_field_categories: Dict mapping category names to field lists
            - classification_mappings: For platform genre extraction
            - platform_genre_types: List of platform types to extract

    Returns:
        Dict organized by category:
        {
            "platform_genres": {"amazon": ["Drama"], "apple": ["Drama"]},
            "advertising": {"ad_category": "Entertainment:General"},
            "timing": {"timelines": {...}, "markers": [...]},
            "technical": {"AFD": "10", "needs_watermark": false},
            "rights": {"platform_rights": "..."},
            "other": {"placement": {...}},
        }

    Example config:
        {
            "custom_field_categories": {
                "advertising": ["ad_category", "ad_content_id", "cue_points"],
                "timing": ["timelines", "segments", "markers"],
                "technical": ["AFD", "needs_watermark", "semitextless"],
                "rights": ["platform_rights", "carousel"],
                "other": ["placement"],
            },
            "classification_mappings": {
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            },
            "platform_genre_types": ["Amazon", "Apple", "Roku"],
        }

    Example usage:
        >>> raw = {
        ...     "ad_category": "Entertainment:General",
        ...     "AFD": "10",
        ...     "needs_watermark": False,
        ...     "genres": {
        ...         "genre": [
        ...             {"@type": "Amazon", "#text": "Drama"},
        ...             {"@type": "Apple", "#text": "Drama"},
        ...         ]
        ...     },
        ... }
        >>> config = {
        ...     "custom_field_categories": {
        ...         "advertising": ["ad_category"],
        ...         "technical": ["AFD", "needs_watermark"],
        ...     },
        ...     "classification_mappings": {
        ...         "genres_field": "genres",
        ...         "genre_type_attr": "@type",
        ...         "genre_text_key": "#text",
        ...     },
        ... }
        >>> custom = extract(raw, config)
        >>> custom["advertising"]["ad_category"]
        'Entertainment:General'
        >>> custom["platform_genres"]["amazon"]
        ['Drama']
    """
    custom_fields: dict[str, Any] = {}

    # Extract platform-specific genres (reuse existing function from map_classifications)
    platform_genres = extract_platform_genres(raw_metadata, config)
    if platform_genres:
        custom_fields["platform_genres"] = platform_genres

    # Extract advertising fields
    advertising = extract_advertising_fields(raw_metadata, config)
    if advertising:
        custom_fields["advertising"] = advertising

    # Extract timing/segment fields
    timing = extract_timing_fields(raw_metadata, config)
    if timing:
        custom_fields["timing"] = timing

    # Extract technical custom fields
    technical = extract_technical_custom_fields(raw_metadata, config)
    if technical:
        custom_fields["technical"] = technical

    # Extract rights custom fields
    rights = extract_rights_custom_fields(raw_metadata, config)
    if rights:
        custom_fields["rights"] = rights

    # Extract other custom fields
    other = extract_other_custom_fields(raw_metadata, config)
    if other:
        custom_fields["other"] = other

    return custom_fields
