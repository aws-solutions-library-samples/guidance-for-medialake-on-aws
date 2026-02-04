# Separate Asset Embeddings Index Architecture

## Overview

This document describes the architectural changes to separate Marengo 3.0 vector embeddings into their own OpenSearch index (`asset-embeddings`), while keeping Marengo 2.7 embeddings in the existing `media` index.

## Current State

### Single Index Architecture

Currently, both Marengo 2.7 and 3.0 embeddings are stored in the same `media` OpenSearch index:

```
OpenSearch Index: "media"
├── Master Documents (Asset metadata)
│   ├── InventoryID
│   ├── DigitalSourceAsset
│   ├── DerivedRepresentations
│   └── Marengo 2.7 embeddings (embedded in document)
│       ├── embedding (root level)
│       ├── embedding_scope: "clip"
│       └── DigitalAsset.embedding (nested)
│
└── Marengo 3.0 Embedding Documents (separate)
    ├── inventory_id (reference to parent)
    ├── embedding_granularity: "asset" | "segment"
    ├── embedding_representation: "visual" | "audio" | "text" | "video"
    ├── embedding_1024_cosine, embedding_3072_cosine, etc.
    ├── start_seconds, end_seconds
    └── model_version: "3.0"
```

### Problems with Current State

1. Mixed document types in single index complicates queries
2. Marengo 3.0 documents pollute the main asset index
3. No clear separation of concerns between metadata and embeddings
4. Search queries must handle both formats simultaneously

## Target State

### Dual Index Architecture

```
OpenSearch Index: "media" (Metadata + Marengo 2.7)
├── Master Documents (Asset metadata)
│   ├── InventoryID
│   ├── DigitalSourceAsset
│   ├── DerivedRepresentations
│   └── Marengo 2.7 embeddings (legacy, embedded)
│       ├── embedding (root level)
│       ├── embedding_scope: "clip"
│       └── DigitalAsset.embedding (nested)

OpenSearch Index: "asset-embeddings" (Marengo 3.0 only)
├── Embedding Documents
│   ├── inventory_id (reference to parent in "media" index)
│   ├── embedding_granularity: "asset" | "segment"
│   ├── embedding_representation: "visual" | "audio" | "text" | "video"
│   ├── embedding_1024_cosine, embedding_3072_cosine, etc.
│   ├── start_seconds, end_seconds
│   ├── model_version: "3.0"
│   └── created_at
```

### S3 Vector Store (Unchanged)

```
S3 Vector Bucket: "media-vectors"
├── Vectors with metadata
│   ├── inventory_id
│   ├── embedding_option
│   └── timecodes
```

## Implementation Phases

### Phase 1: Infrastructure (CDK/CloudFormation) ✅ COMPLETED

**Files Modified:**

- `medialake_stacks/base_infrastructure.py` - Added `asset_embeddings_index_name` property, updated `collection_indexes` list
- `medialake_constructs/shared_constructs/opensearch_managed_cluster.py` - Already supports multiple indexes
- `lambdas/back_end/create_os_index/index.py` - Added `ASSET_EMBEDDINGS_INDEX` constant and dedicated mapping

**Implementation Details:**

1. Added `asset_embeddings_index_name = "asset-embeddings"` local variable
2. Updated `collection_indexes` to include both `["media", "asset-embeddings"]`
3. Created dedicated `asset_embeddings_payload` mapping with:
   - KNN fields: `embedding_1024_cosine`, `embedding_3072_cosine`
   - Keyword fields: `inventory_id`, `embedding_granularity`, `embedding_representation`, `model_version`
   - Date field: `created_at`
   - Float fields: `start_seconds`, `end_seconds`
4. Modified index creation loop to use index-specific mappings

### Phase 2: Embedding Store (Lambda) ✅ COMPLETED

**Files Modified:**

- `lambdas/nodes/embedding_store/index.py` - Added index routing logic
- `lambdas/api/pipelines/post_pipelines/lambda_operations.py` - Added env var to pipeline lambdas
- `medialake_constructs/api_gateway/api_gateway_pipelines.py` - Added env var to post_pipelines Lambda

**Implementation Details:**

1. Added `ASSET_EMBEDDINGS_INDEX` environment variable (defaults to "asset-embeddings")
2. Added `_get_target_index()` helper function for model version detection
3. Marengo 3.0 (detected by `is_marengo_30=True`) → writes to `asset-embeddings`
4. Marengo 2.7/legacy → writes to `media` (unchanged)
5. Clear logging showing which index is selected for each write

### Phase 3: Search Lambda (Config-Based Query) ✅ COMPLETED

**Files Modified:**

- `lambdas/api/search/get_search/opensearch_embedding_store.py` - Added configurable `target_index` parameter
- `lambdas/api/search/get_search/bedrock_twelvelabs_search_provider.py` - Uses `target_index` from config
- `lambdas/api/search/get_search/unified_search_orchestrator.py` - Routes based on provider type config
- `medialake_constructs/api_gateway/api_gateway_search.py` - Added `ASSET_EMBEDDINGS_INDEX` env var

**Implementation Details:**

1. Added `PROVIDER_INDEX_MAPPING` constant in unified_search_orchestrator.py
2. Added `_get_target_index_for_provider()` method to determine target index
3. Provider config now includes `target_index` field
4. `BedrockTwelveLabsSearchProvider` uses `self._target_index` for queries
5. `OpenSearchEmbeddingStore` accepts optional `target_index` parameter
6. Clear logging with `[INDEX ROUTING]` prefix for debugging

