# Unified Search with Coactive Integration - Implementation Guide

## Overview

This document provides a comprehensive guide for implementing and configuring the unified search interface with Coactive integration in MediaLake. The implementation supports two primary search architecture patterns:

1. **Provider + MediaLake-managed embedding store** (TwelveLabs + OpenSearch/S3Vector)
2. **External semantic search services** (Coactive)

## Architecture Components

### Core Components

1. **Unified Search Models** (`unified_search_models.py`)
   - Common data structures and enums
   - Query parsing and validation
   - Filter handling

2. **Base Search Provider Interface** (`unified_search_provider.py`)
   - Abstract base classes for all providers
   - Provider factory and configuration management
   - Query validation and capability checking

3. **Coactive Search Provider** (`coactive_search_provider.py`)
   - External semantic service implementation
   - API integration with Coactive
   - Result enrichment with MediaLake metadata

4. **Unified Search Orchestrator** (`unified_search_orchestrator.py`)
   - Main routing logic
   - Provider selection based on query type
   - Fallback to legacy systems

5. **Configuration Manager** (`search_provider_config_manager.py`)
   - DynamoDB-based configuration storage
   - Secrets Manager integration
   - Configuration validation

6. **Pipeline Integration** (`coactive_ingestion_node.py`)
   - Asset ingestion into Coactive
   - Proxy URL generation
   - Callback handling

## Configuration

### Search Provider Configuration Format

#### Coactive Configuration

```json
{
  "provider": "coactive",
  "provider_location": "external",
  "architecture": "external_semantic_service",
  "capabilities": {
    "media": ["video", "audio", "image"],
    "semantic": true
  },
  "dataset_id": "your-coactive-dataset-id",
  "endpoint": "https://api.coactive.ai/v1/search",
  "auth": {
    "type": "bearer",
    "secret_arn": "arn:aws:secretsmanager:region:account:secret:coactive-api-key"
  },
  "metadata_mapping": {
    "asset_id": "medialake_uuid",
    "mediaType": "media_type",
    "duration": "duration_ms"
  }
}
```

#### TwelveLabs Configuration

```json
{
  "provider": "twelvelabs",
  "provider_location": "external",
  "architecture": "provider_plus_store",
  "capabilities": {
    "media": ["video", "audio", "image"],
    "semantic": true
  },
  "endpoint": "https://api.twelvelabs.io/v1",
  "store": "opensearch",
  "auth": {
    "type": "api_key",
    "secret_arn": "arn:aws:secretsmanager:region:account:secret:twelvelabs-api-key"
  }
}
```

### DynamoDB Configuration Storage

Store configurations in the system settings table:

```json
{
  "PK": "SYSTEM_SETTINGS",
  "SK": "SEARCH_PROVIDERS",
  "providers": [
    {
      // Provider configurations as shown above
    }
  ],
  "lastUpdated": "2025-08-11T20:00:00Z"
}
```

### AWS Secrets Manager

Store API keys securely:

```json
{
  "api_key": "your-api-key-here",
  "token": "your-api-key-here"
}
```

## API Usage

### Search Endpoint

The unified search API maintains backward compatibility while supporting new features:

```http
GET /search?q=<query>&page=<int>&pageSize=<int>&semantic=<bool>&filters=<json>&fields=<csv>
```

#### Parameters

- `q`: Search query text (required)
- `page`: Page number (default: 1)
- `pageSize`: Results per page (default: 50, max: 200)
- `semantic`: Enable semantic search (default: false)
- `filters`: JSON-encoded filters object
- `fields`: Comma-separated list of fields to return

#### Filter Examples

**Media Type Filter:**

```json
{ "mediaType": ["video", "image"] }
```

**Range Filter:**

```json
{ "duration": { "gte": 60, "lte": 3600 } }
```

**Combined Filters:**

```json
{
  "mediaType": ["video"],
  "duration": { "lte": 600 },
  "createdAt": { "gte": "2024-01-01" }
}
```

#### Response Format

```json
{
  "status": "200",
  "message": "ok",
  "data": {
    "searchMetadata": {
      "totalResults": 150,
      "page": 1,
      "pageSize": 50,
      "searchTerm": "goal scored",
      "provider": "coactive",
      "architecture": "external_semantic_service",
      "providerLocation": "external",
      "tookMs": 245
    },
    "results": [
      {
        "score": 0.95,
        "InventoryID": "asset-uuid-123",
        "mediaType": "video",
        "DigitalSourceAsset": {
          // MediaLake asset data
        },
        "coactive_metadata": {
          // Coactive-specific metadata
        },
        "clips": [
          // Video clips if applicable
        ]
      }
    ]
  }
}
```

### Provider Status Endpoint

Check the status of configured providers:

```http
GET /search/providers/status
```

Response:

```json
{
  "status": "200",
  "message": "ok",
  "data": {
    "providers": {
      "coactive": {
        "available": true,
        "architecture": "external_semantic_service",
        "location": "external",
        "supportedMediaTypes": ["video", "audio", "image"],
        "supportsSemanticSearch": true
      }
    },
    "defaultProvider": "coactive",
    "totalProviders": 1
  }
}
```

## Pipeline Integration

### Coactive Asset Ingestion

Add the Coactive ingestion node to your pipeline:

