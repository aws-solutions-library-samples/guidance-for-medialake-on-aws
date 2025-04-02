# Semantic Search Implementation Plan

## Current Behavior
Currently, when semantic search is enabled (`params.semantic` is true), the code:
1. Generates an embedding for the search query using the Twelve Labs API
2. Creates a KNN search query to find semantically similar content
3. Explicitly excludes documents with `"embedding_scope": "clip"` using a `must_not` clause

## Requirements
The goal is to modify the search functionality to:
1. Include clips in semantic search results (remove the exclusion)
2. Merge clips with the same parent asset (grouped by `DigitalSourceAsset.ID`)
3. Include the top 30 clips per parent asset, ordered by score
4. Structure clips as a nested array within each parent asset result
5. Optimize for performance using multi-threading

## Implementation Plan

### 1. Modify the Semantic Query
Remove the exclusion of clips in the `build_semantic_query` function so that documents with `"embedding_scope": "clip"` are included in search results.

```python
# Current code (to be modified)
return {
    "size": params.pageSize,
    "query": {
        "bool": {
            "must": [
                {
                    "knn": {
                        "embedding": {
                            "vector": embedding,
                            "k": params.pageSize * 3
                        }
                    }
                }
            ],
            "must_not": [
                {
                    "term": {
                        "embedding_scope": "clip"
                    }
                }
            ]
        }
    },
    "_source": {
        "excludes": ["embedding"]
    }
}

# Modified code (remove the must_not clause)
return {
    "size": params.pageSize * 10,  # Increase size to get more results for grouping
    "query": {
        "bool": {
            "must": [
                {
                    "knn": {
                        "embedding": {
                            "vector": embedding,
                            "k": params.pageSize * 10  # Increase k to get more results
                        }
                    }
                }
            ]
        }
    },
    "_source": {
        "excludes": ["embedding"]
    }
}
```

### 2. Process and Group Search Results
Create a new function `process_semantic_results` to:
- Separate parent assets and clips
- Group clips by parent asset ID
- Sort and limit clips to top 30 per parent
- Merge clips into parent assets

```python
def process_semantic_results(hits: List[Dict]) -> List[Dict]:
    """
    Process semantic search results to group clips with their parent assets.
    
    Args:
        hits: List of search hits from OpenSearch
        
    Returns:
        List of processed results with clips grouped by parent asset
    """
    # Separate parent assets and clips
    parent_assets = {}
    clips = {}
    
    for hit in hits:
        source = hit["_source"]
        if source.get("embedding_scope") == "clip":
            # This is a clip
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                if asset_id not in clips:
                    clips[asset_id] = []
                clips[asset_id].append({
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                })
        else:
            # This is a parent asset
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                parent_assets[asset_id] = {
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                }
    
    # Process clips for each parent asset (keep top 30 by score)
    for asset_id, asset_clips in clips.items():
        # Sort clips by score (descending)
        asset_clips.sort(key=lambda x: x["score"], reverse=True)
        # Keep only top 30
        clips[asset_id] = asset_clips[:30]
    
    # Merge clips into parent assets
    results = []
    for asset_id, asset in parent_assets.items():
        # Process the parent asset
        processed_asset = process_search_hit(asset["hit"])
        # Add clips if available
        if asset_id in clips:
            processed_asset.clips = [process_search_hit(clip["hit"]) for clip in clips[asset_id]]
        else:
            processed_asset.clips = []
        results.append(processed_asset)
    
    # Handle orphaned clips (clips without a parent in the results)
    for asset_id, asset_clips in clips.items():
        if asset_id not in parent_assets:
            # Create a placeholder parent asset from the first clip
            if asset_clips:
                first_clip = asset_clips[0]
                parent_hit = first_clip["hit"].copy()
                # Remove clip-specific fields
                parent_source = first_clip["source"].copy()
                if "embedding_scope" in parent_source:
                    del parent_source["embedding_scope"]
                if "start_timecode" in parent_source:
                    del parent_source["start_timecode"]
                if "end_timecode" in parent_source:
                    del parent_source["end_timecode"]
                parent_hit["_source"] = parent_source
                
                processed_asset = process_search_hit(parent_hit)
                processed_asset.clips = [process_search_hit(clip["hit"]) for clip in asset_clips]
                results.append(processed_asset)
    
    return results
```

### 3. Performance Optimization with Multi-Threading
Implement threading for better performance:

