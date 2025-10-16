# Import Fixes Required - Collections API

## Problem

Runtime error: `cannot import name 'PERM_SK_PREFIX' from 'collections_utils'`

## Root Cause

Some handlers were importing constants that didn't exist in `collections_utils.py`, and several handlers still use the old boto3 approach instead of PynamoDB.

## Fixes Applied ✅

### 1. Added Missing Constants to `collections_utils.py`

```python
# Added to lambdas/common_libraries/collections_utils.py
ITEM_SK_PREFIX = "ITEM#"
ASSET_SK_PREFIX = "ASSET#"
RULE_SK_PREFIX = "RULE#"
PERM_SK_PREFIX = "PERM#"
```

### 2. Updated Handlers to Import from `collections_utils`

- ✅ `collections_ID_share_post.py` - Imports `PERM_SK_PREFIX`
- ✅ `collections_ID_share_get.py` - Imports `PERM_SK_PREFIX`
- ✅ `collections_ID_share_ID_delete.py` - Imports `PERM_SK_PREFIX` and uses PynamoDB
- ✅ `collections_ID_rules_post.py` - Imports `RULE_SK_PREFIX` and uses PynamoDB

## Still Need Fixing ⚠️

The following 5 handlers still use the old `register_route(app, dynamodb, table_name)` signature and need to be converted to PynamoDB:

### 1. `collections_ID_rules_get.py`

**Current:** Uses `dynamodb.Table` and boto3
**Needs:** PynamoDB with `RuleModel.query()`

```python
# TODO: Change from
def register_route(app, dynamodb, table_name):
    table = dynamodb.Table(table_name)
    response = table.query(...)

# To:
def register_route(app):
    for rule in RuleModel.query(
        f"{COLLECTION_PK_PREFIX}{collection_id}",
        RuleModel.SK.startswith(RULE_SK_PREFIX)
    ):
        ...
```

### 2. `collections_ID_rules_ID_put.py`

**Current:** Uses `table.update_item()`
**Needs:** PynamoDB with `RuleModel.get()` and `.update()`

```python
# TODO: Change from
def register_route(app, dynamodb, table_name):
    table.update_item(Key={...}, UpdateExpression=...)

# To:
def register_route(app):
    rule = RuleModel.get(pk, sk)
    rule.update(actions=[
        RuleModel.name.set(request_data["name"]),
        RuleModel.updatedAt.set(timestamp)
    ])
```

### 3. `collections_ID_rules_ID_delete.py`

**Current:** Uses `table.delete_item()`
**Needs:** PynamoDB with `RuleModel.get()` and `.delete()`

```python
# TODO: Change from
def register_route(app, dynamodb, table_name):
    table.delete_item(Key={...})

# To:
def register_route(app):
    rule = RuleModel.get(pk, sk)
    rule.delete()
```

### 4. `collections_ID_assets_get.py` ⚠️ COMPLEX

**Current:** Uses boto3 for DynamoDB, OpenSearch, and CloudFront URL generation
**Needs:** Full PynamoDB conversion

**Status:** This is the most complex handler with:

- DynamoDB queries for collection items
- OpenSearch queries for asset metadata
- CloudFront URL generation
- Clip boundary handling

### 5. `collections_shared_with_me_get.py`

**Current:** Uses boto3 GSI query
**Needs:** PynamoDB with `UserRelationshipModel` GSI query

```python
# TODO: Change from
def register_route(app, dynamodb, table_name):
    table.query(IndexName="UserCollectionsGSI", ...)

# To:
def register_route(app):
    # Query using GSI - Note: May need to scan if GSI not properly configured in model
    for relationship in UserRelationshipModel.scan(...):
        ...
```

## Quick Fix Priority

### CRITICAL (Blocks Deployment):

1. ✅ Add constants to `collections_utils.py` - **DONE**
2. ✅ Fix `PERM_SK_PREFIX` imports - **DONE**
3. ⚠️ Update `collections_ID_rules_*` handlers (3 files) - **IN PROGRESS**

### IMPORTANT (Should Fix Soon):

4. ⚠️ Update `collections_shared_with_me_get.py`
5. ⚠️ Update `collections_ID_assets_get.py` (most complex)

## Deployment Strategy

### Option A: Deploy Now with Minimal Fixes ✅ RECOMMENDED

1. Deploy with the constant fixes already applied
2. Test collections creation, sharing, and deletion
3. **Known limitations**: Some rule operations and "shared with me" won't work yet

### Option B: Complete All Fixes Before Deploy

1. Convert remaining 5 handlers to PynamoDB
2. Test all functionality
3. Deploy complete solution

**Recommendation:** Option A - Get the critical TransactWrite fixes deployed first, then fix remaining handlers in next iteration.

## Testing After Deployment

Test these critical paths first:

1. ✅ `POST /collections` with parentId (TransactWrite fix)
2. ✅ `POST /collections/{id}/share` (TransactWrite fix)
3. ✅ `DELETE /collections/{id}/share/{userId}` (PynamoDB transactions)
4. ⚠️ `POST /collections/{id}/rules` - Should work now
5. ⚠️ `GET /collections/{id}/rules` - Will fail (not converted yet)
6. ⚠️ `PUT /collections/{id}/rules/{ruleId}` - Will fail (not converted yet)
7. ⚠️ `DELETE /collections/{id}/rules/{ruleId}` - Will fail (not converted yet)
8. ⚠️ `GET /collections/shared-with-me` - Will fail (not converted yet)

## Files Changed Summary

### Modified ✅:

- `lambdas/common_libraries/collections_utils.py` - Added 4 new constants
- `lambdas/api/collections_api/handlers/collections_post.py` - Fixed TransactWrite
- `lambdas/api/collections_api/handlers/collections_ID_share_post.py` - Fixed TransactWrite
- `lambdas/api/collections_api/handlers/collections_ID_share_ID_delete.py` - Full PynamoDB conversion
- `lambdas/api/collections_api/handlers/collections_ID_share_get.py` - Import fix
- `lambdas/api/collections_api/handlers/collections_ID_rules_post.py` - Full PynamoDB conversion

### Still Need Updates ⚠️:

- `lambdas/api/collections_api/handlers/collections_ID_rules_get.py`
- `lambdas/api/collections_api/handlers/collections_ID_rules_ID_put.py`
- `lambdas/api/collections_api/handlers/collections_ID_rules_ID_delete.py`
- `lambdas/api/collections_api/handlers/collections_shared_with_me_get.py`
- `lambdas/api/collections_api/handlers/collections_ID_assets_get.py`

---

**Status:** Partial fix applied. Core TransactWrite issues resolved. Additional handler conversions needed for full functionality.
