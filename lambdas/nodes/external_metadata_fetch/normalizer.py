"""Metadata normalizer facade for external metadata enrichment.

This module provides the MetadataNormalizer facade that:
- Supports pluggable source normalizers via the normalizer factory
- Maintains backward compatibility with the placeholder implementation
- Allows configuration-driven normalization for different source formats

The normalizer can operate in two modes:
1. Placeholder mode (default): Simple extraction of basic fields
2. Full normalization mode: MEC-compliant transformation using source normalizers

Configuration is passed from the node's NodeConfig, allowing customer-specific
field mappings to be defined at pipeline configuration time.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SourceAttribution:
    """Attribution information for the metadata source.

    Attributes:
        source_system: Adapter name (e.g., "generic_rest_api:oauth2_client_credentials")
        fetch_timestamp: ISO 8601 timestamp when metadata was fetched
        correlation_id: ID used for lookup in the external system
        source_record_id: Original record ID from source system (optional)
    """

    source_system: str
    fetch_timestamp: str
    correlation_id: str
    source_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage.

        Returns:
            Dictionary representation with None values excluded
        """
        result: dict[str, Any] = {
            "source_system": self.source_system,
            "fetch_timestamp": self.fetch_timestamp,
            "correlation_id": self.correlation_id,
        }
        if self.source_record_id is not None:
            result["source_record_id"] = self.source_record_id
        return result


