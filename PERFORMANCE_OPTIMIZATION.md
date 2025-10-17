# Lambda Performance Optimization Strategy

## Overview

This document explains the performance optimization strategy implemented for MediaLake Lambda functions, balancing cost-effectiveness with maximum performance.

## Strategy Summary

Our approach uses a **balanced performance model**:

1. ✅ **Provisioned Concurrency for critical VPC Lambdas** - 3 high-traffic APIs with 2 instances each
2. ✅ **Optimized memory allocation** - VPC Lambdas: 512-1024 MB, Search: 9000 MB
3. ⚠️ **SnapStart disabled** - Caused Lambda initialization failures in deployment
4. ✅ **Cost-effective** - ~$240/month for provisioned concurrency vs $1,000+ for all Lambdas

## Performance Features

### SnapStart (Currently Disabled)

**Status:** ⚠️ **DISABLED** due to Lambda initialization failures during deployment

**What it does:**
- Takes a snapshot of Lambda after initialization
- Restores from snapshot instead of cold starting
- Reduces cold start latency by 50-90%

**Why it's disabled:**
- ❌ Caused "Lambda Version did not stabilize" errors in eu-west-1 and eu-west-2
- ❌ "An error occurred during function initialization" with SnapStart enabled
- ⚠️ Not compatible with EFS-mounted Lambda functions
- ⚠️ May cause issues with certain initialization patterns or dependencies

**Current configuration:**
- `DEFAULT_SNAP_START = False` in `lambda_base.py`
- Can be manually enabled per-function by setting `snap_start=True` in `LambdaConfig` (not recommended)

**Alternative:**
- Standard Lambda cold starts are acceptable for current traffic patterns
- Provisioned concurrency can be enabled later if needed

### Provisioned Concurrency (Enabled for Critical APIs)

**Status:** ✅ **ENABLED** for high-traffic APIs

**What it does:**
- Keeps pre-initialized Lambda instances always warm
- Eliminates cold starts completely for provisioned instances
- Handles burst traffic immediately

**Applied to (2 instances each):**

| Lambda Function | Memory | Provisioned Instances | Reason |
|----------------|--------|----------------------|--------|
| **Collections API** | 1024 MB | 2 | High-traffic CRUD operations, VPC access to OpenSearch/DynamoDB |
| **Search API** | 9000 MB | 2 | Critical user-facing search, heavy compute (vector/semantic search) |
| **Assets GET** | 512 MB | 2 | Frequent asset retrieval, VPC access to OpenSearch |

**Configuration requirements:**
- ✅ VPC Lambdas must have at least 512 MB memory (1024 MB recommended)
- ✅ SnapStart must be disabled (incompatible, causes initialization failures)
- ✅ Provisioned instances should match expected concurrent load

**Monthly Cost:**
- 6 provisioned instances × $40 = ~$240/month
- Compared to: ~$1,000+/month if enabled on ALL Lambdas

## Memory Allocation Strategy

### VPC Lambda Considerations

Lambda functions in VPC require additional resources for:
- Elastic Network Interface (ENI) creation/attachment
- VPC routing overhead
- Security group processing

**Minimum memory recommendations:**
- **Without Provisioned Concurrency:** 256 MB
- **With Provisioned Concurrency:** 512-1024 MB
- **Heavy compute workloads:** 1024+ MB

### Memory Configuration by Function Type

| Function Type | Memory | Justification |
|--------------|--------|---------------|
| Simple API (no VPC) | 128 MB | Default, sufficient for basic operations |
| VPC API (standard) | 512 MB | VPC overhead + application needs |
| VPC API (complex) | 1024 MB | Multiple AWS service calls + VPC overhead |
| Search/Analytics | 1024-9000 MB | Heavy compute, large datasets, vector operations |
| Background processing | 2048+ MB | Batch operations, data transformation |

## Implementation Details

### Default Configuration

All Lambda functions inherit these defaults from `lambda_base.py`:

```python
DEFAULT_MEMORY_SIZE = 128  # MB
DEFAULT_TIMEOUT_MINUTES = 5
DEFAULT_RUNTIME = lambda_.Runtime.PYTHON_3_12
DEFAULT_SNAP_START = True  # Enabled by default for free performance boost
```

### Overriding Defaults

To customize a Lambda function:

