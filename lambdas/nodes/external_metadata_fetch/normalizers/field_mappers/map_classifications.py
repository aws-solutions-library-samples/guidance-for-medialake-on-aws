"""Configuration-driven content classification field mapping for MEC WorkType and Genre elements.

This module provides functions to map source system content classification fields
to MEC-compliant WorkType, WorkTypeDetail, and Genre elements. All field names
are configuration-driven - NO hardcoded customer-specific values.

The classification_mappings configuration defines which source fields map to
which MEC classification elements.

Example configuration:
    {
        "classification_mappings": {
            "is_movie_field": "is_movie",
            "content_type_field": "content_type",
            "video_type_field": "video_type",
            "genre_field": "genre",
            "genres_field": "genres",
        },
        "work_type_mappings": {
            "movie_values": ["TRUE", "true", "True", "1", "yes"],
            "episode_content_types": ["Series", "series", "SERIES"],
            "promotion_content_types": ["Interstitial", "interstitial", "INTERSTITIAL", "Trailer", "trailer"],
        },
    }

Reference: MovieLabs MEC v2.25 - WorkType, WorkTypeDetail, LocalizedInfo/Genre elements
"""

from typing import Any

# Default work type mappings - can be overridden via config
DEFAULT_WORK_TYPE_MAPPINGS = {
    "movie_values": ["TRUE", "true", "True", "1", "yes", "Yes", "YES"],
    "episode_content_types": [
        "Series",
        "series",
        "SERIES",
        "Episode",
        "episode",
        "EPISODE",
    ],
    "promotion_content_types": [
        "Interstitial",
        "interstitial",
        "INTERSTITIAL",
        "Trailer",
        "trailer",
        "TRAILER",
        "Promo",
        "promo",
        "PROMO",
    ],
}


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


def determine_work_type(
    is_movie_value: str | None,
    content_type_value: str | None,
    config: dict[str, Any],
) -> str:
    """Determine the MEC WorkType based on source field values.

    WorkType determination logic:
    1. If is_movie is a "true" value → "Movie"
    2. If content_type is a promotion type → "Promotion"
    3. If content_type is an episode type → "Episode"
    4. Default → "Episode" (most common case for TV content)

    Args:
        is_movie_value: Value of the is_movie field (may be None).
        content_type_value: Value of the content_type field (may be None).
        config: Configuration dictionary containing work_type_mappings.

    Returns:
        MEC WorkType string: "Movie", "Episode", or "Promotion"
    """
    # Get work type mappings from config or use defaults
    work_type_mappings = config.get("work_type_mappings", DEFAULT_WORK_TYPE_MAPPINGS)
    movie_values = work_type_mappings.get(
        "movie_values", DEFAULT_WORK_TYPE_MAPPINGS["movie_values"]
    )
    episode_content_types = work_type_mappings.get(
        "episode_content_types", DEFAULT_WORK_TYPE_MAPPINGS["episode_content_types"]
    )
    promotion_content_types = work_type_mappings.get(
        "promotion_content_types", DEFAULT_WORK_TYPE_MAPPINGS["promotion_content_types"]
    )

    # Check if it's a movie
    if is_movie_value and is_movie_value in movie_values:
        return "Movie"

    # Check content type for promotion
    if content_type_value and content_type_value in promotion_content_types:
        return "Promotion"

    # Check content type for episode
    if content_type_value and content_type_value in episode_content_types:
        return "Episode"

    # Default to Episode for TV content
    return "Episode"


