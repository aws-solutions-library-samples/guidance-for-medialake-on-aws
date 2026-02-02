# S3 Auto-Delete Permissions Fix

## Problem

When tearing down the CDK deployment, the `MediaLakeBaseInfrastructure` stack fails with:

```
DELETE_FAILED: The following resource(s) failed to delete: [MediaAssetsS3BucketAutoDeleteObjectsCustomResource]
AccessDenied: User: arn:aws:sts::XXX:assumed-role/.../CustomS3AutoDeleteObjects is not authorized to perform: s3:GetBucketTagging
```

## Root Cause

When `auto_delete_objects=True` is set on an S3 bucket, CDK creates a custom resource Lambda function that empties the bucket before deletion. This Lambda needs several S3 permissions to function properly:

- `s3:GetBucketTagging` - To read bucket tags
- `s3:GetBucketVersioning` - To handle versioned objects
- `s3:GetBucketLocation` - To determine bucket region
- `s3:ListBucket` - To list objects (already granted)
- `s3:DeleteObject` - To delete objects (already granted)

The CDK auto-delete handler grants `ListBucket` and `DeleteObject` by default, but **does not grant the metadata read permissions** (`GetBucketTagging`, `GetBucketVersioning`, `GetBucketLocation`), causing the deletion to fail.

## Solution

Added a bucket policy to the S3Bucket construct that explicitly grants these missing permissions to the auto-delete custom resource Lambda:

```python
if props.destroy_on_delete:
    self._bucket.add_to_resource_policy(
        iam.PolicyStatement(
            sid="AllowAutoDeleteCustomResourceAccess",
            effect=iam.Effect.ALLOW,
            principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
            actions=[
                "s3:GetBucketTagging",
                "s3:GetBucketVersioning",
                "s3:GetBucketLocation",
            ],
            resources=[self._bucket.bucket_arn],
            conditions={
                "StringLike": {
                    "aws:userid": "*:*CustomS3AutoDeleteObject*"
                }
            }
        )
    )
```

## Security Considerations

The fix is secure because:

1. **Scoped to Lambda service**: Only Lambda functions can use this policy
2. **Condition-based**: The `aws:userid` condition ensures only the auto-delete Lambda (with `CustomS3AutoDeleteObject` in its session name) can use these permissions
3. **Read-only metadata**: The granted permissions only allow reading bucket metadata, not accessing or modifying objects
4. **Resource-specific**: The policy only applies to the specific bucket ARN

## Files Modified

- `medialake_constructs/shared_constructs/s3bucket.py`
  - Added `aws_iam` import
  - Added bucket policy statement for auto-delete permissions

## Testing

After deploying this fix:

1. Deploy the stack: `cdk deploy --all`
2. Verify buckets are created successfully
3. Tear down the stack: `cdk destroy --all`
4. Confirm the MediaLakeBaseInfrastructure stack deletes without errors

## Impact

This fix applies to all S3 buckets created through the `S3Bucket` construct with `destroy_on_delete=True`, including:

- Media assets bucket
- Access logs bucket
- Any other buckets using the shared construct

The fix ensures clean teardown of CDK stacks without manual intervention to delete buckets from the AWS console.
