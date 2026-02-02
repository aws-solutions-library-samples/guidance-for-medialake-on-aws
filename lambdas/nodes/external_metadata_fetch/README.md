# External Metadata Fetch Node

> **Documentation Hub:** For a complete overview of External Metadata Enrichment, including normalization and configuration guides, see the [External Metadata Enrichment Hub](../../../assets/docs/external-metadata-enrichment.md).

A pipeline node for fetching metadata from external source systems (MAM/DAM) and storing it alongside MediaLake asset records.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Authentication Types](#authentication-types)
- [Response Formats](#response-formats)
- [Extending the Node](#extending-the-node)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)

## Overview

This node enables MediaLake to enrich assets with metadata from external systems by:

1. Extracting a correlation ID from the asset filename (or using an override)
2. Authenticating with the external system
3. Fetching metadata via REST API
4. Normalizing and storing the metadata in the asset record

The node uses a pluggable architecture that separates authentication logic from API communication, allowing any authentication strategy to be combined with any metadata adapter.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    External_Metadata_Fetch_Node                              │
│                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────────────────┐│
│  │     AuthStrategy        │         │        MetadataAdapter              ││
│  │     (Pluggable)         │────────▶│        (Pluggable)                  ││
│  │                         │         │                                     ││
│  │  ┌─────────────────┐    │         │  ┌─────────────────────────────┐   ││
│  │  │ OAuth2Client    │    │         │  │ GenericRestAdapter          │   ││
│  │  │ Credentials     │    │         │  │  - JSON responses           │   ││
│  │  └─────────────────┘    │         │  │  - XML responses            │   ││
│  │  ┌─────────────────┐    │         │  │  - Configurable endpoints   │   ││
│  │  │ APIKey          │    │         │  └─────────────────────────────┘   ││
│  │  └─────────────────┘    │         │                                     ││
│  │  ┌─────────────────┐    │         │  ┌─────────────────────────────┐   ││
│  │  │ BasicAuth       │    │         │  │ [Your Custom Adapter]       │   ││
│  │  └─────────────────┘    │         │  └─────────────────────────────┘   ││
│  │  ┌─────────────────┐    │         │                                     ││
│  │  │ [Your Custom    │    │         └─────────────────────────────────────┘│
│  │  │  Strategy]      │    │                                                │
│  │  └─────────────────┘    │                                                │
│  └─────────────────────────┘                                                │
│                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────────────────┐│
│  │   SecretsRetriever      │         │      MetadataNormalizer             ││
│  │   (AWS Secrets Manager) │         │      (MovieLabs DDF Compatible)     ││
│  └─────────────────────────┘         └─────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns**: Authentication logic is completely separate from API communication
2. **Composition over Inheritance**: Adapters receive auth strategies via constructor injection
3. **Mix and Match**: Any auth strategy can be combined with any adapter
4. **Easy Extension**: Add new auth types or adapters without modifying existing code

## Quick Start

### 1. Create AWS Secrets Manager Secret

> **IMPORTANT:** The secret name **must** start with `medialake/` (e.g., `medialake/external-mam-credentials`).

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

> **TIP:** You can also store additional API headers (like Azure subscription keys) in the secret. See [Authentication Types](#authentication-types) for details on the `additional_headers` option.

### 2. Configure the Pipeline Node

```json
{
  "adapter_type": "generic_rest",
  "auth_type": "oauth2_client_credentials",
  "secret_arn": "arn:aws:secretsmanager:us-east-1:123456789:secret:medialake/external-mam-credentials",
  "auth_endpoint": "https://auth.example.com/oauth/token",
  "metadata_endpoint": "https://api.example.com/v1/assets"
}
```

### 3. Deploy the Pipeline

Use the "External Metadata Enrichment" template from the pipeline library, or create a custom pipeline with the `external_metadata_fetch` node.

## Configuration Reference

### Node Configuration Schema

```json
{
  "adapter_type": "generic_rest",
  "auth_type": "oauth2_client_credentials",
  "secret_arn": "arn:aws:secretsmanager:region:account:secret:name",
  "auth_endpoint": "https://auth.example.com/oauth/token",
  "metadata_endpoint": "https://api.example.com/metadata",
  "max_retries": 3,
  "initial_backoff_seconds": 1.0,
  "adapter_config": {
    "correlation_id_param": "assetId",
    "http_method": "GET",
    "timeout_seconds": 30,
    "response_format": "auto",
    "response_metadata_path": "ProgramMetadata",
    "additional_headers": {}
  },
  "auth_config": {
    "scope": "read:metadata",
    "timeout_seconds": 30
  }
}
```

### Configuration Options

| Option                    | Type   | Required | Default | Description                                         |
| ------------------------- | ------ | -------- | ------- | --------------------------------------------------- |
| `adapter_type`            | string | Yes      | -       | Adapter to use (e.g., `"generic_rest"`)             |
| `auth_type`               | string | Yes      | -       | Auth strategy (e.g., `"oauth2_client_credentials"`) |
| `secret_arn`              | string | Yes      | -       | AWS Secrets Manager ARN for credentials             |
| `auth_endpoint`           | string | Depends  | -       | Auth endpoint URL (required for OAuth2)             |
| `metadata_endpoint`       | string | Yes      | -       | Metadata API endpoint URL                           |
| `max_retries`             | int    | No       | `3`     | Maximum retry attempts for transient errors         |
| `initial_backoff_seconds` | float  | No       | `1.0`   | Initial backoff delay for retries                   |

### Adapter Configuration (`adapter_config`)

| Option                   | Type   | Default     | Description                                      |
| ------------------------ | ------ | ----------- | ------------------------------------------------ |
| `correlation_id_param`   | string | `"assetId"` | Query/body parameter name for the correlation ID |
| `http_method`            | string | `"GET"`     | HTTP method (`GET` or `POST`)                    |
| `timeout_seconds`        | int    | `30`        | Request timeout in seconds                       |
| `response_format`        | string | `"auto"`    | Response format: `"json"`, `"xml"`, or `"auto"`  |
| `response_metadata_path` | string | `null`      | Dot-notation path to extract metadata            |
| `additional_headers`     | object | `{}`        | Extra headers to include in requests             |

### Auth Configuration (`auth_config`)

#### OAuth2 Client Credentials

| Option            | Type   | Default | Description             |
| ----------------- | ------ | ------- | ----------------------- |
| `scope`           | string | -       | OAuth2 scope to request |
| `timeout_seconds` | int    | `30`    | Auth request timeout    |

#### API Key

| Option             | Type   | Default       | Description                                       |
| ------------------ | ------ | ------------- | ------------------------------------------------- |
| `header_name`      | string | `"X-API-Key"` | Header name for API key                           |
| `key_location`     | string | `"header"`    | Where to send key: `"header"` or `"query"`        |
| `query_param_name` | string | `"api_key"`   | Query param name (if `key_location` is `"query"`) |

## Authentication Types

### OAuth2 Client Credentials

Server-to-server authentication using client ID and secret.

**Secret Structure:**

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

**With Additional Headers (e.g., Azure subscription key):**

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "additional_headers": {
    "subscription-key": "your-azure-subscription-key"
  }
}
```

### API Key

Simple API key authentication via header or query parameter.

**Secret Structure:**

```json
{
  "api_key": "your-api-key"
}
```

### Basic Auth

HTTP Basic Authentication with username and password.

**Secret Structure:**

```json
{
  "username": "your-username",
  "password": "your-password"
}
```

## Response Formats

The `GenericRestAdapter` supports both JSON and XML responses:

| Format | Content-Type                  | Auto-Detection |
| ------ | ----------------------------- | -------------- |
| JSON   | `application/json`            | Yes            |
| XML    | `application/xml`, `text/xml` | Yes            |

### XML to Dictionary Conversion

XML responses are automatically converted to Python dictionaries using `xmltodict`:

- Element names become dictionary keys
- Attributes are prefixed with `@` (e.g., `@type`)
- Text content with attributes is stored under `#text`
- Repeated elements automatically become lists

### Using `response_metadata_path`

Extract nested metadata using dot-notation:

```json
{
  "adapter_config": {
    "response_metadata_path": "data.metadata"
  }
}
```

This extracts the value at `response["data"]["metadata"]`.

## Extending the Node

The node's pluggable architecture makes it easy to add support for new authentication methods or external API types.

### Adding a New Authentication Strategy

To add a new auth strategy (e.g., JWT, SAML, AWS IAM):

1. **Create a new class** in `auth/` that extends `AuthStrategy` from `auth/base.py`
2. **Implement the required methods**: `authenticate()`, `get_auth_header()`, and `get_strategy_name()`
3. **Register the strategy** by adding it to `AUTH_STRATEGIES` dict in `auth/__init__.py`

See `auth/oauth2_client_credentials.py` for a complete reference implementation.

### Adding a New Metadata Adapter

To add a new adapter (e.g., GraphQL, SOAP, vendor-specific API):

1. **Create a new class** in `adapters/` that extends `MetadataAdapter` from `adapters/base.py`
2. **Implement the required methods**: `fetch_metadata()` and `get_adapter_name()`
3. **Register the adapter** by adding it to `ADAPTERS` dict in `adapters/__init__.py`

The adapter receives an `AuthStrategy` via constructor injection, so authentication is handled separately from your API logic.

### Extension Points Summary

| Extension Point     | Location        | Interface            | Registration                            |
| ------------------- | --------------- | -------------------- | --------------------------------------- |
| Auth Strategy       | `auth/`         | `AuthStrategy`       | `AUTH_STRATEGIES` in `auth/__init__.py` |
| Metadata Adapter    | `adapters/`     | `MetadataAdapter`    | `ADAPTERS` in `adapters/__init__.py`    |
| Normalizer Mappings | `normalizer.py` | `MetadataNormalizer` | `DEFAULT_MAPPINGS` dict                 |

## Error Handling

The node handles various error scenarios:

| Error Type              | Behavior                                        |
| ----------------------- | ----------------------------------------------- |
| Authentication failure  | Marks enrichment as failed, logs error          |
| 404 Not Found           | Records "asset not found in external system"    |
| Network timeout         | Retries with exponential backoff (configurable) |
| Invalid response format | Marks enrichment as failed with parse error     |
| Missing correlation ID  | Fails with descriptive error message            |

### Enrichment Status Values

The node returns an `enrichment_status` field that determines the Step Function end state:

| Status       | Description                                                         |
| ------------ | ------------------------------------------------------------------- |
| `success`    | Metadata successfully retrieved and stored                          |
| `no_match`   | Correlation ID invalid, missing, or not found in external system    |
| `auth_error` | Authentication failed (credentials, OAuth token, or API key errors) |
| `error`      | Unexpected error (HTTP 500, unhandled exceptions)                   |

## Troubleshooting

### Common Issues

**"Secret not found" error**

- Ensure the secret name starts with `medialake/`
- Verify the secret ARN is correct and the Lambda has permission to access it

**"Authentication failed" error**

- Check credentials in Secrets Manager are correct
- Verify the auth endpoint URL is accessible
- For OAuth2, ensure the scope is correct

**"Asset not found in external system" error**

- Verify the correlation ID matches the external system's identifier
- Use the `correlation_id` override in the trigger API to specify a different ID

**Empty or malformed metadata**

- Check `response_metadata_path` is set correctly for nested responses
- Verify `response_format` matches the API's actual response type

## Dependencies

- `requests>=2.31.0` - HTTP client
- `boto3>=1.34.0` - AWS SDK
- `aws-lambda-powertools>=2.32.0` - Logging, tracing, metrics
- `xmltodict>=0.13.0` - XML to dictionary conversion

## Related Documentation

- [External Metadata Enrichment Hub](../../../assets/docs/external-metadata-enrichment.md) - Complete feature overview and user journeys
- [Pipeline Template README](../../../pipeline_library/Enrichment/README.md) - Pipeline setup and configuration
- [Normalization Documentation](../../../assets/docs/external-metadata-normalization/) - Field mappings and configuration
- [Configuration Reference](../../../assets/docs/external-metadata-normalization/configuration.md) - Normalizer configuration options
- [Architecture Guide](../../../assets/docs/external-metadata-normalization/architecture.md) - System design and extension guide
