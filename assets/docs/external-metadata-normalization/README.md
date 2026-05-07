# External Metadata Retrieval and Normalization

> **Documentation Hub:** For a complete overview of External Metadata Enrichment, including setup guides and user journeys, see the [External Metadata Enrichment Hub](../external-metadata-enrichment.md).

MediaLake's External Metadata Fetch pipeline node retrieves metadata from external systems and normalizes it into MovieLabs MEC (Media Entertainment Core) v2.25 compliant format for consistent storage and querying.

## Table of Contents

- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Key Concepts](#key-concepts)
- [Pipeline Integration](#pipeline-integration)
- [External References](#external-references)
- [Related Documentation](#related-documentation)

## Quick Start

The normalizer transforms source-specific metadata (XML, JSON) into a standardized MEC-compliant structure. It's fully configuration-driven—all customer-specific field names and mappings are defined in configuration, not code.

```python
from normalizers import create_normalizer

# Create normalizer with customer configuration
config = {
    "source_namespace_prefix": "CUSTOMER",
    "identifier_mappings": {"content_id": "", "ref_id": "-REF"},
    "title_mappings": {"title_field": "episode_title"},
}
normalizer = create_normalizer("generic_xml", config)

# Normalize metadata
result = normalizer.normalize(raw_metadata)
if result.success:
    normalized = result.normalized_metadata  # MEC-compliant structure
```

## Documentation

| Document                              | Description                                                                   |
| ------------------------------------- | ----------------------------------------------------------------------------- |
| [Architecture](./architecture.md)     | System architecture, component overview, and guide for adding new normalizers |
| [Field Mappings](./field-mappings.md) | Complete reference for source → MEC field mappings                            |
| [Configuration](./configuration.md)   | Full configuration schema with all available options                          |

## Key Concepts

### Configuration-Driven Design

All customer-specific values are defined in configuration:

- **Namespace prefixes** for identifiers (e.g., "CUSTOMER", "TMS")
- **Field name mappings** for each metadata category
- **Rating system mappings** to regions
- **Custom field categories** for unmapped data

### MEC Compliance

Output follows MovieLabs MEC v2.25 schema:

- `BasicMetadata` - Core content information
- `LocalizedInfo` - Titles, descriptions, genres
- `People` - Cast and crew with proper MEC element names
- `Ratings` - Content ratings with region/system/value
- `AltIdentifiers` - External system identifiers
- `CustomFields` - Preserved unmapped source data

### Pluggable Architecture

New source formats can be added by:

1. Implementing the `SourceNormalizer` interface
2. Registering with the normalizer factory
3. Creating a configuration for the new source

## Pipeline Integration

Configure the External_Metadata_Fetch_Node with normalizer settings:

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config_s3_path": "normalizer-configs/customer-config.json",
    "config": {
      "include_raw_source": true
    }
  }
}
```

## External References

- [MovieLabs MEC v2.25 Specification](https://movielabs.com/md/)
- [MovieLabs MDDF Documentation](https://movielabs.com/md/md/)

## Related Documentation

- [External Metadata Enrichment Hub](../external-metadata-enrichment.md) - Complete feature overview and user journeys
- [Pipeline Template README](../../pipeline_library/Enrichment/README.md) - Pipeline setup and configuration
- [Node Implementation](../../lambdas/nodes/external_metadata_fetch/README.md) - Auth strategies and adapters
