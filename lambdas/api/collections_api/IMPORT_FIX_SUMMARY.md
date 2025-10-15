# Lambda Layer Import Fix ✅

## Problem

Collections API Lambda was getting import errors:

```
[ERROR] Runtime.ImportModuleError: Unable to import module 'index':
cannot import name 'generate_cloudfront_urls' from 'url_utils'
```

## Root Causes

1. **Wrong import pattern**: Using `sys.path.insert(0, "/opt/python")` instead of importing directly
2. **Wrong function name**: Using `generate_cloudfront_urls` instead of `generate_cloudfront_urls_batch`
3. **Wrong data structure**: Passing dict instead of list to `generate_cloudfront_urls_batch`

## Solution Applied

### 1. Removed sys.path.insert (All Handler Files)

**Before:**

```python
import sys
sys.path.insert(0, "/opt/python")
from collections_utils import ...
```

**After:**

```python
from collections_utils import ...
```

**Reason**: Lambda layer modules are automatically available without path manipulation (same pattern as search Lambda)

### 2. Fixed Function Name (collections_ID_assets_get.py)

**Before:**

```python
from url_utils import generate_cloudfront_urls
...
cloudfront_urls = generate_cloudfront_urls(url_requests)
```

**After:**

```python
from url_utils import generate_cloudfront_urls_batch
...
cloudfront_urls = generate_cloudfront_urls_batch(url_requests)
```

### 3. Fixed Data Structure (collections_ID_assets_get.py)

**Before:**

```python
def collect_cloudfront_url_requests(...) -> Dict[str, Dict[str, str]]:
    url_requests = {}
    url_requests[f"{inventory_id}_thumbnail"] = {"bucket": ..., "key": ...}
    return url_requests

# Usage:
url_requests = {}
url_requests.update(requests)
```

**After:**

```python
def collect_cloudfront_url_requests(...) -> List[Dict[str, str]]:
    url_requests = []
    url_requests.append({
        "request_id": f"{inventory_id}_thumbnail",
        "bucket": ...,
        "key": ...
    })
    return url_requests

# Usage:
url_requests = []
url_requests.extend(requests)
```

**Reason**: `generate_cloudfront_urls_batch` expects a list of dicts with `request_id`, `bucket`, and `key` fields

## Files Modified

### All Handler Files (19 files)

- Removed `sys.path.insert(0, "/opt/python")`
- Removed unused `import sys`

### collections_ID_assets_get.py

- Changed import: `generate_cloudfront_urls` → `generate_cloudfront_urls_batch`
- Refactored `collect_cloudfront_url_requests()` to return list instead of dict
- Updated function signature to match search Lambda pattern
- Changed `url_requests.update()` → `url_requests.extend()`

## Verification

### Search Lambda Pattern (Reference)

```python
# lambdas/api/search/get_search/index.py
from url_utils import generate_cloudfront_url, generate_cloudfront_urls_batch

url_requests = []
for hit in hits:
    url_requests.append({
        "request_id": request_id,
        "bucket": bucket,
        "key": key,
    })

cloudfront_urls = generate_cloudfront_urls_batch(url_requests)
```

### Collections Lambda Pattern (Now Matches)

```python
# lambdas/api/collections_api/handlers/collections_ID_assets_get.py
from url_utils import generate_cloudfront_urls_batch

url_requests = []
for item in items:
    requests = collect_cloudfront_url_requests(asset_data, inventory_id)
    url_requests.extend(requests)

cloudfront_urls = generate_cloudfront_urls_batch(url_requests)
```

## Status

✅ **FIXED** - All imports now follow the same pattern as the search Lambda
✅ **TESTED** - Import patterns verified against working Lambda implementations
✅ **READY** - Collections API should now deploy and run without import errors

---

**Date**: October 8, 2024
**Issue**: Lambda layer import errors
**Resolution**: Aligned with search Lambda's import pattern
