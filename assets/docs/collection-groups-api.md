# Collection Groups API Documentation

## Overview

Collection Groups provide a way to organize collections into logical groups for better management and filtering. This feature enables users to:

- Create named groups of collections
- Add/remove collections from groups
- Filter collections by group membership
- Use groups in dashboard widgets for focused views

## Authentication

All Collection Groups API endpoints require:

- **Cognito Authentication**: Valid JWT token in Authorization header
- **X-Origin-Verify**: Origin verification header

## Base URL

```
https://{apiId}.execute-api.{region}.amazonaws.com/v1/collections/groups
```

## Endpoints

### 1. List Collection Groups

Retrieve a paginated list of collection groups.

**Endpoint:** `GET /collections/groups`

**Query Parameters:**

- `search` (optional): Search term to filter groups by name
- `limit` (optional): Maximum number of results (default: 20, max: 100)
- `nextToken` (optional): Pagination token from previous response

**Request Example:**

```bash
curl -X GET "https://api.example.com/v1/collections/groups?search=project&limit=20" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}"
```

**Response (200 OK):**

```json
{
  "groups": [
    {
      "id": "grp_abc123",
      "name": "Project Alpha Assets",
      "description": "All assets related to Project Alpha",
      "ownerId": "user_123",
      "isPublic": true,
      "collectionIds": ["col_1", "col_2", "col_3"],
      "collectionCount": 3,
      "createdAt": "2025-01-15T10:30:00Z",
      "updatedAt": "2025-01-20T14:45:00Z",
      "isOwner": true,
      "userRole": "owner"
    }
  ],
  "nextToken": "eyJpZCI6ImdycF94eXoifQ==",
  "count": 1
}
```

**Error Responses:**

- `400 Bad Request`: Invalid query parameters
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

---

### 2. Create Collection Group

Create a new collection group.

**Endpoint:** `POST /collections/groups`

**Request Body:**

```json
{
  "name": "Project Alpha Assets",
  "description": "All assets related to Project Alpha",
  "isPublic": true
}
```

**Field Descriptions:**

- `name` (required): Group name (1-255 characters)
- `description` (optional): Group description (max 1000 characters)
- `isPublic` (optional): Whether group is publicly visible (default: true)

**Request Example:**

```bash
curl -X POST "https://api.example.com/v1/collections/groups" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Project Alpha Assets",
    "description": "All assets related to Project Alpha",
    "isPublic": true
  }'
```

**Response (201 Created):**

```json
{
  "id": "grp_abc123",
  "name": "Project Alpha Assets",
  "description": "All assets related to Project Alpha",
  "ownerId": "user_123",
  "isPublic": true,
  "collectionIds": [],
  "collectionCount": 0,
  "createdAt": "2025-01-30T10:30:00Z",
  "updatedAt": "2025-01-30T10:30:00Z",
  "isOwner": true,
  "userRole": "owner"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid request body or missing required fields
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

---

### 3. Get Collection Group

Retrieve details of a specific collection group.

**Endpoint:** `GET /collections/groups/{groupId}`

**Path Parameters:**

- `groupId` (required): Unique identifier of the collection group

**Request Example:**

```bash
curl -X GET "https://api.example.com/v1/collections/groups/grp_abc123" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}"
```

**Response (200 OK):**

```json
{
  "id": "grp_abc123",
  "name": "Project Alpha Assets",
  "description": "All assets related to Project Alpha",
  "ownerId": "user_123",
  "isPublic": true,
  "collectionIds": ["col_1", "col_2", "col_3"],
  "collectionCount": 3,
  "createdAt": "2025-01-15T10:30:00Z",
  "updatedAt": "2025-01-20T14:45:00Z",
  "isOwner": true,
  "userRole": "owner"
}
```

**Error Responses:**

- `404 Not Found`: Group does not exist
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

---

### 4. Update Collection Group

Update metadata of an existing collection group.

**Endpoint:** `PUT /collections/groups/{groupId}`

**Path Parameters:**

- `groupId` (required): Unique identifier of the collection group

**Request Body:**

```json
{
  "name": "Updated Project Name",
  "description": "Updated description",
  "isPublic": false
}
```

**Field Descriptions:**

- `name` (optional): New group name
- `description` (optional): New group description
- `isPublic` (optional): New visibility setting

**Request Example:**

```bash
curl -X PUT "https://api.example.com/v1/collections/groups/grp_abc123" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Project Name",
    "description": "Updated description"
  }'
