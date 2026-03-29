# Normalizer Configuration Templates

This directory contains sample configuration templates for the metadata normalizer. Use these as starting points when configuring normalization for a new source system.

## Template Files

| File                          | Purpose                        | Use Case                                          |
| ----------------------------- | ------------------------------ | ------------------------------------------------- |
| `inline-config-template.json` | Inline node configuration      | Small configs embedded in pipeline node settings  |
| `s3-config-template.json`     | S3-storable configuration      | Large configs stored in S3 and referenced by path |
| `minimal-config.json`         | Minimal required configuration | Quick start with defaults                         |

## Usage

### Inline Configuration

For small configurations, embed directly in the pipeline node configuration:

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config": {
      // Copy contents from inline-config-template.json
    }
  }
}
```

### S3-Based Configuration

For large configurations:

1. Copy `s3-config-template.json` to your S3 bucket
2. Customize the configuration for your source system
3. Reference in node configuration:

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config_s3_path": "normalizer-configs/your-config.json"
  }
}
```

### Hybrid Configuration

Combine S3 config with inline overrides:

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config_s3_path": "normalizer-configs/base-config.json",
    "config": {
      "include_raw_source": true
    }
  }
}
```

## Customization Guide

### Required Changes

Replace these placeholders with your actual values:

| Placeholder    | Description               | Example                       |
| -------------- | ------------------------- | ----------------------------- |
| `CUSTOMER`     | Your namespace prefix     | `"ACME"`, `"NBC"`, `"DISNEY"` |
| `content_id`   | Primary ID field name     | `"asset_id"`, `"media_id"`    |
| `reference_id` | Correlation ID field name | `"ref_id"`, `"external_ref"`  |

### Field Mapping Customization

1. **Identifier Mappings**: Map your source ID fields to namespaces
2. **Title Mappings**: Map your title/description field names
3. **People Mappings**: Map your cast/crew field names
4. **Rating Mappings**: Map your rating system names to regions

### Testing Your Configuration

1. Create a test pipeline with your configuration
2. Process a sample asset
3. Verify the normalized output in DynamoDB
4. Check for validation warnings in CloudWatch logs

## Related Documentation

- [Configuration Reference](../configuration.md) - Complete configuration schema
- [Field Mappings](../field-mappings.md) - Source to MEC field mappings
- [Architecture](../architecture.md) - System architecture and extension guide
