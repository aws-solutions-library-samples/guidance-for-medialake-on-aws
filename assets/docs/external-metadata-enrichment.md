# External Metadata Enrichment

MediaLake's External Metadata Enrichment feature enables automatic retrieval and normalization of metadata from external source systems (MAM/DAM) into your asset records.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [User Journeys](#user-journeys)
- [Documentation Map](#documentation-map)
- [Feature Capabilities](#feature-capabilities)
- [Enrichment Status](#enrichment-status)
- [Troubleshooting](#troubleshooting)
- [Related Specifications](#related-specifications)
- [External References](#external-references)

## Overview

External Metadata Enrichment consists of two integrated capabilities:

1. **Metadata Fetch** - Retrieves metadata from external APIs using configurable authentication and adapters
2. **Metadata Normalization** - Transforms source-specific formats into MovieLabs MEC v2.25 compliant structure

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    External Metadata Enrichment                              │
│                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────────────────┐│
│  │     Metadata Fetch      │         │      Metadata Normalization         ││
│  │                         │         │                                     ││
│  │  • Authentication       │────────▶│  • Field Mapping                    ││
│  │  • API Communication    │         │  • MEC Compliance                   ││
│  │  • Response Parsing     │         │  • Custom Fields                    ││
│  └─────────────────────────┘         └─────────────────────────────────────┘│
│                                                                              │
│  Triggers: Automatic (workflow completion) or Manual (API)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Set Up Credentials

Create an AWS Secrets Manager secret with your external system credentials:

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

> **Important:** Secret name must start with `medialake/`

### 2. Deploy the Pipeline

Use the "External Metadata Enrichment" template from the pipeline library:

1. Navigate to **Pipelines** in MediaLake
2. Click **Create Pipeline**
3. Select **External Metadata Enrichment** template
4. Configure the `external_metadata_fetch` node with your endpoints

### 3. Configure Normalization (Optional)

For custom field mappings, create a normalizer configuration:

```json
{
  "normalizer": {
    "source_type": "generic_xml",
    "config": {
      "source_namespace_prefix": "CUSTOMER",
      "identifier_mappings": { "content_id": "", "ref_id": "-REF" }
    }
  }
}
```

## User Journeys

### "I want to set up external metadata enrichment"

**Goal:** Connect MediaLake to an external metadata system and automatically enrich assets.

**Steps:**

1. Review [Pipeline Template Setup](../../pipeline_library/Enrichment/README.md) for prerequisites
2. Create credentials in AWS Secrets Manager
3. Deploy the External Metadata Enrichment pipeline
4. Configure authentication and API endpoints
5. Test with a sample asset

**Key Documentation:**

- [Pipeline Template README](../../pipeline_library/Enrichment/README.md) - Setup instructions and configuration
- [Node README](../../lambdas/nodes/external_metadata_fetch/README.md) - Authentication types and adapter options

### "I want to customize how metadata is normalized"

**Goal:** Configure field mappings for your specific source system format.

**Steps:**

1. Analyze your source metadata structure
2. Create a normalizer configuration mapping your fields to MEC elements
3. Upload configuration to S3 or embed inline
4. Test normalization with sample data

**Key Documentation:**

- [Configuration Reference](./external-metadata-normalization/configuration.md) - All configuration options
- [Field Mappings](./external-metadata-normalization/field-mappings.md) - Source to MEC field mappings
- [Config Templates](./external-metadata-normalization/config-templates/) - Sample configurations

### "I want to add a new source system"

**Goal:** Implement support for a new metadata source format.

**Steps:**

1. Understand the normalizer architecture
2. Implement the `SourceNormalizer` interface
3. Reuse existing field mappers where possible
4. Register the new normalizer
5. Write tests for the new source

**Key Documentation:**

- [Architecture Guide](./external-metadata-normalization/architecture.md) - System design and extension guide
- [Adding New Normalizers](./external-metadata-normalization/architecture.md#adding-a-new-normalizer) - Step-by-step guide
- [Testing Requirements](./external-metadata-normalization/architecture.md#testing-requirements-for-new-normalizers) - Test coverage requirements

## Documentation Map

| Document                   | Location                                                        | Purpose                                        |
| -------------------------- | --------------------------------------------------------------- | ---------------------------------------------- |
| **This Hub**               | `assets/docs/external-metadata-enrichment.md`                   | Starting point and navigation                  |
| **Pipeline Template**      | `pipeline_library/Enrichment/README.md`                         | Pipeline setup, triggers, troubleshooting      |
| **Node Implementation**    | `lambdas/nodes/external_metadata_fetch/README.md`               | Auth strategies, adapters, extension points    |
| **Normalization Overview** | `assets/docs/external-metadata-normalization/README.md`         | Normalizer quick start                         |
| **Architecture**           | `assets/docs/external-metadata-normalization/architecture.md`   | System design, adding normalizers, limitations |
| **Configuration**          | `assets/docs/external-metadata-normalization/configuration.md`  | Complete configuration schema                  |
| **Field Mappings**         | `assets/docs/external-metadata-normalization/field-mappings.md` | Source to MEC field reference                  |
| **Config Templates**       | `assets/docs/external-metadata-normalization/config-templates/` | Sample configurations                          |

### Documentation Relationships

```text
                    ┌─────────────────────────────────────┐
                    │  External Metadata Enrichment Hub   │
                    │  (assets/docs/external-metadata-    │
                    │   enrichment.md) - THIS FILE        │
                    └─────────────────┬───────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  Pipeline Template  │   │  Node Implementation │   │    Normalization    │
│  README             │   │  README              │   │    Documentation    │
│  (pipeline_library/ │   │  (lambdas/nodes/     │   │    (assets/docs/    │
│   Enrichment/)      │   │   external_metadata_ │   │     external-       │
│                     │   │   fetch/)            │   │     metadata-       │
│  • Setup steps      │   │  • Auth strategies   │   │     normalization/) │
│  • Trigger config   │   │  • Adapter config    │   │                     │
│  • End states       │   │  • Extension guide   │   │  • Architecture     │
│  • Troubleshooting  │   │  • Error handling    │   │  • Configuration    │
└─────────────────────┘   └─────────────────────┘   │  • Field mappings   │
                                                     │  • Config templates │
                                                     └─────────────────────┘
```

## Feature Capabilities

### Authentication Support

| Auth Type                 | Use Case                               |
| ------------------------- | -------------------------------------- |
| OAuth2 Client Credentials | Server-to-server with client ID/secret |
| API Key                   | Simple key-based authentication        |
| Basic Auth                | Username/password authentication       |

### Response Formats

| Format | Auto-Detection | Notes                                 |
| ------ | -------------- | ------------------------------------- |
| JSON   | Yes            | Native dictionary conversion          |
| XML    | Yes            | Converted to dictionary via xmltodict |

### Normalization Features

| Feature              | Description                           |
| -------------------- | ------------------------------------- |
| MEC v2.25 Compliance | Output follows MovieLabs schema       |
| Configuration-Driven | All field names from config, not code |
| Custom Fields        | Unmapped data preserved               |
| Validation           | Input and output validation           |
| Performance          | < 100ms per asset                     |

## Enrichment Status

After enrichment, assets have an `ExternalMetadataStatus` field:

| Status    | Description            |
| --------- | ---------------------- |
| `pending` | Enrichment in progress |
| `success` | Completed successfully |
| `failed`  | Failed after retries   |

## Troubleshooting

### Common Issues

| Issue                   | Cause                                       | Solution                              |
| ----------------------- | ------------------------------------------- | ------------------------------------- |
| "Secret not found"      | Secret name doesn't start with `medialake/` | Rename secret                         |
| "Authentication failed" | Invalid credentials or endpoint             | Verify credentials in Secrets Manager |
| "Asset not found"       | Correlation ID mismatch                     | Use `correlation_id` override         |
| "Empty metadata"        | Wrong `response_metadata_path`              | Check API response structure          |

### Getting Help

1. Check CloudWatch logs for the `External_Metadata_Fetch_Node` Lambda
2. Review the Step Functions execution for detailed error messages
3. Verify configuration against the [Configuration Reference](./external-metadata-normalization/configuration.md)

## Related Specifications

For developers working on the feature:

- [External Metadata Enrichment Spec](../../.kiro/specs/external-metadata-enrichment/) - Original feature specification (requirements, design, tasks)
- [MovieLabs Normalization Spec](../../.kiro/specs/movielabs-metadata-normalization/) - Normalization implementation spec

### Feature Relationship

The External Metadata Enrichment feature is implemented in two phases:

1. **Phase 1: Metadata Fetch** (external-metadata-enrichment spec)

   - Pipeline node for fetching metadata from external APIs
   - Pluggable authentication strategies (OAuth2, API Key, Basic Auth)
   - Pluggable metadata adapters (Generic REST)
   - Placeholder normalization (stores raw metadata)

2. **Phase 2: Full Normalization** (movielabs-metadata-normalization spec)
   - MovieLabs MEC v2.25 compliant output
   - Configuration-driven field mappings
   - Pluggable normalizer architecture
   - Comprehensive field mappers for all MEC elements

## External References

- [MovieLabs MEC v2.25 Specification](https://movielabs.com/md/)
- [MovieLabs MDDF Documentation](https://movielabs.com/md/md/)
