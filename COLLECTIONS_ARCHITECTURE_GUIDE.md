# Collections Architecture & Developer Guide

## Table of Contents

- [Overview](#overview)
- [Architecture Patterns](#architecture-patterns)
- [Database Design](#database-design)
- [Backend API Structure](#backend-api-structure)
- [Frontend Architecture](#frontend-architecture)
- [Key Implementation Details](#key-implementation-details)
- [Common Patterns](#common-patterns)
- [Troubleshooting Guide](#troubleshooting-guide)

---

## Overview

The Collections feature allows users to organize and group media assets in MediaLake. Collections support hierarchical organization (parent-child relationships), sharing with other users/groups, and rule-based automation.

### Key Features

- **Hierarchical Organization**: Collections can have parent-child relationships (unlimited depth)
- **Asset Management**: Add/remove assets from collections with optional clip boundaries
- **Sharing**: Share collections with users or groups with different permission levels
- **Rules**: Automate collection membership based on metadata criteria
- **Public/Private**: Collections can be public or private
- **Full Search Integration**: Assets in collections are searchable with full OpenSearch metadata

---

## Architecture Patterns

### 1. Single-Table DynamoDB Design

**Why**: Cost-effective, efficient querying, supports complex access patterns with GSIs.

All collection data lives in a single DynamoDB table with the following entity types:

- Collection Metadata
- Collection Items (assets)
- Collection Rules
- Collection Shares/Permissions
- User Relationships (for share tracking)

**Key Principle**: Use composite keys (PK + SK) to organize related data together for efficient queries.

### 2. PynamoDB ORM

**Why**: Type safety, cleaner code, automatic attribute marshaling, built-in pagination.

All DynamoDB operations use PynamoDB models instead of direct boto3 calls.

**Location**: `lambdas/api/collections_api/db_models.py`

**Example**:

```python
from db_models import CollectionModel, CollectionItemModel

# Get a collection
collection = CollectionModel.get(f"COLLECTION#{collection_id}", "METADATA#")

# Query collection items
items = CollectionItemModel.query(
    f"COLLECTION#{collection_id}",
    CollectionItemModel.SK.startswith("ASSET#")
)
```

### 3. Lambda Powertools

**Why**: Built-in logging, tracing, metrics, validation, and API routing.

All Lambda functions use AWS Lambda Powertools for:

- API Gateway routing with type hints
- Structured logging with correlation IDs
- X-Ray tracing for performance monitoring
- CloudWatch metrics for operational insights
- Input validation with Pydantic v2

**Example**:

```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver

logger = Logger(service="collections-handler")
tracer = Tracer(service="collections-handler")
metrics = Metrics(namespace="medialake", service="collections")

app = APIGatewayRestResolver()

@app.get("/collections/<collection_id>")
@tracer.capture_method
def get_collection(collection_id: str):
    logger.info(f"Getting collection {collection_id}")
    # ... implementation
```

### 4. Pydantic V2 Validation

**Why**: Runtime type checking, automatic API documentation, clear error messages.

All request bodies and query parameters use Pydantic models for validation.

**Location**: `lambdas/api/collections_api/models.py`

**Example**:

```python
from pydantic import BaseModel, Field

class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    parentId: str | None = Field(None, alias="parentId")
    isPublic: bool = False
```

### 5. React Query for State Management

**Why**: Automatic caching, background refetching, optimistic updates, built-in loading/error states.

Frontend uses React Query (TanStack Query) for all API interactions.

**Location**: `medialake_user_interface/src/api/hooks/useCollections.ts`

**Example**:

```typescript
const { data: collection, isLoading } = useGetCollection(collectionId);
const deleteMutation = useDeleteItemFromCollection();

deleteMutation.mutate({ collectionId, itemId });
```

---

## Database Design

### Primary Table Structure

**Table Name**: `MediaLakeTable` (shared with other entities)

### Access Patterns

#### 1. Collection Metadata

```
PK: COLLECTION#<collection_id>
SK: METADATA#
Attributes: name, description, ownerId, parentId, itemCount, childCollectionCount, isPublic, status, createdAt, updatedAt
```

#### 2. Collection Items (Assets)

```
PK: COLLECTION#<collection_id>
SK: ASSET#<inventory_id>#<clip_identifier>
Attributes: itemType, assetId, addedAt, addedBy, clipBoundary (optional)
```

**Clip Identifier Examples**:

- Full asset: `ASSET#asset:uuid:123#FULL`
- Clip: `ASSET#asset:uuid:123#CLIP#00-00-10-00_00-00-20-00`

#### 3. Collection Rules

```
PK: COLLECTION#<collection_id>
SK: RULE#<rule_id>
Attributes: name, conditions, actions, isActive, createdAt, updatedAt
```

#### 4. Collection Shares (Permissions)

```
PK: COLLECTION#<collection_id>
SK: PERM#<user_id_or_group_id>
Attributes: role, expiresAt, sharedBy, createdAt
```

#### 5. User Relationships (Share Tracking)

```
PK: USER#<user_id>
SK: SHARED_COLLECTION#<collection_id>
Attributes: role, sharedAt, sharedBy
```

### Global Secondary Indexes (GSIs)

#### GSI1: Query by Owner

```
GSI1PK: USER#<owner_id>
GSI1SK: COLLECTION#<collection_id>
Use Case: Get all collections owned by a user
```

#### GSI2: Query by Parent

```
GSI2PK: PARENT#<parent_collection_id>
GSI2SK: COLLECTION#<child_collection_id>
Use Case: Get all child collections of a parent
```

#### GSI3: Query Collections Shared With User

```
GSI3PK: SHARED_WITH#<user_id>
GSI3SK: COLLECTION#<collection_id>
Use Case: Get all collections shared with a user
```

#### GSI5: Query by Type (for filtering)

```
GSI5PK: TYPE#collection
GSI5SK: COLLECTION#<collection_id>
Use Case: List all collections (filtered queries)
```

---

## Backend API Structure

### Directory Layout

```
lambdas/api/collections_api/
├── index.py                 # Main Lambda entry point
├── db_models.py            # PynamoDB models
├── models.py               # Pydantic request/response models
└── handlers/
    ├── __init__.py                       # Route registration
    ├── collections_get.py                # List collections
    ├── collections_post.py               # Create collection
    ├── collections_ID_get.py             # Get collection details
    ├── collections_ID_put.py             # Update collection
    ├── collections_ID_delete.py          # Delete collection
    ├── collections_ID_assets_get.py      # Get collection assets
    ├── collections_ID_items_ID_delete.py # Remove item from collection
    ├── collections_ID_share_post.py      # Share collection
    ├── collections_ID_share_ID_delete.py # Remove share
    ├── collections_ID_rules_*.py         # Rule management
    └── collections_ID_ancestors_get.py   # Get breadcrumb path
```

### Handler Pattern

Each handler follows this structure:

```python
"""Docstring explaining endpoint"""

import os
from aws_lambda_powertools import Logger, Tracer, Metrics
from collections_utils import *
from db_models import *
from models import *

logger = Logger(service="handler-name")
tracer = Tracer(service="handler-name")
metrics = Metrics(namespace="medialake", service="collections")

def register_route(app):
    """Register route with the API Gateway resolver"""

    @app.get("/collections/<collection_id>")
    @tracer.capture_method
    def handler_function(collection_id: str):
        try:
            # 1. Extract user context
            user_context = extract_user_context(app.current_event.raw_event)

            # 2. Validate inputs (Pydantic handles this)

            # 3. Perform business logic with PynamoDB

            # 4. Add metrics
            metrics.add_metric(name="SuccessCount", unit=MetricUnit.Count, value=1)

            # 5. Return standardized response
            return create_success_response(
                data=result,
                request_id=app.current_event.request_context.request_id
            )
        except NotFoundError:
            raise  # Powertools handles this
        except Exception as e:
            logger.exception("Error message", exc_info=e)
            return create_error_response(...)
```

### Common Utilities

**Location**: `lambdas/common_libraries/collections_utils.py`

Key constants:

```python
COLLECTION_PK_PREFIX = "COLLECTION#"
METADATA_SK = "METADATA#"
ITEM_SK_PREFIX = "ITEM#"  # Legacy
ASSET_SK_PREFIX = "ASSET#"  # Current
RULE_SK_PREFIX = "RULE#"
PERM_SK_PREFIX = "PERM#"
```

Helper functions:

- `create_success_response()`: Standardized success response
- `create_error_response()`: Standardized error response
- `format_collection_item()`: Convert DB item to API response format

---

## Frontend Architecture

### Directory Structure

```
medialake_user_interface/src/
├── api/
│   ├── endpoints.ts           # API endpoint definitions
│   ├── queryKeys.ts          # React Query cache keys
│   └── hooks/
│       └── useCollections.ts  # All collection-related hooks
├── pages/
│   ├── CollectionsPage.tsx           # List all collections (card view)
│   └── CollectionViewPage.tsx        # View single collection with assets
└── components/
    └── collections/
        ├── CollectionTreeView.tsx     # Hierarchical tree navigation
        ├── AddToCollectionModal.tsx   # Add asset to collection
        └── CollectionBreadcrumbs.tsx  # Navigation breadcrumbs
```

### React Query Hooks

**Location**: `medialake_user_interface/src/api/hooks/useCollections.ts`

All hooks follow this pattern:

```typescript
export const useGetCollections = (filters?: Record<string, any>) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.list(filters),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionsResponse>(
          API_ENDPOINTS.COLLECTIONS.LIST,
          { params: filters, signal },
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch collections error:", error);
        showError("Failed to fetch collections");
        throw error;
      }
    },
  });
};
```

**Mutations** (create, update, delete) automatically invalidate affected queries:

```typescript
export const useDeleteItemFromCollection = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ collectionId, itemId }) => {
      const encodedItemId = encodeURIComponent(itemId);
      await apiClient.delete(
        `/collections/${collectionId}/items/${encodedItemId}`,
      );
    },
    onSuccess: (_, variables) => {
      // Invalidate cache to trigger refetch
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.assets(variables.collectionId),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(variables.collectionId),
      });
    },
  });
};
```

### Query Key Structure

**Location**: `medialake_user_interface/src/api/queryKeys.ts`

```typescript
COLLECTIONS: {
  all: ["collections"] as const,
  lists: () => [...QUERY_KEYS.COLLECTIONS.all, "list"] as const,
  list: (filters?: Record<string, any>) =>
    [...QUERY_KEYS.COLLECTIONS.lists(), filters] as const,
  details: () => [...QUERY_KEYS.COLLECTIONS.all, "detail"] as const,
  detail: (id: string) =>
    [...QUERY_KEYS.COLLECTIONS.details(), id] as const,
  assets: (id: string) =>
    [...QUERY_KEYS.COLLECTIONS.all, id, "assets"] as const,
  ancestors: (id: string) =>
    [...QUERY_KEYS.COLLECTIONS.all, id, "ancestors"] as const,
}
```

---

## Key Implementation Details

### 1. URL Encoding for Special Characters

**Problem**: DynamoDB sort keys contain `#` characters (e.g., `ASSET#asset:uuid:123#FULL`), which browsers treat as URL fragments.

**Solution**: URL-encode on frontend, URL-decode on backend.

**Frontend**:

```typescript
const encodedItemId = encodeURIComponent(itemId);
await apiClient.delete(`/collections/${collectionId}/items/${encodedItemId}`);
```

**Backend**:

```python
from urllib.parse import unquote

decoded_item_id = unquote(item_id)
# Now use decoded_item_id for DynamoDB operations
```

### 2. Hierarchical Tree Navigation

**Implementation**: `CollectionTreeView.tsx`

- Fetches all collections in one query
- Builds tree recursively on client side
- Maintains expanded state using `useState`
- Auto-expands to current collection using ancestors

**Key Pattern**:

```typescript
const getAncestorIds = (
  collectionId: string,
  allCollections: Collection[],
): string[] => {
  const ancestors: string[] = [];
  let currentId = collectionId;

  while (currentId) {
    const collection = allCollections.find((c) => c.id === currentId);
    if (!collection || !collection.parentId) break;

    ancestors.push(collection.parentId);
    currentId = collection.parentId;
  }

  return ancestors;
};

// Auto-expand to current collection
useEffect(() => {
  if (currentCollectionId && allCollectionsResponse?.data) {
    const ancestorIds = getAncestorIds(
      currentCollectionId,
      allCollectionsResponse.data,
    );
    setExpandedItems((prev) => Array.from(new Set([...prev, ...ancestorIds])));
  }
}, [currentCollectionId, allCollectionsResponse]);
```

### 3. Breadcrumb Navigation

**Backend**: Ancestors included in collection response

```python
def get_collection_ancestors(collection_id: str, max_depth: int = 10):
    """Get the ancestor chain for a collection (from root to current)"""
    ancestors = []
    current_id = collection_id
    depth = 0

    while current_id and depth < max_depth:
        collection = CollectionModel.get(f"{COLLECTION_PK_PREFIX}{current_id}", METADATA_SK)
        parent_id = collection.parentId if collection.parentId else None
        ancestors.append({
            "id": current_id,
            "name": collection.name,
            "parentId": parent_id,
        })
        current_id = parent_id
        depth += 1

    ancestors.reverse()  # Root → current order
    return ancestors

# Include in collection response
formatted_collection["ancestors"] = get_collection_ancestors(collection_id)
```

**Frontend**: Renders breadcrumbs from ancestors

```typescript
const ancestors = collection?.ancestors || [];

<Breadcrumbs>
  <Link to="/collections">Collections</Link>
  {ancestors.map((ancestor) => (
    <Link key={ancestor.id} to={`/collections/${ancestor.id}/view`}>
      {ancestor.name}
    </Link>
  ))}
</Breadcrumbs>
```

### 4. Asset Integration with OpenSearch

Collections store only asset references (inventory IDs). Full asset data comes from OpenSearch.

**Backend Flow**:

```python
# 1. Get collection items from DynamoDB
items = CollectionItemModel.query(
    f"{COLLECTION_PK_PREFIX}{collection_id}",
    CollectionItemModel.SK.startswith(ASSET_SK_PREFIX)
)

# 2. Extract asset IDs
asset_ids = [item.assetId for item in items]

# 3. Fetch full asset data from OpenSearch
opensearch_client = get_opensearch_client()
response = opensearch_client.mget(index=OPENSEARCH_INDEX, body={"ids": asset_ids})

# 4. Merge DynamoDB metadata with OpenSearch data
for item in items:
    asset_data = opensearch_data.get(item.assetId)
    result = {
        **asset_data,  # OpenSearch data (format, path, metadata, etc.)
        "collectionItemId": item.SK,  # DynamoDB SK for deletion
        "addedAt": item.addedAt,
        "addedBy": item.addedBy,
    }
```

### 5. CloudFront URL Generation

Batch URL generation for performance:

```python
def generate_cloudfront_urls_batch(url_requests: List[Dict]) -> Dict[str, str]:
    """Generate CloudFront URLs in parallel"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(generate_cloudfront_url, req["bucket"], req["key"]): req["request_id"]
            for req in url_requests
        }
        return {
            futures[future]: future.result()
            for future in concurrent.futures.as_completed(futures)
        }
```

### 6. Transaction Safety

Use PynamoDB transactions for atomic operations:

```python
from pynamodb.connection import Connection
from pynamodb.transactions import TransactWrite

connection = Connection(region=os.environ["AWS_REGION"])

with TransactWrite(connection=connection) as transaction:
    # Create collection
    collection_item = CollectionModel()
    # ... set attributes
    transaction.save(collection_item)

    # Create GSI entries
    gsi_item = CollectionGSIModel()
    # ... set attributes
    transaction.save(gsi_item)

    # Update parent child count
    if parent_id:
        parent = CollectionModel.get(f"{COLLECTION_PK_PREFIX}{parent_id}", METADATA_SK)
        transaction.update(
            parent,
            actions=[CollectionModel.childCollectionCount.add(1)]
        )
```

---

## Common Patterns

### 1. Pagination

**Backend**:

```python
# PynamoDB handles pagination automatically
items = list(CollectionItemModel.query(
    pk,
    CollectionItemModel.SK.startswith(ASSET_SK_PREFIX),
    limit=page_size
))

# Manual pagination
start_idx = (page - 1) * page_size
end_idx = start_idx + page_size
paginated = all_items[start_idx:end_idx]
```

**Frontend**:

```typescript
const [page, setPage] = useState(1);
const { data } = useGetCollectionAssets(collectionId, page, pageSize);
```

### 2. Error Handling

**Backend**:

```python
try:
    # Operation
    pass
except NotFoundError:
    raise  # Powertools handles 404
except ValidationError as e:
    raise BadRequestError(str(e))
except Exception as e:
    logger.exception("Detailed error message", exc_info=e)
    return create_error_response(
        error_code="InternalServerError",
        error_message="User-friendly message",
        status_code=500
    )
```

**Frontend**:

```typescript
const { showError } = useErrorModal();

try {
  await someOperation();
} catch (error) {
  logger.error("Operation failed:", error);
  showError("User-friendly error message");
  throw error; // React Query handles retry logic
}
```

### 3. Permission Checks

**Backend**:

```python
def check_collection_access(collection_id: str, user_id: str, required_role: str = "viewer"):
    # 1. Check ownership
    collection = CollectionModel.get(f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK)
    if collection.ownerId == user_id:
        return True

    # 2. Check if public
    if collection.isPublic and required_role == "viewer":
        return True

    # 3. Check share permissions
    try:
        share = ShareModel.get(
            f"{COLLECTION_PK_PREFIX}{collection_id}",
            f"{PERM_SK_PREFIX}{user_id}"
        )
        return has_required_permission(share.role, required_role)
    except DoesNotExist:
        raise ForbiddenError("Access denied")
```

### 4. Soft Navigation (No Page Reload)

**Frontend**:

```typescript
const navigate = useNavigate();

const handleCollectionSelect = useCallback(
  (collectionId: string) => {
    navigate(`/collections/${collectionId}/view`);
    // React Query automatically fetches new data
    // Tree view stays expanded
  },
  [navigate],
);
```

---

## Troubleshooting Guide

### Common Issues

#### 1. Items Not Deleting

**Symptoms**: API returns 200, but item still appears after refresh.

**Causes**:

- URL encoding issue (special characters in item ID)
- Wrong SK format
- Item doesn't exist in DynamoDB

**Debug Steps**:

```python
# Add logging to handler
logger.info(f"[DELETE] Received: {item_id}")
logger.info(f"[DELETE] Decoded: {unquote(item_id)}")
logger.info(f"[DELETE] SK: {sk}")
logger.info(f"[DELETE] PK: {pk}")

# Check DynamoDB directly
aws dynamodb get-item --table-name MediaLakeTable \
  --key '{"PK":{"S":"COLLECTION#col_123"},"SK":{"S":"ASSET#asset:uuid:456#FULL"}}'
```

**Solution**: Always URL-encode special characters on frontend, decode on backend.

#### 2. Tree Not Expanding

**Symptoms**: Collections tree collapses when navigating.

**Causes**:

- Not managing expanded state
- Not calculating ancestors
- Using hard navigation instead of React Router

**Solution**:

```typescript
// Maintain expanded state
const [expandedItems, setExpandedItems] = useState<string[]>([]);

// Auto-expand ancestors
useEffect(() => {
  if (currentCollectionId) {
    const ancestors = getAncestorIds(currentCollectionId, allCollections);
    setExpandedItems((prev) => Array.from(new Set([...prev, ...ancestors])));
  }
}, [currentCollectionId]);

// Use soft navigation
const handleClick = (collectionId: string) => {
  navigate(`/collections/${collectionId}/view`); // ✅ Good
  // window.location.href = ...  // ❌ Bad - causes page reload
};
```

#### 3. Missing Asset Metadata

**Symptoms**: Assets show but missing format, path, or date fields.

**Cause**: Not calling `add_common_fields()` after fetching from OpenSearch.

**Solution**:

```python
# After getting asset data from OpenSearch
result = {
    "InventoryID": inventory_id,
    "DigitalSourceAsset": asset_data.get("DigitalSourceAsset", {}),
    # ...
}

# Add common fields (flattens nested structure)
result = add_common_fields(result)
```

#### 4. Query Not Invalidating

**Symptoms**: UI doesn't update after mutation.

**Cause**: Not invalidating affected queries.

**Solution**:

```typescript
export const useDeleteItem = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ...,
    onSuccess: (_, variables) => {
      // Invalidate ALL affected queries
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.assets(variables.collectionId)
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(variables.collectionId)
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists()  // List view shows counts
      });
    },
  });
};
```

#### 5. TransactWrite Errors

**Symptoms**: `AttributeError: 'TableConnection' object has no attribute 'transact_write_items'`

**Cause**: Not providing correct `Connection` object to `TransactWrite`.

**Solution**:

```python
from pynamodb.connection import Connection
from pynamodb.transactions import TransactWrite

# Create connection with region
connection = Connection(region=os.environ["AWS_REGION"])

# Use with TransactWrite
with TransactWrite(connection=connection) as transaction:
    transaction.save(item)
```

### Logging Best Practices

```python
# Use structured logging
logger.info("Operation started", extra={
    "collection_id": collection_id,
    "user_id": user_id,
    "operation": "delete_item"
})

# Log at decision points
logger.info(f"[DELETE] Decoded item_id: {decoded_item_id}")
logger.info(f"[DELETE] Final SK: {sk}")

# Log errors with context
logger.exception("Error deleting item", exc_info=e, extra={
    "collection_id": collection_id,
    "item_id": item_id,
    "sk": sk
})
```

### Performance Monitoring

Use X-Ray and CloudWatch:

```python
@tracer.capture_method
def expensive_operation():
    with tracer.provider.in_subsegment("## fetch_from_opensearch"):
        results = opensearch_client.mget(...)

    with tracer.provider.in_subsegment("## process_results"):
        processed = process(results)

    return processed
```

---

## Best Practices Summary

### Backend

1. ✅ Always use PynamoDB for DynamoDB operations
2. ✅ URL-decode path parameters that may contain special characters
3. ✅ Use transactions for multi-item operations
4. ✅ Include comprehensive logging with context
5. ✅ Validate inputs with Pydantic v2
6. ✅ Return standardized responses (success/error helpers)
7. ✅ Add CloudWatch metrics for key operations
8. ✅ Use X-Ray subsegments for performance tracking

### Frontend

1. ✅ URL-encode special characters before API calls
2. ✅ Use React Query for all API interactions
3. ✅ Invalidate affected queries after mutations
4. ✅ Use soft navigation (React Router) not hard reloads
5. ✅ Manage UI state locally (expanded items, filters)
6. ✅ Show loading/error states consistently
7. ✅ Use TypeScript for type safety
8. ✅ Follow Material-UI design patterns

### Database

1. ✅ Use composite keys (PK + SK) for access patterns
2. ✅ Create GSIs for alternative query patterns
3. ✅ Keep related data together (same PK)
4. ✅ Use meaningful prefixes (COLLECTION#, ASSET#, etc.)
5. ✅ Plan for pagination from the start
6. ✅ Use transactions for atomic operations
7. ✅ Consider query costs when designing access patterns

---

## Additional Resources

### Documentation

- [PynamoDB Documentation](https://pynamodb.readthedocs.io/)
- [AWS Lambda Powertools Python](https://docs.powertools.aws.dev/lambda/python/)
- [React Query Documentation](https://tanstack.com/query/latest/docs/react/overview)
- [DynamoDB Single Table Design](https://aws.amazon.com/blogs/compute/creating-a-single-table-design-with-amazon-dynamodb/)

### Code Locations

- **Backend**: `lambdas/api/collections_api/`
- **Frontend**: `medialake_user_interface/src/`
- **Common Libraries**: `lambdas/common_libraries/collections_utils.py`
- **Database Models**: `lambdas/api/collections_api/db_models.py`

### Related Documentation

- `SINGLE_TABLE_DESIGN_IMPLEMENTATION.md` - Detailed database schema
- `COLLECTION_HIERARCHY_IMPLEMENTATION.md` - Hierarchical collections design
- `CHILD_COLLECTIONS_FIX.md` - Parent-child relationship fixes
- `lambdas/api/collections_api/README.md` - API endpoint documentation

---

## Questions?

When making changes to collections:

1. Start by understanding the data flow (frontend → API → DynamoDB → OpenSearch)
2. Check existing handlers for patterns
3. Use logging liberally during development
4. Test with various edge cases (special characters, deep hierarchies, etc.)
5. Ensure proper error handling and user feedback
6. Invalidate affected React Query caches

**Remember**: Collections are tightly integrated with assets, so changes often affect both systems. Always consider the impact on OpenSearch queries, CloudFront URL generation, and UI rendering performance.