def get_work_type(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> tuple[str, str | None]:
    """Get the MEC WorkType and WorkTypeDetail from source metadata.

    Uses configuration to determine field names for is_movie, content_type,
    and video_type fields.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - classification_mappings: Dict with field name configurations
            - work_type_mappings: Dict with value mappings for work types

    Returns:
        Tuple of (work_type, work_type_detail):
            - work_type: "Movie", "Episode", or "Promotion"
            - work_type_detail: Additional detail (e.g., "Full Episode") or None

    Example config:
        {
            "classification_mappings": {
                "is_movie_field": "is_movie",
                "content_type_field": "content_type",
                "video_type_field": "video_type",
            },
            "work_type_mappings": {
                "movie_values": ["TRUE", "true", "1"],
                "episode_content_types": ["Series"],
                "promotion_content_types": ["Interstitial", "Trailer"],
            },
        }

    Example usage:
        >>> raw = {"is_movie": "FALSE", "content_type": "Series", "video_type": "Full Episode"}
        >>> config = {
        ...     "classification_mappings": {
        ...         "is_movie_field": "is_movie",
        ...         "content_type_field": "content_type",
        ...         "video_type_field": "video_type",
        ...     }
        ... }
        >>> work_type, detail = get_work_type(raw, config)
        >>> work_type
        'Episode'
        >>> detail
        'Full Episode'
    """
    # Get field names from configuration
    classification_mappings = config.get("classification_mappings", {})
    is_movie_field = classification_mappings.get("is_movie_field", "is_movie")
    content_type_field = classification_mappings.get(
        "content_type_field", "content_type"
    )
    video_type_field = classification_mappings.get("video_type_field", "video_type")

    # Extract field values
    is_movie_value = get_string_value(raw_metadata, is_movie_field)
    content_type_value = get_string_value(raw_metadata, content_type_field)
    video_type_value = get_string_value(raw_metadata, video_type_field)

    # Determine work type
    work_type = determine_work_type(is_movie_value, content_type_value, config)

    # video_type becomes WorkTypeDetail
    work_type_detail = video_type_value

    return work_type, work_type_detail


def extract_primary_genre(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    """Extract the primary genre from source metadata.

    The primary genre is typically in a simple "genre" field and maps
    directly to MEC LocalizedInfo/Genre.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing classification_mappings.

    Returns:
        The primary genre string, or None if not found.

    Example:
        >>> raw = {"genre": "Drama"}
        >>> config = {"classification_mappings": {"genre_field": "genre"}}
        >>> extract_primary_genre(raw, config)
        'Drama'
    """
    classification_mappings = config.get("classification_mappings", {})
    genre_field = classification_mappings.get("genre_field", "genre")

    return get_string_value(raw_metadata, genre_field)


def extract_genres_list(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    """Extract all genres (primary and subgenres) for MEC LocalizedInfo/Genre.

    This extracts genres that should go into the standard MEC Genre element.
    Platform-specific genres are handled separately by extract_platform_genres().

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing classification_mappings.

    Returns:
        List of genre strings for MEC LocalizedInfo/Genre.
        Returns empty list if no genres found.

    Example:
        >>> raw = {"genre": "Drama", "subgenre": "Horror"}
        >>> config = {
        ...     "classification_mappings": {
        ...         "genre_field": "genre",
        ...         "subgenre_field": "subgenre",
        ...     }
        ... }
        >>> extract_genres_list(raw, config)
        ['Drama', 'Horror']
    """
    genres: list[str] = []

    classification_mappings = config.get("classification_mappings", {})

    # Get primary genre
    primary_genre = extract_primary_genre(raw_metadata, config)
    if primary_genre:
        genres.append(primary_genre)

    # Get subgenre if configured
    subgenre_field = classification_mappings.get("subgenre_field")
    if subgenre_field:
        subgenre = get_string_value(raw_metadata, subgenre_field)
        if subgenre and subgenre not in genres:
            genres.append(subgenre)

    return genres


def extract_platform_genres(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, list[str]]:
    """Extract platform-specific genres for custom fields.

    Platform-specific genres (Amazon, Apple, Roku, etc.) don't map to standard
    MEC Genre elements. They are extracted and organized by platform for
    storage in custom_fields.

    The genres field structure is expected to be:
    - A dict with "genre" key containing a list of genre entries
    - Each genre entry has a "@type" attribute indicating the platform

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - classification_mappings.genres_field: Field containing platform genres
            - classification_mappings.genre_type_attr: Attribute name for genre type
            - classification_mappings.genre_text_key: Key for genre text value
            - platform_genre_types: List of platform type values to extract

    Returns:
        Dict mapping platform names to lists of genre strings.
        Example: {"amazon": ["Drama", "Horror"], "apple": ["Drama"]}

    Example config:
        {
            "classification_mappings": {
                "genres_field": "genres",
                "genre_type_attr": "@type",
                "genre_text_key": "#text",
            },
            "platform_genre_types": ["Amazon", "Apple", "Roku", "SN Series", "Bell Series"],
        }
    """
    platform_genres: dict[str, list[str]] = {}

    classification_mappings = config.get("classification_mappings", {})
    genres_field = classification_mappings.get("genres_field", "genres")
    genre_type_attr = classification_mappings.get("genre_type_attr", "@type")
    genre_text_key = classification_mappings.get("genre_text_key", "#text")

    # Get the genres container
    genres_container = raw_metadata.get(genres_field)
    if not genres_container:
        return platform_genres

    # Handle different structures
    genre_list = None
    if isinstance(genres_container, dict):
        # Structure: {"genre": [...]} or {"genre": {...}}
        genre_list = genres_container.get("genre")
    elif isinstance(genres_container, list):
        # Structure: [...]
        genre_list = genres_container

    if not genre_list:
        return platform_genres

    # Ensure it's a list
    if isinstance(genre_list, dict):
        genre_list = [genre_list]

    # Get platform types to extract from config
    platform_types = config.get(
        "platform_genre_types",
        [
            "Amazon",
            "Apple",
            "Roku",
            "SN Series",
            "SN Genres",
            "Shudder Prod",
            "Bell Series",
            "TELUS Series",
        ],
    )

    # Process each genre entry
    for genre_entry in genre_list:
        if not isinstance(genre_entry, dict):
            continue

        genre_type = genre_entry.get(genre_type_attr)
        if not genre_type:
            continue

        # Check if this is a platform-specific genre
        if genre_type not in platform_types:
            continue

        # Get the genre text
        genre_text = genre_entry.get(genre_text_key)
        if not genre_text or not str(genre_text).strip():
            continue

        genre_text = str(genre_text).strip()

        # Normalize platform name for storage (lowercase, replace spaces with underscore)
        platform_key = genre_type.lower().replace(" ", "_")

        # Add to platform genres
        if platform_key not in platform_genres:
            platform_genres[platform_key] = []

        if genre_text not in platform_genres[platform_key]:
            platform_genres[platform_key].append(genre_text)

    return platform_genres


def extract_default_genres_from_genres_field(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    """Extract default/subgenre genres from the structured genres field.

    This extracts genres with type "default" or "subgenre" from the structured
    genres field (as opposed to the simple genre field).

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing classification_mappings.

    Returns:
        List of genre strings from default/subgenre entries.

    Example:
        >>> raw = {
        ...     "genres": {
        ...         "genre": [
        ...             {"@type": "default", "#text": "Drama"},
        ...             {"@type": "subgenre", "#text": "Horror"},
        ...             {"@type": "Amazon", "#text": "Drama - Crime"},
        ...         ]
        ...     }
        ... }
        >>> config = {"classification_mappings": {"genres_field": "genres"}}
        >>> extract_default_genres_from_genres_field(raw, config)
        ['Drama', 'Horror']
    """
    genres: list[str] = []

    classification_mappings = config.get("classification_mappings", {})
    genres_field = classification_mappings.get("genres_field", "genres")
    genre_type_attr = classification_mappings.get("genre_type_attr", "@type")
    genre_text_key = classification_mappings.get("genre_text_key", "#text")

    # Get the genres container
    genres_container = raw_metadata.get(genres_field)
    if not genres_container:
        return genres

    # Handle different structures
    genre_list = None
    if isinstance(genres_container, dict):
        genre_list = genres_container.get("genre")
    elif isinstance(genres_container, list):
        genre_list = genres_container

    if not genre_list:
        return genres

    # Ensure it's a list
    if isinstance(genre_list, dict):
        genre_list = [genre_list]

    # Default genre types to include in MEC Genre
    default_types = config.get("default_genre_types", ["default", "subgenre"])

    # Process each genre entry
    for genre_entry in genre_list:
        if not isinstance(genre_entry, dict):
            continue

        genre_type = genre_entry.get(genre_type_attr)

        # Include if type is in default types or if no type specified
        if genre_type and genre_type not in default_types:
            continue

        # Get the genre text
        genre_text = genre_entry.get(genre_text_key)
        if not genre_text or not str(genre_text).strip():
            continue

        genre_text = str(genre_text).strip()

        if genre_text not in genres:
            genres.append(genre_text)

    return genres


def map_all_genres(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    """Map all standard genres for MEC LocalizedInfo/Genre.

    This combines genres from:
    1. The simple genre field (primary genre)
    2. The subgenre field (if configured)
    3. Default/subgenre entries from the structured genres field

    Platform-specific genres are NOT included here - they go to custom_fields.

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing classification_mappings.

    Returns:
        List of unique genre strings for MEC LocalizedInfo/Genre.

    Example:
        >>> raw = {
        ...     "genre": "Drama",
        ...     "genres": {
        ...         "genre": [
        ...             {"@type": "default", "#text": "Drama"},
        ...             {"@type": "subgenre", "#text": "Horror"},
        ...         ]
        ...     }
        ... }
        >>> config = {"classification_mappings": {"genre_field": "genre", "genres_field": "genres"}}
        >>> map_all_genres(raw, config)
        ['Drama', 'Horror']
    """
    genres: list[str] = []

    # Get genres from simple fields
    simple_genres = extract_genres_list(raw_metadata, config)
    for genre in simple_genres:
        if genre not in genres:
            genres.append(genre)

    # Get genres from structured genres field
    structured_genres = extract_default_genres_from_genres_field(raw_metadata, config)
    for genre in structured_genres:
        if genre not in genres:
            genres.append(genre)

    return genres
