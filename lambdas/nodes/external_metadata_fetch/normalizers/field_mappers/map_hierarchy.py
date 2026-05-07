"""Configuration-driven hierarchy and sequence field mapping for MEC elements.

This module provides functions to map source system hierarchy and sequence fields
to MEC-compliant SequenceInfo and Parent elements. All field names are
configuration-driven - NO hardcoded customer-specific values.

The hierarchy_mappings configuration defines which source fields map to which
MEC hierarchy elements.

Hierarchy Structure:
    Episode → Season → Series
    - Episode has Parent relationship "isepisodeof" to Season
    - Season has Parent relationship "isseasonof" to Series

Example configuration:
    {
        "hierarchy_mappings": {
            "episode_number_field": "episode_number",
            "season_number_field": "season_number",
            "season_id_field": "season_id",
            "series_id_field": "series_id",
        },
        "parent_metadata_mappings": {
            "show_name_field": "show_name",
            "short_series_description_field": "short_series_description",
            "long_series_description_field": "long_series_description",
            "series_premiere_date_field": "series_premiere_date",
            "season_count_field": "season_count",
            "short_season_description_field": "short_season_description",
            "long_season_description_field": "long_season_description",
            "episode_count_field": "episode_count",
        },
        "source_namespace_prefix": "CUSTOMER",
    }

Reference: MovieLabs MEC v2.25 - SequenceInfo, Parent elements
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.mec_schema import (
        Parent,
        SequenceInfo,
    )
except ImportError:
    from normalizers.mec_schema import Parent, SequenceInfo


def get_string_value(
    raw_metadata: dict[str, Any],
    field_name: str | None,
) -> str | None:
    """Extract a string value from raw metadata, handling None and empty strings.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        field_name: The field name to extract. If None, returns None.

    Returns:
        The string value if non-empty, None otherwise.
    """
    if field_name is None:
        return None

    value = raw_metadata.get(field_name)

    if value is None:
        return None

    # Convert to string if needed
    if not isinstance(value, str):
        value = str(value)

    # Return None for empty/whitespace-only strings
    stripped = value.strip()
    return stripped if stripped else None


def get_int_value(
    raw_metadata: dict[str, Any],
    field_name: str | None,
) -> int | None:
    """Extract an integer value from raw metadata.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        field_name: The field name to extract. If None, returns None.

    Returns:
        The integer value if valid, None otherwise.
    """
    if field_name is None:
        return None

    value = raw_metadata.get(field_name)

    if value is None:
        return None

    # Handle string values
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None

    # Handle numeric values
    if isinstance(value, (int, float)):
        return int(value)

    return None


def map_sequence_info(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> SequenceInfo | None:
    """Map episode/season number to MEC SequenceInfo element.

    For episodes, this maps the episode_number field to SequenceInfo/Number.
    The season number is accessed via the Parent relationship to the Season entity.

    Uses config["hierarchy_mappings"]["episode_number_field"] for the source field name.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - hierarchy_mappings: Dict with field name configurations

    Returns:
        SequenceInfo element with episode number, or None if not found.

    Example config:
        {
            "hierarchy_mappings": {
                "episode_number_field": "episode_number",
                "distribution_number_field": "distribution_number",
            }
        }

    Example usage:
        >>> raw = {"episode_number": "5", "distribution_number": "105"}
        >>> config = {
        ...     "hierarchy_mappings": {
        ...         "episode_number_field": "episode_number",
        ...         "distribution_number_field": "distribution_number",
        ...     }
        ... }
        >>> result = map_sequence_info(raw, config)
        >>> result.number
        5
        >>> result.distribution_number
        '105'
    """
    hierarchy_mappings = config.get("hierarchy_mappings", {})

    # Get episode number field name from config
    episode_number_field = hierarchy_mappings.get(
        "episode_number_field", "episode_number"
    )
    distribution_number_field = hierarchy_mappings.get("distribution_number_field")

    # Extract episode number
    episode_number = get_int_value(raw_metadata, episode_number_field)

    # If no episode number, return None
    if episode_number is None:
        return None

    # Extract distribution number if configured
    distribution_number = None
    if distribution_number_field:
        distribution_number = get_string_value(raw_metadata, distribution_number_field)

    return SequenceInfo(
        number=episode_number,
        distribution_number=distribution_number,
    )


def generate_parent_content_id(
    parent_id: str,
    source_namespace_prefix: str,
) -> str:
    """Generate a content ID for a parent entity.

    Creates a URN-style content ID using the source namespace prefix
    and the parent entity's identifier.

    Args:
        parent_id: The parent entity's identifier from the source system.
        source_namespace_prefix: The customer's namespace prefix from config.

    Returns:
        URN-style content ID (e.g., "urn:customer:RLS25733")

    Example:
        >>> generate_parent_content_id("RLS25733", "CUSTOMER")
        'urn:customer:RLS25733'
    """
    # Normalize namespace to lowercase for URN
    namespace_lower = source_namespace_prefix.lower()
    return f"urn:{namespace_lower}:{parent_id}"


def map_parents(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[Parent]:
    """Map parent relationships for hierarchical content.

    Creates Parent elements for Episode→Season and Season→Series relationships.
    For episodes, creates a parent relationship to the season.
    The season's parent relationship to series is stored in parent_metadata.

    Uses config["hierarchy_mappings"] for field names:
    - season_id_field: Field containing the season ID (for Episode→Season)
    - series_id_field: Field containing the series ID (for Season→Series, if applicable)

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - hierarchy_mappings: Dict with field name configurations
            - source_namespace_prefix: Customer namespace prefix

    Returns:
        List of Parent elements representing hierarchical relationships.
        Returns empty list if no parent relationships found.

    Example config:
        {
            "hierarchy_mappings": {
                "season_id_field": "season_id",
                "series_id_field": "series_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

    Example usage:
        >>> raw = {"season_id": "RLS25733", "series_id": "RLA236634"}
        >>> config = {
        ...     "hierarchy_mappings": {
        ...         "season_id_field": "season_id",
        ...         "series_id_field": "series_id",
        ...     },
        ...     "source_namespace_prefix": "CUSTOMER",
        ... }
        >>> result = map_parents(raw, config)
        >>> len(result)
        1
        >>> result[0].relationship_type
        'isepisodeof'
    """
    parents: list[Parent] = []

    hierarchy_mappings = config.get("hierarchy_mappings", {})
    source_namespace_prefix = config.get("source_namespace_prefix", "SOURCE")

    # Get field names from config
    season_id_field = hierarchy_mappings.get("season_id_field", "season_id")
    series_id_field = hierarchy_mappings.get("series_id_field", "series_id")

    # Extract parent IDs
    season_id = get_string_value(raw_metadata, season_id_field)
    series_id = get_string_value(raw_metadata, series_id_field)

    # Create Episode → Season relationship
    if season_id:
        parent_content_id = generate_parent_content_id(
            season_id, source_namespace_prefix
        )
        parents.append(
            Parent(
                relationship_type="isepisodeof",
                parent_content_id=parent_content_id,
            )
        )

    # Note: For episodes, we typically only create the immediate parent relationship
    # (Episode → Season). The Season → Series relationship is stored in the
    # Season entity itself, not duplicated in the Episode.
    #
    # However, if the content is a Season (not an Episode), we would create
    # a Season → Series relationship. This is determined by the work_type.
    #
    # For now, we check if there's no season_id but there is a series_id,
    # which might indicate this is a Season entity or special content.
    if not season_id and series_id:
        parent_content_id = generate_parent_content_id(
            series_id, source_namespace_prefix
        )
        parents.append(
            Parent(
                relationship_type="isseasonof",
                parent_content_id=parent_content_id,
            )
        )

    return parents


def extract_parent_metadata(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract denormalized parent entity metadata.

    Extracts series-level and season-level metadata that is often denormalized
    in the source data. This metadata can be stored separately for reference
    without requiring additional lookups.

    Uses config["parent_metadata_mappings"] for field names.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - parent_metadata_mappings: Dict with field name configurations
            - hierarchy_mappings: Dict with ID field configurations
            - source_namespace_prefix: Customer namespace prefix

    Returns:
        Dictionary containing series and season metadata, or None if no
        parent metadata found.

    Example config:
        {
            "parent_metadata_mappings": {
                "show_name_field": "show_name",
                "short_series_description_field": "short_series_description",
                "long_series_description_field": "long_series_description",
                "series_premiere_date_field": "series_premiere_date",
                "season_count_field": "season_count",
                "short_season_description_field": "short_season_description",
                "long_season_description_field": "long_season_description",
                "episode_count_field": "episode_count",
                "season_number_field": "season_number",
            },
            "hierarchy_mappings": {
                "series_id_field": "series_id",
                "season_id_field": "season_id",
            },
            "source_namespace_prefix": "CUSTOMER",
        }

    Example usage:
        >>> raw = {
        ...     "series_id": "RLA236634",
        ...     "show_name": "Test Series",
        ...     "short_series_description": "A test series description",
        ...     "season_id": "RLS25733",
        ...     "season_number": "1",
        ...     "episode_count": "9",
        ... }
        >>> config = {
        ...     "parent_metadata_mappings": {
        ...         "show_name_field": "show_name",
        ...         "short_series_description_field": "short_series_description",
        ...         "season_number_field": "season_number",
        ...         "episode_count_field": "episode_count",
        ...     },
        ...     "hierarchy_mappings": {
        ...         "series_id_field": "series_id",
        ...         "season_id_field": "season_id",
        ...     },
        ...     "source_namespace_prefix": "CUSTOMER",
        ... }
        >>> result = extract_parent_metadata(raw, config)
        >>> result["series"]["title"]
        'Test Series'
        >>> result["season"]["episode_count"]
        9
    """
    parent_metadata_mappings = config.get("parent_metadata_mappings", {})
    hierarchy_mappings = config.get("hierarchy_mappings", {})
    source_namespace_prefix = config.get("source_namespace_prefix", "SOURCE")

    result: dict[str, Any] = {}

    # Extract series metadata
    series_metadata = _extract_series_metadata(
        raw_metadata,
        parent_metadata_mappings,
        hierarchy_mappings,
        source_namespace_prefix,
    )
    if series_metadata:
        result["series"] = series_metadata

    # Extract season metadata
    season_metadata = _extract_season_metadata(
        raw_metadata,
        parent_metadata_mappings,
        hierarchy_mappings,
        source_namespace_prefix,
    )
    if season_metadata:
        result["season"] = season_metadata

    return result if result else None


def _extract_series_metadata(
    raw_metadata: dict[str, Any],
    parent_metadata_mappings: dict[str, Any],
    hierarchy_mappings: dict[str, Any],
    source_namespace_prefix: str,
) -> dict[str, Any] | None:
    """Extract series-level metadata.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        parent_metadata_mappings: Field name mappings for parent metadata.
        hierarchy_mappings: Field name mappings for hierarchy IDs.
        source_namespace_prefix: Customer namespace prefix.

    Returns:
        Dictionary containing series metadata, or None if no series data found.
    """
    series: dict[str, Any] = {}

    # Get field names from config
    series_id_field = hierarchy_mappings.get("series_id_field", "series_id")
    show_name_field = parent_metadata_mappings.get("show_name_field", "show_name")
    short_series_desc_field = parent_metadata_mappings.get(
        "short_series_description_field", "short_series_description"
    )
    long_series_desc_field = parent_metadata_mappings.get(
        "long_series_description_field", "long_series_description"
    )
    series_premiere_date_field = parent_metadata_mappings.get(
        "series_premiere_date_field", "series_premiere_date"
    )
    season_count_field = parent_metadata_mappings.get(
        "season_count_field", "season_count"
    )

    # Extract series ID
    series_id = get_string_value(raw_metadata, series_id_field)
    if series_id:
        series["content_id"] = generate_parent_content_id(
            series_id, source_namespace_prefix
        )
        series["source_id"] = series_id

    # Extract series title (show name)
    show_name = get_string_value(raw_metadata, show_name_field)
    if show_name:
        series["title"] = show_name

    # Extract series descriptions
    short_desc = get_string_value(raw_metadata, short_series_desc_field)
    if short_desc:
        series["short_description"] = short_desc

    long_desc = get_string_value(raw_metadata, long_series_desc_field)
    if long_desc:
        series["long_description"] = long_desc

    # Extract series premiere date
    premiere_date = get_string_value(raw_metadata, series_premiere_date_field)
    if premiere_date:
        series["premiere_date"] = premiere_date

    # Extract season count
    season_count = get_int_value(raw_metadata, season_count_field)
    if season_count is not None:
        series["season_count"] = season_count

    return series if series else None


def _extract_season_metadata(
    raw_metadata: dict[str, Any],
    parent_metadata_mappings: dict[str, Any],
    hierarchy_mappings: dict[str, Any],
    source_namespace_prefix: str,
) -> dict[str, Any] | None:
    """Extract season-level metadata.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        parent_metadata_mappings: Field name mappings for parent metadata.
        hierarchy_mappings: Field name mappings for hierarchy IDs.
        source_namespace_prefix: Customer namespace prefix.

    Returns:
        Dictionary containing season metadata, or None if no season data found.
    """
    season: dict[str, Any] = {}

    # Get field names from config
    season_id_field = hierarchy_mappings.get("season_id_field", "season_id")
    season_number_field = parent_metadata_mappings.get(
        "season_number_field", "season_number"
    )
    short_season_desc_field = parent_metadata_mappings.get(
        "short_season_description_field", "short_season_description"
    )
    long_season_desc_field = parent_metadata_mappings.get(
        "long_season_description_field", "long_season_description"
    )
    episode_count_field = parent_metadata_mappings.get(
        "episode_count_field", "episode_count"
    )

    # Extract season ID
    season_id = get_string_value(raw_metadata, season_id_field)
    if season_id:
        season["content_id"] = generate_parent_content_id(
            season_id, source_namespace_prefix
        )
        season["source_id"] = season_id

    # Extract season number
    season_number = get_int_value(raw_metadata, season_number_field)
    if season_number is not None:
        season["number"] = season_number

    # Extract season descriptions
    short_desc = get_string_value(raw_metadata, short_season_desc_field)
    if short_desc:
        season["short_description"] = short_desc

    long_desc = get_string_value(raw_metadata, long_season_desc_field)
    if long_desc:
        season["long_description"] = long_desc

    # Extract episode count
    episode_count = get_int_value(raw_metadata, episode_count_field)
    if episode_count is not None:
        season["episode_count"] = episode_count

    return season if season else None
