"""MovieLabs MEC-compliant metadata normalizers.

This package provides pluggable normalizers for transforming source-specific
metadata into MovieLabs Media Entertainment Core (MEC) compliant format.

The normalizer architecture is configuration-driven - all customer-specific
field names and namespace prefixes are defined in configuration, NOT in code.

Usage:
    from normalizers import create_normalizer

    # Create normalizer with customer-specific configuration
    config = {
        "source_namespace_prefix": "CUSTOMER",
        "identifier_mappings": {...},
        ...
    }
    normalizer = create_normalizer("generic_xml", config)
    result = normalizer.normalize(raw_metadata)

S3-based configuration:
    from normalizers import resolve_normalizer_config

    # Load config from S3 with optional inline overrides
    node_config = {
        "source_type": "generic_xml",
        "config_s3_path": "normalizer-configs/customer-config.json",
        "config": {"include_raw_source": True}  # Optional overrides
    }
    resolved_config = resolve_normalizer_config(node_config)
    normalizer = create_normalizer(node_config["source_type"], resolved_config)
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.base import (
        NormalizationResult,
        SourceNormalizer,
        ValidationIssue,
        ValidationResult,
        ValidationSeverity,
    )
    from nodes.external_metadata_fetch.normalizers.config_loader import (
        clear_config_cache,
        load_config_from_s3,
        resolve_normalizer_config,
    )
    from nodes.external_metadata_fetch.normalizers.generic_xml import (
        GenericXmlNormalizer,
    )
    from nodes.external_metadata_fetch.normalizers.validation import (
        validate_input_metadata,
        validate_output_metadata,
    )
except ImportError:
    from normalizers.base import (
        NormalizationResult,
        SourceNormalizer,
        ValidationIssue,
        ValidationResult,
        ValidationSeverity,
    )
    from normalizers.config_loader import (
        clear_config_cache,
        load_config_from_s3,
        resolve_normalizer_config,
    )
    from normalizers.generic_xml import GenericXmlNormalizer
    from normalizers.validation import (
        validate_input_metadata,
        validate_output_metadata,
    )

# Registry of available normalizers
# Maps source_type string to normalizer class
NORMALIZER_REGISTRY: dict[str, type[SourceNormalizer]] = {
    "generic_xml": GenericXmlNormalizer,
}


def create_normalizer(
    source_type: str, config: dict[str, Any] | None = None
) -> SourceNormalizer:
    """Factory function to create the appropriate normalizer.

    Args:
        source_type: The normalizer type identifier (e.g., "generic_xml")
        config: Configuration dict containing customer-specific field mappings.
                All field names and namespace prefixes come from this config.

    Returns:
        SourceNormalizer instance configured for the specified source type

    Raises:
        ValueError: If source_type is not registered in NORMALIZER_REGISTRY
    """
    normalizer_class = NORMALIZER_REGISTRY.get(source_type)

    if not normalizer_class:
        available = ", ".join(sorted(NORMALIZER_REGISTRY.keys())) or "(none registered)"
        raise ValueError(
            f"Unknown source type: '{source_type}'. "
            f"Available normalizers: {available}"
        )

    return normalizer_class(config)


def register_normalizer(source_type: str, normalizer_class: type) -> None:
    """Register a new normalizer type.

    This allows extending the normalizer system with new source formats
    without modifying the core factory code.

    Args:
        source_type: Unique identifier for this normalizer type
        normalizer_class: Class implementing SourceNormalizer interface

    Raises:
        TypeError: If normalizer_class doesn't inherit from SourceNormalizer
    """
    if not issubclass(normalizer_class, SourceNormalizer):
        raise TypeError(
            f"Normalizer class must inherit from SourceNormalizer, "
            f"got {normalizer_class.__name__}"
        )
    NORMALIZER_REGISTRY[source_type] = normalizer_class


__all__ = [
    "create_normalizer",
    "register_normalizer",
    "SourceNormalizer",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "NormalizationResult",
    "NORMALIZER_REGISTRY",
    "GenericXmlNormalizer",
    "validate_input_metadata",
    "validate_output_metadata",
    "load_config_from_s3",
    "resolve_normalizer_config",
    "clear_config_cache",
]
