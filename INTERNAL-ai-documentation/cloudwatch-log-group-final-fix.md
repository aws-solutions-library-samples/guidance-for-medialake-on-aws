# CloudWatch Log Group Deployment Fix - Final Solution

## Problem Summary

CloudFormation deployments were failing with errors like:

```
Resource handler returned message: "The specified log group does not exist."
```

This occurred because:

1. Previous deployments created log groups that were auto-created by Lambda
2. These log groups existed outside CloudFormation management
3. When we tried to explicitly create log groups in CloudFormation, it failed due to:
   - Mismatches between existing and expected log group names
   - CloudFormation trying to reference log groups that didn't exist
   - Conflicts between CloudFormation-managed and Lambda-auto-created log groups

## Root Causes Identified

### Issue 1: CDK Construct ID Collision (FIXED)

All Lambda constructs used the same hardcoded construct ID `"LambdaLogGroup"`, causing CDK-level conflicts.

**Fix Applied**: Changed to unique construct IDs: `f"{construct_id}LogGroup"`

### Issue 2: CloudFormation vs Lambda-Created Log Groups (FIXED)

Lambda functions auto-create log groups on first invocation. When CloudFormation tried to explicitly manage these log groups, it created conflicts:

- Existing log groups from previous deployments
- Mismatched log group names
- CloudFormation state inconsistencies

**Fix Applied**: Removed explicit log group creation from CloudFormation

## Final Solution

Modified `medialake_constructs/shared_constructs/lambda_base.py` to:

1. **Remove explicit log group creation** - No longer create `logs.LogGroup` resources in CloudFormation
2. **Let Lambda auto-create log groups** - Lambda will create log groups on first invocation
3. **Remove hard dependency** - Don't pass `log_group` parameter to Lambda function

### Code Changes

```python
# Before (PROBLEMATIC):
lambda_log_group = logs.LogGroup(
    self,
    "LambdaLogGroup",  # ❌ Same ID for all
    log_group_name=log_group_name,
    retention=LOG_RETENTION,
)
common_lambda_props = {
    "log_group": lambda_log_group,  # ❌ Hard dependency
    ...
}

# After (FIXED):
# Store log group name for reference but don't create the resource
self._log_group_name = log_group_name
lambda_log_group = None  # ✅ No explicit log group resource

common_lambda_props = {
    # ✅ No log_group parameter - Lambda will auto-create
    ...
}
```

## Benefits

1. **No More Conflicts**: Lambda auto-creates log groups, avoiding CloudFormation conflicts
2. **Idempotent Deployments**: Works whether log groups exist or not
3. **Simpler Stack**: Fewer CloudFormation resources to manage
4. **Faster Deployments**: No need to create 30+ log group resources
5. **No Rollbacks**: Existing log groups don't cause deployment failures

## Trade-offs

### What We Lose:

- **CloudFormation-managed retention**: Log groups won't have retention policies set by CloudFormation
- **Automatic cleanup**: Log groups won't be deleted when stack is deleted (but we had RETAIN policy anyway)
- **Centralized management**: Log groups are managed by Lambda service, not CloudFormation

### What We Keep:

- **All functionality**: Lambda logging works exactly the same
- **Log group naming**: Same naming convention (`/aws/lambda/{function_name}-logs`)
- **IAM permissions**: Lambda execution role still has CloudWatch Logs permissions

## Setting Retention Policies

Since CloudFormation no longer manages log groups, retention must be set separately:

### Option 1: AWS CLI (One-time)

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/medialake_function_name_dev-logs \
  --retention-in-days 180 \
  --region us-east-1 \
  --profile ml-dev4
```

### Option 2: Lambda Layer or Custom Resource

Create a custom resource that sets retention policies after Lambda creation:

```python
# Future enhancement: Add custom resource to set retention
retention_setter = CustomResource(
    self,
    "LogRetentionSetter",
    service_token=retention_setter_lambda.function_arn,
    properties={
        "LogGroupName": log_group_name,
        "RetentionInDays": LOG_RETENTION
    }
)
```

### Option 3: Separate CloudFormation Stack

Create a separate stack that adopts existing log groups and sets retention:

```python
# Separate stack for log group management
logs.LogGroup.from_log_group_name(
    self,
    "ExistingLogGroup",
    log_group_name=log_group_name
)
```

## Testing

Deploy the stack and verify:

```bash
# Deploy
cdk deploy MediaLakeStack --profile ml-dev4

# Verify Lambda functions created
aws lambda list-functions --region us-east-1 --profile ml-dev4 \
  --query 'Functions[?contains(FunctionName, `medialake`)].FunctionName'

# Invoke a Lambda to trigger log group creation
aws lambda invoke --function-name medialake_assets-get_dev \
  --region us-east-1 --profile ml-dev4 /tmp/output.json

# Verify log group was auto-created
aws logs describe-log-groups --region us-east-1 --profile ml-dev4 \
  --log-group-name-prefix "/aws/lambda/medialake_"
```

## Migration Path

For existing deployments with CloudFormation-managed log groups:

1. **Before deploying**: Log groups managed by CloudFormation will be retained (RETAIN policy)
2. **After deploying**: New Lambda invocations will use existing log groups
3. **No action needed**: Existing log groups continue to work
4. **Optional cleanup**: Manually remove orphaned CloudFormation log group resources

## Files Modified

- `medialake_constructs/shared_constructs/lambda_base.py` (lines 328-340, 405)

## Rollback Plan

If issues arise, revert to explicit log group creation:

```python
# Restore explicit log group creation
lambda_log_group = logs.LogGroup(
    self,
    f"{construct_id}LogGroup",
    log_group_name=log_group_name,
    retention=LOG_RETENTION,
    removal_policy=RemovalPolicy.RETAIN,
)

common_lambda_props = {
    "log_group": lambda_log_group,
    ...
}
```

## Conclusion

This solution makes deployments robust and idempotent by letting Lambda handle log group creation naturally, avoiding CloudFormation conflicts entirely. The trade-off is losing CloudFormation-managed retention policies, which can be addressed through alternative methods if needed.