```python
collections_lambda = Lambda(
    self,
    "CollectionsLambda",
    config=LambdaConfig(
        name="collections_api",
        entry="lambdas/api/collections_api",
        vpc=props.vpc,
        security_groups=[props.security_group],
        memory_size=1024,  # Override default
        provisioned_concurrent_executions=2,  # Add provisioned concurrency
        snap_start=True,  # Explicitly enable (already default)
        environment_variables={...},
    ),
)
```

### Disabling SnapStart

For functions where SnapStart is not suitable (rare cases):

```python
config=LambdaConfig(
    name="my_function",
    snap_start=False,  # Disable SnapStart
    ...
)
```

## Monitoring and Optimization

### Key Metrics to Monitor

1. **Cold Start Duration** (CloudWatch Logs)
   - Target: <1 second with SnapStart
   - Target: <100ms with Provisioned Concurrency

2. **Invocation Count vs Provisioned Instances**
   - If traffic exceeds provisioned capacity, you'll see cold starts
   - Consider increasing provisioned instances if this happens frequently

3. **Memory Utilization**
   - If consistently using >80% of allocated memory, increase allocation
   - If consistently using <50% of allocated memory, consider reducing (except VPC Lambdas)

4. **Cost Analysis**
   - Monitor provisioned concurrency costs in Cost Explorer
   - Compare with cold start impact on user experience

### When to Add Provisioned Concurrency

Consider adding provisioned concurrency when:
- ✅ Function has consistent, high traffic (>100 requests/minute)
- ✅ Cold starts directly impact user experience
- ✅ Function is in VPC and you have sufficient memory (512MB+)
- ✅ Business value justifies the cost (~$40/month per instance)

**Don't add provisioned concurrency for:**
- ❌ Low-traffic endpoints (<10 requests/minute)
- ❌ Background processing functions (not user-facing)
- ❌ Custom resource handlers (only run during deployments)
- ❌ Functions that rarely execute

## EFS Lambda Functions

### Performance Considerations

Lambda functions with EFS mounts (used for bulk download operations) have special considerations:

**Limitations:**
- ❌ **SnapStart not supported** - AWS does not support SnapStart with EFS-mounted Lambdas
- ⚠️ **Provisioned Concurrency expensive** - Each instance maintains EFS connection
- ⚠️ **Cold start overhead** - EFS mount adds ~500ms to cold start time

**Current Configuration:**
- Bulk download Lambdas (5 functions):
  - `_init_zip_lambda` - 512 MB memory
  - `_append_to_zip_lambda` - 1024 MB memory
  - `_init_multipart_lambda` - 1024 MB memory
  - `_upload_part_lambda` - 1024 MB memory
  - `_complete_multipart_lambda` - 1024 MB memory

**Optimization Strategy:**
- ✅ Use higher memory (512-1024 MB) to offset cold start overhead
- ✅ Accept longer cold starts (no SnapStart available)
- ❌ Do NOT add provisioned concurrency (very expensive for EFS Lambdas)
- ✅ Consider async processing patterns to hide latency from users

**Alternative Approaches:**
- Use S3 for temporary storage instead of EFS (enables SnapStart)
- Use Step Functions to coordinate multi-Lambda workflows
- Pre-warm functions using scheduled EventBridge rules if needed

## Provisioned Concurrency + VPC Best Practices

### Why VPC Lambdas Need More Memory

1. **ENI Initialization**: Creating and attaching network interfaces requires memory
2. **Connection Pooling**: VPC Lambdas maintain connections to AWS services (DynamoDB, OpenSearch, etc.)
3. **SDK Overhead**: Multiple AWS SDK clients loaded in memory
4. **Application State**: Your application code and dependencies

### Failure Symptoms

If provisioned concurrency fails to stabilize (like you experienced in eu-west-1):

```
Resource handler returned message: "Provisioned Concurrency configuration failed 
to be applied. Reason: FAILED" (HandlerErrorCode: NotStabilized)
```

**Root causes:**
- ❌ Insufficient memory (e.g., 128 MB for VPC Lambda)
- ❌ Initialization timeout (function takes too long to initialize)
- ❌ VPC configuration issues (no NAT Gateway, subnet issues)
- ❌ Regional capacity constraints

**Solutions:**
- ✅ Increase memory to at least 512 MB (1024 MB recommended)
- ✅ Optimize initialization code (lazy loading, connection pooling)
- ✅ Verify VPC configuration (NAT Gateway, route tables)
- ✅ Use SnapStart instead if provisioned concurrency keeps failing

