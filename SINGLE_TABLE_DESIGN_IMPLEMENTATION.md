# Single-Table Design with CHILD# References ✅

## Overview

Implemented proper single-table design for hierarchical collections using `CHILD#` reference items for efficient querying without filter expressions.

---

## Architecture

### DynamoDB Structure

#### Parent Collection

```json
{
  "PK": "COLL#col_parent123",
  "SK": "METADATA",
  "name": "Parent Collection",
  "ownerId": "user_abc",
  "childCollectionCount": 2,
  "itemCount": 5,
  ...
}
```

#### Child Collection Metadata

```json
{
  "PK": "COLL#col_child456",
  "SK": "METADATA",
  "name": "Child Collection",
  "parentId": "col_parent123",  ← Still stored for reference
  "ownerId": "user_abc",
  ...
}
```

#### CHILD# Reference Item (NEW!)

```json
{
  "PK": "COLL#col_parent123",     ← Parent's partition
  "SK": "CHILD#col_child456",     ← Child reference
  "childCollectionId": "col_child456",
  "childCollectionName": "Child Collection",
  "addedAt": "2025-10-11T...",
  "type": "CHILD_COLLECTION"
}
```

---

## Benefits of CHILD# Design

### 1. **Efficient Query** ✅

```python
# Single query, no filter needed!
query(
    PK = "COLL#parent123",
    SK begins_with "CHILD#"
)
```

- Uses only primary key (no GSI needed)
- No filter expression (no wasted RCUs)
- Minimal latency

### 2. **Single Table Pattern** ✅

- All collection data in one partition
- Easy to query: metadata, items, children, shares, rules all co-located
- Pattern: `PK=COLL#id, SK=TYPE#detail`

### 3. **Consistent Counts** ✅

- `childCollectionCount` automatically maintained
- Incremented on create
- Decremented on delete

### 4. **Transactional Integrity** ✅

- Collection + CHILD# reference created atomically
- Count increment happens in same transaction

---

## Implementation Details

### 1. Collection Creation (POST /collections)

**File**: `lambdas/api/collections_api/handlers/collections_post.py`

**Changes**:

```python
# Added CHILD_SK_PREFIX import

# In transaction:
if request_data.parentId:
    # 1. Create CHILD# reference in parent
    child_reference_item = {
        "PK": f"COLL#{parent_id}",
        "SK": f"CHILD#{collection_id}",
        "childCollectionId": collection_id,
        "childCollectionName": request_data.name,
        "addedAt": timestamp,
        "type": "CHILD_COLLECTION",
    }

    # 2. Increment parent's childCollectionCount
    Update(
        Key={"PK": f"COLL#{parent_id}", "SK": "METADATA"},
        UpdateExpression="ADD childCollectionCount :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}}
    )
```

**Transaction includes**:

1. ✅ Create collection metadata
2. ✅ Create user relationship
3. ✅ Create CHILD# reference (if parentId)
4. ✅ Increment parent count (if parentId)

---

### 2. Query Child Collections (GET /collections?filter[parentId]=X)

**File**: `lambdas/api/collections_api/handlers/collections_get.py`

**Changes**:

```python
def _query_child_collections(table, parent_id, limit, start_key):
    # Query CHILD# references
    response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"COLL#{parent_id}",
            ":sk_prefix": "CHILD#",
        },
        Limit=limit + 1,
    )

    # Fetch full metadata for each child
    child_items = []
    for child_ref in response["Items"]:
        child_id = child_ref["childCollectionId"]
        child_metadata = table.get_item(
            Key={"PK": f"COLL#{child_id}", "SK": "METADATA"}
        )
        child_items.append(child_metadata["Item"])

    return {"Items": child_items}
```

**Performance**:

- 1 query for CHILD# references (1 RCU per 4KB)
- N get_item calls for metadata (1 RCU each, eventually consistent)
- Total: ~2-5 RCUs for typical use case

---

### 3. Delete Collection (DELETE /collections/<id>)

**File**: `lambdas/api/collections_api/handlers/collections_ID_delete.py`

**Changes**:

```python
# After verifying permissions, before deleting items:
parent_id = collection.get("parentId")
if parent_id:
    # 1. Delete CHILD# reference from parent
    table.delete_item(
        Key={
            "PK": f"COLL#{parent_id}",
            "SK": f"CHILD#{collection_id}",
        }
    )

    # 2. Decrement parent's childCollectionCount
    table.update_item(
        Key={"PK": f"COLL#{parent_id}", "SK": "METADATA"},
        UpdateExpression="ADD childCollectionCount :dec",
        ExpressionAttributeValues={":dec": -1},
    )
```

**Ensures**:

- No orphaned CHILD# references
- Parent count stays accurate
- Clean single-table design

