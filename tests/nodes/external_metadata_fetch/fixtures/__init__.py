"""Test fixtures for external_metadata_fetch normalizer tests.

This package contains anonymized XML fixtures for testing the metadata
normalization functionality. All fixtures use generic, customer-agnostic
data to ensure the codebase remains configuration-driven.

Fixture Categories:
- Full Episodes: Complete episode metadata with all fields populated
- Trailers: Interstitial/promotional content with minimal metadata
- Special Content: Edge cases and special content types

Usage:
    from tests.nodes.external_metadata_fetch.fixtures import (
        load_fixture,
        SAMPLE_CONFIG,
    )

    metadata = load_fixture("episode_full_001.xml")
    result = normalizer.normalize(metadata)
"""

import json
from pathlib import Path
from typing import Any

import xmltodict

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent


def load_fixture(filename: str) -> dict[str, Any]:
    """Load and parse an XML fixture file.

    Args:
        filename: Name of the fixture file (e.g., "episode_full_001.xml")

    Returns:
        Parsed metadata dictionary (as xmltodict would produce)

    Raises:
        FileNotFoundError: If fixture file doesn't exist
    """
    filepath = FIXTURES_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse XML to dict (same as the normalizer receives)
    parsed = xmltodict.parse(content)

    # Return the root element's content
    if "ProgramMetadata" in parsed:
        return parsed["ProgramMetadata"]
    return parsed


def load_json_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON fixture file.

    Args:
        filename: Name of the JSON fixture file

    Returns:
        Parsed JSON dictionary
    """
    filepath = FIXTURES_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# Sample configuration for testing (matches the anonymized fixtures)
SAMPLE_CONFIG: dict[str, Any] = {
    "source_namespace_prefix": "ACME",
    "default_language": "en-US",
    "include_raw_source": False,
    "primary_id_field": "acme_id",
    "ref_id_field": "refid",
    "title_field": "title",
    "title_brief_field": "titlebrief",
    "premiere_year_field": "premiere_year",
    "original_air_date_field": "original_air_date",
    "country_code_field": "country_code",
    "language_field": "language",
    "identifier_mappings": {
        "acme_id": "",
        "refid": "-REF",
        "version_id": "-VERSION",
        "id_sequence": "-SEQ",
        "tms_series_id": "TMS",
        "tms_episode_id": "TMS",
        "tms_movie_id": "TMS",
        "ad_content_id": "-AD",
    },
    "title_mappings": {
        "title_field": "title",
        "title_brief_field": "titlebrief",
        "description_field": "long_description",
        "description_short_field": "short_description",
        "copyright_holder_field": "copyright_holder",
        "keywords_field": "keywords",
    },
    "hierarchy_field_mappings": {
        "series_id_field": "series_id",
        "season_id_field": "season_id",
        "episode_number_field": "episode_number",
        "season_number_field": "season_number",
        "show_name_field": "show_name",
        "short_series_description_field": "short_series_description",
        "long_series_description_field": "long_series_description",
        "short_season_description_field": "short_season_description",
        "long_season_description_field": "long_season_description",
        "series_premiere_date_field": "series_premiere_date",
        "season_count_field": "season_count",
        "episode_count_field": "episode_count",
    },
    "people_field_mappings": {
        "actors": "Actor",
        "directors": "Director",
        "writers": "Writer",
        "producers": "Producer",
        "executive_producers": "ExecutiveProducer",
        "series_creators": "Creator",
        "guest_actors": "Actor",
    },
    "person_first_name_attr": "@first_name",
    "person_last_name_attr": "@last_name",
    "person_order_attr": "@order",
    "person_role_attr": "@role",
    "guest_actors_field": "guest_actors",
    "classification_field_mappings": {
        "is_movie_field": "is_movie",
        "content_type_field": "content_type",
        "video_type_field": "video_type",
        "genre_field": "genre",
        "genres_container_field": "genres",
    },
    "rating_system_mappings": {
        "TV Rating": {"system": "us-tv", "region": "US"},
        "us-tv": {"system": "us-tv", "region": "US"},
        "ca-tv": {"system": "ca-tv", "region": "CA"},
        "au-tv": {"system": "au-tv", "region": "AU"},
        "ACMA": {"system": "ACMA", "region": "AU"},
        "DMEC": {"system": "DMEC", "region": "MX"},
        "in-tv": {"system": "in-tv", "region": "IN"},
        "nz-tv": {"system": "nz-tv", "region": "NZ"},
        "nz-am": {"system": "nz-am", "region": "NZ"},
    },
    "technical_field_mappings": {
        "frame_rate_field": "frame_rate",
        "video_dar_field": "video_dar",
        "video_definition_field": "video_definition",
        "resolution_field": "resolution",
        "in_color_flag_field": "in_color_flag",
        "video_filename_field": "video_filename",
        "captions_filename_field": "captions_filename",
    },
    # custom_field_categories maps category names to lists of field names
    "custom_field_categories": {
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
        ],
        "rights": [
            "platform_rights",
            "carousel",
        ],
        "other": [
            "placement",
        ],
    },
    "platform_genre_types": [
        "Amazon",
        "Apple",
        "Roku",
        "SN Series",
        "SN Genres",
        "Shudder Prod",
        "Bell Series",
        "TELUS Series",
    ],
}
