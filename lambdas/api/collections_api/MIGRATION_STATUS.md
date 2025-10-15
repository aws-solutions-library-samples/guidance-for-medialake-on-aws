# Collections API Migration Status

## Overview

Migration to use Pydantic V2 models and AWS Powertools best practices with new directory structure.

## New Directory Structure

```
lambdas/api/collections_api/
├── models/                    # ✅ COMPLETED
│   ├── __init__.py
│   ├── common_models.py       # Enums, ApiResponse, QueryParams
│   ├── collection_models.py   # Collection request/response models
│   ├── item_models.py         # Item request/response models
│   └── share_models.py        # Share request/response models
├── handlers/                  # 🔄 IN PROGRESS
│   ├── __init__.py
│   ├── collections.py         # ✅ COMPLETED - Migrated with Pydantic
│   ├── collection_detail.py   # ⏳ TODO - Needs migration
│   ├── items.py               # ⏳ TODO - Needs migration
│   ├── assets.py              # ⏳ TODO - Needs migration
│   ├── shares.py              # ⏳ TODO - Needs migration
│   ├── rules.py               # ⏳ TODO - Needs migration
│   └── collection_types.py    # ⏳ TODO - Needs migration
├── utils/                     # ⏳ TODO - Create if needed
├── index.py                   # ⏳ TODO - Update imports
└── requirements.txt           # ✅ Already includes pydantic>=2.0.0
```

## Migration Checklist

### ✅ Completed (Phase 1 - Models)

- [x] Create `models/` directory
- [x] Create `common_models.py` with enums and base models
- [x] Create `collection_models.py` with CollectionRequest/Response models
- [x] Create `item_models.py` with AddItemToCollectionRequest
- [x] Create `share_models.py` with ShareCollectionRequest
- [x] Create `models/__init__.py` with proper exports

### 🔄 In Progress (Phase 2 - Handlers)

- [x] Create `handlers/` directory
- [x] Migrate `collections_routes.py` → `handlers/collections.py` with Pydantic
  - Uses `CreateCollectionRequest` model
  - Uses `ListCollectionsQueryParams` model
  - Uses Powertools `BadRequestError` exceptions
  - Removed manual `_validate_collection_data()` function
- [ ] Migrate remaining route files (see below)
- [ ] Create `handlers/__init__.py`

### ⏳ TODO (Phase 3 - Remaining Handlers)

#### 1. collection_detail.py

**Source:** `routes/collection_detail_routes.py`
**Endpoints:**

- `GET /collections/<collection_id>` - Get single collection
- `PATCH /collections/<collection_id>` - Update collection
- `DELETE /collections/<collection_id>` - Delete collection

**Models to Use:**

- `UpdateCollectionRequest` for PATCH endpoint
- Use `NotFoundError` from Powertools for 404s

#### 2. items.py

**Source:** `routes/items_routes.py`
**Endpoints:**

- `POST /collections/<collection_id>/items` - Add item to collection
- `GET /collections/<collection_id>/items` - List collection items
- `DELETE /collections/<collection_id>/items/<item_id>` - Remove item

**Models to Use:**

- `AddItemToCollectionRequest` - Already supports clipBoundary validation
- Has custom validator for HH:MM:SS:FF format

#### 3. assets.py

**Source:** `routes/assets_routes.py`
**Endpoints:**

- `GET /collections/<collection_id>/assets` - Get collection assets with OpenSearch data

**Models to Use:**

- `GetCollectionAssetsQueryParams` for pagination

#### 4. shares.py

**Source:** `routes/shares_routes.py`
**Endpoints:**

- `POST /collections/<collection_id>/shares` - Share collection
- `GET /collections/<collection_id>/shares` - List shares
- `DELETE /collections/<collection_id>/shares/<user_id>` - Remove share

**Models to Use:**

- `ShareCollectionRequest`

#### 5. rules.py

**Source:** `routes/rules_routes.py`
**Endpoints:**