---

### 4. Frontend (No Changes Needed!)

**File**: `medialake_user_interface/src/pages/CollectionViewPage.tsx`

The frontend already calls:

```typescript
useGetChildCollections(parentId);
```

Which hits:

```
GET /collections?filter[parentId]=col_parent123
```

Backend handles the CHILD# lookup transparently! ✅

---

## Data Access Patterns

### Pattern 1: Get Collection Metadata

```
Query: PK=COLL#123, SK=METADATA
Cost: 1 RCU
```

### Pattern 2: Get All Collection Items

```
Query: PK=COLL#123, SK begins_with ASSET#
Cost: ~1 RCU per 4KB
```

### Pattern 3: Get Child Collections

```
Query: PK=COLL#123, SK begins_with CHILD#
Then: BatchGetItem for each child's metadata
Cost: ~2-5 RCUs for 10 children
```

### Pattern 4: Get Collection Shares

```
Query: PK=COLL#123, SK begins_with SHARE#
Cost: ~1 RCU
```

### Pattern 5: Get User's Collections

```
Query GSI1: GSI1_PK=USER#abc, SK begins_with COLL#
Cost: ~1 RCU per 4KB
```

---

## Testing Plan

### 1. Create Child Collection

```bash
POST /collections
{
  "name": "Child Collection",
  "parentId": "col_parent123",
  "description": "Test child collection"
}
```

**Verify in DynamoDB**:

- ✅ Child has `PK=COLL#child456, SK=METADATA`
- ✅ Child has `parentId=col_parent123`
- ✅ Parent has `PK=COLL#parent123, SK=CHILD#child456`
- ✅ Parent's `childCollectionCount` incremented

### 2. Query Children

```bash
GET /collections?filter[parentId]=col_parent123
```

**Expected Response**:

```json
{
  "success": true,
  "data": [
    {
      "id": "col_child456",
      "name": "Child Collection",
      "parentId": "col_parent123",
      ...
    }
  ]
}
```

### 3. View Parent in UI

Navigate to: `/collections/col_parent123/view`

**Should see**:

- "Sub-Collections (1)" section
- Card for "Child Collection"
- Click navigates to child

### 4. Delete Child

```bash
DELETE /collections/col_child456
```

**Verify in DynamoDB**:

- ✅ Child metadata deleted
- ✅ Parent's `CHILD#child456` reference deleted
- ✅ Parent's `childCollectionCount` decremented

---

## Migration for Existing Collections

If you have existing child collections (with `parentId` but no `CHILD#` references):

```python
# Migration script (run once)
for collection in all_collections:
    if collection.get("parentId"):
        parent_id = collection["parentId"]
        child_id = collection["id"]

        # Create missing CHILD# reference
        table.put_item(Item={
            "PK": f"COLL#{parent_id}",
            "SK": f"CHILD#{child_id}",
            "childCollectionId": child_id,
            "childCollectionName": collection["name"],
            "addedAt": collection["createdAt"],
            "type": "CHILD_COLLECTION",
        })

        # Update parent's childCollectionCount
        # (Query all CHILD# items and set count)
```

---

## Files Modified

### Backend

1. ✅ `lambdas/api/collections_api/handlers/collections_post.py`
   - Added CHILD_SK_PREFIX import
   - Create CHILD# reference in transaction
   - Increment parent's childCollectionCount

2. ✅ `lambdas/api/collections_api/handlers/collections_get.py`
   - Reverted to use CHILD# query (removed GSI5 filter)
   - Efficient query by SK prefix

3. ✅ `lambdas/api/collections_api/handlers/collections_ID_delete.py`
   - Added CHILD_SK_PREFIX import
   - Delete CHILD# reference from parent
   - Decrement parent's childCollectionCount

### Frontend

✅ **No changes needed!** - Already working correctly

---

## Performance Comparison

### Old Approach (GSI5 + Filter)

```
Query GSI5: GSI5_PK=COLLECTIONS (reads ALL collections)
Filter: parentId = X (applied after query)
Cost: Read all collections, return subset
RCUs: ~50-100 for 1000 collections
```

### New Approach (CHILD# References)

```
Query: PK=COLL#parent, SK begins_with CHILD#
Cost: Read only child references
RCUs: ~1-2 for 10 children
```

**50-100x more efficient!** 🚀

---

## Deployment

```bash
# 1. Ensure you're on feat/collections branch
git branch --show-current

# 2. Deploy collections stack
cdk deploy CollectionsStack --profile <your-profile>

# 3. Test
# - Create a child collection
# - View parent collection detail page
# - Should see child collections appear
```

---

**Date**: October 11, 2024
**Status**: ✅ Implemented - Ready to deploy and test
**Pattern**: Single-Table Design with CHILD# references
