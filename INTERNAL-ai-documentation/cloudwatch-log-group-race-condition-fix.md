# CloudWatch Log Group Race Condition Fix

## Issue Summary

Intermittent CloudFormation deployment failures occurring randomly in the API Gateway nested stack, specifically when creating CloudWatch log groups for Lambda functions. The error message pattern:

```
Embedded stack arn:aws:cloudformation:...:stack/MediaLakeStack-MediaLakeApiGatewayStackNestedStack...
was not successfully created: The following resource(s) failed to create:
[AssetsApiGatewayTranscriptAssetLambdaLambdaLogGroupDE9F7129]
```

The failure would randomly affect different Lambda log groups on each deployment attempt.

## Root Cause

The issue was in `medialake_constructs/shared_constructs/lambda_base.py` where all Lambda constructs used the same hardcoded CDK construct ID `"LambdaLogGroup"` for their CloudWatch log groups:

```python
lambda_log_group = logs.LogGroup(
    self,
    "LambdaLogGroup",  # ❌ Same ID for all Lambdas in the same scope!
    log_group_name=log_group_name,
    retention=LOG_RETENTION,
)
```

### Why This Caused Random Failures

1. **Multiple Lambdas in Same Construct**: Constructs like `AssetsConstruct` create 30+ Lambda functions, each trying to create a log group with the construct ID `"LambdaLogGroup"`

2. **CDK Construct ID Collision**: While the actual CloudWatch log group names were unique (they included the function name), the CDK construct IDs must be unique within the same scope

3. **Race Condition**: CloudFormation processes resources in parallel when possible, causing intermittent conflicts when multiple log groups with the same construct ID were created simultaneously

4. **Random Failures**: The failure was non-deterministic because it depended on CloudFormation's parallel execution order, which varies between deployments

## Solution

Changed the log group construct ID to be unique by incorporating the parent Lambda construct's ID:

```python
# Use unique construct ID to avoid conflicts when multiple Lambdas are created in same scope
log_group_construct_id = f"{construct_id}LogGroup"
lambda_log_group = logs.LogGroup(
    self,
    log_group_construct_id,  # ✅ Unique ID per Lambda!
    log_group_name=log_group_name,
    retention=LOG_RETENTION,
)
```

### How This Fixes the Issue

- Each Lambda construct has a unique `construct_id` (e.g., "GetAssetsLambda", "DeleteAssetLambda", "TranscriptAssetLambda")
- The log group construct ID becomes unique (e.g., "GetAssetsLambdaLogGroup", "DeleteAssetLambdaLogGroup")
- No more construct ID collisions
- CloudFormation can safely create all log groups in parallel without conflicts

## Files Modified

- `medialake_constructs/shared_constructs/lambda_base.py` (line 332-334)

## Testing Recommendations

1. Deploy the full stack multiple times to verify no random failures occur
2. Pay special attention to the API Gateway nested stack deployment
3. Verify all Lambda log groups are created successfully
4. Check that log group names remain unchanged (only the CDK construct IDs changed)

## Impact

- **Breaking Change**: No - this only affects CDK construct IDs, not actual AWS resource names
- **Deployment**: Existing log groups will not be affected; CDK will recognize them by their physical names
- **Rollback**: Safe to rollback if needed, though the issue will return

## Related Constructs Checked

Also verified that other constructs in `lambda_base.py` don't have similar issues:

- ✅ IAM Roles: Already use unique IDs (`f"{lambda_function_name}ExecutionRole"`)
- ✅ Lambda Layers: Use IDs passed from parent construct
- ✅ Lambda Functions: Use unique construct IDs

## Prevention

When creating multiple instances of the same CDK construct within a parent construct, always ensure:

1. Each child construct has a unique construct ID
2. Avoid hardcoded construct IDs like "MyResource" - use dynamic IDs based on parent context
3. Test with constructs that create many children (like AssetsConstruct with 30+ Lambdas)