```python
def process_semantic_results_parallel(hits: List[Dict]) -> List[Dict]:
    """
    Process semantic search results using parallel processing for better performance.
    """
    # Separate parent assets and clips (this is fast, no need for parallelization)
    parent_assets = {}
    clips_by_asset = {}
    
    for hit in hits:
        source = hit["_source"]
        if source.get("embedding_scope") == "clip":
            # This is a clip
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                if asset_id not in clips_by_asset:
                    clips_by_asset[asset_id] = []
                clips_by_asset[asset_id].append({
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                })
        else:
            # This is a parent asset
            asset_id = source.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                parent_assets[asset_id] = {
                    "source": source,
                    "score": hit["_score"],
                    "hit": hit
                }
    
    # Process each parent asset and its clips in parallel
    def process_asset_with_clips(asset_id):
        result = None
        # Process parent asset if it exists
        if asset_id in parent_assets:
            result = process_search_hit(parent_assets[asset_id]["hit"])
            result_dict = result.model_dump(by_alias=True)
            result_dict["clips"] = []
            
            # Add clips if available
            if asset_id in clips_by_asset:
                # Sort clips by score and take top 30
                asset_clips = sorted(clips_by_asset[asset_id], key=lambda x: x["score"], reverse=True)[:30]
                # Process clips in parallel
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    clip_results = list(executor.map(
                        lambda clip: process_search_hit(clip["hit"]).model_dump(by_alias=True),
                        asset_clips
                    ))
                result_dict["clips"] = clip_results
            
            return result_dict
        # Handle orphaned clips
        elif asset_id in clips_by_asset:
            asset_clips = sorted(clips_by_asset[asset_id], key=lambda x: x["score"], reverse=True)[:30]
            if asset_clips:
                # Create parent from first clip
                first_clip = asset_clips[0]
                parent_hit = first_clip["hit"].copy()
                parent_source = first_clip["source"].copy()
                # Remove clip-specific fields
                if "embedding_scope" in parent_source:
                    del parent_source["embedding_scope"]
                if "start_timecode" in parent_source:
                    del parent_source["start_timecode"]
                if "end_timecode" in parent_source:
                    del parent_source["end_timecode"]
                parent_hit["_source"] = parent_source
                
                result = process_search_hit(parent_hit)
                result_dict = result.model_dump(by_alias=True)
                
                # Process clips in parallel
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    clip_results = list(executor.map(
                        lambda clip: process_search_hit(clip["hit"]).model_dump(by_alias=True),
                        asset_clips
                    ))
                result_dict["clips"] = clip_results
                
                return result_dict
        
        return None
    
    # Process all assets in parallel
    all_asset_ids = set(list(parent_assets.keys()) + list(clips_by_asset.keys()))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_asset_with_clips, all_asset_ids))
    
    # Filter out None results
    return [r for r in results if r is not None]
```

### 4. Update the Response Structure
Modify the `AssetSearchResult` model to include clips:

```python
class AssetSearchResult(BaseModelWithConfig):
    """Model for search result with presigned URL"""

    InventoryID: str
    DigitalSourceAsset: Dict[str, Any]
    DerivedRepresentations: List[Dict[str, Any]]
    FileHash: str
    Metadata: Dict[str, Any]
    score: float
    thumbnailUrl: Optional[str] = None
    proxyUrl: Optional[str] = None
    clips: Optional[List[Dict[str, Any]]] = None
```

### 5. Update the `perform_search` Function
Modify the `perform_search` function to use the new processing logic for semantic search:

```python
def perform_search(params: SearchParams) -> Dict:
    """Perform search operation in OpenSearch with proper error handling."""
    client = get_opensearch_client()
    index_name = os.environ["OPENSEARCH_INDEX"]

    try:
        search_body = build_search_query(params)
        logger.info("OpenSearch query body:", extra={"query": search_body})

        response = client.search(body=search_body, index=index_name)

        logger.info(f"Total hits from OpenSearch: {response['hits']['total']['value']}")
        logger.info("OpenSearch response:", extra={"response": response})

        hits = []
        
        if params.semantic:
            # Use the parallel processing function for semantic search
            import concurrent.futures
            processed_results = process_semantic_results_parallel(response["hits"]["hits"])
            
            search_metadata = SearchMetadata(
                totalResults=len(processed_results),  # Count of parent assets after grouping
                page=params.page,
                pageSize=params.pageSize,
                searchTerm=params.q,
                facets=response.get("aggregations"),
                suggestions=response.get("suggest"),
            )
            
            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": search_metadata.model_dump(by_alias=True),
                    "results": processed_results,
                },
            }
        else:
            # Standard processing for non-semantic search
            for hit in response["hits"]["hits"]:
                try:
                    result = process_search_hit(hit)
                    hits.append(result)
                except Exception as e:
                    logger.warning(f"Error processing hit: {str(e)}", extra={"hit": hit})
                    continue

            logger.info(f"Successfully processed hits: {len(hits)}")

            search_metadata = SearchMetadata(
                totalResults=response["hits"]["total"]["value"],
                page=params.page,
                pageSize=params.pageSize,
                searchTerm=params.q,
                facets=response.get("aggregations"),
                suggestions=response.get("suggest"),
            )

            return {
                "status": "200",
                "message": "ok",
                "data": {
                    "searchMetadata": search_metadata.model_dump(by_alias=True),
                    "results": [hit.model_dump(by_alias=True) for hit in hits],
                },
            }

    except (RequestError, NotFoundError) as e:
        # Error handling code remains the same
        # ...
```

## Implementation Considerations

1. **Performance**: 
   - Using ThreadPoolExecutor for parallel processing
   - Optimizing the grouping algorithm to minimize memory usage
   - Increasing the initial query size to ensure we get enough clips for grouping

2. **Backward Compatibility**:
   - Maintaining the existing response structure
   - Adding clips as a new field to avoid breaking existing clients

3. **Error Handling**:
   - Robust error handling for clip processing
   - Fallback mechanisms for orphaned clips

4. **Testing**:
   - Test with various query scenarios
   - Verify performance with large result sets
   - Ensure correct grouping of clips with parent assets

## Next Steps

1. Implement the changes as outlined above
2. Test the implementation with various search scenarios
3. Measure performance and optimize as needed
4. Deploy the changes to the production environment