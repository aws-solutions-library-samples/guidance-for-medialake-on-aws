# Collection Hierarchy Implementation

## Overview

Implemented full hierarchical collection support with cascade delete, tree view navigation, and breadcrumb trails.

## Features Implemented

### 1. Cascade Delete ✅

**File**: `lambdas/api/collections_api/handlers/collections_ID_delete.py`

- Recursively deletes all child collections when a parent is deleted
- Walks the collection tree depth-first, deleting children before parents
- Automatically removes `CHILD#` reference items from parent collections
- Updates parent's `childCollectionCount` when removing a child reference
- Returns total items deleted in the API response

**How it works**:

```python
def _delete_collection_recursive(table, collection_id, user_id, current_timestamp):
    """Recursively delete a collection and all its children"""
    # 1. Query for CHILD# references
    # 2. Recursively delete each child first
    # 3. Delete this collection's items (metadata, assets, shares, etc.)
    # 4. Return count of deleted items
```

**Response format**:

```json
{
  "success": true,
  "data": {
    "id": "col_123",
    "status": "DELETED",
    "itemsDeleted": 147,
    "deletionType": "CASCADE"
  }
}
```

### 2. Collection Ancestors API ✅

**File**: `lambdas/api/collections_api/handlers/collections_ID_ancestors_get.py`

**Endpoint**: `GET /collections/{collection_id}/ancestors`

- Returns the full path from root to current collection
- Walks up the `parentId` chain
- Includes max depth protection (10 levels) to prevent infinite loops
- Returns ancestors in root→current order

**Response format**:

```json
{
  "success": true,
  "data": [
    { "id": "col_root", "name": "Root Collection", "parentId": null },
    { "id": "col_child", "name": "Child Collection", "parentId": "col_root" },
    { "id": "col_grandchild", "name": "Grandchild", "parentId": "col_child" }
  ]
}
```

### 3. MUI X Tree View Component ✅

**Package**: `@mui/x-tree-view` (installed via npm)

**File**: `medialake_user_interface/src/components/collections/CollectionTreeView.tsx`

- Uses `RichTreeView` from MUI X for interactive navigation
- Displays collection hierarchy in a collapsible tree structure
- Shows child collection count in parentheses: `"Parent Collection (3)"`
- Highlights the currently selected collection
- Clicking any collection navigates to that collection's view page
- Responsive and styled to match the application theme

**Features**:

- Hover effects on tree items
- Selected item highlighting with `primary.light` background
- Automatic scrolling for long lists
- Loading state while fetching collections

### 4. Enhanced Breadcrumb Trail ✅

**File**: `medialake_user_interface/src/pages/CollectionViewPage.tsx`

- Shows full hierarchical path: `Home > Collections > Parent > Child > Current`
- Each ancestor is a clickable link that navigates to that collection
- Dynamically built from the `/ancestors` API response
- Uses Material-UI `Breadcrumbs` component with consistent styling

**Example breadcrumb trail**:

```
🏠 Home > 📁 Collections > 📁 Projects > 📁 2024 > 📁 Q4 Campaign
```

### 5. Left Sidebar with Tree Navigation ✅

**File**: `medialake_user_interface/src/pages/CollectionViewPage.tsx`

- Added a persistent left sidebar (280px wide)
- Displays `CollectionTreeView` component
- Sticky positioning to stay visible while scrolling
- Border separator between sidebar and main content
- Full height with independent scroll

**Layout structure**:

```
┌─────────────────────────────────────────────────────────┐
│ [Tree Sidebar] │  Main Content Area                     │
│                │  - Breadcrumbs                          │
│  Collection    │  - Collection Header                    │
│  Hierarchy     │  - Sub-Collections Grid                 │
│                │  - Assets Grid/List                     │
│  ▼ Root 1      │                                         │
│    ► Child 1   │                                         │
│    ▼ Child 2   │                                         │
│      ► Sub 1   │                                         │
│  ▼ Root 2      │                                         │
│                │                                         │
└─────────────────────────────────────────────────────────┘
```

## Frontend Changes

### API Hooks Added

**File**: `medialake_user_interface/src/api/hooks/useCollections.ts`

```typescript
// Get collection ancestors for breadcrumb trail
export const useGetCollectionAncestors = (id: string, enabled = true) => {
  // Returns CollectionAncestorsResponse with data: CollectionAncestor[]
};

export interface CollectionAncestor {
  id: string;
  name: string;
  parentId?: string;
}
```

