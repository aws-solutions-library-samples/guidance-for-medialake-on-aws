# S3 Vector Bucket Cleanup Fix

## Problem

When tearing down a MediaLake deployment, the S3 Vector bucket and indexes were not being destroyed, even in non-production environments where `RemovalPolicy.DESTROY` was set. This caused:

1. **Orphaned resources** - The bucket and indexes remained after stack deletion
2. **Failed redeployments** - Subsequent deployments failed due to resource name conflicts
3. **Manual cleanup required** - Users had to manually delete the bucket and indexes

## Root Cause

The issue had three contributing factors:

### 1. Vectors Not Emptied Before Deletion

The cleanup Lambda (`provisioned_resource_cleanup`) was attempting to delete S3 Vector indexes and the bucket, but **wasn't emptying the vectors first**. Just like regular S3 buckets, S3 Vector buckets cannot be deleted if they contain data (vectors).

### 2. Missing Permissions

The cleanup Lambda lacked the necessary IAM permissions to:

- List vectors in an index (`s3vectors:ListVectors`)
- Delete vectors from an index (`s3vectors:DeleteVectors`)

### 3. Incorrect Bucket Name

The cleanup Lambda was constructing the bucket name manually using a pattern, rather than receiving the actual bucket name from the infrastructure stack. This could lead to mismatches if the naming pattern changed.

## Solution

### Changes Made

#### 1. Enhanced Vector Cleanup Logic (`lambdas/back_end/provisioned_resource_cleanup/index.py`)

Added a new function `empty_s3_vector_index()` that:

- Lists all vectors in an index using pagination
- Deletes vectors in batches
- Handles errors gracefully
- Logs progress

Updated `delete_s3_vector_indexes()` to:

- Call `empty_s3_vector_index()` before deleting each index
- Ensure indexes are empty before deletion

```python
def empty_s3_vector_index(client, bucket_name: str, index_name: str):
    """Delete all vectors from an index."""
    # Lists and deletes all vectors in batches
    # Handles pagination for large vector sets
    # Logs progress and errors
```

#### 2. Added IAM Permissions (`medialake_stacks/clean_up_stack.py`)

Added permissions to the cleanup Lambda role:

- `s3vectors:ListVectors` - To list vectors in indexes
- `s3vectors:DeleteVectors` - To delete vectors from indexes

Updated resource ARN patterns to use the actual bucket name instead of wildcards.

#### 3. Pass Actual Bucket Name

**Updated `CleanupStackProps`** to include:

```python
s3_vector_bucket_name: str  # Actual bucket name from infrastructure
```

**Updated `app.py`** to pass the bucket name:

```python
cleanup_stack = CleanupStack(
    props=CleanupStackProps(
        s3_vector_bucket_name=base_infrastructure.s3_vector_bucket_name,
        # ... other props
    ),
)
```

**Updated Lambda environment variables** to use the passed bucket name:

```python
"VECTOR_BUCKET_NAME": props.s3_vector_bucket_name,
```

#### 4. Added Documentation Comment

Added a comment in `s3_vectors.py` to clarify that the cleanup Lambda handles emptying:

```python
# NOTE: Even with DESTROY policy, the bucket must be empty before deletion
# The provisioned_resource_cleanup Lambda handles emptying the bucket/indexes
```

## How It Works

### Cleanup Flow

1. **Stack Deletion Triggered** - User runs `cdk destroy` or deletes the stack
2. **Cleanup Lambda Invoked** - CloudFormation triggers the cleanup custom resource
3. **Empty Indexes** - For each index in the bucket:
   - List all vectors (with pagination)
   - Delete vectors in batches
   - Log progress
4. **Delete Indexes** - After emptying, delete each index
5. **Delete Bucket** - After all indexes are deleted, delete the bucket
6. **CloudFormation Cleanup** - CloudFormation then removes the bucket/index resources

### Order of Operations

```
Custom Resource (Cleanup Lambda)
  ↓
Empty Index 1 (delete all vectors)
  ↓
Delete Index 1
  ↓
Empty Index 2 (delete all vectors)
  ↓
Delete Index 2
  ↓
Delete Vector Bucket
  ↓
CloudFormation removes resources
```

## Testing

To verify the fix:

1. **Deploy a stack** with S3 Vector resources
2. **Add some vectors** to the indexes (via the application)
3. **Destroy the stack**: `cdk destroy`
4. **Verify cleanup**:
   - Check CloudWatch Logs for the cleanup Lambda
   - Confirm vectors were deleted
   - Confirm indexes were deleted
   - Confirm bucket was deleted
   - No orphaned resources remain

### Expected Log Output

```
INFO: Cleaning up S3 Vector bucket: medialake-vectors-{account}-{region}-{env}
INFO: Emptying vectors from index media in bucket medialake-vectors-...
INFO: Deleted 150 vectors from index media
INFO: Deleted S3 Vector index media from bucket medialake-vectors-...
INFO: Deleted S3 Vector bucket medialake-vectors-...
```

## Environment Behavior

- **Production (`prod`)**: `RemovalPolicy.RETAIN` - Bucket and indexes are retained
- **Non-Production (`dev`, `staging`, etc.)**: `RemovalPolicy.DESTROY` - Bucket and indexes are deleted after being emptied

## Files Modified

1. `lambdas/back_end/provisioned_resource_cleanup/index.py` - Added vector emptying logic
2. `medialake_stacks/clean_up_stack.py` - Added permissions and bucket name parameter
3. `medialake_constructs/shared_constructs/s3_vectors.py` - Added documentation comment
4. `app.py` - Pass bucket name to cleanup stack

## Related Issues

This fix resolves:

- Orphaned S3 Vector buckets after stack deletion
- Failed redeployments due to resource conflicts
- Manual cleanup requirements

## Notes

- The S3 Vectors API may have rate limits on vector deletion operations
- For very large vector sets (millions of vectors), cleanup may take several minutes
- The cleanup Lambda has a 15-minute timeout to accommodate large deletions
- Errors during vector deletion are logged but don't fail the entire cleanup process