```

**Response (200 OK):**

```json
{
  "id": "grp_abc123",
  "name": "Updated Project Name",
  "description": "Updated description",
  "ownerId": "user_123",
  "isPublic": true,
  "collectionIds": ["col_1", "col_2", "col_3"],
  "collectionCount": 3,
  "createdAt": "2025-01-15T10:30:00Z",
  "updatedAt": "2025-01-30T15:20:00Z",
  "isOwner": true,
  "userRole": "owner"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid request body
- `403 Forbidden`: User is not the owner of the group
- `404 Not Found`: Group does not exist
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

---

### 5. Delete Collection Group

Delete a collection group. This does not delete the collections themselves.

**Endpoint:** `DELETE /collections/groups/{groupId}`

**Path Parameters:**

- `groupId` (required): Unique identifier of the collection group

**Request Example:**

```bash
curl -X DELETE "https://api.example.com/v1/collections/groups/grp_abc123" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}"
```

**Response (204 No Content)**

**Error Responses:**

- `403 Forbidden`: User is not the owner of the group
- `404 Not Found`: Group does not exist
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

---

### 6. Add Collections to Group

Add one or more collections to a collection group.

**Endpoint:** `POST /collections/groups/{groupId}/collections`

**Path Parameters:**

- `groupId` (required): Unique identifier of the collection group

**Request Body:**

```json
{
  "collectionIds": ["col_4", "col_5", "col_6"]
}
```

**Field Descriptions:**

- `collectionIds` (required): Array of collection IDs to add (1-100 IDs per request)

**Request Example:**

```bash
curl -X POST "https://api.example.com/v1/collections/groups/grp_abc123/collections" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionIds": ["col_4", "col_5", "col_6"]
  }'
```

**Response (200 OK):**

```json
{
  "id": "grp_abc123",
  "name": "Project Alpha Assets",
  "description": "All assets related to Project Alpha",
  "ownerId": "user_123",
  "isPublic": true,
  "collectionIds": ["col_1", "col_2", "col_3", "col_4", "col_5", "col_6"],
  "collectionCount": 6,
  "createdAt": "2025-01-15T10:30:00Z",
  "updatedAt": "2025-01-30T16:00:00Z",
  "isOwner": true,
  "userRole": "owner"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid collection IDs or collections don't exist
- `403 Forbidden`: User is not the owner of the group
- `404 Not Found`: Group does not exist
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

**Notes:**

- Duplicate collection IDs are automatically handled (idempotent operation)
- All collection IDs are validated before adding
- Invalid collection IDs will result in a 400 error with details

---

### 7. Remove Collections from Group

Remove one or more collections from a collection group.

**Endpoint:** `DELETE /collections/groups/{groupId}/collections`

**Path Parameters:**

- `groupId` (required): Unique identifier of the collection group

**Request Body:**

```json
{
  "collectionIds": ["col_4", "col_5"]
}
```

**Field Descriptions:**

- `collectionIds` (required): Array of collection IDs to remove

**Request Example:**

```bash
curl -X DELETE "https://api.example.com/v1/collections/groups/grp_abc123/collections" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionIds": ["col_4", "col_5"]
  }'
