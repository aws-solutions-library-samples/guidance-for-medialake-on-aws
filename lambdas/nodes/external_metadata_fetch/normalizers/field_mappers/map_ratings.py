"""Configuration-driven ratings field mapping for MEC Rating elements.

This module provides functions to map source system content ratings to MEC-compliant
Rating elements. All field names and rating system mappings are configuration-driven -
NO hardcoded customer-specific values.

The rating_system_mappings configuration defines which source rating types map to which
MEC rating systems and regions.

Example configuration:
    {
        "rating_field": "rating",
        "rating_container": "Rating",
        "rating_type_attr": "@Type",
        "rating_value_attr": "#text",
        "rating_descriptor_attr": "@Descriptor",
        "rating_system_mappings": {
            "TV Rating": {"system": "us-tv", "region": "US"},
            "us-tv": {"system": "us-tv", "region": "US"},
            "ca-tv": {"system": "ca-tv", "region": "CA"},
            "au-tv": {"system": "au-tv", "region": "AU"},
            "ACMA": {"system": "ACMA", "region": "AU"},
            "DMEC": {"system": "DMEC", "region": "MX"},
            "in-tv": {"system": "in-tv", "region": "IN"},
            "nz-tv": {"system": "nz-tv", "region": "NZ"},
            "nz-am": {"system": "nz-am", "region": "NZ"}
        }
    }

Reference: MovieLabs MEC v2.25 - Rating element (ContentRatingDetail-type)
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.mec_schema import Rating
except ImportError:
    from normalizers.mec_schema import Rating


# Default rating system to region mappings
# These are standard rating systems - can be overridden via config
DEFAULT_RATING_SYSTEM_MAPPINGS: dict[str, dict[str, str]] = {
    # US Rating Systems
    "TV Rating": {"system": "us-tv", "region": "US"},
    "us-tv": {"system": "us-tv", "region": "US"},
    "MPAA": {"system": "MPAA", "region": "US"},
    # Canadian Rating Systems
    "ca-tv": {"system": "ca-tv", "region": "CA"},
    # Australian Rating Systems
    "au-tv": {"system": "au-tv", "region": "AU"},
    "ACMA": {"system": "ACMA", "region": "AU"},
    # Mexican Rating Systems
    "DMEC": {"system": "DMEC", "region": "MX"},
    # Indian Rating Systems
    "in-tv": {"system": "in-tv", "region": "IN"},
    # New Zealand Rating Systems
    "nz-tv": {"system": "nz-tv", "region": "NZ"},
    "nz-am": {"system": "nz-am", "region": "NZ"},
}


def map_rating(
    rating_data: dict[str, Any],
    config: dict[str, Any],
) -> Rating | None:
    """Map a single rating entry to an MEC Rating element.

    IMPORTANT MEC v2.25 Schema Notes:
    - Region is REQUIRED and contains a country child element
    - System and Value are also REQUIRED
    - Reason is optional and contains content descriptors

    Args:
        rating_data: Dictionary containing rating information with:
            - Type attribute (rating system identifier)
            - Text content (rating value)
            - Optional Descriptor attribute (content descriptors)
        config: Configuration dictionary containing:
            - rating_type_attr: Attribute name for rating type (default: "@Type")
            - rating_value_attr: Attribute name for rating value (default: "#text")
            - rating_descriptor_attr: Attribute name for descriptors (default: "@Descriptor")
            - rating_system_mappings: Dict mapping type → {system, region}

    Returns:
        Rating element if valid data provided, None otherwise.

    Example:
        >>> rating_data = {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"}
        >>> config = {"rating_system_mappings": {"us-tv": {"system": "us-tv", "region": "US"}}}
        >>> rating = map_rating(rating_data, config)
        >>> rating.value
        'TV-MA'
        >>> rating.region
        'US'
    """
    if not rating_data:
        return None

    # Get attribute names from config with defaults
    type_attr = config.get("rating_type_attr", "@Type")
    value_attr = config.get("rating_value_attr", "#text")
    descriptor_attr = config.get("rating_descriptor_attr", "@Descriptor")

    # Extract rating type (system identifier)
    rating_type = rating_data.get(type_attr)
    if not rating_type:
        # Try to get type from a 'type' key as fallback
        rating_type = rating_data.get("type") or rating_data.get("Type")

    # Extract rating value
    rating_value = rating_data.get(value_attr)
    if not rating_value:
        # Try alternative value keys
        rating_value = rating_data.get("value") or rating_data.get("Value")

    # Skip if no value
    if not rating_value or not str(rating_value).strip():
        return None

    # Clean up the value
    rating_value = str(rating_value).strip()

    # Get rating system mappings from config or use defaults
    system_mappings = config.get(
        "rating_system_mappings", DEFAULT_RATING_SYSTEM_MAPPINGS
    )

    # Look up the system and region for this rating type
    if rating_type and rating_type in system_mappings:
        mapping = system_mappings[rating_type]
        system = mapping.get("system", rating_type)
        region = mapping.get("region", "US")  # Default to US if not specified
    else:
        # Unknown rating type - use the type as system, default region to US
        system = rating_type if rating_type else "unknown"
        region = "US"

    # Extract content descriptors (Reason field)
    descriptor = rating_data.get(descriptor_attr)
    if not descriptor:
        # Try alternative descriptor keys
        descriptor = rating_data.get("descriptor") or rating_data.get("Descriptor")

    reason = str(descriptor).strip() if descriptor else None

    return Rating(
        region=region,
        system=system,
        value=rating_value,
        reason=reason,
    )


def extract_ratings_list(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract the list of rating entries from raw metadata.

    Handles various XML-to-dict conversion patterns:
    - Single rating as dict
    - Multiple ratings as list
    - Nested container structure (e.g., rating/Rating)

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - rating_field: Field name for ratings container (default: "rating")
            - rating_container: Container element name (default: "Rating")

    Returns:
        List of rating data dictionaries.
    """
    # Get field names from config with defaults
    rating_field = config.get("rating_field", "rating")
    rating_container = config.get("rating_container", "Rating")

    # Get the ratings container
    ratings_container = raw_metadata.get(rating_field, {})

    if not ratings_container:
        return []

    # Handle nested container structure (e.g., rating/Rating)
    if isinstance(ratings_container, dict):
        ratings_list = ratings_container.get(rating_container, [])
    else:
        # ratings_container is already a list
        ratings_list = ratings_container

    # Normalize to list
    if isinstance(ratings_list, dict):
        ratings_list = [ratings_list]
    elif not isinstance(ratings_list, list):
        return []

    return ratings_list


def map_ratings(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[Rating]:
    """Map all rating fields from source metadata using configuration.

    This function extracts ratings from the raw metadata and converts them
    to MEC-compliant Rating elements. It handles multiple rating systems
    per asset (e.g., US-TV, Canadian, Australian ratings).

    NO hardcoded field names - all field names come from config.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - rating_field: Field name for ratings container (default: "rating")
            - rating_container: Container element name (default: "Rating")
            - rating_type_attr: Attribute name for rating type (default: "@Type")
            - rating_value_attr: Attribute name for rating value (default: "#text")
            - rating_descriptor_attr: Attribute name for descriptors (default: "@Descriptor")
            - rating_system_mappings: Dict mapping type → {system, region}

    Returns:
        List of Rating elements for all valid ratings found.

    Example config:
        {
            "rating_field": "rating",
            "rating_container": "Rating",
            "rating_type_attr": "@Type",
            "rating_value_attr": "#text",
            "rating_descriptor_attr": "@Descriptor",
            "rating_system_mappings": {
                "TV Rating": {"system": "us-tv", "region": "US"},
                "us-tv": {"system": "us-tv", "region": "US"},
                "ca-tv": {"system": "ca-tv", "region": "CA"},
                "au-tv": {"system": "au-tv", "region": "AU"},
                "ACMA": {"system": "ACMA", "region": "AU"},
                "DMEC": {"system": "DMEC", "region": "MX"},
                "in-tv": {"system": "in-tv", "region": "IN"},
                "nz-tv": {"system": "nz-tv", "region": "NZ"},
                "nz-am": {"system": "nz-am", "region": "NZ"}
            }
        }

    Example usage:
        >>> raw = {
        ...     "rating": {
        ...         "Rating": [
        ...             {"@Type": "us-tv", "#text": "TV-MA", "@Descriptor": "LSV"},
        ...             {"@Type": "ca-tv", "#text": "18+"}
        ...         ]
        ...     }
        ... }
        >>> config = {
        ...     "rating_system_mappings": {
        ...         "us-tv": {"system": "us-tv", "region": "US"},
        ...         "ca-tv": {"system": "ca-tv", "region": "CA"}
        ...     }
        ... }
        >>> ratings = map_ratings(raw, config)
        >>> len(ratings)
        2
    """
    ratings: list[Rating] = []

    # Extract the list of rating entries
    ratings_list = extract_ratings_list(raw_metadata, config)

    # Process each rating entry
    for rating_data in ratings_list:
        if not rating_data:
            continue

        rating = map_rating(rating_data, config)
        if rating is not None:
            ratings.append(rating)

    return ratings


def map_hierarchical_ratings(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, list[Rating]]:
    """Map ratings at episode, season, and series levels.

    Some metadata sources provide ratings at multiple hierarchy levels.
    This function extracts ratings from all levels.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - rating_field: Field name for episode ratings (default: "rating")
            - season_rating_field: Field name for season ratings (default: "season_rating")
            - series_rating_field: Field name for series ratings (default: "series_rating")
            - Plus all other rating config options

    Returns:
        Dictionary with keys 'episode', 'season', 'series' containing
        lists of Rating elements for each level.

    Example:
        >>> raw = {
        ...     "rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-MA"}]},
        ...     "season_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-14"}]},
        ...     "series_rating": {"Rating": [{"@Type": "us-tv", "#text": "TV-14"}]}
        ... }
        >>> config = {"rating_system_mappings": {"us-tv": {"system": "us-tv", "region": "US"}}}
        >>> result = map_hierarchical_ratings(raw, config)
        >>> len(result['episode'])
        1
    """
    result: dict[str, list[Rating]] = {
        "episode": [],
        "season": [],
        "series": [],
    }

    # Get field names from config with defaults
    config.get("rating_field", "rating")
    season_rating_field = config.get("season_rating_field", "season_rating")
    series_rating_field = config.get("series_rating_field", "series_rating")

    # Map episode-level ratings
    result["episode"] = map_ratings(raw_metadata, config)

    # Map season-level ratings
    if season_rating_field in raw_metadata:
        season_config = {**config, "rating_field": season_rating_field}
        result["season"] = map_ratings(raw_metadata, season_config)

    # Map series-level ratings
    if series_rating_field in raw_metadata:
        series_config = {**config, "rating_field": series_rating_field}
        result["series"] = map_ratings(raw_metadata, series_config)

    return result