### API Endpoints Updated

**File**: `medialake_user_interface/src/api/endpoints.ts`

```typescript
COLLECTIONS: {
  ANCESTORS: (id: string) => `/collections/${id}/ancestors`,
  // ... other endpoints
}
```

### Query Keys Updated

**File**: `medialake_user_interface/src/api/queryKeys.ts`

```typescript
COLLECTIONS: {
  ancestors: (id: string) =>
    [...QUERY_KEYS.COLLECTIONS.detail(id), "ancestors"] as const,
  // ... other keys
}
```

## Backend Changes

### New Handler Registered

**File**: `lambdas/api/collections_api/handlers/__init__.py`

Added:

- `collections_ID_ancestors_get` import
- Registration in `register_all_routes()`

### Updated Handlers

- `collections_ID_delete.py` - Cascade delete implementation
- `collections_post.py` - Already creates `CHILD#` references (existing)
- `collections_ID_ancestors_get.py` - New endpoint for breadcrumbs

## Data Model

### Collection References (Single-Table Design)

```
Parent Collection:
  PK = COLLECTION#parent_id
  SK = METADATA → Collection metadata
  SK = CHILD#child_id_1 → Reference to child 1
  SK = CHILD#child_id_2 → Reference to child 2
  SK = ASSET#... → Collection assets

Child Collection:
  PK = COLLECTION#child_id_1
  SK = METADATA → {parentId: "parent_id", ...}
  SK = ASSET#... → Collection assets
```

## User Experience

### Navigation Flow

1. User lands on `/collections` - sees only root collections (no `parentId`)
2. User clicks a collection → navigates to `/collections/{id}/view`
3. Left sidebar shows full collection tree with current selection highlighted
4. Breadcrumbs show full path: `Home > Collections > [ancestors] > Current`
5. Sub-collections section shows immediate children as cards
6. User can click any ancestor in breadcrumbs to navigate up
7. User can click any collection in tree sidebar to navigate

### Delete Behavior

- **Before**: Deleting a parent left children orphaned
- **After**: Deleting a parent recursively deletes all descendants
- **Confirmation**: User sees "Delete Collection" dialog
- **Feedback**: Shows count of items deleted: `"Successfully deleted 147 items"`

## Performance Considerations

1. **Tree View**: Only loads root collections initially, uses React Query caching
2. **Ancestors API**: Single DynamoDB query walking up the parent chain (max 10 levels)
3. **Cascade Delete**: Batched deletes (25 items per batch) to stay within DynamoDB limits
4. **Breadcrumbs**: Cached via React Query, doesn't re-fetch on every render

## Testing Checklist

### Backend

- [ ] Create nested collections (Root > Child > Grandchild > Great-grandchild)
- [ ] Get ancestors for deeply nested collection
- [ ] Delete root collection and verify all descendants are deleted
- [ ] Delete middle collection and verify only its subtree is deleted
- [ ] Verify `CHILD#` references are updated correctly

### Frontend

- [ ] Navigate through collection hierarchy using tree sidebar
- [ ] Click breadcrumb ancestors to navigate up the tree
- [ ] Verify tree view highlights current collection
- [ ] Verify breadcrumbs show full path for deeply nested collections
- [ ] Delete a collection and verify cascade behavior
- [ ] Check responsive layout on different screen sizes

## Known Limitations

1. **Max Depth**: Ancestors API has a 10-level max depth to prevent infinite loops
2. **Tree Loading**: Tree view only shows root collections; children load on demand by navigating
3. **Sidebar Width**: Fixed at 280px (not resizable)
4. **Delete Confirmation**: Doesn't show preview of what will be deleted (just item count after deletion)

## Future Enhancements

1. **Lazy Loading**: Expand tree nodes to show children without navigating
2. **Drag & Drop**: Reorder collections or move collections between parents
3. **Max Depth Validation**: Prevent creating collections beyond a certain depth
4. **Delete Preview**: Show list of collections that will be cascade deleted
5. **Resizable Sidebar**: Allow users to adjust tree sidebar width
6. **Search in Tree**: Filter/search collections in tree view
7. **Keyboard Navigation**: Arrow keys to navigate tree, Enter to select
8. **Context Menu**: Right-click on tree items for quick actions

## References

- [MUI X Tree View Documentation](https://mui.com/x/react-tree-view/)
- Single-Table Design Pattern for DynamoDB
- AWS Lambda Powertools for Python
- React Query for data fetching and caching
