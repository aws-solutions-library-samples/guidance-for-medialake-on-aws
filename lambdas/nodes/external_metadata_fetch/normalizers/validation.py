"""Validation utilities for metadata normalization.

This module provides comprehensive validation for both input metadata
and normalized output. Validation is configuration-driven - all field
names come from the normalizer configuration.

Key Functions:
    validate_input_metadata: Validate raw source metadata structure
    validate_output_metadata: Validate normalized MEC-compliant output
    validate_data_format: Validate specific data format requirements

Reference: MovieLabs MEC v2.25 (December 2025)
"""

import re
from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.base import ValidationResult
except ImportError:
    from normalizers.base import ValidationResult


# Valid MEC WorkType values
VALID_WORK_TYPES = frozenset(
    {
        "Movie",
        "Episode",
        "Season",
        "Series",
        "Promotion",
        "Short",
        "Clip",
        "Supplemental",
        "Compilation",
        "Collection",
    }
)

# Valid MEC JobFunction values
VALID_JOB_FUNCTIONS = frozenset(
    {
        "Actor",
        "Director",
        "Writer",
        "Producer",
        "ExecutiveProducer",
        "Creator",
        "Composer",
        "Cinematographer",
        "Editor",
        "ProductionDesigner",
        "CostumeDesigner",
        "Choreographer",
        "Narrator",
        "Host",
        "Presenter",
        "Voice",
        "Other",
    }
)

# ISO 8601 duration pattern (e.g., PT45M, PT1H30M, PT1H30M45S)
ISO_DURATION_PATTERN = re.compile(
    r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$", re.IGNORECASE
)

# ISO 8601 date pattern (YYYY-MM-DD)
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Language code pattern (e.g., en, en-US, en-GB)
LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")

# Country code pattern (ISO 3166-1 alpha-2)
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")


