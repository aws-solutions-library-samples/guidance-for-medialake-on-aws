# Connector Modal Payload Fixes

## Overview

Fixed four critical issues in the ConnectorModal component related to payload handling, field normalization, and API contract alignment.

## Changes Implemented

### 1. Integration Method Normalization (Edit Mode)

**Issue**: Editing mode did not show S3 Integration Method value and could send undefined.

**Fix**:

- Added normalization logic in the `useEffect` hook for editing mode
- Reads from either `editingConnector.integrationMethod` or `editingConnector.configuration?.s3IntegrationMethod`
- Updates configuration state with the normalized value
- Ensures the disabled Select in edit mode displays the correct value

**Location**: Lines 152-156

### 2. Standardized on `s3IntegrationMethod`

**Issue**: Request payload redundantly included both `integrationMethod` and `s3IntegrationMethod`.

**Fix**:

- Changed UI state to use `configuration.s3IntegrationMethod` consistently
- Updated all Select components to read/write `s3IntegrationMethod`
- Sanitized payload before sending by destructuring out `integrationMethod`
- Default initialization for new connectors sets `s3IntegrationMethod` to `"eventbridge"`
- Validation logic updated to check `s3IntegrationMethod`

**Locations**:

- Initial state: Line 183
- Edit mode Select: Line 460
- Create mode Select: Lines 508-514
- Validation: Line 284
- Save logic: Lines 297-317

### 3. Conditional Region Inclusion

**Issue**: Region could be sent as empty string for new buckets after hiding region requirement.

**Fix**:

- Created conditional `newBucketExtras` object
- Only includes `region` when `awsRegion.trim()` is truthy
- Empty strings are no longer sent in the payload

**Location**: Lines 301-303

### 4. Removed `bucketType` from Payload

**Issue**: `bucketType` was included in payload though not part of the typed API contract.

**Fix**:

- Removed all `bucketType` spreads from payload construction
- `bucketType` remains as local UI state for form logic
- Payload no longer includes `{ bucketType: 'new' }` or `{ bucketType: 'existing' }`

**Location**: Lines 305-319

## Testing Recommendations

1. **Edit Mode**: Verify integration method displays correctly when editing existing connectors
2. **Create Mode**: Verify new connectors default to "eventbridge" integration method
3. **New Bucket**: Verify region is optional and not sent as empty string
4. **Payload Structure**: Verify API requests only contain expected fields per `CreateConnectorRequest` type

## Files Modified

- `medialake_user_interface/src/features/settings/connectors/components/ConnectorModal.tsx`

## API Contract Alignment

The changes ensure the payload matches the `CreateConnectorRequest` type definition:

- Uses `s3IntegrationMethod` (not `integrationMethod`)
- Conditionally includes `region` only when provided
- Excludes UI-only fields like `bucketType`
