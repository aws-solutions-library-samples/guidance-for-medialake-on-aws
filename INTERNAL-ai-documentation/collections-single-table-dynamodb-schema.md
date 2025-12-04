# Collections API Single-Table DynamoDB Schema Design

## Table Structure

**Table Name:** `{resource_prefix}-collections-{environment}`

**Primary Key:** `PK` (String), `SK` (String)

**TTL Attribute:** `expiresAt` (on collection metadata records)

## Access Patterns & Item Types

### System Settings - Collection Types Configuration

**Pattern:** `PK: SYSTEM` `SK: COLLTYPE#{typeId}`

**Purpose:** Store collection type definitions and configuration

**Attributes:**

- `typeName`: Display name of the collection type
- `description`: Description of the collection type
- `allowedItemTypes`: Array of item types that can be added
- `icon`: Icon identifier for UI display
- `color`: Color code for UI display
- `defaultPermissions`: Default permission template
- `metadataSchema`: JSON Schema defining required/optional metadata fields
- `createdAt`: Timestamp
- `updatedAt`: Timestamp
- `isActive`: Boolean indicating if this type is available for use
- `sortOrder`: Number for display ordering in UI
- `validationRules`: Array of validation rules

**Access Method:** Scan with filter on `isActive` for UI display

---

### Collection Metadata

**Pattern:** `PK: COLL#{collectionId}` `SK: METADATA`

**Purpose:** Core collection information and properties

**Attributes:**

- `name`: Collection name
- `description`: Collection description
- `collectionTypeId`: Reference to the collection type
- `ownerId`: User who created the collection
- `createdAt`: Timestamp
- `updatedAt`: Timestamp
- `isPublic`: Boolean for visibility setting
- `customMetadata`: Object containing metadata fields
- `status`: "ACTIVE", "ARCHIVED", "DELETED"
- `itemCount`: Number of items in collection
- `childCollectionCount`: Number of child collections
- `tags`: Map of key-value pairs for tagging
- `expiresAt`: Optional TTL for temporary collections

**GSI Attributes:**

- `GSI3-PK`: `collectionTypeId`
- `GSI3-SK`: `COLL#{collectionId}`
- `GSI5-PK`: `"COLLECTIONS"` (constant)
- `GSI5-SK`: `updatedAt`

---

### Collection Items

**Pattern:** `PK: COLL#{collectionId}` `SK: ITEM#{itemId}`

**Purpose:** Items contained within collections

**Attributes:**

- `itemType`: "ASSET", "WORKFLOW", or "COLLECTION"
- `addedAt`: Timestamp
- `addedBy`: User ID
- `sortOrder`: Number for custom ordering
- `metadata`: Item-specific metadata within collection context

**GSI Attributes:**

- `GSI2-PK`: `ITEM#{itemId}`
- `GSI2-SK`: `COLL#{collectionId}`

---

### Collection Rules (NEW)

**Pattern:** `PK: COLL#{collectionId}` `SK: RULE#{priority}#{ruleId}`

**Purpose:** Automatic item assignment rules with priority-based evaluation

**Attributes:**

- `ruleId`: Unique rule identifier
- `name`: Human-readable rule name
- `description`: Rule description
- `ruleType`: "semantic", "metadata", "keyword", "composite"
- `criteria`: Rule-specific criteria object
- `isActive`: Boolean indicating if rule is active
- `priority`: Number for evaluation order (higher = first)
- `matchCount`: Cached count of items currently matching
- `lastEvaluatedAt`: Timestamp of last rule evaluation
- `createdAt`: Timestamp
- `updatedAt`: Timestamp
- `createdBy`: User who created the rule

**Sort Order:** Rules naturally sort by priority due to SK structure `RULE#{priority}#{ruleId}`

---

### Child Collections

**Pattern:** `PK: COLL#{collectionId}` `SK: CHILD#{childCollectionId}`

**Purpose:** Hierarchical parent-child collection relationships

**Attributes:**