@dataclass
class NormalizedMetadata:
    """Normalized metadata schema for external metadata.

    This is a placeholder implementation that stores most data in custom_fields.
    Full MovieLabs DDF-compatible normalization will be implemented in a later phase.

    Reference: https://movielabs.com/md/

    Attributes:
        title: Asset title (extracted if present in raw metadata)
        description: Asset description (extracted if present in raw metadata)
        custom_fields: All raw metadata fields stored for future normalization
        source_attribution: Attribution information (always populated)
    """

    # Basic fields extracted from raw metadata
    title: str | None = None
    description: str | None = None

    # All raw metadata stored here for placeholder implementation
    custom_fields: dict[str, Any] = field(default_factory=dict)

    # Source attribution (always populated)
    source_attribution: SourceAttribution | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage.

        Returns:
            Dictionary representation with empty/None values excluded
        """
        result: dict[str, Any] = {}

        if self.title is not None:
            result["title"] = self.title

        if self.description is not None:
            result["description"] = self.description

        if self.custom_fields:
            result["custom_fields"] = self.custom_fields

        if self.source_attribution is not None:
            result["source_attribution"] = self.source_attribution.to_dict()

        return result


class MetadataNormalizer:
    """Facade for metadata normalization supporting pluggable source normalizers.

    This class provides a unified interface for metadata normalization that:
    - Supports pluggable source normalizers via the normalizer factory
    - Maintains backward compatibility with the placeholder implementation
    - Allows configuration-driven normalization for different source formats

    The normalizer operates in two modes:
    1. Placeholder mode (default, source_type=None): Simple extraction of basic fields
    2. Full normalization mode (source_type specified): MEC-compliant transformation

    Example (placeholder mode - backward compatible):
        >>> normalizer = MetadataNormalizer()
        >>> raw = {"title": "My Asset", "customField": "value"}
        >>> result = normalizer.normalize(raw, "generic_rest_api", "ABC123")
        >>> result.title
        'My Asset'

    Example (full normalization mode):
        >>> config = {"source_namespace_prefix": "ACME", ...}
        >>> normalizer = MetadataNormalizer(source_type="generic_xml", config=config)
        >>> result = normalizer.normalize(raw, "generic_rest_api", "ABC123")
        >>> # Returns MEC-compliant normalized metadata
    """

    # Basic field mappings for placeholder implementation
    # Maps normalized field name to list of possible source field names
    BASIC_FIELD_MAPPINGS: dict[str, list[str]] = {
        "title": ["title", "name", "assetTitle", "displayName", "Title", "Name"],
        "description": [
            "description",
            "synopsis",
            "summary",
            "longDescription",
            "Description",
            "Synopsis",
        ],
    }

    def __init__(
        self,
        source_type: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """Initialize the normalizer with optional source type and configuration.

        Args:
            source_type: The normalizer type identifier (e.g., "generic_xml").
                        If None, uses placeholder behavior for backward compatibility.
            config: Configuration dictionary containing customer-specific field
                   mappings. Required when source_type is specified.
                   All field names and namespace prefixes come from this config.
        """
        self._source_type: str | None = source_type
        self._config: dict[str, Any] = config or {}
        self._source_normalizer: Any = None

        # Create source normalizer if source_type is specified
        if source_type:
            # Import here to avoid circular imports and allow lazy loading
            # Support both pytest imports (package-qualified) and Lambda runtime (absolute)
            try:
                from nodes.external_metadata_fetch.normalizers import create_normalizer
            except ImportError:
                from normalizers import create_normalizer
            self._source_normalizer = create_normalizer(source_type, config)

    def normalize(
        self,
        raw_metadata: dict[str, Any],
        source_system: str,
        correlation_id: str,
    ) -> NormalizedMetadata | dict[str, Any]:
        """Normalize raw metadata into standard format.

        Behavior depends on whether a source_type was specified at construction:

        Placeholder mode (source_type=None):
        1. Extracts title and description if present in raw metadata
        2. Stores ALL raw metadata in custom_fields
        3. Populates source_attribution with required fields
        4. Returns NormalizedMetadata instance

        Full normalization mode (source_type specified):
        1. Uses the configured source normalizer for MEC-compliant transformation
        2. Returns the normalized metadata dictionary from the source normalizer
        3. Falls back to placeholder behavior if normalization fails

        Args:
            raw_metadata: Raw metadata dictionary from adapter
            source_system: Name of the source system for attribution
                          (e.g., "generic_rest_api:oauth2_client_credentials")
            correlation_id: Correlation ID used for lookup

        Returns:
            NormalizedMetadata instance (placeholder mode) or
            dict with MEC-compliant normalized metadata (full normalization mode)
        """
        # Use source normalizer if configured
        if self._source_normalizer is not None:
            return self._normalize_with_source_normalizer(
                raw_metadata, source_system, correlation_id
            )

        # Placeholder behavior for backward compatibility
        return self._normalize_placeholder(raw_metadata, source_system, correlation_id)

    def _normalize_with_source_normalizer(
        self,
        raw_metadata: dict[str, Any],
        source_system: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Normalize using the configured source normalizer.

        Args:
            raw_metadata: Raw metadata dictionary from adapter
            source_system: Name of the source system for attribution
            correlation_id: Correlation ID used for lookup

        Returns:
            Dictionary with MEC-compliant normalized metadata

        Raises:
            RuntimeError: If normalization fails with errors
        """
        result = self._source_normalizer.normalize(raw_metadata)

        if not result.success:
            # Collect error messages from validation
            error_messages = [
                f"{issue.field_path}: {issue.message}"
                for issue in result.validation.errors
            ]
            error_detail = (
                "; ".join(error_messages) if error_messages else "Unknown error"
            )
            raise RuntimeError(f"Metadata normalization failed: {error_detail}")

        # Add timestamp to source attribution
        normalized_metadata = result.normalized_metadata or {}
        if "source_attribution" in normalized_metadata:
            normalized_metadata["source_attribution"]["normalized_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            # Override with provided values
            normalized_metadata["source_attribution"]["correlation_id"] = correlation_id
            normalized_metadata["source_attribution"]["source_system"] = source_system

        return normalized_metadata

    def _normalize_placeholder(
        self,
        raw_metadata: dict[str, Any],
        source_system: str,
        correlation_id: str,
    ) -> NormalizedMetadata:
        """Placeholder normalization for backward compatibility.

        This implementation:
        1. Extracts title and description if present in raw metadata
        2. Stores ALL raw metadata in custom_fields
        3. Populates source_attribution with required fields

        Args:
            raw_metadata: Raw metadata dictionary from adapter
            source_system: Name of the source system for attribution
            correlation_id: Correlation ID used for lookup

        Returns:
            NormalizedMetadata instance with basic fields and source attribution
        """
        normalized = NormalizedMetadata()

        # Extract basic fields if present
        normalized.title = self._extract_field(raw_metadata, "title")
        normalized.description = self._extract_field(raw_metadata, "description")

        # Store ALL raw metadata in custom_fields (placeholder behavior)
        normalized.custom_fields = dict(raw_metadata)

        # Always populate source attribution
        normalized.source_attribution = SourceAttribution(
            source_system=source_system,
            fetch_timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
            source_record_id=self._extract_source_record_id(raw_metadata),
        )

        return normalized

    def _extract_field(
        self, raw_metadata: dict[str, Any], field_name: str
    ) -> str | None:
        """Extract a field value from raw metadata using field mappings.

        Args:
            raw_metadata: Raw metadata dictionary
            field_name: Normalized field name to extract

        Returns:
            Field value if found, None otherwise
        """
        source_fields = self.BASIC_FIELD_MAPPINGS.get(field_name, [])

        for source_field in source_fields:
            if source_field in raw_metadata:
                value = raw_metadata[source_field]
                # Only return string values for basic fields
                if isinstance(value, str):
                    return value
                # Convert non-string values to string if present
                if value is not None:
                    return str(value)

        return None

    def _extract_source_record_id(self, raw_metadata: dict[str, Any]) -> str | None:
        """Extract the source record ID from raw metadata.

        Looks for common ID field names in the raw metadata.

        Args:
            raw_metadata: Raw metadata dictionary

        Returns:
            Source record ID if found, None otherwise
        """
        id_fields = ["id", "assetId", "recordId", "ID", "AssetId", "RecordId"]

        for id_field in id_fields:
            if id_field in raw_metadata:
                value = raw_metadata[id_field]
                if value is not None:
                    return str(value)

        return None
