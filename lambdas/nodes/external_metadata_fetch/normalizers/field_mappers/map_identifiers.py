"""Configuration-driven identifier field mapping for MEC AltIdentifier elements.

This module provides functions to map source system identifiers to MEC-compliant
AltIdentifier elements. All field names and namespace prefixes are configuration-driven -
NO hardcoded customer-specific values.

The identifier_mappings configuration defines which source fields map to which
namespace prefixes. Namespaces can be:
- Relative: Suffix appended to source_namespace_prefix (e.g., "-REF" → "CUSTOMER-REF")
- Absolute: Used as-is (e.g., "TMS" for Gracenote IDs)
- Empty: Uses source_namespace_prefix directly

Example configuration:
    {
        "source_namespace_prefix": "CUSTOMER",
        "identifier_mappings": {
            "primary_id": "",           # Uses "CUSTOMER" directly
            "ref_id": "-REF",           # Uses "CUSTOMER-REF"
            "version_id": "-VERSION",   # Uses "CUSTOMER-VERSION"
            "tms_series_id": "TMS",     # Uses "TMS" (absolute)
            "tms_episode_id": "TMS",    # Uses "TMS" (absolute)
        }
    }

Reference: MovieLabs MEC v2.25 - AltIdentifier element
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.mec_schema import AltIdentifier
except ImportError:
    from normalizers.mec_schema import AltIdentifier


def map_identifier(
    value: str | None,
    namespace: str,
) -> AltIdentifier | None:
    """Map a single identifier value to an AltIdentifier element.

    Args:
        value: The identifier value from the source system.
               Empty strings and None values are skipped.
        namespace: The fully-resolved namespace for this identifier.

    Returns:
        AltIdentifier if value is non-empty, None otherwise.

    Example:
        >>> map_identifier("RLA236635", "CUSTOMER")
        AltIdentifier(namespace="CUSTOMER", identifier="RLA236635")

        >>> map_identifier("", "CUSTOMER")
        None

        >>> map_identifier(None, "CUSTOMER")
        None
    """
    # Skip empty or None values
    if not value or not str(value).strip():
        return None

    # Preserve the original identifier format without modification
    return AltIdentifier(
        namespace=namespace,
        identifier=str(value).strip(),
    )


def resolve_namespace(
    namespace_suffix: str,
    source_namespace_prefix: str,
) -> str:
    """Resolve the full namespace from a suffix and prefix.

    Namespace resolution rules:
    - If suffix starts with "-": Append to prefix (relative namespace)
    - If suffix is empty "": Use prefix directly
    - Otherwise: Use suffix as-is (absolute namespace)

    Args:
        namespace_suffix: The namespace suffix from identifier_mappings config.
        source_namespace_prefix: The customer's namespace prefix from config.

    Returns:
        The fully-resolved namespace string.

    Examples:
        >>> resolve_namespace("-REF", "CUSTOMER")
        "CUSTOMER-REF"

        >>> resolve_namespace("", "CUSTOMER")
        "CUSTOMER"

        >>> resolve_namespace("TMS", "CUSTOMER")
        "TMS"
    """
    if namespace_suffix.startswith("-"):
        # Relative namespace: append suffix to prefix
        return f"{source_namespace_prefix}{namespace_suffix}"
    elif namespace_suffix == "":
        # Empty suffix: use prefix directly
        return source_namespace_prefix
    else:
        # Absolute namespace: use suffix as-is
        return namespace_suffix


def map_all_identifiers(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[AltIdentifier]:
    """Map all identifier fields from source metadata using configuration.

    This function iterates through the identifier_mappings configuration and
    extracts matching fields from the raw metadata, converting them to
    MEC-compliant AltIdentifier elements.

    NO hardcoded field names - all field names come from config["identifier_mappings"].

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - source_namespace_prefix: Customer namespace prefix (e.g., "CUSTOMER")
            - identifier_mappings: Dict mapping field names to namespace suffixes

    Returns:
        List of AltIdentifier elements for all non-empty identifier fields.

    Example config:
        {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "primary_id": "",           # → namespace="CUSTOMER"
                "ref_id": "-REF",           # → namespace="CUSTOMER-REF"
                "version_id": "-VERSION",   # → namespace="CUSTOMER-VERSION"
                "sequence_id": "-SEQ",      # → namespace="CUSTOMER-SEQ"
                "tms_series_id": "TMS",     # → namespace="TMS" (absolute)
                "tms_episode_id": "TMS",    # → namespace="TMS" (absolute)
                "tms_movie_id": "TMS",      # → namespace="TMS" (absolute)
                "ad_content_id": "-AD",     # → namespace="CUSTOMER-AD"
            }
        }

    Example usage:
        >>> raw = {"primary_id": "RLA236635", "ref_id": "L01039285", "tms_episode_id": "EP043931170004"}
        >>> config = {
        ...     "source_namespace_prefix": "CUSTOMER",
        ...     "identifier_mappings": {
        ...         "primary_id": "",
        ...         "ref_id": "-REF",
        ...         "tms_episode_id": "TMS",
        ...     }
        ... }
        >>> identifiers = map_all_identifiers(raw, config)
        >>> len(identifiers)
        3
    """
    identifiers: list[AltIdentifier] = []

    # Get configuration values with defaults
    source_prefix = config.get("source_namespace_prefix", "SOURCE")
    identifier_mappings = config.get("identifier_mappings", {})

    # Process each configured identifier mapping
    for field_name, namespace_suffix in identifier_mappings.items():
        # Get the value from raw metadata
        value = raw_metadata.get(field_name)

        # Skip if no value
        if value is None:
            continue

        # Handle non-string values (convert to string)
        if not isinstance(value, str):
            value = str(value)

        # Skip empty values
        if not value.strip():
            continue

        # Resolve the full namespace
        namespace = resolve_namespace(namespace_suffix, source_prefix)

        # Create the AltIdentifier
        alt_id = map_identifier(value, namespace)
        if alt_id is not None:
            identifiers.append(alt_id)

    return identifiers