```python
from pipeline_library.coactive_ingestion_node import CoactiveIngestionNode

# Initialize the node
coactive_node = CoactiveIngestionNode(logger, metrics)

# Process single asset
result = coactive_node.process_asset(asset_data)

# Process batch of assets
batch_result = coactive_node.process_batch(assets_list)
```

### Pipeline Configuration

Configure the ingestion node in your pipeline definition:

```json
{
  "nodes": [
    {
      "id": "coactive_ingestion",
      "type": "CoactiveIngestionNode",
      "config": {
        "enabled": true,
        "batch_size": 10,
        "retry_attempts": 3
      }
    }
  ]
}
```

## Deployment Steps

### 1. Update Lambda Dependencies

Add required dependencies to `requirements.txt`:

```txt
requests>=2.31.0
```

### 2. Configure Environment Variables

Ensure these environment variables are set:

```bash
SYSTEM_SETTINGS_TABLE=your-system-settings-table
OPENSEARCH_ENDPOINT=your-opensearch-endpoint
OPENSEARCH_INDEX=your-search-index
AWS_REGION=your-aws-region
SCOPE=es
```

### 3. Set Up Provider Configuration

Use the configuration manager to set up providers:

```python
from search_provider_config_manager import SearchProviderConfigManager

config_manager = SearchProviderConfigManager(logger)

# Create Coactive configuration
coactive_config = config_manager.create_coactive_config(
    dataset_id="your-dataset-id",
    api_key="your-api-key",
    endpoint="https://api.coactive.ai/v1/search"
)

# Save configuration
config_manager.save_provider_config(coactive_config)
```

### 4. Deploy Lambda Function

Deploy the updated search Lambda with the new unified search components.

### 5. Test Integration

Test the integration with sample queries:

```bash
# Keyword search
curl "https://your-api-gateway/search?q=test&semantic=false"

# Semantic search
curl "https://your-api-gateway/search?q=person+running&semantic=true"

# Filtered search
curl "https://your-api-gateway/search?q=sports&semantic=true&filters={\"mediaType\":[\"video\"]}"
```

## Monitoring and Troubleshooting

### CloudWatch Metrics

Monitor these key metrics:

- Search request count by provider
- Search latency by provider
- Error rates
- Provider availability

### Logging

Key log messages to monitor:

```
INFO: Selected external semantic provider: coactive
INFO: Coactive search completed in 245ms, returned 25 hits
ERROR: Coactive search failed: API error: 429
WARNING: No suitable provider found for query
```

### Common Issues

1. **Provider Not Available**
   - Check configuration in DynamoDB
   - Verify API keys in Secrets Manager
   - Ensure required environment variables are set

2. **Search Timeouts**
   - Check network connectivity to external providers
   - Monitor provider API status
   - Consider increasing timeout values

3. **Empty Results**
   - Verify asset ingestion into provider
   - Check metadata mapping configuration
   - Review filter logic

## Migration Guide

### From Legacy Search

The unified search system maintains backward compatibility:

1. Existing search queries continue to work
2. Legacy parameters are automatically mapped
3. Fallback to existing embedding stores when providers unavailable

### Gradual Migration

1. Deploy unified search system alongside existing system
2. Configure providers gradually
3. Monitor performance and results
4. Gradually increase traffic to unified system
5. Deprecate legacy endpoints when ready

## Security Considerations

### API Key Management

- Store all API keys in AWS Secrets Manager
- Use IAM roles for Lambda access to secrets
- Rotate keys regularly
- Monitor key usage

### Network Security

- Use VPC endpoints for internal communication
- Implement rate limiting
- Monitor for unusual traffic patterns
- Use HTTPS for all external API calls

### Data Privacy

- Ensure proxy URLs have appropriate expiration
- Review metadata sent to external providers
- Implement data retention policies
- Consider data residency requirements

## Performance Optimization

### Caching

- Cache provider configurations
- Cache frequently accessed metadata
- Implement result caching for common queries

### Batch Processing

- Use batch ingestion for initial data loads
- Implement parallel processing for large datasets
- Monitor and tune batch sizes

### Connection Pooling

- Reuse HTTP connections to external providers
- Configure appropriate timeout values
- Monitor connection pool metrics

## Future Enhancements

### Planned Features

1. **Cursor-based Pagination**
   - Replace offset-based pagination
   - Improve performance for large result sets

2. **Advanced Filtering**
   - Support for complex filter expressions
   - Faceted search capabilities
   - Custom filter operators

3. **Multi-provider Queries**
   - Query multiple providers simultaneously
   - Merge and rank results
   - Provider-specific result weighting

4. **Real-time Updates**
   - Webhook support for provider updates
   - Real-time asset status synchronization
   - Event-driven reindexing

### Extension Points

The architecture supports easy extension:

- Add new search providers by implementing `BaseSearchProvider`
- Extend filter types in `unified_search_models.py`
- Add custom metadata enrichment in providers
- Implement custom routing logic in orchestrator

## Support and Maintenance

### Regular Tasks

1. Monitor provider API changes
2. Update API client libraries
3. Review and optimize configurations
4. Analyze search performance metrics
5. Update documentation

### Troubleshooting Resources

- Provider API documentation
- CloudWatch logs and metrics
- AWS X-Ray traces
- Provider status pages
- Community forums and support channels
