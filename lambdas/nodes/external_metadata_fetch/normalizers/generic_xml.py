"""Configuration-driven Generic XML normalizer for MEC-compliant metadata.

This module provides a generic XML normalizer that transforms XML metadata from
external systems into MovieLabs MEC-compliant structure using configuration-driven
field mappings.

The normalizer is designed to be customer-agnostic - ALL customer-specific field
names and namespace prefixes are defined in configuration, NOT in code.

Example configuration:
    {
        "source_namespace_prefix": "CUSTOMER",
        "default_language": "en-US",
        "primary_id_field": "primary_id",
        "ref_id_field": "ref_id",
        "identifier_mappings": {...},
        "title_mappings": {...},
        "people_field_mappings": {...},
        "rating_system_mappings": {...},
        ...
    }

Reference: MovieLabs MEC v2.25 (December 2025)
"""

import json
import logging
import time
from typing import Any, override

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.base import (
        NormalizationResult,
        SourceNormalizer,
        ValidationResult,
    )
    from nodes.external_metadata_fetch.normalizers.field_mappers import (
        extract_custom_fields,
        map_classifications,
        map_hierarchy,
        map_identifiers,
        map_people,
        map_ratings,
        map_technical,
        map_titles,
    )
    from nodes.external_metadata_fetch.normalizers.mec_schema import (
        BasicMetadata,
        NormalizedMetadata,
        SourceAttribution,
    )
    from nodes.external_metadata_fetch.normalizers.validation import (
        validate_input_metadata,
        validate_output_metadata,
    )
except ImportError:
    from normalizers.base import (
        NormalizationResult,
        SourceNormalizer,
        ValidationResult,
    )
    from normalizers.field_mappers import (
        extract_custom_fields,
        map_classifications,
        map_hierarchy,
        map_identifiers,
        map_people,
        map_ratings,
        map_technical,
        map_titles,
    )
    from normalizers.mec_schema import (
        BasicMetadata,
        NormalizedMetadata,
        SourceAttribution,
    )
    from normalizers.validation import (
        validate_input_metadata,
        validate_output_metadata,
    )

# Module-level logger for performance metrics
# Uses standard logging to work in both Lambda and test environments
logger = logging.getLogger(__name__)