- `childCollectionId`: ID of the child collection
- `addedAt`: When child was linked to parent
- `addedBy`: User who created the relationship

**GSI Attributes:**

- `GSI4-PK`: `CHILD#{childCollectionId}`
- `GSI4-SK`: `COLL#{collectionId}`

---

### User Collection Relationships

**Pattern:** `PK: USER#{userId}` `SK: COLL#{collectionId}`

**Purpose:** Track user relationships and access to collections

**Attributes:**

- `relationship`: "OWNER", "CONTRIBUTOR", "VIEWER"
- `addedAt`: Timestamp
- `lastAccessed`: Timestamp
- `isFavorite`: Boolean for user favorites

**GSI Attributes:**

- `GSI1-PK`: `USER#{userId}`
- `GSI1-SK`: `lastAccessed` (for sorting by recent access)

---

### Collection Permissions

**Pattern:** `PK: COLL#{collectionId}` `SK: PERM#{userId/groupId}`

**Purpose:** Granular permissions for users and groups

**Attributes:**

- `targetType`: "USER" or "GROUP"
- `targetId`: User ID or Group ID
- `permissions`: Detailed permission object:
  ```json
  {
    "items": {
      "read": boolean,
      "create": boolean,
      "update": boolean,
      "delete": boolean
    },
    "metadata": {
      "read": boolean,
      "update": boolean
    },
    "settings": {
      "read": boolean,
      "update": boolean
    }
  }
  ```
- `grantedBy`: User who granted these permissions
- `grantedAt`: Timestamp
- `expiresAt`: Optional expiration for temporary permissions

---

### Collection Versions

**Pattern:** `PK: COLL#{collectionId}` `SK: VERSION#{versionNumber}`

**Purpose:** Track collection changes and enable version history

**Attributes:**

- `changedBy`: User ID who made the change
- `changedAt`: Timestamp
- `changes`: Array of changed fields
- `previousValues`: Map of previous values before change

---

## Global Secondary Indexes

### GSI1: UserCollectionsGSI

**Purpose:** Find all collections a user has access to

- **GSI1-PK:** `USER#{userId}`
- **GSI1-SK:** `lastAccessed` (for sorting by recent access)
- **Projection:** ALL

**Query Pattern:** Get user's collections sorted by recent access

### GSI2: ItemCollectionsGSI

**Purpose:** Find all collections containing a specific item

- **GSI2-PK:** `ITEM#{itemId}`
- **GSI2-SK:** `COLL#{collectionId}`
- **Projection:** ALL

**Query Pattern:** Find which collections contain a specific asset/workflow/collection

### GSI3: CollectionTypeGSI

**Purpose:** Find collections by type

- **GSI3-PK:** `collectionTypeId`
- **GSI3-SK:** `COLL#{collectionId}`
- **Projection:** ALL

**Query Pattern:** Get all collections of a specific type

### GSI4: ParentChildGSI

**Purpose:** Find all parent collections of a child collection

- **GSI4-PK:** `CHILD#{childCollectionId}`
- **GSI4-SK:** `COLL#{collectionId}`
- **Projection:** ALL

**Query Pattern:** Find parent collections for hierarchical navigation

### GSI5: RecentlyModifiedGSI

**Purpose:** Find recently modified collections across all users

- **GSI5-PK:** `"COLLECTIONS"` (constant value)
- **GSI5-SK:** `updatedAt` (in descending order)
- **Projection:** ALL

**Query Pattern:** Get recently modified collections system-wide

## Cursor Pagination Strategy

### For Main Table Queries

**Cursor Format:**

```json
{
  "pk": "COLL#col_12345",
  "sk": "METADATA",
  "timestamp": "2025-07-25T10:30:00Z"
}
```

### For GSI Queries

**Cursor Format:**

```json
{
  "pk": "COLL#col_12345",
  "sk": "METADATA",
  "gsi1_pk": "USER#user_456",
  "gsi1_sk": "2025-07-25T10:30:00Z",
  "timestamp": "2025-07-25T10:30:00Z"
}
```

