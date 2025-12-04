# Collections API DynamoDB Schema Design

## Access Patterns Analysis

### Collection Types Access Patterns

1. **List Collection Types** (`GET /collection-types`)

   - Cursor pagination
   - Filter by `active` status
   - Sort by: `sortOrder`, `typeName`, `createdAt` (ascending/descending)
   - Primary query: Scan/Query all collection types with optional filtering

2. **Create Collection Type** (`POST /collection-types`)
   - Insert new collection type record

### Collections Access Patterns

1. **List Collections** (`GET /collections`)

   - Cursor pagination
   - Filters: `type`, `ownerId`, `favorite`, `status`, `search`, `parentId`
   - Sort by: `name`, `createdAt`, `updatedAt` (ascending/descending)
   - Field selection and includes: `owner`, `children`, `items`, `permissions`
   - Complex query patterns requiring multiple GSIs

2. **Get Single Collection** (`GET /collections/{collectionId}`)

   - Direct lookup by collectionId
   - Includes: `items`, `children`, `owner`, `permissions`, `rules`
   - Field selection capability

3. **Create Collection** (`POST /collections`)

   - Insert new collection with hierarchical parent/child relationships

4. **Update Collection** (`PATCH /collections/{collectionId}`)

   - Update collection attributes and metadata

5. **Delete Collection** (`DELETE /collections/{collectionId}`)
   - Soft delete with cascade options for children

### Collection Items Access Patterns

1. **List Collection Items** (`GET /collections/{collectionId}/items`)

   - Query items by collection ID
   - Cursor pagination
   - Filter by item `type` (asset, workflow, collection)
   - Sort by: `sortOrder`, `addedAt`

2. **Add Single Item** (`POST /collections/{collectionId}/items`)

   - Insert item-collection relationship

3. **Batch Add Items** (`POST /collections/{collectionId}/items/batch`)

   - Batch insert up to 100 items efficiently

4. **Batch Remove Items** (`POST /collections/{collectionId}/items/batch-remove`)

   - Batch delete up to 100 items efficiently

5. **Update Item** (`PUT /collections/{collectionId}/items/{itemId}`)

   - Update item metadata within collection context

6. **Remove Single Item** (`DELETE /collections/{collectionId}/items/{itemId}`)
   - Remove item-collection relationship

### Collection Rules Access Patterns

1. **List Collection Rules** (`GET /collections/{collectionId}/rules`)

   - Query rules by collection ID
   - Cursor pagination
   - Filter by `active` status
   - Implicit priority-based ordering

2. **Create Rule** (`POST /collections/{collectionId}/rules`)

   - Insert new rule with priority handling

3. **Update Rule** (`PUT /collections/{collectionId}/rules/{ruleId}`)

   - Update rule criteria and status

4. **Delete Rule** (`DELETE /collections/{collectionId}/rules/{ruleId}`)
   - Remove rule

### Collection Sharing Access Patterns

1. **List Collection Shares** (`GET /collections/{collectionId}/share`)

   - Query shares by collection ID
   - Cursor pagination

2. **Share Collection** (`POST /collections/{collectionId}/share`)

   - Create sharing relationship with users/groups

3. **Remove Share** (`DELETE /collections/{collectionId}/share/{userId}`)

   - Remove sharing relationship

4. **List Shared Collections** (`GET /collections/shared-with-me`)
   - Query collections shared with current user
   - Filter by user's role in collection
   - Cursor pagination

## DynamoDB Table Schemas

### 1. Collection Types Table

**Table Name:** `{resource_prefix}-collection-types-{environment}`

**Primary Key:**

- **PK**: `typeId` (String) - Unique collection type identifier
- **SK**: Not used (single-item records)

**Attributes:**

- `typeId`: `"type_project"`
- `typeName`: `"Project"`
- `description`: `"Project collections for organizing work"`
- `allowedItemTypes`: `["asset", "workflow", "collection"]`
- `icon`: `"folder-project"`
- `color`: `"#4A90E2"`
- `metadataSchema`: `{JSON Schema object}`
- `isActive`: `true`
- `sortOrder`: `1`
- `createdAt`: `"2025-01-15T10:00:00Z"`
- `updatedAt`: `"2025-01-15T10:00:00Z"`

**Global Secondary Indexes:**

- **GSI1**: `isActive` (PK) + `sortOrder` (SK) - For filtering active types by sort order
- **GSI2**: `isActive` (PK) + `typeName` (SK) - For filtering active types by name
- **GSI3**: `isActive` (PK) + `createdAt` (SK) - For filtering active types by creation date

### 2. Collections Table

**Table Name:** `{resource_prefix}-collections-{environment}`

**Primary Key:**

- **PK**: `collectionId` (String) - Unique collection identifier
- **SK**: `METADATA` (String) - Fixed value for collection metadata records

**Attributes:**

- `collectionId`: `"col_98765"`
- `name`: `"Q3 Marketing Campaign"`
- `description`: `"All assets for Q3 2025 marketing push"`
- `collectionTypeId`: `"type_project"`
- `parentId`: `"col_parent"` (nullable)
- `ownerId`: `"user_12345"`
- `metadata`: `{...}` (flexible JSON)
- `tags`: `{...}` (key-value pairs)
- `status`: `"ACTIVE"` | `"ARCHIVED"` | `"DELETED"`
- `itemCount`: `42`
- `childCollectionCount`: `3`
- `expiresAt`: `"2025-12-31T23:59:59Z"` (TTL, nullable)
- `createdAt`: `"2025-07-24T18:54:00Z"`
- `updatedAt`: `"2025-07-25T10:30:00Z"`

