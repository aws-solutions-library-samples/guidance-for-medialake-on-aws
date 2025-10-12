# Child Collections Fix 🔧

## Issue Identified

Child collections weren't appearing even though they existed in DynamoDB with correct `parentId` values.

### Root Cause

The backend `_query_child_collections()` function was querying for `CHILD#` reference items:

```python
# OLD (Broken):
"KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
"ExpressionAttributeValues": {
    ":pk": f"COLLECTION#{parent_id}",
    ":sk_prefix": "CHILD#",  # ❌ These items don't exist!
}
```

**Problem**: When creating a child collection, only the `parentId` field is set in the child's metadata. No bidirectional `CHILD#` reference items are created in the parent's partition.

---

## The Fix

### Backend Change

**File**: `lambdas/api/collections_api/handlers/collections_get.py`

Changed `_query_child_collections()` to query using GSI5 with a filter expression:

```python
# NEW (Fixed):
query_params = {
    "IndexName": "GSI5",
    "KeyConditionExpression": "GSI5_PK = :gsi_pk",
    "FilterExpression": "parentId = :parent_id AND SK = :sk",
    "ExpressionAttributeValues": {
        ":gsi_pk": "COLLECTIONS",
        ":parent_id": parent_id,
        ":sk": "METADATA",
    },
    "Limit": limit + 1,
}
```

**How it works**:

1. Query all collections using GSI5 (`GSI5_PK = "COLLECTIONS"`)
2. Filter for items where:
   - `parentId` = the parent collection's ID
   - `SK = "METADATA"` (to get only collection metadata, not items/shares/etc.)
3. Return the matching child collections

---

### Frontend Changes

**File**: `medialake_user_interface/src/pages/CollectionViewPage.tsx`

- Removed debug logging
- Removed debug info box

The frontend code was already correct - it just needed the backend to return data!

---

## Deployment Steps

```bash
# 1. Navigate to project root
cd /Users/raverrr/codebase/gitlab-guidance-for-medialake-on-aws

# 2. Verify you're on feat/collections branch
git branch --show-current  # Should show: feat/collections

# 3. Deploy the updated Lambda
cdk deploy CollectionsStack --profile <your-profile>

# Or if you need to deploy all:
cdk deploy --all --profile <your-profile>
```

---

## Testing

After deployment:

1. **Navigate** to `/collections/{parentId}/view`
2. **You should see**:
   - "Sub-Collections (1)" section header
   - A card for the child collection "asdf"
   - Card shows:
     - 📁 Icon + Name
     - Description (if any)
     - "0 items" chip
   - Hover effect (card lifts up)
3. **Click** the child collection card
   - Should navigate to `/collections/col_ccc323d6/view`

---

## Example DynamoDB Items

### Parent Collection

```json
{
  "PK": "COLL#col_31261a7a",
  "SK": "METADATA",
  "name": "Parent Collection",
  "childCollectionCount": 1,
  "GSI5_PK": "COLLECTIONS",
  "GSI5_SK": "2025-10-11T..."
}
```

### Child Collection

```json
{
  "PK": "COLL#col_ccc323d6",
  "SK": "METADATA",
  "name": "asdf",
  "parentId": "col_31261a7a", // ✅ This is what we query by!
  "GSI5_PK": "COLLECTIONS",
  "GSI5_SK": "2025-10-11T02:25:59..."
}
```

---

## Files Modified

### Backend

1. ✅ `lambdas/api/collections_api/handlers/collections_get.py`
   - Updated `_query_child_collections()` to use GSI5 + filter

### Frontend

2. ✅ `medialake_user_interface/src/pages/CollectionViewPage.tsx`
   - Removed debug code

---

## Performance Note

Using GSI5 with `FilterExpression` means:

- **Query**: Fast - uses index
- **Filter**: Applied after query, before returning results
- **Cost**: Minimal - only reads collections (metadata items only)
- **Scale**: Efficient for reasonable numbers of collections (<1000)

For massive scale (10,000+ collections), consider:

- Adding a dedicated GSI on `parentId` field
- Or maintaining bidirectional references with `CHILD#` items

---

**Date**: October 11, 2024
**Status**: ✅ Fixed - Ready to deploy
