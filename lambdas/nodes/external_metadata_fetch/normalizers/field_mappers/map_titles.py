"""Configuration-driven title and description field mapping for MEC LocalizedInfo elements.

This module provides functions to map source system title and description fields
to MEC-compliant LocalizedInfo elements. All field names are configuration-driven -
NO hardcoded customer-specific values.

The title_mappings and description_mappings configurations define which source fields
map to which MEC LocalizedInfo elements.

Example configuration:
    {
        "default_language": "en-US",
        "title_mappings": {
            "title_field": "title",
            "title_brief_field": "titlebrief",
        },
        "description_mappings": {
            "short_description_field": "short_description",
            "long_description_field": "long_description",
        },
        "copyright_field": "copyright_holder",
        "keywords_field": "keywords",
    }

Reference: MovieLabs MEC v2.25 - LocalizedInfo element
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.mec_schema import LocalizedInfo
except ImportError:
    from normalizers.mec_schema import LocalizedInfo


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


def parse_keywords(
    raw_metadata: dict[str, Any],
    keywords_field: str | None,
) -> list[str]:
    """Parse keywords from raw metadata.

    Keywords can be:
    - A comma-separated string
    - A list of strings
    - A single string

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        keywords_field: The field name containing keywords.

    Returns:
        List of keyword strings, empty list if no keywords found.
    """
    if keywords_field is None:
        return []

    value = raw_metadata.get(keywords_field)

    if value is None:
        return []

    # Handle list of keywords
    if isinstance(value, list):
        return [str(k).strip() for k in value if k and str(k).strip()]

    # Handle comma-separated string
    if isinstance(value, str):
        if not value.strip():
            return []
        # Split by comma and strip whitespace
        return [k.strip() for k in value.split(",") if k.strip()]

    return []


def map_title_display_unlimited(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Map the full title field to TitleDisplayUnlimited.

    Uses config["title_mappings"]["title_field"] for the source field name.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing title_mappings.

    Returns:
        The full title string, or None if not found.
    """
    title_mappings = config.get("title_mappings", {})
    title_field = title_mappings.get("title_field", "title")

    return get_string_value(raw_metadata, title_field)


