# Architecture Analysis: S3 GetBucketLocation Permission Issue

## Problem Statement

The `generate_presigned_url` Lambda function is failing with an `AccessDenied` error when attempting to call `s3:GetBucketLocation` on the bucket `bluescape-n8n`. The error indicates that the Lambda's IAM role lacks the necessary permissions.

**Error Details:**
```
User: arn:aws:sts::887148515409:assumed-role/role-medialake_generate_presigned_url_dev/medialake_generate_presigned_url_dev 
is not authorized to perform: s3:GetBucketLocation on resource: "arn:aws:s3:::bluescape-n8n" 
because no identity-based policy allows the s3:GetBucketLocation action
```

## Current Architecture Analysis

### Lambda Function Architecture
The [`generate_presigned_url`](lambdas/api/assets/generate_presigned_url/index.py:1) Lambda implements a sophisticated region-aware S3 client pattern:

1. **Region Discovery Pattern** (Lines 33-56):
   - Uses a generic `us-east-1` S3 client to call [`get_bucket_location()`](lambdas/api/assets/generate_presigned_url/index.py:44)
   - Caches region-specific S3 clients for performance
   - Creates endpoint-specific clients for cross-region compatibility

2. **Current IAM Permissions** (Lines 366-391 in [`api_gateway_assets.py`](medialake_constructs/api_gateway/api_gateway_assets.py:366)):
   ```python
   # DynamoDB permissions
   actions=["dynamodb:GetItem"]
   
   # KMS permissions  
   actions=["kms:Decrypt", "kms:DescribeKey"]
   
   # S3 object permissions
   actions=["s3:GetObject", "s3:GetObjectVersion"]
   resources=["arn:aws:s3:::*/*"]  # Objects only, not buckets
   ```

### Root Cause
The Lambda role has permissions for S3 objects (`arn:aws:s3:::*/*`) but **lacks bucket-level permissions** (`arn:aws:s3:::*`) required for [`s3:GetBucketLocation`](lambdas/api/assets/generate_presigned_url/index.py:44).

## Architecture Solutions

### Solution 1: Add Missing S3 Bucket Permissions (Recommended)

**Approach**: Extend existing IAM policy to include bucket-level operations.

**Implementation**:
```python
# Add to medialake_constructs/api_gateway/api_gateway_assets.py
generate_presigned_url_lambda.function.add_to_role_policy(
    iam.PolicyStatement(
        actions=[
            "s3:GetBucketLocation",
            "s3:ListBucket",  # Optional: for enhanced error handling
        ],
        resources=["arn:aws:s3:::*"],  # Bucket-level permissions
    )
)
```

**Pros**:
- Minimal code changes
- Maintains existing architecture pattern
- Preserves region-aware optimization
- Follows principle of least privilege

**Cons**:
- Grants broad bucket access across all S3 buckets

### Solution 2: Bucket-Specific Permissions (Most Secure)

**Approach**: Grant permissions only to specific buckets that contain media assets.

**Implementation**:
```python
# Define allowed buckets based on asset storage patterns
allowed_buckets = [
    props.media_assets_bucket.bucket_arn,
    "arn:aws:s3:::bluescape-n8n",  # External bucket
    # Add other known asset buckets
]

generate_presigned_url_lambda.function.add_to_role_policy(
    iam.PolicyStatement(
        actions=["s3:GetBucketLocation"],
        resources=allowed_buckets,
    )
)
```

**Pros**:
- Maximum security (principle of least privilege)
- Explicit bucket control
- Audit-friendly

**Cons**:
- Requires maintenance when new buckets are added
- May break if assets are stored in unknown buckets

### Solution 3: Architectural Refactor - Remove Region Discovery

**Approach**: Eliminate the need for `GetBucketLocation` by using alternative patterns.

**Options**:
1. **Configuration-Based Regions**: Store bucket-region mappings in DynamoDB
2. **Default Region Strategy**: Use a default region and handle cross-region errors
3. **Multi-Region Client Pool**: Pre-configure clients for known regions

**Implementation Example** (Configuration-Based):
```python
# Store in DynamoDB or environment variables
BUCKET_REGIONS = {
    "bluescape-n8n": "us-east-1",
    # other known buckets
}

def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    region = BUCKET_REGIONS.get(bucket, "us-east-1")  # Default fallback
    
    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3", region_name=region, config=_SIGV4_CFG
        )
    return _S3_CLIENT_CACHE[region]
```

**Pros**:
- Eliminates permission requirement
- Potentially faster (no API call)
- More predictable behavior

**Cons**:
- Requires configuration management
- Less dynamic/flexible
- May not handle unknown buckets gracefully

## Security Considerations

### Current Security Posture
- Lambda has broad object access (`arn:aws:s3:::*/*`)
- KMS permissions are wildcard (`"*"`)
- DynamoDB access is properly scoped

### Security Recommendations

1. **Implement Solution 1** for immediate fix
2. **Plan migration to Solution 2** for long-term security
3. **Consider bucket tagging** for dynamic permission management
4. **Implement monitoring** for S3 access patterns

### Compliance Impact
- **SOC 2**: Requires documented access controls
- **GDPR**: May need data location tracking
- **Industry Standards**: Principle of least privilege

## Implementation Plan

### Phase 1: Immediate Fix (Solution 1)
1. Update [`api_gateway_assets.py`](medialake_constructs/api_gateway/api_gateway_assets.py:383) IAM policy
2. Deploy and test with existing bucket
3. Monitor CloudTrail for S3 API usage

### Phase 2: Security Hardening (Solution 2)
1. Audit all buckets accessed by the system
2. Create bucket inventory in configuration
3. Implement bucket-specific permissions
4. Add monitoring and alerting

### Phase 3: Architectural Enhancement (Optional)
1. Evaluate region discovery alternatives
2. Implement configuration-based approach
3. Add bucket metadata caching

## Monitoring and Observability

### Metrics to Track
- S3 API call success/failure rates
- Cross-region request patterns
- Permission denied errors
- Lambda cold start impact

### Alerting Strategy
- CloudWatch alarms for permission errors
- S3 access pattern anomalies
- New bucket access attempts

## Testing Strategy

### Unit Tests
- Mock S3 client behavior
- Test permission error handling
- Validate region discovery logic

### Integration Tests
- Test with multiple bucket regions
- Verify presigned URL generation
- Test cross-account bucket access

### Security Tests
- Verify least privilege compliance
- Test unauthorized bucket access
- Validate error handling

## Conclusion

**Recommended Approach**: Implement Solution 1 immediately for operational continuity, then plan migration to Solution 2 for enhanced security posture.

The architecture demonstrates good practices with region-aware S3 clients and caching, but requires the missing `s3:GetBucketLocation` permission to function correctly. The proposed solutions balance security, maintainability, and operational requirements.