# Upload Lambda Server-Side Path Validation Implementation

## Overview

Added server-side path validation to the upload Lambda to enforce connector `objectPrefix` restrictions, preventing unauthorized uploads outside whitelisted paths. The implementation mirrors the established pattern from the S3 Explorer Lambda for consistency.

## Changes Implemented

### 1. Type Imports Updated

- Added `List` to typing imports for type hints on helper functions

### 2. Three Helper Functions Added

#### `normalize_prefix(prefix: str) -> str`

- Normalizes prefix strings for consistent formatting
- Returns empty string for None/empty inputs
- Ensures single trailing slash for non-empty prefixes
- Decorated with `@tracer.capture_method` for X-Ray tracing

#### `parse_object_prefixes(object_prefix) -> List[str]`

- Parses `objectPrefix` from connector configuration
- Handles both string (legacy) and list (new) formats
- Returns list of normalized prefixes or empty list if no restrictions
- Decorated with `@tracer.capture_method` for X-Ray tracing

#### `validate_prefix_access(requested_path: str, allowed_prefixes: List[str]) -> bool`

- Validates requested path against allowed prefix boundaries
- Returns `True` if no restrictions exist (allow all)
- Returns `True` if path starts with any allowed prefix
- Returns `False` if path is outside all allowed prefixes
- Decorated with `@tracer.capture_method` for X-Ray tracing

### 3. Lambda Handler Updates

#### Prefix Parsing

- After retrieving connector details, parses `objectPrefix` using `parse_object_prefixes()`
- Adds debug logging showing parsed prefixes

#### Path Validation

- After path normalization, validates against allowed prefixes
- If validation fails:
  - Logs warning with connector ID, requested path, and allowed prefixes
  - Adds `UploadPathValidationFailures` metric
  - Raises `APIError` with 403 status and detailed message including allowed prefixes
- If validation passes:
  - Logs info message
  - Adds `UploadPathValidationSuccess` metric

#### Key Construction

- Uses first prefix from parsed `allowed_prefixes` list
- Simplified by removing redundant `strip("/")` call (normalization handles this)
- Maintains backward compatibility with connectors lacking prefix restrictions

#### Structured Logging Context

- Added `allowed_prefixes_count` - number of allowed prefixes
- Added `path_validation_required` - boolean indicating if validation is required

## Backward Compatibility

- **No `objectPrefix` configured**: Returns empty list, validation skipped, all paths allowed
- **String `objectPrefix`**: Parsed into single-item list, validation works as expected
- **List `objectPrefix`**: Parsed into list, validation checks against all prefixes
- Existing upload flow unchanged when no prefixes are configured

## Security Benefits

- Prevents uploads outside whitelisted paths at the server level
- Provides clear error messages with allowed prefixes for debugging
- Adds CloudWatch metrics for monitoring validation success/failures
- Enables X-Ray tracing for all validation steps

## Testing Considerations

- Test with no `objectPrefix` configured (should allow all paths)
- Test with string `objectPrefix` (legacy format)
- Test with list `objectPrefix` (new format)
- Test validation failures (paths outside allowed prefixes)
- Test validation success (paths within allowed prefixes)
- Verify metrics: `UploadPathValidationSuccess` and `UploadPathValidationFailures`
- Verify structured logging includes prefix information