def validate_input_metadata(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> ValidationResult:
    """Validate raw source metadata structure before normalization.

    Performs comprehensive validation including:
    - Required field presence (using configured field names)
    - Recommended field presence (generates warnings)
    - Data format validation
    - Structural integrity checks

    Args:
        raw_metadata: Raw metadata dictionary from the source system
        config: Normalizer configuration with field name mappings

    Returns:
        ValidationResult with is_valid=True if no blocking errors,
        or is_valid=False with error details if validation fails
    """
    result = ValidationResult(is_valid=True)

    # Check for empty/None metadata
    if raw_metadata is None:
        result.add_error(
            field_path="root",
            message="Metadata is None - expected a dictionary",
        )
        return result

    if not isinstance(raw_metadata, dict):
        result.add_error(
            field_path="root",
            message=f"Metadata must be a dictionary, got {type(raw_metadata).__name__}",
            source_value=type(raw_metadata).__name__,
        )
        return result

    if not raw_metadata:
        result.add_error(
            field_path="root",
            message="Empty metadata received - no fields present",
        )
        return result

    # Validate identifier fields
    _validate_identifier_fields(raw_metadata, config, result)

    # Validate title fields
    _validate_title_fields(raw_metadata, config, result)

    # Validate temporal fields
    _validate_temporal_fields(raw_metadata, config, result)

    # Validate classification fields
    _validate_classification_fields(raw_metadata, config, result)

    # Validate people fields structure
    _validate_people_fields(raw_metadata, config, result)

    # Validate ratings fields structure
    _validate_ratings_fields(raw_metadata, config, result)

    return result


def _validate_identifier_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate identifier fields are present and valid."""
    primary_id_field = str(config.get("primary_id_field", "id"))
    ref_id_field = str(config.get("ref_id_field", "ref_id"))

    primary_id = raw_metadata.get(primary_id_field)
    ref_id = raw_metadata.get(ref_id_field)

    # At least one identifier should be present
    if not primary_id and not ref_id:
        result.add_warning(
            field_path=f"{primary_id_field}/{ref_id_field}",
            message="No primary identifier found - content_id will be 'unknown'",
        )
    else:
        # Validate identifier format if present
        if primary_id is not None:
            _validate_string_field(
                value=primary_id,
                field_path=primary_id_field,
                field_name="Primary identifier",
                result=result,
                allow_empty=False,
            )

        if ref_id is not None:
            _validate_string_field(
                value=ref_id,
                field_path=ref_id_field,
                field_name="Reference identifier",
                result=result,
                allow_empty=False,
            )


def _validate_title_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate title and description fields."""
    title_mappings = config.get("title_mappings", {})
    title_field = str(title_mappings.get("title_field", "title"))
    title_brief_field = str(title_mappings.get("title_brief_field", "titlebrief"))
    description_field = str(title_mappings.get("description_field", "description"))
    description_short_field = str(
        title_mappings.get("description_short_field", "short_description")
    )

    title = raw_metadata.get(title_field)
    title_brief = raw_metadata.get(title_brief_field)

    # At least one title should be present
    if not title and not title_brief:
        result.add_warning(
            field_path=title_field,
            message="No title found - LocalizedInfo will have no title",
        )
    else:
        # Validate title format if present
        if title is not None:
            _validate_string_field(
                value=title,
                field_path=title_field,
                field_name="Title",
                result=result,
                allow_empty=False,
            )

        if title_brief is not None:
            _validate_string_field(
                value=title_brief,
                field_path=title_brief_field,
                field_name="Brief title",
                result=result,
                allow_empty=True,
            )

    # Descriptions are recommended but not required
    description = raw_metadata.get(description_field)
    description_short = raw_metadata.get(description_short_field)

    if not description and not description_short:
        result.add_warning(
            field_path=description_field,
            message="No description found - LocalizedInfo will have no summary",
        )


def _validate_temporal_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate temporal fields (dates, years, durations)."""
    premiere_year_field = str(config.get("premiere_year_field", "premiere_year"))
    air_date_field = str(config.get("original_air_date_field", "original_air_date"))
    run_length_field = str(config.get("run_length_field", "run_length"))

    # Validate year if present
    year = raw_metadata.get(premiere_year_field)
    if year is not None:
        _validate_year_field(year, premiere_year_field, result)

    # Validate date if present
    date_value = raw_metadata.get(air_date_field)
    if date_value is not None:
        _validate_date_field(date_value, air_date_field, result)

    # Validate duration if present
    duration = raw_metadata.get(run_length_field)
    if duration is not None:
        _validate_duration_field(duration, run_length_field, result)


def _validate_classification_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate content classification fields."""
    classification_mappings = config.get("classification_mappings", {})
    content_type_field = str(
        classification_mappings.get("content_type_field", "content_type")
    )

    content_type = raw_metadata.get(content_type_field)

    # Content type is recommended
    if not content_type:
        result.add_warning(
            field_path=content_type_field,
            message="No content type found - WorkType will be inferred or default to 'Episode'",
        )


def _validate_people_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate people/credits field structure."""
    people_mappings = config.get("people_field_mappings", {})

    for field_name in people_mappings.keys():
        container = raw_metadata.get(field_name)
        if container is None:
            continue

        if not isinstance(container, dict):
            # Could be a list directly
            if isinstance(container, list):
                _validate_people_list(container, field_name, config, result)
            else:
                result.add_warning(
                    field_path=field_name,
                    message=f"Expected dict or list for people field, got {type(container).__name__}",
                    source_value=type(container).__name__,
                )
            continue

        # Get the singular form (actors -> actor)
        singular = field_name.rstrip("s")
        people_list = container.get(singular, [])

        if isinstance(people_list, dict):
            # Single item, wrap in list
            people_list = [people_list]

        if isinstance(people_list, list):
            _validate_people_list(people_list, field_name, config, result)


def _validate_people_list(
    people_list: list[Any],
    field_name: str,
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate a list of people entries."""
    first_name_attr = str(config.get("person_first_name_attr", "first_name"))
    last_name_attr = str(config.get("person_last_name_attr", "last_name"))

    for idx, person in enumerate(people_list):
        if person is None:
            continue

        if not isinstance(person, dict):
            # Could be a simple string (just the name)
            if not isinstance(person, str):
                result.add_warning(
                    field_path=f"{field_name}[{idx}]",
                    message=f"Expected dict or string for person, got {type(person).__name__}",
                    source_value=type(person).__name__,
                )
            continue

        # Check for name information
        has_text = "#text" in person and person["#text"]
        has_first = first_name_attr in person and person[first_name_attr]
        has_last = last_name_attr in person and person[last_name_attr]

        if not has_text and not has_first and not has_last:
            result.add_warning(
                field_path=f"{field_name}[{idx}]",
                message="Person entry has no name information",
                source_value=person,
            )


def _validate_ratings_fields(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate ratings field structure."""
    # Common rating field names
    rating_fields = ["rating", "ratings", "Rating", "Ratings"]

    for field_name in rating_fields:
        container = raw_metadata.get(field_name)
        if container is None:
            continue

        if isinstance(container, dict):
            # Could be nested (rating/Rating) or direct list
            for key, value in container.items():
                if isinstance(value, list):
                    _validate_ratings_list(value, f"{field_name}.{key}", result)
                elif isinstance(value, dict):
                    _validate_ratings_list([value], f"{field_name}.{key}", result)
        elif isinstance(container, list):
            _validate_ratings_list(container, field_name, result)


def _validate_ratings_list(
    ratings_list: list[Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate a list of rating entries."""
    for idx, rating in enumerate(ratings_list):
        if rating is None:
            continue

        if not isinstance(rating, dict):
            result.add_warning(
                field_path=f"{field_path}[{idx}]",
                message=f"Expected dict for rating, got {type(rating).__name__}",
                source_value=type(rating).__name__,
            )
            continue

        # Check for rating value (could be #text or @Value or value)
        has_value = (
            "#text" in rating
            or "@Value" in rating
            or "value" in rating
            or "Value" in rating
        )

        if not has_value:
            result.add_warning(
                field_path=f"{field_path}[{idx}]",
                message="Rating entry has no value",
                source_value=rating,
            )


def _validate_string_field(
    value: Any,
    field_path: str,
    field_name: str,
    result: ValidationResult,
    allow_empty: bool = False,
) -> None:
    """Validate a string field value."""
    if value is None:
        return

    if not isinstance(value, (str, int, float)):
        result.add_warning(
            field_path=field_path,
            message=f"{field_name} should be a string, got {type(value).__name__}",
            source_value=type(value).__name__,
        )
        return

    str_value = str(value).strip()
    if not allow_empty and not str_value:
        result.add_warning(
            field_path=field_path,
            message=f"{field_name} is empty or whitespace-only",
            source_value=value,
        )


def _validate_year_field(
    value: Any,
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate a year field value."""
    if value is None:
        return

    try:
        year = int(value)
        # Reasonable year range for media content
        if year < 1800 or year > 2100:
            result.add_warning(
                field_path=field_path,
                message=f"Year {year} is outside reasonable range (1800-2100)",
                source_value=value,
            )
    except (ValueError, TypeError):
        result.add_error(
            field_path=field_path,
            message=f"Invalid year format: expected integer, got '{value}'",
            source_value=value,
        )


def _validate_date_field(
    value: Any,
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate a date field value."""
    if value is None:
        return

    str_value = str(value).strip()
    if not str_value:
        return

    # Check for ISO 8601 date format
    if not ISO_DATE_PATTERN.match(str_value):
        result.add_warning(
            field_path=field_path,
            message=f"Date '{str_value}' is not in ISO 8601 format (YYYY-MM-DD)",
            source_value=value,
        )


def _validate_duration_field(
    value: Any,
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate a duration field value."""
    if value is None:
        return

    str_value = str(value).strip()
    if not str_value:
        return

    # Check if it's already ISO 8601 duration
    if str_value.upper().startswith("PT"):
        if not ISO_DURATION_PATTERN.match(str_value):
            result.add_warning(
                field_path=field_path,
                message=f"Duration '{str_value}' appears to be ISO 8601 but is malformed",
                source_value=value,
            )
        return

    # Check if it's a numeric value (seconds)
    try:
        seconds = int(str_value)
        if seconds < 0:
            result.add_warning(
                field_path=field_path,
                message=f"Duration cannot be negative: {seconds}",
                source_value=value,
            )
        elif seconds > 86400 * 7:  # More than a week
            result.add_warning(
                field_path=field_path,
                message=f"Duration {seconds} seconds seems unusually long",
                source_value=value,
            )
    except (ValueError, TypeError):
        result.add_warning(
            field_path=field_path,
            message=f"Duration '{str_value}' is not a valid format (expected ISO 8601 or seconds)",
            source_value=value,
        )


def validate_output_metadata(
    normalized_metadata: dict[str, Any] | None,
) -> ValidationResult:
    """Validate normalized output against MEC requirements.

    Performs comprehensive validation including:
    - Required MEC fields are populated
    - Data types and formats are correct
    - MEC element values are valid

    Args:
        normalized_metadata: Normalized metadata dictionary

    Returns:
        ValidationResult with is_valid=True if output is valid,
        or is_valid=False with error details if validation fails
    """
    result = ValidationResult(is_valid=True)

    if normalized_metadata is None:
        result.add_error(
            field_path="root",
            message="Normalized metadata is None",
        )
        return result

    if not isinstance(normalized_metadata, dict):
        result.add_error(
            field_path="root",
            message=f"Normalized metadata must be a dictionary, got {type(normalized_metadata).__name__}",
        )
        return result

    # Validate basic_metadata (required)
    basic_metadata = normalized_metadata.get("basic_metadata")
    if basic_metadata is None:
        result.add_error(
            field_path="basic_metadata",
            message="basic_metadata is required in normalized output",
        )
        return result

    _validate_basic_metadata(basic_metadata, result)

    # Validate source_attribution (recommended)
    source_attribution = normalized_metadata.get("source_attribution")
    if source_attribution:
        _validate_source_attribution(source_attribution, result)

    # Validate schema_version
    schema_version = normalized_metadata.get("schema_version")
    if not schema_version:
        result.add_warning(
            field_path="schema_version",
            message="schema_version is missing",
        )

    return result


def _validate_basic_metadata(
    basic_metadata: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate BasicMetadata structure."""
    # content_id is required
    content_id = basic_metadata.get("content_id")
    if not content_id:
        result.add_error(
            field_path="basic_metadata.content_id",
            message="content_id is required",
        )
    elif content_id == "unknown":
        result.add_warning(
            field_path="basic_metadata.content_id",
            message="content_id is 'unknown' - no identifier was found in source",
        )

    # work_type is required
    work_type = basic_metadata.get("work_type")
    if not work_type:
        result.add_error(
            field_path="basic_metadata.work_type",
            message="work_type is required",
        )
    elif work_type not in VALID_WORK_TYPES:
        result.add_warning(
            field_path="basic_metadata.work_type",
            message=f"work_type '{work_type}' is not a standard MEC WorkType",
            source_value=work_type,
        )

    # Validate localized_info
    localized_info = basic_metadata.get("localized_info", [])
    if not localized_info:
        result.add_warning(
            field_path="basic_metadata.localized_info",
            message="No localized_info present - content has no title or description",
        )
    else:
        for idx, info in enumerate(localized_info):
            _validate_localized_info(
                info, f"basic_metadata.localized_info[{idx}]", result
            )

    # Validate release_year if present
    release_year = basic_metadata.get("release_year")
    if release_year is not None:
        if not isinstance(release_year, int):
            result.add_error(
                field_path="basic_metadata.release_year",
                message=f"release_year must be an integer, got {type(release_year).__name__}",
                source_value=release_year,
            )
        elif release_year < 1800 or release_year > 2100:
            result.add_warning(
                field_path="basic_metadata.release_year",
                message=f"release_year {release_year} is outside reasonable range",
                source_value=release_year,
            )

    # Validate release_date if present
    release_date = basic_metadata.get("release_date")
    if release_date is not None:
        if not isinstance(release_date, str):
            result.add_error(
                field_path="basic_metadata.release_date",
                message=f"release_date must be a string, got {type(release_date).__name__}",
                source_value=release_date,
            )
        elif not ISO_DATE_PATTERN.match(release_date):
            result.add_warning(
                field_path="basic_metadata.release_date",
                message=f"release_date '{release_date}' is not in ISO 8601 format",
                source_value=release_date,
            )

    # Validate ratings
    ratings = basic_metadata.get("ratings", [])
    for idx, rating in enumerate(ratings):
        _validate_rating(rating, f"basic_metadata.ratings[{idx}]", result)

    # Validate people
    people = basic_metadata.get("people", [])
    for idx, person in enumerate(people):
        _validate_job(person, f"basic_metadata.people[{idx}]", result)

    # Validate alt_identifiers
    alt_identifiers = basic_metadata.get("alt_identifiers", [])
    for idx, alt_id in enumerate(alt_identifiers):
        _validate_alt_identifier(
            alt_id, f"basic_metadata.alt_identifiers[{idx}]", result
        )

    # Validate sequence_info if present
    sequence_info = basic_metadata.get("sequence_info")
    if sequence_info:
        _validate_sequence_info(sequence_info, "basic_metadata.sequence_info", result)

    # Validate parents
    parents = basic_metadata.get("parents", [])
    for idx, parent in enumerate(parents):
        _validate_parent(parent, f"basic_metadata.parents[{idx}]", result)

    # Validate run_length if present
    run_length = basic_metadata.get("run_length")
    if run_length is not None:
        if not isinstance(run_length, str):
            result.add_error(
                field_path="basic_metadata.run_length",
                message=f"run_length must be a string, got {type(run_length).__name__}",
                source_value=run_length,
            )
        elif not run_length.upper().startswith("PT"):
            result.add_warning(
                field_path="basic_metadata.run_length",
                message=f"run_length '{run_length}' should be in ISO 8601 duration format",
                source_value=run_length,
            )


def _validate_localized_info(
    info: dict[str, Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate LocalizedInfo structure."""
    # language is required
    language = info.get("language")
    if not language:
        result.add_error(
            field_path=f"{field_path}.language",
            message="language is required in LocalizedInfo",
        )
    elif not LANGUAGE_CODE_PATTERN.match(language):
        result.add_warning(
            field_path=f"{field_path}.language",
            message=f"language '{language}' may not be a valid language code",
            source_value=language,
        )

    # At least one title should be present
    has_title = (
        info.get("title_display_unlimited")
        or info.get("title_display_19")
        or info.get("title_internal_alias")
    )
    if not has_title:
        result.add_warning(
            field_path=field_path,
            message="LocalizedInfo has no title fields",
        )


def _validate_rating(
    rating: dict[str, Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate Rating structure."""
    # region is required
    region = rating.get("region")
    if not region:
        result.add_error(
            field_path=f"{field_path}.region",
            message="region is required in Rating (MEC v2.25)",
        )
    elif not COUNTRY_CODE_PATTERN.match(region):
        result.add_warning(
            field_path=f"{field_path}.region",
            message=f"region '{region}' may not be a valid country code",
            source_value=region,
        )

    # system is required
    system = rating.get("system")
    if not system:
        result.add_error(
            field_path=f"{field_path}.system",
            message="system is required in Rating",
        )

    # value is required
    value = rating.get("value")
    if not value:
        result.add_error(
            field_path=f"{field_path}.value",
            message="value is required in Rating",
        )


def _validate_job(
    job: dict[str, Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate Job (person) structure."""
    # job_function is required
    job_function = job.get("job_function")
    if not job_function:
        result.add_error(
            field_path=f"{field_path}.job_function",
            message="job_function is required in Job",
        )
    elif job_function not in VALID_JOB_FUNCTIONS:
        result.add_warning(
            field_path=f"{field_path}.job_function",
            message=f"job_function '{job_function}' is not a standard MEC JobFunction",
            source_value=job_function,
        )

    # name is required
    name = job.get("name")
    if not name:
        result.add_error(
            field_path=f"{field_path}.name",
            message="name is required in Job",
        )
    elif isinstance(name, dict):
        # display_name is required in PersonName
        display_name = name.get("display_name")
        if not display_name:
            result.add_error(
                field_path=f"{field_path}.name.display_name",
                message="display_name is required in PersonName (MEC v2.25)",
            )

    # billing_block_order should be positive if present
    billing_order = job.get("billing_block_order")
    if billing_order is not None:
        if not isinstance(billing_order, int):
            result.add_warning(
                field_path=f"{field_path}.billing_block_order",
                message=f"billing_block_order should be an integer, got {type(billing_order).__name__}",
                source_value=billing_order,
            )
        elif billing_order < 1:
            result.add_warning(
                field_path=f"{field_path}.billing_block_order",
                message=f"billing_block_order should be positive, got {billing_order}",
                source_value=billing_order,
            )


def _validate_alt_identifier(
    alt_id: dict[str, Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate AltIdentifier structure."""
    # namespace is required
    namespace = alt_id.get("namespace")
    if not namespace:
        result.add_error(
            field_path=f"{field_path}.namespace",
            message="namespace is required in AltIdentifier",
        )

    # identifier is required
    identifier = alt_id.get("identifier")
    if not identifier:
        result.add_error(
            field_path=f"{field_path}.identifier",
            message="identifier is required in AltIdentifier",
        )


def _validate_sequence_info(
    seq_info: dict[str, Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate SequenceInfo structure."""
    # number is required
    number = seq_info.get("number")
    if number is None:
        result.add_error(
            field_path=f"{field_path}.number",
            message="number is required in SequenceInfo",
        )
    elif not isinstance(number, int):
        result.add_error(
            field_path=f"{field_path}.number",
            message=f"number must be an integer, got {type(number).__name__}",
            source_value=number,
        )
    elif number < 0:
        result.add_warning(
            field_path=f"{field_path}.number",
            message=f"number should be non-negative, got {number}",
            source_value=number,
        )


def _validate_parent(
    parent: dict[str, Any],
    field_path: str,
    result: ValidationResult,
) -> None:
    """Validate Parent relationship structure."""
    # relationship_type is required
    rel_type = parent.get("relationship_type")
    if not rel_type:
        result.add_error(
            field_path=f"{field_path}.relationship_type",
            message="relationship_type is required in Parent",
        )
    elif rel_type not in ("isepisodeof", "isseasonof"):
        result.add_warning(
            field_path=f"{field_path}.relationship_type",
            message=f"relationship_type '{rel_type}' is not a standard MEC relationship",
            source_value=rel_type,
        )

    # parent_content_id is required
    parent_id = parent.get("parent_content_id")
    if not parent_id:
        result.add_error(
            field_path=f"{field_path}.parent_content_id",
            message="parent_content_id is required in Parent",
        )


def _validate_source_attribution(
    source_attr: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate SourceAttribution structure."""
    # source_system is required
    if not source_attr.get("source_system"):
        result.add_warning(
            field_path="source_attribution.source_system",
            message="source_system is missing in source_attribution",
        )

    # source_type is required
    if not source_attr.get("source_type"):
        result.add_warning(
            field_path="source_attribution.source_type",
            message="source_type is missing in source_attribution",
        )

    # correlation_id is required
    if not source_attr.get("correlation_id"):
        result.add_warning(
            field_path="source_attribution.correlation_id",
            message="correlation_id is missing in source_attribution",
        )