```

**Response (200 OK):**

```json
{
  "id": "grp_abc123",
  "name": "Project Alpha Assets",
  "description": "All assets related to Project Alpha",
  "ownerId": "user_123",
  "isPublic": true,
  "collectionIds": ["col_1", "col_2", "col_3", "col_6"],
  "collectionCount": 4,
  "createdAt": "2025-01-15T10:30:00Z",
  "updatedAt": "2025-01-30T16:15:00Z",
  "isOwner": true,
  "userRole": "owner"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid request body
- `403 Forbidden`: User is not the owner of the group
- `404 Not Found`: Group does not exist
- `401 Unauthorized`: Missing or invalid authentication
- `500 Internal Server Error`: Server error

**Notes:**

- Removing non-existent collection IDs is silently ignored (idempotent operation)
- The collections themselves are not deleted, only the group membership

---

## Collection Filtering by Groups

Collection Groups can be used to filter collections in the main collections endpoint.

**Endpoint:** `GET /collections?groupIds={groupId1},{groupId2}`

**Query Parameters:**

- `groupIds` (optional): Comma-separated list of group IDs
- Other standard collection query parameters (viewType, limit, etc.)

**Request Example:**

```bash
curl -X GET "https://api.example.com/v1/collections?groupIds=grp_abc123,grp_xyz789&viewType=all" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}"
```

**Response (200 OK):**

```json
{
  "collections": [
    {
      "id": "col_1",
      "name": "Collection 1",
      "groups": ["grp_abc123"]
    },
    {
      "id": "col_2",
      "name": "Collection 2",
      "groups": ["grp_abc123", "grp_xyz789"]
    }
  ],
  "nextToken": null,
  "count": 2
}
```

**Filtering Logic:**

- **Multiple Groups (OR logic)**: Returns collections that belong to ANY of the specified groups
- **Combined with viewType (AND logic)**: Applies both group filter and viewType filter

**Examples:**

- `?groupIds=grp_1` - Collections in group 1
- `?groupIds=grp_1,grp_2` - Collections in group 1 OR group 2
- `?groupIds=grp_1&viewType=favorites` - Collections in group 1 AND marked as favorites

---

## Data Models

### CollectionGroup

```typescript
interface CollectionGroup {
  id: string; // Unique identifier (grp_*)
  name: string; // Group name (required)
  description?: string; // Optional description
  ownerId: string; // User ID of the owner
  isPublic: boolean; // Visibility flag
  collectionIds: string[]; // Array of collection IDs
  collectionCount: number; // Number of collections in group
  createdAt: string; // ISO 8601 timestamp
  updatedAt: string; // ISO 8601 timestamp
  isOwner?: boolean; // Whether current user is owner
  userRole?: string; // User's role (owner, viewer, etc.)
}
```

### CreateGroupRequest

```typescript
interface CreateGroupRequest {
  name: string; // Required, 1-255 characters
  description?: string; // Optional, max 1000 characters
  isPublic?: boolean; // Optional, default: true
}
```

### UpdateGroupRequest

```typescript
interface UpdateGroupRequest {
  name?: string; // Optional, 1-255 characters
  description?: string; // Optional, max 1000 characters
  isPublic?: boolean; // Optional
}
```

### AddCollectionsRequest

```typescript
interface AddCollectionsRequest {
  collectionIds: string[]; // Required, 1-100 IDs
}
```

### RemoveCollectionsRequest

```typescript
interface RemoveCollectionsRequest {
  collectionIds: string[]; // Required
}
```

---

## Authorization

### Permissions

- **Create Group**: Any authenticated user
- **View Group**: Owner (public groups visible to all in future)
- **Update Group**: Owner only
- **Delete Group**: Owner only
- **Add Collections**: Owner only (pipelines can also add in future)
- **Remove Collections**: Owner only (pipelines can also remove in future)

### Owner Assignment

- The user who creates a group is automatically assigned as the owner
- Owner cannot be changed after creation
- Only the owner can modify or delete the group

---

## Error Handling

### Standard Error Response

```json
{
  "error": "Error message",
  "message": "Detailed error description",
  "statusCode": 400
}
```

### Common Error Codes

- `400 Bad Request`: Invalid input, validation errors
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error

### Validation Errors

When adding collections, invalid collection IDs are returned in the error:

```json
{
  "error": "Invalid collection IDs",
  "message": "The following collection IDs do not exist: col_invalid1, col_invalid2",
  "invalidIds": ["col_invalid1", "col_invalid2"],
  "statusCode": 400
}
```

---

## Best Practices

### 1. Group Naming

- Use descriptive names that clearly indicate the group's purpose
- Keep names concise (under 100 characters recommended)
- Use consistent naming conventions across your organization

### 2. Group Organization

- Create groups based on projects, teams, or workflows
- Avoid creating too many small groups (consider consolidation)
- Use descriptions to provide context

### 3. Collection Management

- Add collections in batches (up to 100 at a time) for efficiency
- Regularly review and clean up unused groups
- Use group filtering in dashboards for focused views

### 4. Performance

- Limit the number of groups per user to improve performance
- Use pagination when listing groups
- Cache group data on the client side when appropriate

---

## Examples

### Complete Workflow Example

```bash
# 1. Create a new group
GROUP_ID=$(curl -X POST "https://api.example.com/v1/collections/groups" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Origin-Verify: $ORIGIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q1 2025 Campaign",
    "description": "All collections for Q1 marketing campaign"
  }' | jq -r '.id')

# 2. Add collections to the group
curl -X POST "https://api.example.com/v1/collections/groups/$GROUP_ID/collections" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Origin-Verify: $ORIGIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionIds": ["col_1", "col_2", "col_3"]
  }'

# 3. Filter collections by group
curl -X GET "https://api.example.com/v1/collections?groupIds=$GROUP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Origin-Verify: $ORIGIN_TOKEN"

# 4. Update group metadata
curl -X PUT "https://api.example.com/v1/collections/groups/$GROUP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Origin-Verify: $ORIGIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated: All collections for Q1 2025 marketing campaign"
  }'

# 5. Remove a collection from the group
curl -X DELETE "https://api.example.com/v1/collections/groups/$GROUP_ID/collections" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Origin-Verify: $ORIGIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionIds": ["col_3"]
  }'

# 6. Delete the group (when no longer needed)
curl -X DELETE "https://api.example.com/v1/collections/groups/$GROUP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Origin-Verify: $ORIGIN_TOKEN"
```

---

## Changelog

### Version 1.0.0 (2025-01-30)

- Initial release of Collection Groups API
- Support for creating, updating, and deleting groups
- Support for adding and removing collections
- Collection filtering by group IDs
- Owner-based authorization model

---

## Support

For API support or to report issues:

- Email: api-support@medialake.example.com
- Documentation: https://docs.medialake.example.com
- GitHub Issues: https://github.com/medialake/medialake/issues