**Encoding:** Base64-encoded JSON cursor for opacity

## OpenAPI Endpoint Mapping

### Collection Types

- `GET /collection-types` → Scan `PK: SYSTEM, SK: begins_with("COLLTYPE#")` with filter
- `POST /collection-types` → Put item with `PK: SYSTEM, SK: COLLTYPE#{typeId}`

### Collections

- `GET /collections` → Multiple patterns:

  - All collections: GSI5 query with `PK: "COLLECTIONS"`
  - By owner: GSI1 query with `PK: USER#{userId}`
  - By type: GSI3 query with `PK: {collectionTypeId}`
  - By parent: Query `PK: COLL#{parentId}, SK: begins_with("CHILD#")`

- `GET /collections/{id}` → Get item `PK: COLL#{id}, SK: METADATA`
- `POST /collections` → Put item + create USER relationship
- `PATCH /collections/{id}` → Update item
- `DELETE /collections/{id}` → Update status or delete + cascade

### Collection Items

- `GET /collections/{id}/items` → Query `PK: COLL#{id}, SK: begins_with("ITEM#")`
- `POST /collections/{id}/items` → Put item + update itemCount
- `POST /collections/{id}/items/batch` → Batch write items
- `PUT /collections/{id}/items/{itemId}` → Update item
- `DELETE /collections/{id}/items/{itemId}` → Delete item + update count

### Collection Rules

- `GET /collections/{id}/rules` → Query `PK: COLL#{id}, SK: begins_with("RULE#")` (auto-sorted by priority)
- `POST /collections/{id}/rules` → Put item with calculated priority SK
- `PUT /collections/{id}/rules/{ruleId}` → Update item
- `DELETE /collections/{id}/rules/{ruleId}` → Delete item

### Collection Sharing

- `GET /collections/{id}/share` → Query `PK: COLL#{id}, SK: begins_with("PERM#")`
- `POST /collections/{id}/share` → Put permission item
- `DELETE /collections/{id}/share/{userId}` → Delete item
- `GET /collections/shared-with-me` → GSI1 query with relationship filter

## Performance Benefits of Single-Table Design

### Cost Optimization

- **Single Table**: 1 table × $0.25/month base = $0.25/month
- **Multi-Table**: 5 tables × $0.25/month base = $1.25/month
- **Savings**: 80% reduction in base costs

### Query Efficiency

- **Related Data Locality**: Items, permissions, rules co-located with collection
- **Reduced Cross-Table Joins**: No application-level joins needed
- **Hot Partition Avoidance**: Well-distributed access patterns
- **GSI Optimization**: Strategic indexes for common query patterns

### Operational Benefits

- **Single Backup/Restore**: One table to manage
- **Unified Monitoring**: Single set of metrics
- **Simplified Scaling**: One table scaling policy
- **Atomic Transactions**: Related items can be updated atomically

## Hierarchical Collection Support

### Parent-Child Relationships

- **Child Storage**: `PK: COLL#{parentId}, SK: CHILD#{childId}`
- **Parent Lookup**: GSI4 reverse lookup `PK: CHILD#{childId}`
- **Breadcrumb Navigation**: Recursive GSI4 queries up the hierarchy
- **Cascade Operations**: Query children before parent operations

### Metadata Inheritance

- Application-level logic to merge parent metadata with child metadata
- Version tracking captures inheritance changes

## Data Consistency Patterns

### Collection Operations

- **Create**: Atomic write of metadata + user relationship
- **Delete**: Conditional delete with child check or cascade
- **Item Count**: Update metadata itemCount on item add/remove
- **Permission Inheritance**: Check parent permissions via GSI4

### Rule Evaluation

- **Priority Ordering**: Natural sort via SK structure
- **Batch Processing**: Query all rules for collection, evaluate in order
- **Match Caching**: Update matchCount attribute on rule changes

This single-table design provides excellent performance, cost efficiency, and scalability while supporting all OpenAPI specification requirements.