**TTL Attribute:** `expiresAt`

**Global Secondary Indexes:**

- **GSI1**: `ownerId` (PK) + `updatedAt` (SK) - Query collections by owner
- **GSI2**: `collectionTypeId` (PK) + `createdAt` (SK) - Query collections by type
- **GSI3**: `status` (PK) + `updatedAt` (SK) - Query collections by status
- **GSI4**: `parentId` (PK) + `name` (SK) - Query child collections by parent
- **GSI5**: `ownerId#status` (PK) + `name` (SK) - Composite key for owner+status queries

### 3. Collection Items Table

**Table Name:** `{resource_prefix}-collection-items-{environment}`

**Primary Key:**

- **PK**: `collectionId` (String) - Collection identifier
- **SK**: `itemType#itemId` (String) - Composite sort key for item identification

**Attributes:**

- `collectionId`: `"col_98765"`
- `itemType`: `"asset"` | `"workflow"` | `"collection"`
- `itemId`: `"asset_1001"`
- `sortOrder`: `1` (nullable, for custom ordering)
- `metadata`: `{...}` (item-specific metadata within collection)
- `addedAt`: `"2025-07-24T19:00:00Z"`
- `addedBy`: `"user_12345"`

**Global Secondary Indexes:**

- **GSI1**: `collectionId` (PK) + `sortOrder` (SK) - Query items by custom sort order
- **GSI2**: `collectionId` (PK) + `addedAt` (SK) - Query items by added date
- **GSI3**: `collectionId#itemType` (PK) + `addedAt` (SK) - Query items by type within collection

### 4. Collection Rules Table

**Table Name:** `{resource_prefix}-collection-rules-{environment}`

**Primary Key:**

- **PK**: `collectionId` (String) - Collection identifier
- **SK**: `priority#ruleId` (String) - Composite sort key for priority-based ordering

**Attributes:**

- `collectionId`: `"col_98765"`
- `ruleId`: `"rule_543"`
- `name`: `"Purple Racing Cars"`
- `description`: `"Automatically add images of purple racing cars"`
- `ruleType`: `"semantic"` | `"metadata"` | `"keyword"` | `"composite"`
- `criteria`: `{...}` (rule-specific criteria JSON)
- `isActive`: `true`
- `priority`: `10` (higher = evaluated first)
- `matchCount`: `42` (cached count)
- `lastEvaluatedAt`: `"2025-07-25T09:00:00Z"`
- `createdAt`: `"2025-07-20T10:00:00Z"`
- `updatedAt`: `"2025-07-20T10:00:00Z"`

**Global Secondary Indexes:**

- **GSI1**: `collectionId#isActive` (PK) + `priority` (SK) - Query active rules by priority
- **GSI2**: `ruleType` (PK) + `lastEvaluatedAt` (SK) - Query rules by type for batch evaluation

### 5. Collection Sharing Table

**Table Name:** `{resource_prefix}-collection-sharing-{environment}`

**Primary Key:**

- **PK**: `collectionId` (String) - Collection identifier
- **SK**: `targetType#targetId` (String) - Target user or group identifier

**Attributes:**

- `collectionId`: `"col_98765"`
- `targetType`: `"user"` | `"group"`
- `targetId`: `"user_67890"`
- `role`: `"viewer"` | `"editor"` | `"admin"` | `"owner"`
- `sharedAt`: `"2025-07-25T10:00:00Z"`
- `sharedBy`: `"user_12345"`
- `expiresAt`: `"2025-12-31T23:59:59Z"` (nullable, for temporary shares)

**Global Secondary Indexes:**

- **GSI1**: `targetId` (PK) + `sharedAt` (SK) - Query collections shared with a user
- **GSI2**: `targetId#role` (PK) + `sharedAt` (SK) - Query collections by user and role
- **GSI3**: `sharedBy` (PK) + `sharedAt` (SK) - Query collections shared by a user

## Cursor Pagination Strategy

All tables will implement cursor-based pagination using base64-encoded JSON objects containing:

- Primary key values (PK + SK)
- GSI key values when querying via GSI
- Timestamp for tie-breaking

**Cursor Format:**

```json
{
  "pk": "col_98765",
  "sk": "METADATA",
  "timestamp": "2025-07-25T10:30:00Z"
}
```

**Encoded Cursor:** `eyJwayI6ImNvbF85ODc2NSIsInNrIjoiTUVUQURBVEEiLCJ0aW1lc3RhbXAiOiIyMDI1LTA3LTI1VDEwOjMwOjAwWiJ9`

## MediaLake Naming Convention Compliance

Following established patterns from `users_groups_stack.py`:

- Table names: `f"{config.resource_prefix}-{purpose}-{config.environment}"`
- Consistent use of `pk`/`sk` naming for composite keys
- GSI naming: `GSI1`, `GSI2`, etc.
- Point-in-time recovery enabled
- On-demand billing mode
- DynamoDB-owned encryption by default

## Performance Considerations

1. **Hot Partition Avoidance**: Use composite keys and distributed primary keys
2. **GSI Projection**: Use `ALL` projection for comprehensive querying
3. **Batch Operations**: Support batch writes for up to 100 items
4. **Consistent Pagination**: Maintain sort order consistency across requests
5. **TTL Optimization**: Automatic cleanup of expired collections and related items

## Data Consistency Patterns

- **Collection Deletion**: Implement cascade deletion for child collections and items
- **Item Count Maintenance**: Update parent collection item counts on item add/remove
- **Rule Evaluation**: Cache match counts for performance
- **Sharing Inheritance**: Handle permission inheritance for nested collections
