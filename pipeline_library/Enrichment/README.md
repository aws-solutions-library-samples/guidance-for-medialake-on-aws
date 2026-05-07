# Enrichment Pipeline Templates

> **Documentation Hub:** For a complete overview of External Metadata Enrichment, including normalization and configuration guides, see the [External Metadata Enrichment Hub](../../assets/docs/external-metadata-enrichment.md).

This folder contains pipeline templates for enriching MediaLake assets with additional metadata from external sources.

## External Metadata Enrichment

**Template:** `External Metadata Enrichment.json`

Fetches metadata from external source systems (MAM/DAM) and stores it alongside asset records in MediaLake.

### Features

- **Dual Trigger Support**: Works with both automatic (workflow completion) and manual (API) triggers
- **Pluggable Authentication**: Supports OAuth2, API Key, and Basic Auth
- **Multiple Response Formats**: Handles JSON and XML responses automatically
- **Differentiated End States**: Routes to Success, NoMatch, AuthError, or Error based on outcome

### Prerequisites

Before deploying this pipeline, you must:

1. **Create an AWS Secrets Manager secret** with your external system credentials
2. **Configure the pipeline parameters** with your API endpoints

> **IMPORTANT:** The secret name must start with `medialake/` (e.g., `medialake/external-mam-credentials`)

### Setup Instructions

#### Step 1: Create Credentials Secret

Navigate to AWS Secrets Manager and create a secret with the appropriate structure for your auth type:

**OAuth2 Client Credentials:**

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

**API Key:**

```json
{
  "api_key": "your-api-key"
}
```

**Basic Auth:**

```json
{
  "username": "your-username",
  "password": "your-password"
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

#### Step 2: Configure Pipeline Parameters

After importing the template, update these parameters in the `external_metadata_fetch` node:

| Parameter              | Description                                                    | Example                                                                                |
| ---------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `secret_arn`           | Full ARN of your Secrets Manager secret                        | `arn:aws:secretsmanager:us-east-1:123456789:secret:medialake/external-mam-credentials` |
| `auth_endpoint`        | OAuth2 token endpoint URL (leave empty for API Key/Basic Auth) | `https://auth.example.com/oauth/token`                                                 |
| `metadata_endpoint`    | External system's metadata API URL                             | `https://api.example.com/v1/assets`                                                    |
| `auth_type`            | Authentication method                                          | `oauth2_client_credentials`, `api_key`, or `basic_auth`                                |
| `correlation_id_param` | Query parameter name for the asset ID                          | `assetId`, `externalId`, etc.                                                          |

#### Step 3: Configure Automatic Trigger (Optional)

If you want assets to be automatically enriched after processing:

1. Edit the "Workflow Completed" trigger node
2. Set `pipeline_name` to the pipeline that should trigger enrichment (e.g., "Default Video Pipeline")

### Pipeline Flow

```
┌─────────────────────┐     ┌─────────────────────┐
│ Workflow Completed  │────▶│                     │
│ (automatic trigger) │     │  External Metadata  │
└─────────────────────┘     │       Fetch         │
                            │                     │
┌─────────────────────┐     │                     │     ┌─────────────────┐
│   Manual Trigger    │────▶│                     │────▶│  Choice Node    │
│   (API trigger)     │     └─────────────────────┘     │                 │
└─────────────────────┘                                 └────────┬────────┘
                                                                 │
                    ┌────────────────────────────────────────────┼────────────────────────────────────────────┐
                    │                        │                   │                        │                   │
                    ▼                        ▼                   ▼                        ▼                   │
            ┌───────────┐            ┌───────────┐       ┌───────────┐            ┌───────────┐              │
            │  Success  │            │  NoMatch  │       │ AuthError │            │   Error   │              │
            │           │            │  (Fail)   │       │  (Fail)   │            │  (Fail)   │              │
            └───────────┘            └───────────┘       └───────────┘            └───────────┘              │
```

### End States

| State         | Description                   | Common Causes                                                           |
| ------------- | ----------------------------- | ----------------------------------------------------------------------- |
| **Success**   | Metadata retrieved and stored | Normal operation                                                        |
| **NoMatch**   | Correlation ID not found      | Asset filename doesn't match external ID; use `correlation_id` override |
| **AuthError** | Authentication failed         | Invalid credentials, wrong endpoint, or network issues                  |
| **Error**     | Unexpected error              | External API returned 500, timeout, or unhandled exception              |

### Manual Triggering via API

To manually trigger enrichment for specific assets:

```bash
POST /pipelines/{pipelineId}/trigger
Content-Type: application/json

{
  "assets": [
    {
      "inventory_id": "asset-uuid-1",
      "params": {
        "correlation_id": "EXTERNAL_ID_123"
      }
    },
    {
      "inventory_id": "asset-uuid-2",
      "params": {}
    }
  ]
}
```

- Use `correlation_id` in params to override the filename-based ID extraction
- Maximum 50 assets per request

**Correlation ID Resolution:**

| Scenario                                   | Behavior                                                     |
| ------------------------------------------ | ------------------------------------------------------------ |
| `correlation_id` provided in params        | Always uses the provided override                            |
| No override, previous enrichment succeeded | Re-uses the stored `ExternalAssetId` from the successful run |
| No override, no previous success           | Extracts from asset filename (without extension)             |

This means if you manually correct an asset's correlation ID and it succeeds, future re-enrichment runs will automatically use that corrected ID without needing to specify it again.

### Monitoring Enrichment Status

After triggering enrichment, you can monitor progress by:

1. **Checking asset status**: Query the asset's `ExternalMetadataStatus.status` field

   - `pending` - Enrichment in progress
   - `success` - Completed successfully
   - `failed` - Failed after retries

2. **Step Functions console**: Use the execution ARN returned by the trigger API

3. **CloudWatch Logs**: Check the `External_Metadata_Fetch_Node` Lambda logs

### Troubleshooting

**NoMatch errors for all assets**

- Verify your external system uses the asset filename (without extension) as the identifier
- Use the `correlation_id` override to specify the correct external ID

**AuthError on every execution**

- Verify the secret ARN is correct and starts with `medialake/`
- Check that credentials in Secrets Manager are valid
- For OAuth2, verify the auth endpoint URL and scope

**Intermittent failures**

- Check the external API's rate limits
- Increase `max_retries` if the API is occasionally slow
- Review CloudWatch logs for specific error messages

### Related Documentation

- [External Metadata Enrichment Hub](../../assets/docs/external-metadata-enrichment.md) - Complete feature overview and user journeys
- [External Metadata Fetch Node README](../../lambdas/nodes/external_metadata_fetch/README.md) - Detailed node configuration and extension guide
- [Normalization Documentation](../../assets/docs/external-metadata-normalization/) - Field mappings and configuration
- [Pipeline Trigger API](../../assets/docs/openapi.yaml) - API specification for manual triggering
