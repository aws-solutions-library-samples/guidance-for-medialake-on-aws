# CloudWatch Log Group Deployment Failure Investigation

## Latest Error (2026-01-31)

```
Embedded stack arn:aws:cloudformation:us-east-1:438465153766:stack/MediaLakeStack-MediaLakeApiGatewayStackNestedStackMediaLakeApiGatewayStackNestedStackR-12O6KZZYUCMNE/22943100-fe63-11f0-a0b9-127561a51745
was not successfully created: The following resource(s) failed to create:
[AssetsApiGatewayDeleteAssetLambdaDeleteAssetLambdaLogGroup43949F15,
 AssetsApiGatewayAssetsBatchDeleteProcessorLambdaAssetsBatchDeleteProcessorLambdaLogGroup9AFDCFBA]
```

## Fix Applied

Changed `medialake_constructs/shared_constructs/lambda_base.py` line 334 to use unique construct IDs:

```python
log_group_construct_id = f"{construct_id}LogGroup"
```

This ensures each Lambda's log group has a unique CDK construct ID.

## Verification

The CloudFormation logical IDs in the error confirm the fix is working:

- `AssetsApiGatewayDeleteAssetLambdaDeleteAssetLambdaLogGroup43949F15`
  - Path: AssetsApiGateway → DeleteAssetLambda → DeleteAssetLambdaLogGroup ✅
- `AssetsApiGatewayAssetsBatchDeleteProcessorLambdaAssetsBatchDeleteProcessorLambdaLogGroup9AFDCFBA`
  - Path: AssetsApiGateway → AssetsBatchDeleteProcessorLambda → AssetsBatchDeleteProcessorLambdaLogGroup ✅

The construct IDs are now unique, so the original CDK construct ID collision issue is resolved.

## Remaining Issue

The deployment is still failing, but now for a different reason. Multiple log groups are failing to create simultaneously, suggesting:

1. **CloudWatch Logs API Rate Limiting**: Creating 30+ log groups in parallel may exceed API rate limits
2. **IAM Permissions**: CloudFormation execution role may lack proper permissions
3. **Service Quotas**: Account may have hit CloudWatch Logs quotas
4. **Transient AWS Issues**: Temporary service problems

## Next Steps to Diagnose

### 1. Capture Actual Error Details

Deploy with no-rollback to preserve failed resources:

```bash
cdk deploy --no-rollback --profile ml-dev4
```

Then immediately check CloudFormation events:

```bash
aws cloudformation describe-stack-events \
  --stack-name <nested-stack-name> \
  --region us-east-1 \
  --profile ml-dev4 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

### 2. Check CloudWatch Logs Quotas

```bash
aws service-quotas list-service-quotas \
  --service-code logs \
  --region us-east-1 \
  --profile ml-dev4 \
  --query 'Quotas[?contains(QuotaName, `Log groups`)]'
```

### 3. Verify IAM Permissions

Check if CloudFormation execution role has `logs:CreateLogGroup`:

```bash
aws iam get-role-policy \
  --role-name cdk-hnb659fds-cfn-exec-role-438465153766-us-east-1 \
  --policy-name default \
  --profile ml-dev4
```

### 4. Check for API Throttling

Look for CloudWatch Logs API throttling in CloudTrail:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateLogGroup \
  --region us-east-1 \
  --profile ml-dev4 \
  --max-items 50 \
  --query 'Events[?contains(CloudTrailEvent, `ThrottlingException`)]'
```

### 5. Test with Smaller Batch

Temporarily comment out some Lambda functions in `AssetsConstruct` to test if it's a rate limiting issue.

## Possible Solutions

### If Rate Limiting:

- Add explicit dependencies between log groups to serialize creation
- Use CDK aspects to add delays between resource creation
- Increase CloudWatch Logs API rate limits via AWS Support

### If IAM Permissions:

- Update CDK execution role with explicit `logs:CreateLogGroup` permission
- Check for SCPs or permission boundaries blocking the action

### If Service Quotas:

- Request quota increase via AWS Service Quotas console
- Clean up unused log groups

## Temporary Workaround

If the issue persists, consider removing explicit log group creation and letting Lambda auto-create them:

```python
# Comment out explicit log group creation
# lambda_log_group = logs.LogGroup(...)

# Remove from Lambda props
common_lambda_props = {
    # "log_group": lambda_log_group,  # Remove this
    ...
}
```

Note: This loses control over retention policies and removal policies.