def map_title_display_19(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Map the brief title field to TitleDisplay19.

    Uses config["title_mappings"]["title_brief_field"] for the source field name.
    TitleDisplay19 is a short title (up to 19 characters) for constrained displays.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing title_mappings.

    Returns:
        The brief title string, or None if not found.
    """
    title_mappings = config.get("title_mappings", {})
    title_brief_field = title_mappings.get("title_brief_field", "titlebrief")

    return get_string_value(raw_metadata, title_brief_field)


def map_title_internal_alias(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Map the internal alias title field to TitleInternalAlias.

    Uses config["title_mappings"]["title_internal_alias_field"] for the source field name.
    Falls back to title_brief_field if internal alias field is not configured.

    TitleInternalAlias is used for internal reference and may be the same as
    the brief title in many cases.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing title_mappings.

    Returns:
        The internal alias title string, or None if not found.
    """
    title_mappings = config.get("title_mappings", {})

    # First try the dedicated internal alias field
    internal_alias_field = title_mappings.get("title_internal_alias_field")
    if internal_alias_field:
        value = get_string_value(raw_metadata, internal_alias_field)
        if value:
            return value

    # Fall back to title_brief_field if configured to do so
    if title_mappings.get("use_brief_as_internal_alias", True):
        title_brief_field = title_mappings.get("title_brief_field", "titlebrief")
        return get_string_value(raw_metadata, title_brief_field)

    return None


def map_summary_190(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Map the short description field to Summary190.

    Uses config["description_mappings"]["short_description_field"] for the source field name.
    Summary190 is a short summary of approximately 190 characters.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing description_mappings.

    Returns:
        The short description string, or None if not found.
    """
    description_mappings = config.get("description_mappings", {})
    short_desc_field = description_mappings.get(
        "short_description_field", "short_description"
    )

    return get_string_value(raw_metadata, short_desc_field)


def map_summary_4000(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Map the long description field to Summary4000.

    Uses config["description_mappings"]["long_description_field"] for the source field name.
    Summary4000 is a full description of up to 4000 characters.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing description_mappings.

    Returns:
        The long description string, or None if not found.
    """
    description_mappings = config.get("description_mappings", {})
    long_desc_field = description_mappings.get(
        "long_description_field", "long_description"
    )

    return get_string_value(raw_metadata, long_desc_field)


def map_copyright_line(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Map the copyright holder field to CopyrightLine.

    Uses config["copyright_field"] for the source field name.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing copyright_field.

    Returns:
        The copyright line string, or None if not found.
    """
    copyright_field = config.get("copyright_field", "copyright_holder")

    return get_string_value(raw_metadata, copyright_field)


def map_keywords(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    """Map the keywords field to a list of Keyword elements.

    Uses config["keywords_field"] for the source field name.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing keywords_field.

    Returns:
        List of keyword strings, empty list if no keywords found.
    """
    keywords_field = config.get("keywords_field", "keywords")

    return parse_keywords(raw_metadata, keywords_field)


def map_localized_info(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[LocalizedInfo]:
    """Map all title and description fields to LocalizedInfo elements.

    This function creates a LocalizedInfo element containing all mapped
    title and description fields. The language attribute is set from
    config["default_language"] or defaults to "en-US".

    NO hardcoded field names - all field names come from config.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - default_language: Language code for LocalizedInfo (default: "en-US")
            - title_mappings: Dict with title field configurations
            - description_mappings: Dict with description field configurations
            - copyright_field: Field name for copyright holder
            - keywords_field: Field name for keywords

    Returns:
        List containing a single LocalizedInfo element with all mapped fields.
        Returns empty list if no title or description fields are found.

    Example config:
        {
            "default_language": "en-US",
            "title_mappings": {
                "title_field": "title",
                "title_brief_field": "titlebrief",
                "title_internal_alias_field": None,  # Optional
                "use_brief_as_internal_alias": True,
            },
            "description_mappings": {
                "short_description_field": "short_description",
                "long_description_field": "long_description",
            },
            "copyright_field": "copyright_holder",
            "keywords_field": "keywords",
        }

    Example usage:
        >>> raw = {
        ...     "title": "The mysterious journey begins with unexpected discoveries...",
        ...     "titlebrief": "Episode 101",
        ...     "short_description": "A protagonist embarks on an adventure...",
        ...     "long_description": "In a world of wonder, our hero discovers secrets...",
        ...     "copyright_holder": "© 2022 Example Productions",
        ...     "keywords": "Science Fiction, Adventure, Drama",
        ... }
        >>> config = {
        ...     "default_language": "en-US",
        ...     "title_mappings": {
        ...         "title_field": "title",
        ...         "title_brief_field": "titlebrief",
        ...     },
        ...     "description_mappings": {
        ...         "short_description_field": "short_description",
        ...         "long_description_field": "long_description",
        ...     },
        ...     "copyright_field": "copyright_holder",
        ...     "keywords_field": "keywords",
        ... }
        >>> result = map_localized_info(raw, config)
        >>> len(result)
        1
        >>> result[0].title_display_unlimited
        'The mysterious journey begins with unexpected discoveries...'
    """
    # Get language from config with default
    language = config.get("default_language", "en-US")

    # Map all fields
    title_display_unlimited = map_title_display_unlimited(raw_metadata, config)
    title_display_19 = map_title_display_19(raw_metadata, config)
    title_internal_alias = map_title_internal_alias(raw_metadata, config)
    summary_190 = map_summary_190(raw_metadata, config)
    summary_4000 = map_summary_4000(raw_metadata, config)
    copyright_line = map_copyright_line(raw_metadata, config)
    keywords = map_keywords(raw_metadata, config)

    # Check if we have any content to include
    has_content = any(
        [
            title_display_unlimited,
            title_display_19,
            title_internal_alias,
            summary_190,
            summary_4000,
            copyright_line,
            keywords,
        ]
    )

    if not has_content:
        return []

    # Create LocalizedInfo element
    localized_info = LocalizedInfo(
        language=language,
        title_display_unlimited=title_display_unlimited,
        title_display_19=title_display_19,
        title_internal_alias=title_internal_alias,
        summary_190=summary_190,
        summary_4000=summary_4000,
        copyright_line=copyright_line,
        keywords=keywords,
    )

    return [localized_info]
