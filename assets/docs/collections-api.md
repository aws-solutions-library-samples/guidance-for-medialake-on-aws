# Collections API Documentation

## Overview

The Collections API provides endpoints for creating and managing collections of media assets. Collections support hierarchical organization (parent/child), tagging, custom metadata, thumbnails, and grouping via Collection Groups.

## Authentication

All endpoints require one of the following authentication methods, plus the origin verification header:

- **Cognito JWT** (primary): Pass a valid JWT token in the `Authorization` header as a Bearer token.
- **API Key** (alternative): Pass a valid API key in the `X-Api-Key` header. API keys are managed via the Settings API and stored in DynamoDB. When using an API key, the authorizer generates synthetic user claims from the key's metadata.

If both an `Authorization` Bearer token and an `X-Api-Key` header are present, JWT authentication takes precedence.

All requests must also include:

- **X-Origin-Verify**: Origin verification header

## Base URL

```
https://{apiId}.execute-api.{region}.amazonaws.com/v1/collections
```

---

## 1. Create a Collection

Create a new collection to organize media assets.

**Endpoint:** `POST /collections`

**Request Body:**

```json
{
  "name": "My Collection",
  "description": "A collection of video assets",
  "collectionTypeId": "type_abc123",
  "parentId": "col_parent01",
  "isPublic": false,
  "metadata": {
    "project": "Campaign Q1",
    "department": "Marketing"
  },
  "tags": ["marketing", "2025"]
}
```

**Field Descriptions:**

| Field              | Type     | Required | Description                                                              |
| ------------------ | -------- | -------- | ------------------------------------------------------------------------ |
| `name`             | string   | Yes      | Collection name (1–200 characters). Whitespace-only values are rejected. |
| `description`      | string   | No       | Collection description (max 1000 characters)                             |
| `collectionTypeId` | string   | No       | ID of a predefined collection type                                       |
| `parentId`         | string   | No       | Parent collection ID to create a nested (child) collection               |
| `isPublic`         | boolean  | No       | Whether the collection is publicly visible (default: `false`)            |
| `metadata`         | object   | No       | Arbitrary key-value pairs for custom metadata                            |
| `tags`             | string[] | No       | List of tags (max 50, duplicates removed automatically)                  |

**Request Example (Cognito JWT):**

```bash
curl -X POST "https://api.example.com/v1/collections" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Collection",
    "description": "A collection of video assets",
    "isPublic": false,
    "tags": ["marketing", "2025"]
  }'
```

**Request Example (API Key):**

```bash
curl -X POST "https://api.example.com/v1/collections" \
  -H "X-Api-Key: {api-key}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Collection",
    "description": "A collection of video assets",
    "isPublic": false,
    "tags": ["marketing", "2025"]
  }'
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": {
    "id": "col_a1b2c3d4",
    "name": "My Collection",
    "description": "A collection of video assets",
    "collectionTypeId": "",
    "parentId": null,
    "ownerId": "user_123",
    "metadata": {},
    "tags": ["marketing", "2025"],
    "status": "ACTIVE",
    "itemCount": 0,
    "childCollectionCount": 0,
    "isPublic": false,
    "isShared": false,
    "shareCount": 0,
    "sharedWithMe": false,
    "isFavorite": false,
    "userRole": "owner",
    "createdAt": "2025-02-10T12:00:00Z",
    "updatedAt": "2025-02-10T12:00:00Z"
  },
  "meta": {
    "timestamp": "2025-02-10T12:00:00Z",
    "version": "v1",
    "request_id": "abc123-def456"
  }
}
```

**Behavior Notes:**

- A unique ID is generated in the format `col_{uuid8}`.
- The authenticated user is automatically assigned as the owner.
- A user-collection relationship record (`OWNER`) is created transactionally.
- If `parentId` is provided, a child reference is created in the parent collection and the parent's `childCollectionCount` is incremented — all within a single DynamoDB transaction.

**Error Responses:**

| Status                      | Description                                                                    |
| --------------------------- | ------------------------------------------------------------------------------ |
| `400 Bad Request`           | Validation error (missing name, name is whitespace-only, tags exceed 50, etc.) |
| `401 Unauthorized`          | Missing or invalid authentication                                              |
| `500 Internal Server Error` | Server error                                                                   |

---

## 2. Upload a Collection Thumbnail

Set or replace the thumbnail image for a collection. Supports direct image upload, copying from an existing asset, or using a captured video frame.

**Endpoint:** `POST /collections/{collectionId}/thumbnail`

**Path Parameters:**

- `collectionId` (required): The collection's unique identifier (e.g. `col_a1b2c3d4`)

**Request Body:**

The request body varies by source type:

### Source: `upload` (base64-encoded image)

