# Upload Path Validation and Key Construction Fixes

## Overview

Fixed critical path validation and S3 key construction issues in the upload Lambda that caused prefix duplication, rejected valid empty paths, and mishandled multiple-prefix connectors.

## Issues Resolved

### 1. Duplicated Prefixes in S3 Keys

**Problem**: When `safe_path` already included an allowed prefix (e.g., "uploads/videos"), the code prepended the prefix again, creating keys like "uploads/uploads/videos/file.mp4".

**Solution**: Detect whether `safe_path` starts with any allowed prefix before key construction. If it does, use `safe_path` directly without prepending.

### 2. Empty Path Rejection Under Restricted Connectors

**Problem**: Uploads to the root of an allowed prefix (empty path) were incorrectly rejected when prefix restrictions existed.

**Solution**: When `safe_path` is empty and restrictions exist, set `effective_path` to the first allowed prefix and allow the upload.

### 3. Multiple-Prefix Connector Mishandling

**Problem**: Connectors with multiple allowed prefixes (e.g., ["uploads/", "media/"]) always used the first prefix, breaking user intent.

**Solution**: Iterate through all allowed prefixes to find which one `safe_path` starts with, and use that matched prefix for key construction.

### 4. Validation of Raw Path Instead of Effective Path

**Problem**: Validation checked the raw `safe_path` instead of the effective path (base prefix + relative path).

**Solution**: Compute `effective_path` by combining the matched prefix with `safe_path` when needed, then validate the `effective_path`.

## Implementation Details

### Path Resolution Logic (Lines 416-439)

```python
# Determine effective path and matched prefix
effective_path = safe_path
matched_prefix = None

if allowed_prefixes:
    # Check if safe_path already starts with any allowed prefix
    for prefix in allowed_prefixes:
        normalized_prefix = normalize_prefix(prefix)
        normalized_safe_path = normalize_prefix(safe_path) if safe_path else ""
        if normalized_safe_path.startswith(normalized_prefix):
            matched_prefix = prefix.rstrip("/")
            effective_path = safe_path
            break

    # If no match found and safe_path is not empty, prepend first allowed prefix
    if matched_prefix is None and safe_path:
        matched_prefix = allowed_prefixes[0].rstrip("/")
        effective_path = f"{matched_prefix}/{safe_path}"

    # If safe_path is empty, use first allowed prefix as the effective path
    if not safe_path:
        matched_prefix = allowed_prefixes[0].rstrip("/")
        effective_path = matched_prefix
```

### Key Construction Logic (Lines 462-472)

```python
# Construct the object key from effective_path (avoiding duplication)
if allowed_prefixes and matched_prefix:
    # If safe_path already contained the prefix, use it directly
    if safe_path and safe_path.startswith(matched_prefix):
        key = f"{safe_path}/{request.filename}"
    else:
        # Use effective_path which includes the matched prefix
        key = f"{effective_path}/{request.filename}"
else:
    # No prefix restrictions
    key = f"{safe_path}/{request.filename}" if safe_path else request.filename
```

## Test Scenarios

### Scenario 1: Path Already Contains Prefix

- **Input**: `safe_path = "uploads/videos"`, `allowed_prefixes = ["uploads/"]`
- **Result**: `key = "uploads/videos/file.mp4"` (no duplication)

### Scenario 2: Empty Path with Restrictions

- **Input**: `safe_path = ""`, `allowed_prefixes = ["uploads/"]`
- **Result**: `effective_path = "uploads"`, `key = "uploads/file.mp4"` (allowed)

### Scenario 3: Multiple Prefixes

- **Input**: `safe_path = "media/audio"`, `allowed_prefixes = ["uploads/", "media/"]`
- **Result**: `matched_prefix = "media"`, `key = "media/audio/file.mp4"`

### Scenario 4: Path Without Prefix

- **Input**: `safe_path = "subfolder"`, `allowed_prefixes = ["uploads/"]`
- **Result**: `effective_path = "uploads/subfolder"`, `key = "uploads/subfolder/file.mp4"`

### Scenario 5: No Restrictions

- **Input**: `safe_path = "any/path"`, `allowed_prefixes = []`
- **Result**: `key = "any/path/file.mp4"`

## Files Modified

- `/lambdas/api/assets/upload/post_upload/index.py` (lines 413-472)

## Testing Recommendations

1. Test uploads with paths that include allowed prefixes
2. Test uploads to root (empty path) with restricted connectors
3. Test connectors with multiple allowed prefixes
4. Test path validation rejections for unauthorized paths
5. Verify CloudWatch logs show correct `effective_path` and `matched_prefix` values