**Index Routing Logic:**

- `twelvelabs` / `twelvelabs-bedrock` → Query `media` index (Marengo 2.7)
- `twelvelabs-bedrock-3-0` → Query `asset-embeddings` index (Marengo 3.0)
- Default fallback to `OPENSEARCH_INDEX` (media) for backward compatibility

**Environment Variables:**

- `OPENSEARCH_INDEX` = "media" (existing)
- `ASSET_EMBEDDINGS_INDEX` = "asset-embeddings" (new)

### Phase 4: Asset Operations (Deletion/Retrieval) ✅ COMPLETED

**Files Modified:**

- `lambdas/common_libraries/asset_deletion_service.py` - Delete from both indexes
- `lambdas/common_libraries/twelvelabs_plugin.py` - Delete from both indexes
- `lambdas/api/assets/rp_assets_id/get_assets/index.py` - Query clips from correct index
- `medialake_constructs/api_gateway/api_gateway_assets.py` - Added ASSET_EMBEDDINGS_INDEX env var

**Implementation Details:**

1. **Asset Deletion Service (`asset_deletion_service.py`)**:

   - Added `ASSET_EMBEDDINGS_INDEX` environment variable
   - Updated `_delete_opensearch_docs()` to call new `_delete_from_opensearch_index()` helper
   - Deletes from `media` index first, then from `asset-embeddings` index
   - Clear logging with `[INDEX DELETION]` prefix for debugging
   - Handles 404 gracefully (index may not exist yet)

2. **TwelveLabs Plugin (`twelvelabs_plugin.py`)**:

   - Added `asset_embeddings_index` instance variable
   - Updated `_delete_from_opensearch()` to delete from both indexes
   - Added `_delete_from_index()` helper method for DRY code
   - Handles 404 gracefully for indexes that don't exist yet

3. **Get Assets Lambda (`get_assets/index.py`)**:

   - Updated `get_asset_clips()` to query `asset-embeddings` first for Marengo 3.0 clips
   - Falls back to `media` index for Marengo 2.7 clips
   - Clear logging with `[INDEX ROUTING]` prefix
   - Handles NotFoundError gracefully when index doesn't exist

4. **CDK Updates (`api_gateway_assets.py`)**:
   - Added `ASSET_EMBEDDINGS_INDEX: "asset-embeddings"` to:
     - `get_asset_lambda` environment variables
     - `delete_asset_lambda` environment variables
     - `batch_delete` common_env_vars

**Deletion Strategy Implemented:**

- Delete from `media` index: Query by InventoryID (master doc) + inventory_id (any 3.0 docs)
- Delete from `asset-embeddings` index: Query by inventory_id (all Marengo 3.0 embedding docs)

**Retrieval Strategy Implemented:**

- Try `asset-embeddings` first for Marengo 3.0 clips (inventory_id + embedding_granularity: segment)
- Fallback to `media` index for Marengo 2.7 clips (DigitalSourceAsset.ID + embedding_scope: clip)

## Index Mapping for "asset-embeddings"

```json
{
  "settings": {
    "index": {
      "knn": true,
      "number_of_shards": 2,
      "number_of_replicas": 1
    }
  },
  "mappings": {
    "properties": {
      "inventory_id": { "type": "keyword" },
      "embedding_granularity": { "type": "keyword" },
      "segmentation_method": { "type": "keyword" },
      "embedding_representation": { "type": "keyword" },
      "embedding_dimension": { "type": "integer" },
      "embedding_type": { "type": "keyword" },
      "model_version": { "type": "keyword" },
      "created_at": { "type": "date" },
      "start_seconds": { "type": "float" },
      "end_seconds": { "type": "float" },
      "start_smpte_timecode": { "type": "keyword" },
      "end_smpte_timecode": { "type": "keyword" },
      "embedding_1024_cosine": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      },
      "embedding_3072_cosine": {
        "type": "knn_vector",
        "dimension": 3072,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      }
    }
  }
}
```

## Environment Variables

| Variable                 | Value              | Used By                             |
| ------------------------ | ------------------ | ----------------------------------- |
| `OPENSEARCH_INDEX`       | `media`            | Search, Asset operations (existing) |
| `ASSET_EMBEDDINGS_INDEX` | `asset-embeddings` | Search, Embedding store (new)       |

## Search Provider Configuration Mapping

| Provider Type            | Query Index        | Embedding Model       |
| ------------------------ | ------------------ | --------------------- |
| `twelvelabs`             | `media`            | Marengo 2.7 (API)     |
| `twelvelabs-bedrock`     | `media`            | Marengo 2.7 (Bedrock) |
| `twelvelabs-bedrock-3-0` | `asset-embeddings` | Marengo 3.0 (Bedrock) |

## Testing Strategy

1. **Unit Tests**: Mock OpenSearch client, verify correct index selection
2. **Integration Tests**: Deploy to dev, test search with both provider types
3. **Backward Compatibility**: Ensure Marengo 2.7 searches still work
4. **Forward Compatibility**: Verify new Marengo 3.0 embeddings go to correct index

## Rollback Plan

1. Revert environment variable changes
2. Remove `asset-embeddings` index creation
3. Marengo 3.0 embeddings will continue to go to `media` index (current behavior)

## Timeline

- Phase 1 (Infrastructure): 1 day
- Phase 2 (Embedding Store): 1 day
- Phase 3 (Search Lambda): 2 days
- Phase 4 (Asset Operations): 1 day
- Phase 5 (Testing): 1 day

**Total: ~6 days**
