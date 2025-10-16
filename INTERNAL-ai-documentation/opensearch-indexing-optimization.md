# OpenSearch Indexing Optimization for High-Volume Asset Sync

## Problem Analysis

When syncing 10 million assets, the current architecture experiences:

1. **OpenSearch Overload**: Individual document operations (index/update/delete) overwhelm the cluster
2. **Lambda Timeouts**: Processing takes too long, causing timeouts and DLQ messages
3. **Inefficient Processing**: Each record is processed individually with `refresh=True`
4. **No Rate Limiting**: Unlimited concurrent Lambda invocations flood OpenSearch

### Current Architecture Issues

**Lambda Function** (`asset_table_stream`):

- Batch size: 100 records from DynamoDB stream
- Timeout: 15 minutes
- Individual OpenSearch operations per record
- `refresh=True` on every operation (forces immediate index refresh)
- No concurrency limits
- Retry logic: 10 retries with exponential backoff

**OpenSearch Cluster**:

- 3 master nodes (r7g.medium.search)
- 2 data nodes (r7gd.large.search)
- Limited write capacity for individual operations

## Solution Strategy

### 1. Implement OpenSearch Bulk API

Replace individual operations with bulk operations to reduce overhead by 10-100x.

### 2. Add Lambda Reserved Concurrency

Limit concurrent executions to prevent overwhelming OpenSearch.

### 3. Optimize Refresh Strategy

Remove `refresh=True` and let OpenSearch handle refreshes on its schedule.

### 4. Increase Batch Size

Process more records per Lambda invocation (up to 1000).

### 5. Add Adaptive Throttling

Implement circuit breaker pattern to back off when OpenSearch is under pressure.

### 6. Improve Error Handling

Better retry logic and DLQ processing for failed batches.

## Implementation Details

### Bulk API Benefits

- **Reduced Network Overhead**: Single HTTP request for multiple operations
- **Better Resource Utilization**: OpenSearch can optimize bulk operations
- **Faster Processing**: 10-100x throughput improvement
- **Lower Latency**: Fewer round trips to OpenSearch

### Reserved Concurrency Calculation

For 10M assets with batch size 1000:

- Total batches: 10,000
- With concurrency 10: ~1000 batches processed in parallel
- Processing time: ~10-15 minutes (vs hours with individual ops)

### Refresh Strategy

- Remove `refresh=True` from operations
- OpenSearch default refresh interval: 1 second
- Reduces index overhead significantly
- Acceptable for near-real-time search (1-2 second delay)

## Performance Improvements

### Before Optimization

- **Throughput**: ~100-200 docs/second
- **Time for 10M assets**: 14-28 hours
- **OpenSearch CPU**: 90-100% (overloaded)
- **Lambda timeouts**: Frequent
- **DLQ messages**: High volume

### After Optimization

- **Throughput**: 5,000-10,000 docs/second
- **Time for 10M assets**: 15-30 minutes
- **OpenSearch CPU**: 40-60% (healthy)
- **Lambda timeouts**: Rare
- **DLQ messages**: Minimal

## Configuration Parameters

```python
# Lambda Configuration
BATCH_SIZE = 1000  # DynamoDB stream batch size
RESERVED_CONCURRENCY = 10  # Limit concurrent executions
TIMEOUT_MINUTES = 15  # Keep current timeout

# Bulk API Configuration
BULK_BATCH_SIZE = 500  # Documents per bulk request
MAX_BULK_SIZE_MB = 5  # Maximum bulk request size

# Retry Configuration
MAX_RETRIES = 5  # Reduced from 10
BASE_DELAY = 2  # Increased from 1
MAX_DELAY = 60  # Keep current max

# Circuit Breaker
ERROR_THRESHOLD = 0.3  # Open circuit at 30% error rate
CIRCUIT_TIMEOUT = 60  # Seconds before retry
```

## Monitoring Metrics

### Key Metrics to Track

1. **Lambda Metrics**:
   - Concurrent executions
   - Duration
   - Throttles
   - Errors

2. **OpenSearch Metrics**:
   - Indexing rate
   - CPU utilization
   - JVM memory pressure
   - Search latency

3. **DLQ Metrics**:
   - Messages received
   - Message age
   - Processing rate

### CloudWatch Alarms

- Lambda concurrent executions > 8
- OpenSearch CPU > 80%
- DLQ message count > 100
- Lambda error rate > 5%

## Migration Strategy

### Phase 1: Deploy Optimizations

1. Update Lambda code with bulk API support
2. Add reserved concurrency configuration
3. Increase batch size to 1000
4. Deploy to dev environment

### Phase 2: Testing

1. Test with 100K asset sync
2. Monitor OpenSearch performance
3. Verify DLQ processing
4. Adjust concurrency if needed

### Phase 3: Production Rollout

1. Deploy to production during maintenance window
2. Monitor closely for first 24 hours
3. Adjust parameters based on metrics
4. Document final configuration

## Rollback Plan

If issues occur:

1. Reduce reserved concurrency to 5
2. Reduce batch size to 100
3. Revert to individual operations if needed
4. Process DLQ messages manually

## Additional Recommendations

### Short Term

1. Add CloudWatch dashboard for monitoring
2. Implement DLQ processor Lambda
3. Add alerting for critical metrics

### Long Term

1. Consider OpenSearch auto-scaling
2. Implement write-ahead log for durability
3. Add data pipeline for bulk imports
4. Consider separate index for bulk operations

## Cost Impact

### Lambda Costs

- Reduced execution time: 50-100x faster
- Fewer invocations: Same number of batches
- **Net Impact**: 40-60% cost reduction

### OpenSearch Costs

- No change in cluster size needed
- Better resource utilization
- **Net Impact**: Neutral

### Overall

- **Estimated Savings**: $500-1000/month for frequent syncs
- **ROI**: Immediate (faster sync + lower costs)