```json
{
  "source": "upload",
  "data": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

### Source: `asset` (copy from existing asset)

```json
{
  "source": "asset",
  "assetId": "asset:uuid:550e8400-e29b-41d4-a716-446655440000"
}
```

### Source: `frame` (base64-encoded video frame capture)

```json
{
  "source": "frame",
  "data": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Field Descriptions:**

| Field     | Type   | Required    | Description                                                                                                                                                  |
| --------- | ------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `source`  | string | Yes         | One of `upload`, `asset`, or `frame`                                                                                                                         |
| `data`    | string | Conditional | Base64-encoded image data. Required when `source` is `upload` or `frame`. Supports data-URL format (`data:image/png;base64,...`). Max 10 MB before encoding. |
| `assetId` | string | Conditional | ID of the asset whose thumbnail to copy. Required when `source` is `asset`.                                                                                  |

**Request Example (Cognito JWT):**

```bash
curl -X POST "https://api.example.com/v1/collections/col_a1b2c3d4/thumbnail" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "upload",
    "data": "iVBORw0KGgoAAAANSUhEUgAA..."
  }'
```

**Request Example (API Key):**

```bash
curl -X POST "https://api.example.com/v1/collections/col_a1b2c3d4/thumbnail" \
  -H "X-Api-Key: {api-key}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "upload",
    "data": "iVBORw0KGgoAAAANSUhEUgAA..."
  }'
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": "col_a1b2c3d4",
    "thumbnailType": "upload",
    "thumbnailUrl": "https://d1234abcdef.cloudfront.net/collections/col_a1b2c3d4/thumbnail.png",
    "updatedAt": "2025-02-10T14:30:00Z"
  },
  "meta": {
    "timestamp": "2025-02-10T14:30:00Z",
    "version": "v1",
    "request_id": "abc123-def456"
  }
}
```

**Behavior Notes:**

- Only the collection owner can set the thumbnail.
- For `upload` and `frame` sources, the image is decoded, resized to fit within 512×512 pixels (aspect ratio preserved), converted to PNG, and stored at `collections/{collectionId}/thumbnail.png` in S3.
- For `asset` source, the asset's existing thumbnail is copied to the collection's S3 location.
- The `thumbnailUrl` in the response is a CloudFront-signed URL.
- Uploading a new thumbnail replaces any previously set thumbnail.

**Error Responses:**

| Status                      | Description                                                                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `400 Bad Request`           | Missing required fields, invalid source type, image too large (>10 MB), image processing failure, or caller is not the owner |
| `404 Not Found`             | Collection or referenced asset not found                                                                                     |
| `401 Unauthorized`          | Missing or invalid authentication                                                                                            |
| `500 Internal Server Error` | Server error                                                                                                                 |

---

## 3. Add Collections to a Collection Group

Add one or more existing collections to a collection group.

**Endpoint:** `POST /collections/groups/{groupId}/collections`

**Path Parameters:**

- `groupId` (required): Unique identifier of the collection group (e.g. `grp_abc123`)

**Request Body:**

```json
{
  "collectionIds": ["col_a1b2c3d4", "col_e5f6g7h8", "col_i9j0k1l2"]
}
```

**Field Descriptions:**

| Field           | Type     | Required | Description                                                                                                  |
| --------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `collectionIds` | string[] | Yes      | Array of collection IDs to add (1–100 per request). Duplicates and empty strings are stripped automatically. |

**Request Example (Cognito JWT):**

```bash
curl -X POST "https://api.example.com/v1/collections/groups/grp_abc123/collections" \
  -H "Authorization: Bearer {token}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionIds": ["col_a1b2c3d4", "col_e5f6g7h8"]
  }'
```

**Request Example (API Key):**

```bash
curl -X POST "https://api.example.com/v1/collections/groups/grp_abc123/collections" \
  -H "X-Api-Key: {api-key}" \
  -H "X-Origin-Verify: {origin-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionIds": ["col_a1b2c3d4", "col_e5f6g7h8"]
  }'
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": "grp_abc123",
    "name": "Project Alpha Assets",
    "description": "All assets related to Project Alpha",
    "ownerId": "user_123",
    "isPublic": true,
    "collectionIds": ["col_1", "col_2", "col_a1b2c3d4", "col_e5f6g7h8"],
    "collectionCount": 4,
    "createdAt": "2025-01-15T10:30:00Z",
    "updatedAt": "2025-02-10T15:00:00Z",
    "isOwner": true,
    "userRole": "owner"
  },
  "meta": {
    "request_id": "abc123-def456"
  }
}
```

**Behavior Notes:**

- Only the group owner can add collections.
- All collection IDs are validated before any are added. If any ID doesn't correspond to an existing collection, the entire request is rejected with a `400` listing the invalid IDs.
- Adding collection IDs that are already in the group is idempotent — no error is raised and no duplicates are created.

**Error Responses:**

| Status                      | Description                                                             |
| --------------------------- | ----------------------------------------------------------------------- |
| `400 Bad Request`           | Validation error, empty list, or one or more collection IDs don't exist |
| `403 Forbidden`             | Caller is not the group owner                                           |
| `404 Not Found`             | Collection group not found                                              |
| `401 Unauthorized`          | Missing or invalid authentication                                       |
| `500 Internal Server Error` | Server error                                                            |

**Validation Error Example:**

```json
{
  "error": "Invalid collection IDs",
  "message": "The following collection IDs do not exist: col_invalid1, col_invalid2",
  "invalidIds": ["col_invalid1", "col_invalid2"],
  "statusCode": 400
}
```

---

## Standard Error Response Format

All error responses follow this structure:

```json
{
  "error": "ErrorCode",
  "message": "Human-readable error description",
  "statusCode": 400
}
```
