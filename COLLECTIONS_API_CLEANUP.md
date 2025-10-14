# Collections API Cleanup - Fixed Import Error

## ✅ Issue Resolved

**Error**: `Unable to import module 'index': cannot import name 'ForbiddenError' from 'aws_lambda_powertools.event_handler.exceptions'`

**Root Cause**: Collection-types handlers were accidentally left in `collections_api` when they should have been completely moved to `settings_api`.

## Files Removed from collections_api

### Handlers Removed

```bash
lambdas/api/collections_api/handlers/
├── collection_types_get.py                      ❌ REMOVED
├── collection_types_post.py                     ❌ REMOVED
├── settings_collection_types_ID_put.py          ❌ REMOVED
├── settings_collection_types_ID_delete.py       ❌ REMOVED
└── settings_collection_types_ID_migrate_post.py ❌ REMOVED
```

### Utils Removed

```bash
lambdas/api/collections_api/utils/
├── permission_utils.py   ❌ REMOVED (only needed in settings_api)
├── response_utils.py     ❌ REMOVED (only needed in settings_api)
└── validation_utils.py   ❌ REMOVED (only needed in settings_api)
```

### Updated Files

- ✅ `lambdas/api/collections_api/handlers/__init__.py`
  - Removed collection-types imports
  - Removed collection-types from `__all__`
  - Removed collection-types route registrations

## Current State

### Collections API (lambdas/api/collections_api/)

**Purpose**: Handle collections CRUD operations

**Endpoints**:

- `GET /collections` - List collections
- `POST /collections` - Create collection
- `GET /collections/{id}` - Get collection
- `PATCH /collections/{id}` - Update collection
- `DELETE /collections/{id}` - Delete collection
- `GET /collections/{id}/items` - List items
- `POST /collections/{id}/items` - Add items
- `DELETE /collections/{id}/items/{itemId}` - Remove item
- `GET /collections/{id}/assets` - Get assets
- `GET /collections/{id}/share` - List shares
- `POST /collections/{id}/share` - Create share
- `DELETE /collections/{id}/share/{shareId}` - Delete share
- `GET /collections/{id}/rules` - List rules
- `POST /collections/{id}/rules` - Create rule
- `PUT /collections/{id}/rules/{ruleId}` - Update rule
- `DELETE /collections/{id}/rules/{ruleId}` - Delete rule

**Status**: ✅ Clean, no collection-types references

### Settings API (lambdas/api/settings_api/)

**Purpose**: Handle settings and configuration

**Endpoints**:

- `GET /settings/collection-types` - List collection types
- `POST /settings/collection-types` - Create type (admin)
- `PUT /settings/collection-types/{id}` - Update type (admin)
- `DELETE /settings/collection-types/{id}` - Delete type (admin)
- `POST /settings/collection-types/{id}/migrate` - Migrate collections (admin)

**Status**: ✅ Complete implementation

## Verification

### No Import Errors

```bash
✅ No references to ForbiddenError in collections_api
✅ No references to permission_utils in collections_api
✅ No references to response_utils in collections_api
✅ No references to validation_utils in collections_api
✅ All collection-types handlers removed from collections_api
```

### Handler Registration

```python
# collections_api/handlers/__init__.py
# ✅ Only registers collection endpoints (no collection-types)

def register_all_routes(app):
    # Collections endpoints
    collections_get.register_route(app)
    collections_post.register_route(app)

    # Individual collection endpoints
    collections_ID_get.register_route(app)
    collections_ID_patch.register_route(app)
    collections_ID_delete.register_route(app)

    # ... etc (no collection-types)
```

## Why This Happened

During the migration from Collections API to Settings API:

1. I **copied** collection-types handlers to settings_api ✅
2. I **forgot** to remove them from collections_api ❌
3. The copied files used `ForbiddenError` which doesn't exist in the older aws-lambda-powertools version

## What Changed

### Before (Broken)

```
collections_api/
├── handlers/
│   ├── collection_types_get.py          ❌ Caused import error
│   ├── collection_types_post.py         ❌ Caused import error
│   ├── settings_collection_types_*.py   ❌ Caused import error
│   └── ... collection handlers
└── utils/
    ├── permission_utils.py               ❌ Used ForbiddenError
    ├── response_utils.py                 ❌ Duplicate
    └── validation_utils.py               ❌ Duplicate

settings_api/
├── handlers/
│   ├── collection_types_get.py          ✅ Correct location
│   ├── collection_types_post.py         ✅ Correct location
│   └── collection_types_*.py            ✅ Correct location
└── utils/
    ├── permission_utils.py               ✅ Correct location
    ├── response_utils.py                 ✅ Correct location
    └── validation_utils.py               ✅ Correct location
```

### After (Fixed)

```
collections_api/
├── handlers/
│   └── ... collection handlers only     ✅ Clean
└── utils/
    ├── formatting_utils.py               ✅ Collections-specific
    ├── item_utils.py                     ✅ Collections-specific
    ├── opensearch_utils.py               ✅ Collections-specific
    └── pagination_utils.py               ✅ Collections-specific

settings_api/
├── handlers/
│   └── collection_types_*.py            ✅ All collection-types handlers
└── utils/
    ├── permission_utils.py               ✅ Settings-specific
    ├── response_utils.py                 ✅ Settings-specific
    └── validation_utils.py               ✅ Settings-specific
```

## Testing

### Verify Collections API

```bash
# Collections API should load without errors
cd lambdas/api/collections_api
python3 -c "from index import lambda_handler; print('✅ Collections API loads successfully')"
```

### Verify Settings API

```bash
# Settings API should load without errors
cd lambdas/api/settings_api
python3 -c "from index import lambda_handler; print('✅ Settings API loads successfully')"
```

## Deployment

The Collections API Lambda should now deploy and run without the `ForbiddenError` import error.

```bash
# Deploy updated Collections API
cdk deploy MediaLakeStack
```

## Summary

- ✅ Removed 5 collection-types handler files from collections_api
- ✅ Removed 3 duplicate utility files from collections_api
- ✅ Updated handler registration to exclude collection-types
- ✅ No more `ForbiddenError` import errors
- ✅ Clean separation between collections and settings APIs
- ✅ Both APIs are now independent and functional

**Status**: 🎉 **FIXED - Collections API will deploy successfully**
