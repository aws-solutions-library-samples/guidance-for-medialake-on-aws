# Collection Groups — OpenSearch Search & Pagination

## Status

Proposed

## Context

Collection groups are already indexed into OpenSearch via the DynamoDB Stream sync Lambda (`documentType: "collection_group"`), but the listing endpoint (`GET /collections/groups`) still queries DynamoDB directly via GSI2 with in-memory search filtering. This creates an inconsistency with the collections listing, which was recently migrated to OpenSearch for server-side pagination, search, sorting, and access control.

## Current State

| Aspect                  | Collections (current)                                        | Groups (current)                    |
| ----------------------- | ------------------------------------------------------------ | ----------------------------------- |
| Data source for listing | OpenSearch                                                   | DynamoDB GSI2                       |
| Pagination              | Page-based (page/pageSize)                                   | Cursor-based (limit/cursor)         |
| Search                  | Server-side via OpenSearch multi_match                       | In-memory substring filter          |
| Sorting                 | Server-side (name, createdAt, updatedAt)                     | GSI2 sort key only (createdAt desc) |
| Access control          | OpenSearch query-time (ownerId, isPublic, sharedWithUserIds) | None (all groups returned)          |
| Indexed in OpenSearch   | Yes                                                          | Yes (but unused for listing)        |

## Proposed Changes

### Goal

Route the groups listing through OpenSearch, matching the collections pattern for consistency, performance at scale, and server-side search.

### 1. Backend — New `search_groups()` function

**File:** `lambdas/api/collections_api/utils/collections_search.py`

Add a `search_groups()` function alongside the existing `search_collections()`:

```python
def search_groups(
    user_id: str,
    search_text: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_field: str = "name",
    sort_direction: str = "asc",
) -> Tuple[List[Dict[str, Any]], int]:
```

**OpenSearch query structure:**

```json
{
  "query": {
    "bool": {
      "filter": [{ "term": { "documentType": "collection_group" } }],
      "should": [
        { "term": { "ownerId": "<user_id>" } },
        { "term": { "isPublic": true } }
      ],
      "minimum_should_match": 1,
      "must": [
        {
          "multi_match": {
            "query": "<search_text>",
            "fields": ["name", "description"]
          }
        }
      ]
    }
  },
  "sort": [{ "name.keyword": { "order": "asc" } }],
  "from": 0,
  "size": 20
}
```

Key differences from `search_collections()`:

- Filters on `documentType: "collection_group"` instead of `"collection"`
- No parentId filtering (groups are flat, not hierarchical)
- No metadata filtering (groups don't have customMetadata)
- No status filtering (groups don't have a status field)
- Access control: `ownerId` or `isPublic` (no `sharedWithUserIds` — groups aren't shared individually)

### 2. Backend — Update `groups_get.py` handler

**File:** `lambdas/api/collections_api/handlers/groups_get.py`

Replace the DynamoDB GSI2 query with a call to `search_groups()`. Switch from cursor-based to page-based pagination to match the collections pattern.

**New query parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | 1-based page number |
| `pageSize` | int | 20 | Results per page (max 100) |
| `sort` | string | "name" | Sort field: name, createdAt, updatedAt |
| `sortDirection` | string | "asc" | asc or desc |
| `search` | string | — | Free-text search (name, description) |

**New response pagination format:**

```json
{
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalResults": 5,
    "totalPages": 1,
    "hasNextPage": false,
    "hasPrevPage": false
  }
}
```

This replaces the current cursor-based format (`has_next_page`, `next_cursor`, `limit`).

### 3. Frontend — Update `collectionGroupsApi.ts`

**File:** `medialake_user_interface/src/features/collection-groups/api/collectionGroupsApi.ts`

Update the `list()` method to send page-based params:

```typescript
list: async (params?: {
  search?: string;
  page?: number;
  pageSize?: number;
  sort?: string;
  sortDirection?: "asc" | "desc";
}): Promise<CollectionGroupListResponse> => {
  const response = await apiClient.get<CollectionGroupListResponse>(
    "/collections/groups",
    { params }
  );
  return response.data;
},
```

### 4. Frontend — Update `CollectionGroupListResponse` type

**File:** `medialake_user_interface/src/features/collection-groups/types/index.ts`

Update the pagination type to match the new page-based format:

```typescript
export interface CollectionGroupListResponse {
  success: boolean;
  data: CollectionGroup[];
  pagination: {
    page: number;
    pageSize: number;
    totalResults: number;
    totalPages: number;
    hasNextPage: boolean;
    hasPrevPage: boolean;
  };
  meta: { ... };
}
```

### 5. Frontend — Update `useCollectionGroups.ts` hook

**File:** `medialake_user_interface/src/features/collection-groups/hooks/useCollectionGroups.ts`

- Add debounced search state (300ms, matching collections pattern)
- Pass `page`, `pageSize`, `sort`, `sortDirection`, `search` to the API
- Use `keepPreviousData` for smooth pagination transitions
- Include query params in the React Query key for proper cache invalidation

### 6. Frontend — Update `CollectionGroupsList.tsx` component

**File:** `medialake_user_interface/src/features/collection-groups/components/CollectionGroupsList.tsx`

- Add sort controls (Name asc/desc, matching the collections page pattern)
- Replace client-side search with server-side debounced search
- Add `AssetPagination` component (same one used by collections)
- Show `totalResults` count

### 7. OpenSearch Document — Already Complete

The `transform_collection_group()` function in `document_transformer.py` already maps:

- `id`, `name`, `description`, `ownerId`, `isPublic`
- `collectionIds`, `createdAt`, `updatedAt`
- `documentType: "collection_group"`

No changes needed to the sync Lambda or document transformer.

## Files Changed

| File                                                                                          | Change                                            |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `lambdas/api/collections_api/utils/collections_search.py`                                     | Add `search_groups()` function                    |
| `lambdas/api/collections_api/handlers/groups_get.py`                                          | Replace DynamoDB query with OpenSearch            |
| `lambdas/api/collections_api/models/common_models.py`                                         | Add `ListGroupsQueryParams` Pydantic model        |
| `medialake_user_interface/src/features/collection-groups/types/index.ts`                      | Update pagination type                            |
| `medialake_user_interface/src/features/collection-groups/api/collectionGroupsApi.ts`          | Update list params                                |
| `medialake_user_interface/src/features/collection-groups/hooks/useCollectionGroups.ts`        | Add pagination/sort/search params                 |
| `medialake_user_interface/src/features/collection-groups/components/CollectionGroupsList.tsx` | Add sort controls, pagination, server-side search |

## Migration & Backward Compatibility

- The DynamoDB GSI2 query path is removed entirely (no fallback needed — OpenSearch is the source of truth, same as collections)
- Existing groups are already indexed in OpenSearch via the sync Lambda
- The cursor-based pagination format changes to page-based — frontend and backend change together in the same deploy
- No data migration needed

## What This Does NOT Change

- Group CRUD operations (create, update, delete) — these still write to DynamoDB, which triggers the stream sync to OpenSearch
- Group detail page (`GET /collections/groups/:id`) — still reads from DynamoDB (single-item get, no search needed)
- Add/remove collections from groups — still DynamoDB operations
- The `CollectionGroupDetailPage` — no changes needed

## Effort Estimate

Small-medium. The pattern is already established by the collections migration. Most of the work is adapting the existing `search_collections()` pattern for groups and updating the frontend components to use page-based pagination with server-side search.