- Collection rules management

#### 6. collection_types.py

**Source:** `routes/collection_types_routes.py`
**Endpoints:**

- Collection types management

### ⏳ TODO (Phase 4 - Final Steps)

- [ ] Create `handlers/__init__.py` importing all handlers
- [ ] Update `index.py` to import from `handlers/` instead of `routes/`
- [ ] Test all endpoints
- [ ] Delete old `routes/` directory
- [ ] Delete old `models.py` and `collections_routes_refactored.py`

## Migration Pattern

### Before (Old Pattern)

```python
from routes import collections_routes

# Manual validation
validation_errors = _validate_collection_data(request_data)
if validation_errors:
    return create_error_response(...)

# Manual error handling
if "Item" not in response:
    return create_error_response(
        error_code="NOT_FOUND",
        status_code=404,
        ...
    )
```

### After (New Pattern with Pydantic)

```python
from handlers import collections
from models import CreateCollectionRequest
from aws_lambda_powertools.utilities.parser import parse, ValidationError
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, NotFoundError

# Pydantic validation
try:
    request_data = parse(
        event=app.current_event.json_body,
        model=CreateCollectionRequest,
    )
except ValidationError as e:
    raise BadRequestError(f"Validation error: {str(e)}")

# Powertools exceptions
if "Item" not in response:
    raise NotFoundError(f"Collection '{collection_id}' not found")
```

## Key Changes in Migrated Code

1. **Pydantic Models Replace Manual Validation**
   - `CreateCollectionRequest` validates name, description, tags
   - Field validators clean data (trim whitespace, deduplicate tags)
   - Max length constraints enforced by Pydantic

2. **Powertools Exceptions**
   - `BadRequestError` for 400 errors (replaces manual error responses)
   - `NotFoundError` for 404 errors
   - Exceptions auto-formatted by API Gateway resolver

3. **Query Parameter Validation**
   - `ListCollectionsQueryParams` validates limit, filters, sort
   - Automatic type conversion and validation

4. **Type Safety**
   - All models have proper type hints
   - IDE autocomplete and type checking
   - Self-documenting code

## Benefits of Migration

1. **Type Safety** - Catch errors at validation time
2. **Less Boilerplate** - No manual validation functions
3. **Better Error Messages** - Pydantic provides detailed errors
4. **Self-Documenting** - Models serve as API documentation
5. **Maintainability** - Centralized validation logic
6. **IDE Support** - Better autocomplete and type checking
7. **OpenAPI Ready** - Can generate API schema automatically

## Next Steps

1. **Create remaining handlers** by following the pattern in `handlers/collections.py`
2. **Update imports** in `index.py` to use new structure
3. **Test thoroughly** - Ensure all endpoints work
4. **Clean up** old files once migration is complete

## Example Handler Migration (items.py)

```python
from models import AddItemToCollectionRequest
from aws_lambda_powertools.utilities.parser import parse, ValidationError
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

@app.post("/collections/<collection_id>/items")
@tracer.capture_method
def add_collection_item(collection_id: str):
    try:
        # Pydantic validates assetId, clipBoundary format, addAllClips
        request_data = parse(
            event=app.current_event.json_body,
            model=AddItemToCollectionRequest,
        )

        # request_data.assetId is guaranteed valid
        # request_data.clipBoundary is validated for HH:MM:SS:FF format
        # ... implementation

    except ValidationError as e:
        raise BadRequestError(f"Validation error: {str(e)}")
```

## Files Ready for Review

1. ✅ `models/` - Complete Pydantic V2 models
2. ✅ `handlers/collections.py` - Fully migrated example
3. ✅ `POWERTOOLS_MIGRATION_GUIDE.md` - Detailed guide with examples
4. ✅ `MIGRATION_STATUS.md` - This file

## Commands to Complete Migration

Once all handlers are created:

```bash
# Update index.py imports
# Test the Lambda
# Deploy
# Clean up old files
```
