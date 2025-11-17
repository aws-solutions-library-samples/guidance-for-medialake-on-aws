# S3 Bucket Creation Fix - bucketType Field Implementation

## Overview

Fixed a critical bug where creating new S3 buckets through the connector modal would fail with the error: "S3 bucket does not exist or is not accessible". The root cause was that the `bucketType` field was not being sent from the frontend to the backend, causing the backend to incorrectly attempt to validate a non-existent bucket instead of creating a new one.

## Problem Analysis

### Symptoms

- Creating a new S3 bucket connector returned a 400 error
- Error message: `"S3 bucket '{bucket_name}' does not exist or is not accessible"`
- The error occurred even when selecting "New S3 Bucket" option in the UI

### Root Cause

The frontend had `bucketType` state for UI logic and validation but was not including it in the API payload sent to the backend. This was a regression from a previous fix that removed `bucketType` from the payload (documented in `connector-modal-payload-fixes.md`).

The backend's Pydantic model had `bucketType` as optional (`str | None = None`), and the conditional logic at line 1298 checked:

```python
if bucket_type == "new":
    # Create new bucket
else:
    # Validate existing bucket
```

When `bucketType` was `None`, the code fell into the `else` block, attempting to validate a non-existent bucket.

## Solution Implemented

### 1. Frontend Changes

**File:** `medialake_user_interface/src/features/settings/connectors/components/ConnectorModal.tsx`

**Change:** Added `bucketType` to the configuration object in the API payload (line ~324)

```typescript
const connectorData: CreateConnectorRequest = {
  name,
  type,
  description,
  configuration: {
    ...restConfig,
    connectorType: s3ConnectorType,
    s3IntegrationMethod: (configuration.s3IntegrationMethod ||
      integrationMethod) as "eventbridge" | "s3Notifications",
    objectPrefix: filteredPrefixes.length > 0 ? filteredPrefixes : [],
    allowUploads: allowUploads,
    bucketType: bucketType as "new" | "existing", // ADDED
    ...newBucketExtras,
  },
};
```

### 2. Backend Changes

**File:** `lambdas/api/connectors/s3/post_s3/index.py`

**Changes:**

1. **Made `bucketType` required in Pydantic model** (line 172):

```python
class S3ConnectorConfig(BaseModel):
    bucket: str
    s3IntegrationMethod: str
    objectPrefix: list[str] | None = None
    bucketType: str  # Required: "new" or "existing"
    region: str | None = None
    allowUploads: bool | None = False
```

2. **Added validation for `bucketType` values** (line ~1295):

```python
# Validate bucketType value
if bucket_type not in ["new", "existing"]:
    return {
        "status": "400",
        "message": f"Invalid bucketType '{bucket_type}'. Must be 'new' or 'existing'",
        "data": {},
    }
```

3. **Improved logging** (line ~1300):

```python
logger.info(f"Processing connector for bucket '{s3_bucket}' with bucketType='{bucket_type}'")
```

4. **Removed diagnostic logs** that were added during investigation

## Files Modified

1. `medialake_user_interface/src/features/settings/connectors/components/ConnectorModal.tsx`
   - Added `bucketType` field to API payload configuration

2. `lambdas/api/connectors/s3/post_s3/index.py`
   - Made `bucketType` required in `S3ConnectorConfig` Pydantic model
   - Added validation to ensure `bucketType` is either "new" or "existing"
   - Improved logging for better debugging
   - Removed temporary diagnostic logs

## Testing Recommendations

1. **Create New Bucket:**
   - Open connector modal
   - Select "Amazon S3"
   - Select "New S3 Bucket"
   - Enter a valid, globally unique bucket name
   - Fill in required fields
   - Click "Add Connector"
   - Verify bucket is created successfully

2. **Create Existing Bucket:**
   - Open connector modal
   - Select "Amazon S3"
   - Select "Existing S3 Bucket"
   - Select a bucket from dropdown
   - Fill in required fields
   - Click "Add Connector"
   - Verify connector is created successfully

3. **Validation:**
   - Verify Pydantic validation rejects requests without `bucketType`
   - Verify backend validation rejects invalid `bucketType` values
   - Check CloudWatch logs for proper logging messages

## Impact

- **Positive:** New S3 bucket creation now works correctly
- **Breaking Change:** API now requires `bucketType` field (previously optional)
- **Backward Compatibility:** Existing connectors are not affected (only applies to new connector creation)

## Related Documentation

- `connector-modal-payload-fixes.md` - Previous fix that removed `bucketType` from payload
- `s3-ingest-connector-architecture.md` - Overall S3 connector architecture

## Notes

- The `bucketType` field should always be sent as either "new" or "existing"
- The frontend UI enforces this through the bucket type selection step
- Backend validation provides an additional safety layer
- This fix ensures proper separation between bucket creation and bucket validation logic