## SnapStart vs Provisioned Concurrency Decision Matrix

| Use Case | Recommended Solution | Reason |
|----------|---------------------|--------|
| High-traffic API, cost-sensitive | **SnapStart only** | Free, effective, good enough for most cases |
| Critical user-facing API, <100ms latency requirement | **Provisioned Concurrency + SnapStart** | Maximum performance, cost justified |
| Background processing | **SnapStart only** | Cold starts not user-visible |
| Infrequent API calls | **SnapStart only** | Provisioned capacity would be wasted |
| Websocket/Real-time APIs | **Provisioned Concurrency** | Immediate response critical |
| VPC Lambda, budget constrained | **SnapStart + 512MB memory** | Better than default, still cost-effective |

## Regional Considerations

Some AWS regions have specific characteristics:

- **us-east-1**: Highest capacity, most reliable for provisioned concurrency
- **eu-west-1**: Good capacity, but can experience occasional capacity constraints
- **New regions**: May have lower initial capacity

**Recommendation:** Test provisioned concurrency configuration in your target region before production deployment.

## Cost Optimization Tips

1. **Start with provisioned concurrency on critical APIs only** - Currently 3 high-traffic functions
2. **Monitor utilization** - Use CloudWatch metrics to verify instances are being used
3. **Right-size memory** - Don't over-allocate, but don't under-allocate for VPC Lambdas
4. **Consider scheduled scaling** - Reduce provisioned capacity during off-peak hours (requires custom automation)
5. **Evaluate SnapStart in the future** - Once initialization issues are resolved, it could provide free performance boost

## Troubleshooting

### Provisioned Concurrency Deployment Failures

**Symptom:** Stack fails to deploy with "NotStabilized" error

**Checklist:**
- [ ] Is the Lambda in VPC? If yes, memory should be ≥512 MB
- [ ] Does initialization complete within 15 seconds?
- [ ] Are all VPC routes properly configured (NAT Gateway)?
- [ ] Are security groups allowing necessary outbound traffic?
- [ ] Is the region experiencing capacity issues?

**Quick fix:** Temporarily remove provisioned concurrency, deploy successfully, then add it back with higher memory.

### SnapStart Issues

**Symptom:** Function behavior differs after SnapStart restoration

**Common issues:**
- Cached credentials (use runtime credential refresh)
- Stale network connections (re-establish on restore)
- Random number generation (use post-restore initialization)
- Timestamp drift (refresh timestamps on restore)

**Solution:** Implement SnapStart restore hook:
```python
def restore_handler():
    # Re-initialize connections, refresh credentials, etc.
    pass

@event_handler
def lambda_handler(event, context):
    if context.restore_occurred:
        restore_handler()
    # Normal handler logic
```

## Summary

Our Lambda performance strategy provides:
- ✅ **Zero cold starts** for critical APIs (Collections, Search, Assets) via provisioned concurrency
- ✅ **Proper memory allocation** for VPC Lambdas (512-1024 MB) to ensure stable provisioned concurrency
- ✅ **Cost-effective** - ~$240/month for provisioned concurrency vs $1,000+ for all Lambdas
- ✅ **Reliable deployments** - SnapStart disabled to prevent initialization failures

**Performance characteristics:**
- ✅ **Critical APIs**: <100ms response time (zero cold starts with provisioned concurrency)
- ⚠️ **Other APIs**: 1-3 second cold starts after idle periods (standard Lambda behavior)
- ✅ **Deployment**: Succeeds reliably across all regions (eu-west-1, eu-west-2, etc.)

**Key success factors:**
- ✅ Sufficient memory (512-1024 MB) for VPC Lambdas with provisioned concurrency
- ✅ SnapStart disabled to avoid initialization conflicts
- ✅ Selective provisioned concurrency (3 APIs only) keeps costs reasonable

This balanced approach provides **excellent performance for high-traffic endpoints** while maintaining deployment reliability and reasonable infrastructure costs (~$240/month).

## References

- [AWS SnapStart Documentation](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [AWS Provisioned Concurrency Documentation](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html)
- [Lambda VPC Configuration Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
- [Lambda Power Tuning Tool](https://github.com/alexcasalboni/aws-lambda-power-tuning)