def _get_size_bytes(data: dict[str, Any] | None) -> int:
    """Calculate the approximate size of a dictionary in bytes.

    Args:
        data: Dictionary to measure

    Returns:
        Size in bytes (0 if data is None)
    """
    if data is None:
        return 0
    try:
        return len(json.dumps(data, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


class GenericXmlNormalizer(SourceNormalizer):
    """Configuration-driven normalizer for XML metadata formats.

    This normalizer transforms XML metadata from external systems into
    MEC-compliant structure. All customer-specific field names and namespace
    prefixes are defined in the configuration passed to the constructor.
    The code contains NO hardcoded customer-specific values.

    Configuration Options:
        source_namespace_prefix: Customer namespace prefix (e.g., "CUSTOMER")
        default_language: Default language code (e.g., "en-US")
        primary_id_field: Field name for primary identifier
        ref_id_field: Field name for reference/correlation ID
        include_raw_source: Whether to include original source in output
        identifier_mappings: Map of field names to namespace suffixes
        title_mappings: Title field configurations
        description_mappings: Description field configurations
        classification_mappings: Content classification configurations
        hierarchy_mappings: Hierarchy/sequence field configurations
        parent_metadata_mappings: Parent metadata field configurations
        people_field_mappings: People/credits field configurations
        rating_system_mappings: Rating system to region mappings
        custom_field_categories: Categories of unmapped fields to preserve

    Example:
        >>> config = {
        ...     "source_namespace_prefix": "ACME",
        ...     "primary_id_field": "content_id",
        ...     "identifier_mappings": {"content_id": "", "ref_id": "-REF"},
        ... }
        >>> normalizer = GenericXmlNormalizer(config)
        >>> result = normalizer.normalize({"content_id": "123", "title": "Test"})
        >>> result.success
        True
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Generic XML normalizer with configuration.

        Args:
            config: Configuration dictionary containing customer-specific
                    field mappings and settings. All field names come from
                    this config - no hardcoded customer values.
        """
        super().__init__(config)

        # Extract commonly used configuration values with defaults
        self._source_namespace_prefix: str = str(
            self.config.get("source_namespace_prefix", "SOURCE")
        )
        self._default_language: str = str(self.config.get("default_language", "en-US"))
        self._primary_id_field: str = str(self.config.get("primary_id_field", "id"))
        self._ref_id_field: str = str(self.config.get("ref_id_field", "ref_id"))
        self._include_raw_source: bool = bool(
            self.config.get("include_raw_source", False)
        )

    @override
    def get_source_type(self) -> str:
        """Return the source type identifier.

        Returns:
            "generic_xml" - identifies this as the generic XML normalizer
        """
        return "generic_xml"

    @override
    def validate_input(self, raw_metadata: dict[str, Any]) -> ValidationResult:
        """Validate the source metadata structure before normalization.

        Performs comprehensive validation using configured field names:
        - Required field presence (identifiers, titles)
        - Recommended field presence (generates warnings)
        - Data format validation (dates, years, durations)
        - Structural integrity checks (people, ratings)

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            ValidationResult with is_valid=True if validation passes,
            or is_valid=False with error details if validation fails.
        """
        return validate_input_metadata(raw_metadata, self.config)

    @override
    def normalize(self, raw_metadata: dict[str, Any]) -> NormalizationResult:
        """Transform source metadata to MEC-compliant normalized format.

        Orchestrates all field mappers with configuration to produce
        MEC-compliant output. All field name lookups use config.

        Performance metrics are logged including:
        - Normalization duration in milliseconds
        - Input size in bytes
        - Output size in bytes

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            NormalizationResult with success=True and normalized_metadata
            if successful, or success=False with validation errors if failed.
        """
        # Start performance timing
        start_time = time.perf_counter()
        input_size_bytes = _get_size_bytes(raw_metadata)

        # Validate input first
        validation = self.validate_input(raw_metadata)

        if not validation.is_valid:
            # Log performance even for validation failures
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "Normalization failed validation",
                extra={
                    "duration_ms": round(duration_ms, 3),
                    "input_size_bytes": input_size_bytes,
                    "success": False,
                    "error_count": len(validation.errors),
                },
            )
            return NormalizationResult(
                success=False,
                validation=validation,
                raw_source=raw_metadata if self._include_raw_source else None,
            )

        try:
            # Generate content ID using configured field names
            content_id = self._generate_content_id(raw_metadata)

            # Determine work type and detail
            work_type, work_type_detail = map_classifications.get_work_type(
                raw_metadata, self.config
            )

            # Map localized info (titles, descriptions, genres)
            localized_info = map_titles.map_localized_info(raw_metadata, self.config)

            # Add genres to localized info
            genres = map_classifications.map_all_genres(raw_metadata, self.config)
            if localized_info and genres:
                localized_info[0].genres = genres

            # Map all identifiers
            alt_identifiers = map_identifiers.map_all_identifiers(
                raw_metadata, self.config
            )

            # Map hierarchy (sequence info and parents)
            sequence_info = map_hierarchy.map_sequence_info(raw_metadata, self.config)
            parents = map_hierarchy.map_parents(raw_metadata, self.config)

            # Map people/credits
            people = map_people.map_all_people(raw_metadata, self.config)

            # Map ratings
            ratings = map_ratings.map_ratings(raw_metadata, self.config)

            # Map technical metadata
            technical = map_technical.map_all_technical(raw_metadata, self.config)

            # Extract temporal information
            release_year = self._extract_year(raw_metadata)
            release_date = self._extract_date(raw_metadata)

            # Extract geographic/linguistic info
            country_of_origin = self._extract_country(raw_metadata)
            original_language = self._extract_language(raw_metadata)

            # Extract run length
            run_length = self._extract_run_length(raw_metadata)

            # Build BasicMetadata
            basic_metadata = BasicMetadata(
                content_id=content_id,
                work_type=work_type,
                work_type_detail=work_type_detail,
                localized_info=localized_info,
                release_year=release_year,
                release_date=release_date,
                ratings=ratings,
                people=people,
                country_of_origin=country_of_origin,
                original_language=original_language,
                sequence_info=sequence_info,
                parents=parents,
                alt_identifiers=alt_identifiers,
                video_attributes=technical.get("video_attributes"),
                audio_attributes=technical.get("audio_attributes", []),
                subtitle_attributes=technical.get("subtitle_attributes", []),
                run_length=run_length,
            )

            # Extract custom fields (unmapped data)
            custom_fields = extract_custom_fields.extract(raw_metadata, self.config)

            # Extract parent metadata for denormalized storage
            parent_metadata = map_hierarchy.extract_parent_metadata(
                raw_metadata, self.config
            )

            # Build source attribution
            source_attribution = SourceAttribution(
                source_system=self._source_namespace_prefix.lower(),
                source_type=self.get_source_type(),
                correlation_id=self._get_correlation_id(raw_metadata),
                normalized_at=None,  # Set by caller
            )

            # Build complete normalized metadata
            normalized = NormalizedMetadata(
                basic_metadata=basic_metadata,
                custom_fields=custom_fields,
                parent_metadata=parent_metadata,
                source_attribution=source_attribution,
            )

            # Convert to dict for storage
            normalized_dict = normalized.to_dict()

            # Validate output against MEC requirements
            output_validation = validate_output_metadata(normalized_dict)

            # Merge output validation issues into the result
            for issue in output_validation.issues:
                validation.issues.append(issue)

            # Output validation errors don't block success, but are reported
            # (input validation errors block, output validation issues are warnings)

            # Calculate performance metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            output_size_bytes = _get_size_bytes(normalized_dict)

            # Log performance metrics
            logger.info(
                "Normalization completed",
                extra={
                    "duration_ms": round(duration_ms, 3),
                    "input_size_bytes": input_size_bytes,
                    "output_size_bytes": output_size_bytes,
                    "content_id": content_id,
                    "work_type": work_type,
                    "success": True,
                    "warning_count": len(validation.warnings),
                },
            )

            return NormalizationResult(
                success=True,
                normalized_metadata=normalized_dict,
                validation=validation,
                raw_source=raw_metadata if self._include_raw_source else None,
            )

        except Exception as e:
            # Calculate performance metrics even on failure
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log performance metrics for failed normalization
            logger.warning(
                "Normalization failed with exception",
                extra={
                    "duration_ms": round(duration_ms, 3),
                    "input_size_bytes": input_size_bytes,
                    "success": False,
                    "error": str(e),
                },
            )

            # Add error to validation result
            validation.add_error(
                field_path="normalization",
                message=f"Normalization failed: {str(e)}",
            )
            return NormalizationResult(
                success=False,
                validation=validation,
                raw_source=raw_metadata if self._include_raw_source else None,
            )

    def _generate_content_id(self, raw_metadata: dict[str, Any]) -> str:
        """Generate a content ID from available identifiers using config.

        Uses the configured primary_id_field and ref_id_field to find
        the best available identifier.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Content ID string, or "unknown" if no identifier found.
        """
        # Try primary ID first
        primary_id = raw_metadata.get(self._primary_id_field)
        if primary_id and str(primary_id).strip():
            return str(primary_id).strip()

        # Fall back to ref ID
        ref_id = raw_metadata.get(self._ref_id_field)
        if ref_id and str(ref_id).strip():
            return str(ref_id).strip()

        return "unknown"

    def _get_correlation_id(self, raw_metadata: dict[str, Any]) -> str:
        """Get the correlation ID for source attribution.

        Prefers ref_id over primary_id for correlation.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Correlation ID string.
        """
        # Prefer ref_id for correlation
        ref_id = raw_metadata.get(self._ref_id_field)
        if ref_id and str(ref_id).strip():
            return str(ref_id).strip()

        # Fall back to primary ID
        primary_id = raw_metadata.get(self._primary_id_field)
        if primary_id and str(primary_id).strip():
            return str(primary_id).strip()

        return "unknown"

    def _extract_year(self, raw_metadata: dict[str, Any]) -> int | None:
        """Extract release year using configured field name.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Release year as integer, or None if not found/invalid.
        """
        year_field: str = str(self.config.get("premiere_year_field", "premiere_year"))
        year = raw_metadata.get(year_field)

        if year is None:
            return None

        try:
            return int(year)
        except (ValueError, TypeError):
            return None

    def _extract_date(self, raw_metadata: dict[str, Any]) -> str | None:
        """Extract release date in ISO format using configured field name.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Release date as ISO format string, or None if not found.
        """
        date_field: str = str(
            self.config.get("original_air_date_field", "original_air_date")
        )
        date_value = raw_metadata.get(date_field)

        if date_value is None:
            return None

        date_str = str(date_value).strip()
        return date_str if date_str else None

    def _extract_country(self, raw_metadata: dict[str, Any]) -> str | None:
        """Extract country of origin using configured field name.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Country code string, or None if not found.
        """
        country_field: str = str(self.config.get("country_code_field", "country_code"))
        country = raw_metadata.get(country_field)

        if country is None:
            return None

        country_str = str(country).strip()
        return country_str if country_str else None

    def _extract_language(self, raw_metadata: dict[str, Any]) -> str | None:
        """Extract original language using configured field name.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Language code string, or None if not found.
        """
        language_field: str = str(self.config.get("language_field", "language"))
        language = raw_metadata.get(language_field)

        if language is None:
            return None

        language_str = str(language).strip()
        return language_str if language_str else None

    def _extract_run_length(self, raw_metadata: dict[str, Any]) -> str | None:
        """Extract run length/duration using configured field name.

        Converts duration to ISO 8601 format if needed.

        Args:
            raw_metadata: Raw metadata dictionary from the source system.

        Returns:
            Duration in ISO 8601 format (e.g., "PT45M"), or None if not found.
        """
        run_length_field: str = str(self.config.get("run_length_field", "run_length"))
        run_length = raw_metadata.get(run_length_field)

        if run_length is None:
            return None

        run_length_str = str(run_length).strip()
        if not run_length_str:
            return None

        # If already in ISO 8601 format (starts with PT), return as-is
        if run_length_str.upper().startswith("PT"):
            return run_length_str

        # Try to convert from seconds or minutes
        try:
            # Assume it's in seconds if it's a number
            seconds = int(run_length_str)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            parts = ["PT"]
            if hours > 0:
                parts.append(f"{hours}H")
            if minutes > 0:
                parts.append(f"{minutes}M")
            if secs > 0 or (hours == 0 and minutes == 0):
                parts.append(f"{secs}S")

            return "".join(parts)
        except (ValueError, TypeError):
            # Return as-is if we can't convert
            return run_length_str
