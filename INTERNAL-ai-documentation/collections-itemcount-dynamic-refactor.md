# Collections itemCount Dynamic Refactor

## Overview

This document describes the refactoring of the Collections `itemCount` functionality from a cached counter approach to a dynamic count approach. The cached `itemCount` attribute was unreliable due to race conditions and partial failures, causing the count to drift from the actual number of items in collections.

## Problem Statement

The previous implementation maintained an `itemCount` attribute in the collection metadata that was incremented when items were added and decremented when items were removed. This approach had a critical flaw:

**Scenario:**

1. User adds item to collection
2. `CollectionItemModel` is successfully saved to DynamoDB
3. System attempts to increment `CollectionModel.itemCount`
4. Increment operation fails (network issue, throttling, etc.)
5. Result: Item exists but count is wrong

Over time, these partial failures caused `itemCount` to drift from the actual number of items, leading to incorrect counts displayed in the UI.

## Solution

Compute `itemCount` dynamically at read time by querying the actual number of `CollectionItemModel` entries for that collection in DynamoDB. This ensures the count is always accurate regardless of past failures.

## Changes Implemented

### 1. lambdas/common_libraries/collections_utils.py

**New Functions Added:**

- `get_collection_item_count(table, collection_pk)` - Main utility function that counts items in a collection

  - Uses DynamoDB `query()` with `Select='COUNT'` for efficiency
  - Queries both `ASSET#` and `ITEM#` SK prefixes
  - Handles pagination for large collections (>1MB of key data)
  - Returns -1 on error to distinguish from legitimate zero counts
  - Logs errors and emits CloudWatch metrics on failures

- `_count_items_with_prefix(table, pk_value, sk_prefix)` - Internal helper function
  - Performs the actual DynamoDB count query for a specific SK prefix
  - Handles pagination via `LastEvaluatedKey`
  - Returns -1 on error

### 2. lambdas/api/collections_api/handlers/collections_ID_get.py

**Changes:**

- Added import for `get_collection_item_count` from `collections_utils`
- Added DynamoDB table resource initialization for count queries
- Modified response to use dynamic count instead of cached `itemCount`

**Before:**

```python
collection_dict = {
    ...
    "itemCount": collection.itemCount,  # Cached value
    ...
}
```

**After:**

```python
# Get dynamic item count (returns -1 on error)
dynamic_item_count = get_collection_item_count(collections_table, collection.PK)
collection_dict = {
    ...
    "itemCount": dynamic_item_count,  # Dynamic count
    ...
}
```

### 3. lambdas/api/collections_api/handlers/collections_get.py

**Changes:**

- Added import for `get_collection_item_count` from `collections_utils`
- Added DynamoDB table resource initialization
- Modified `_model_to_dict()` helper function to compute dynamic count for each collection

**Key Change in `_model_to_dict()`:**

```python
def _model_to_dict(collection) -> dict[str, Any]:
    # Get dynamic item count (returns -1 on error)
    dynamic_item_count: int = get_collection_item_count(collections_table, collection.PK)

    item_dict = {
        ...
        "itemCount": dynamic_item_count,
        ...
    }
```

### 4. lambdas/api/collections_api/handlers/collections_ID_items_post.py

**Changes:**

- Removed `CollectionModel.itemCount.add(len(added_items))` operation
- Kept `CollectionModel.updatedAt.set(current_timestamp)` update
- Added comment explaining itemCount is now computed dynamically

### 5. lambdas/api/collections_api/handlers/collections_ID_items_ID_delete.py

**Changes:**

- Removed `CollectionModel.itemCount.add(-1)` operation
- Kept `CollectionModel.updatedAt.set(current_timestamp)` update
- Added comment explaining itemCount is no longer maintained here

### 6. lambdas/api/collections_api/db_models.py

**Changes:**

- Added deprecation comment to `itemCount` attribute explaining it's no longer maintained
- Attribute retained for backward compatibility with existing data

### 7. lambdas/api/settings/db_models.py

**Changes:**

- Added similar deprecation comment to `itemCount` attribute in the settings module's CollectionModel

## Design Decisions

### Why Dynamic Count Instead of Fixing the Increment Logic?

1. **Simplicity**: Dynamic counting eliminates the need for complex transactional logic
2. **Reliability**: Count is always accurate, regardless of past failures
3. **No Migration Required**: Existing data doesn't need to be corrected
4. **Reduced Complexity**: Fewer code paths to maintain and test

### Why Return -1 on Error?

- Distinguishes errors from legitimate zero counts
- Allows UI to handle error cases appropriately
- Maintains backward compatibility with integer type

### Why Query Both ASSET# and ITEM# Prefixes?

- Historical data may use `ITEM#` prefix
- Newer data uses `ASSET#` prefix with clip boundary support
- Ensures accurate counts across all data formats

### Performance Considerations

- `Select='COUNT'` minimizes data transfer (only returns count, not items)
- Pagination handles large collections (>1MB of key data)
- Expected latency: 10-50ms for typical collections
- CloudWatch metrics track query failures for monitoring

## API Response Format

The API response format remains unchanged:

```json
{
  "success": true,
  "data": {
    "id": "collection_123",
    "name": "My Collection",
    "itemCount": 42,  // Now dynamically computed
    ...
  }
}
```

## Error Handling

When the dynamic count query fails:

1. Error is logged with full context (collection_id, error details)
2. CloudWatch metric `CollectionItemCountQueryFailures` is emitted
3. Function returns -1
4. API passes -1 through to response (UI can interpret as error)

## Testing

Unit tests were added to `tests/common_libraries/test_collections_utils.py`:

- `test_count_empty_collection` - Returns 0 for collection with no items
- `test_count_single_asset_item` - Returns 1 for collection with one ASSET# item
- `test_count_single_item_item` - Returns 1 for collection with one ITEM# item
- `test_count_multiple_items` - Returns correct count for multiple items
- `test_count_mixed_prefixes` - Returns correct count for both ASSET# and ITEM# prefixes
- `test_count_pagination` - Returns correct count when results exceed 1MB
- `test_count_dynamodb_error` - Returns -1 when DynamoDB query fails
- `test_count_nonexistent_collection` - Returns 0 for collection ID with no items

## Backward Compatibility

- API response format unchanged
- Frontend requires no changes
- Existing `itemCount` attribute retained in schema
- No breaking changes to any interface

## Rollback Plan

If issues are detected:

1. Revert handler changes commit to use cached `itemCount` again
2. The cached `itemCount` values still exist (though potentially inaccurate)
3. No data loss occurs since the attribute was never deleted
