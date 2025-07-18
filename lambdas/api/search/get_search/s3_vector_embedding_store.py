"""
S3 Vector embedding store implementation for semantic search.
"""
import os
import time
import boto3
from typing import Dict, List, Any
from base_embedding_store import BaseEmbeddingStore, SearchResult
from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestError,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)


class S3VectorEmbeddingStore(BaseEmbeddingStore):
    """S3 Vector implementation of embedding store"""
    
    def __init__(self, logger, metrics):
        super().__init__(logger, metrics)
        self._s3_vector_client = None
        self._opensearch_client = None
    
    def _get_s3_vector_client(self):
        """Create and return a cached S3 Vector client"""
        if self._s3_vector_client is None:
            self._s3_vector_client = boto3.client("s3vectors", region_name=os.environ["AWS_REGION"])
        return self._s3_vector_client
    
    def _get_opensearch_client(self) -> OpenSearch:
        """Create and return a cached OpenSearch client for metadata filtering"""
        if self._opensearch_client is None:
            host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ["SCOPE"]

            auth = RequestsAWSV4SignerAuth(
                boto3.Session().get_credentials(), region, service_scope
            )

            self._opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                region=region,
                timeout=30,
                max_retries=2,
                retry_on_timeout=True,
                maxsize=20,
            )

        return self._opensearch_client
    
    def is_available(self) -> bool:
        """Check if S3 Vector and OpenSearch are available and properly configured."""
        try:
            # S3 Vector requirements - using actual environment variable names
            s3_vector_vars = ["S3_VECTOR_BUCKET_NAME", "AWS_REGION"]
            # OpenSearch requirements for metadata filtering
            opensearch_vars = ["OPENSEARCH_ENDPOINT", "SCOPE", "OPENSEARCH_INDEX"]
            
            required_env_vars = s3_vector_vars + opensearch_vars
            missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
            
            if missing_vars:
                self.logger.warning(f"S3 Vector missing required environment variables: {missing_vars}")
                return False
            
            return True
        except Exception as e:
            self.logger.warning(f"S3 Vector availability check failed: {str(e)}")
            return False
    
    def build_semantic_query(self, params) -> Dict[str, Any]:
        """Build S3 Vector semantic query using Twelve Labs embeddings"""
        start_time = time.time()
        self.logger.info(f"[PERF] Starting S3 Vector semantic query build for: {params.q}")

        # Use centralized embedding generation
        embedding = self.generate_text_embedding(params.q)

        # Return S3 Vector query parameters - using actual environment variable names
        query = {
            "embedding": embedding,
            "topK": params.pageSize * 20,
            "params": params,
            "bucket_name": os.environ.get("S3_VECTOR_BUCKET_NAME"),
            "index_name": os.environ.get("S3_VECTOR_INDEX_NAME", "media-vectors")
        }
        
        self.logger.info(
            f"[PERF] Total S3 Vector semantic query build time: {time.time() - start_time:.3f}s"
        )
        return query
    
    def execute_search(self, query: Dict[str, Any], params) -> SearchResult:
        """Execute search using S3 Vector Store with metadata filtering"""
        try:
            # Step 1: Get initial results from S3 Vector Store
            s3_vector_client = self._get_s3_vector_client()
            bucket_name = query["bucket_name"]
            index_name = query["index_name"]
            
            if not bucket_name:
                raise Exception("S3 Vector bucket not configured")
            
            self.logger.info("Executing S3 Vector semantic query")
            s3_vector_start = time.time()
            
            # S3 Vector has a max topK of 30
            vector_topK = 30
            
            # First query: Get all results without filtering to identify unique inventory_ids
            initial_response = s3_vector_client.query_vectors(
                vectorBucketName=bucket_name,
                indexName=index_name,
                queryVector={"float32": query["embedding"]},
                topK=vector_topK,
                returnMetadata=True
            )
            
            initial_results = initial_response.get("vectors", [])
            if not initial_results:
                self.logger.info("S3 Vector returned no results")
                return SearchResult(hits=[], total_results=0)
            
            # Extract unique inventory_ids from initial results
            inventory_ids = set()
            for result in initial_results:
                metadata = result.get("metadata", {})
                inventory_id = metadata.get("inventory_id")
                if inventory_id:
                    inventory_ids.add(inventory_id)
            
            if not inventory_ids:
                self.logger.info("No inventory_ids found in S3 Vector results")
                return SearchResult(hits=[], total_results=0)
            
            self.logger.info(f"Found {len(inventory_ids)} unique inventory_ids")
            
            # Step 2: Query OpenSearch for metadata filtering to get valid inventory_ids
            opensearch_hits = self._query_opensearch_for_assets(list(inventory_ids), params)
            valid_inventory_ids = {hit["_source"].get("InventoryID") for hit in opensearch_hits}
            
            if not valid_inventory_ids:
                self.logger.info("No valid inventory_ids after OpenSearch filtering")
                return SearchResult(hits=[], total_results=0)
            
            # Step 3: Query S3 Vector Store for each valid inventory_id to get clips and parent assets
            all_results = []
            for inventory_id in valid_inventory_ids:
                # Query for this specific inventory_id
                filtered_response = s3_vector_client.query_vectors(
                    vectorBucketName=bucket_name,
                    indexName=index_name,
                    queryVector={"float32": query["embedding"]},
                    topK=vector_topK,
                    filter={"inventory_id": {"$eq": inventory_id}},
                    returnMetadata=True,
                    returnDistance=True
                )
                
                filtered_results = filtered_response.get("vectors", [])
                self.logger.info(f"S3 Vector returned {len(filtered_results)} results for inventory_id: {inventory_id}")
                for result in filtered_results:
                    metadata = result.get("metadata", {})
                    key = result.get("key", "")
                    embedding_scope = metadata.get("embedding_scope", "unknown")
                    self.logger.info(f"S3 Vector result - key: {key}, embedding_scope: {embedding_scope}")
                all_results.extend(filtered_results)
            
            s3_vector_time = time.time() - s3_vector_start
            self.logger.info(f"[PERF] S3 Vector query execution took: {s3_vector_time:.3f}s")
            
            # Step 4: Process results with clip logic
            final_hits = self._process_s3_vector_results_with_clips(all_results, opensearch_hits)
            
            self.logger.info(f"S3 Vector search returned {len(final_hits)} results")
            
            # Debug the final structure being returned
            for i, hit in enumerate(final_hits):
                clips_count = len(hit.get("clips", []))
                self.logger.info(f"Final hit {i}: score={hit.get('_score')}, clips_count={clips_count}")
                if clips_count > 0:
                    self.logger.info(f"First clip sample: {hit['clips'][0]}")
            
            search_result = SearchResult(
                hits=final_hits,
                total_results=len(final_hits),
                aggregations=None,
                suggestions=None
            )
            
            self.logger.info(f"Returning SearchResult with {len(search_result.hits)} hits")
            return search_result
            
        except Exception as e:
            self.logger.exception("Error performing S3 Vector search")
            raise Exception(f"S3 Vector search error: {str(e)}")
    
    def _convert_s3_vector_results(self, results: List[Dict]) -> List[Dict]:
        """Convert S3 Vector results to OpenSearch-like format for compatibility"""
        hits = []
        
        for result in results:
            # Extract metadata and create hit structure
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)
            key = result.get("key", "")
            
            # Extract inventory_id from the key
            inventory_id = self._extract_inventory_id_from_key(key)
            
            # Create a hit structure similar to OpenSearch
            hit = {
                "_score": score,
                "_source": {
                    "InventoryID": inventory_id,
                }
            }
            
            # Add metadata fields to source
            for field_name, value in metadata.items():
                hit["_source"][field_name] = value
            
            # If we have structured metadata, try to reconstruct the expected format
            if "DigitalSourceAsset" in metadata:
                hit["_source"]["DigitalSourceAsset"] = metadata["DigitalSourceAsset"]
            
            if "DerivedRepresentations" in metadata:
                hit["_source"]["DerivedRepresentations"] = metadata["DerivedRepresentations"]
            
            if "FileHash" in metadata:
                hit["_source"]["FileHash"] = metadata["FileHash"]
            
            if "Metadata" in metadata:
                hit["_source"]["Metadata"] = metadata["Metadata"]
            
            hits.append(hit)
        
        return hits
    
    def _apply_filters(self, results: List[Dict], params) -> List[Dict]:
        """Apply client-side filtering since S3 Vector doesn't support server-side filtering"""
        filtered_results = results
        
        # Apply type filter
        if params.type:
            allowed_types = params.type.split(",")
            filtered_results = [
                r for r in filtered_results 
                if r.get("_source", {}).get("DigitalSourceAsset", {}).get("Type") in allowed_types
            ]
        
        # Apply extension filter
        if params.extension:
            allowed_extensions = params.extension.split(",")
            filtered_results = [
                r for r in filtered_results 
                if r.get("_source", {}).get("DigitalSourceAsset", {}).get("MainRepresentation", {}).get("Format") in allowed_extensions
            ]
        
        # Apply file size filters
        if params.asset_size_gte is not None or params.asset_size_lte is not None:
            def size_filter(result):
                file_size = result.get("_source", {}).get("DigitalSourceAsset", {}).get("MainRepresentation", {}).get("StorageInfo", {}).get("PrimaryLocation", {}).get("FileInfo", {}).get("Size", 0)
                if params.asset_size_gte is not None and file_size < params.asset_size_gte:
                    return False
                if params.asset_size_lte is not None and file_size > params.asset_size_lte:
                    return False
                return True
            
            filtered_results = [r for r in filtered_results if size_filter(r)]
        
        return filtered_results
    
    def _query_opensearch_for_assets(self, asset_ids: List[str], params) -> List[Dict]:
        """Query OpenSearch for specific assets with metadata filtering"""
        try:
            opensearch_client = self._get_opensearch_client()
            index_name = os.environ["OPENSEARCH_INDEX"]
            
            # Build OpenSearch query for specific asset IDs with filters
            # Use should clauses with match queries since InventoryID is a text field
            should_clauses = [{"match": {"InventoryID": asset_id}} for asset_id in asset_ids]
            
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                            {"exists": {"field": "InventoryID"}},
                            {"bool": {"must_not": {"term": {"InventoryID": ""}}}},
                        ],
                        "must_not": [{"term": {"embedding_scope": "clip"}}],
                        "filter": []
                    }
                },
                "size": len(asset_ids),  # Get all matching assets
                "_source": {
                    "includes": [
                        "InventoryID",
                        "DigitalSourceAsset.Type",
                        "DigitalSourceAsset.MainRepresentation.Format",
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey",
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo",
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
                        "DigitalSourceAsset.CreateDate",
                        "DerivedRepresentations.Purpose",
                        "DerivedRepresentations.StorageInfo.PrimaryLocation",
                        "FileHash",
                        "Metadata.Consolidated.type",
                    ]
                }
            }
            
            # Add filters based on parameters
            self._add_opensearch_filters(query, params)
            
            opensearch_start = time.time()
            response = opensearch_client.search(body=query, index=index_name)
            opensearch_time = time.time() - opensearch_start
            
            self.logger.info(f"[PERF] OpenSearch metadata filtering took: {opensearch_time:.3f}s")
            
            hits = response.get("hits", {}).get("hits", [])
            self.logger.info(f"OpenSearch returned {len(hits)} filtered assets from {len(asset_ids)} candidates")
            
            return hits
            
        except Exception as e:
            self.logger.exception("Error querying OpenSearch for asset metadata")
            # Return empty results rather than failing completely
            return []
    
    def _add_opensearch_filters(self, query: Dict, params):
        """Add metadata filters to OpenSearch query"""
        filters_to_add = []
        
        if params.type:
            var_type = params.type.split(",")
            filters_to_add.append({"terms": {"DigitalSourceAsset.Type": var_type}})
        
        if params.extension:
            var_ext = params.extension.split(",")
            filters_to_add.append(
                {"terms": {"DigitalSourceAsset.MainRepresentation.Format": var_ext}}
            )
        
        if params.asset_size_lte is not None or params.asset_size_gte is not None:
            filters_to_add.append(
                {
                    "range": {
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": {
                            "gte": params.asset_size_gte,
                            "lte": params.asset_size_lte,
                        }
                    }
                }
            )
        
        if params.ingested_date_lte is not None or params.ingested_date_gte is not None:
            filters_to_add.append(
                {
                    "range": {
                        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate": {
                            "gte": params.ingested_date_gte,
                            "lte": params.ingested_date_lte,
                        }
                    }
                }
            )
        
        # Add all filters to the query
        query["query"]["bool"]["filter"].extend(filters_to_add)
    
    def _merge_vector_and_metadata_results(self, opensearch_hits: List[Dict], asset_scores: Dict[str, float]) -> List[Dict]:
        """Merge OpenSearch metadata with S3 Vector similarity scores"""
        merged_results = []
        
        for hit in opensearch_hits:
            source = hit["_source"]
            inventory_id = source.get("InventoryID", "")
            
            # Get the vector similarity score
            vector_score = asset_scores.get(inventory_id, 0.0)
            
            # Create result with vector score
            merged_hit = {
                "_score": vector_score,
                "_source": source
            }
            
            merged_results.append(merged_hit)
        
        # Sort by vector similarity score (descending)
        merged_results.sort(key=lambda x: x["_score"], reverse=True)
        
        return merged_results
    
    def _extract_inventory_id_from_key(self, key: str) -> str:
        """
        Extract inventory_id from the new key format.
        
        Key formats:
        - Non-clip: {inventory_id}_{embedding_option}
        - Clip: {inventory_id}_{embedding_option}_clip_{start_sec}_{end_sec}
        
        Returns the inventory_id part.
        """
        if not key:
            return ""
        
        # Split the key by underscores
        parts = key.split("_")
        
        if len(parts) < 2:
            # Fallback: if key doesn't match expected format, return as-is
            self.logger.warning(f"Unexpected key format: {key}")
            return key
        
        # For both formats, the inventory_id is everything before the last embedding_option part
        # We need to handle the case where inventory_id itself might contain underscores
        
        # Check if this is a clip key (contains "_clip_" pattern)
        if "_clip_" in key:
            # Format: {inventory_id}_{embedding_option}_clip_{start_sec}_{end_sec}
            # Find the last occurrence of "_clip_" and work backwards
            clip_index = key.rfind("_clip_")
            if clip_index > 0:
                # Everything before "_clip_" should be {inventory_id}_{embedding_option}
                before_clip = key[:clip_index]
                # Now split this and take everything except the last part (embedding_option)
                before_clip_parts = before_clip.split("_")
                if len(before_clip_parts) >= 2:
                    # Join all parts except the last one (which is embedding_option)
                    return "_".join(before_clip_parts[:-1])
        else:
            # Format: {inventory_id}_{embedding_option}
            # Take everything except the last part
            if len(parts) >= 2:
                return "_".join(parts[:-1])
        
        # Fallback
        self.logger.warning(f"Could not extract inventory_id from key: {key}")
        return key
    
    def _process_s3_vector_results_with_clips(self, s3_vector_results: List[Dict], opensearch_hits: List[Dict]) -> List[Dict]:
        """
        Process S3 Vector results with clip logic similar to OpenSearch implementation.
        Groups clips with their parent assets and returns results with clips arrays.
        """
        # Create mapping of inventory_id to opensearch hit for metadata
        asset_hit_map = {}
        for hit in opensearch_hits:
            inventory_id = hit["_source"].get("InventoryID", "")
            if inventory_id:
                asset_hit_map[inventory_id] = hit
        
        # Separate clip results from parent asset results and group by inventory_id
        clips_by_asset = {}
        parent_asset_scores = {}
        
        for idx, result in enumerate(s3_vector_results):
            metadata = result.get("metadata", {})
            inventory_id = metadata.get("inventory_id")
            if not inventory_id:
                continue
                
            # S3 Vector returns distance, convert to similarity score
            distance = result.get("distance", 0.0)
            # Convert distance to similarity score (lower distance = higher similarity)
            score = max(0.0, 1.0 - distance) if distance <= 1.0 else 1.0 / (1.0 + distance)
            
            # Check if this is a clip result using metadata
            embedding_scope = metadata.get("embedding_scope", "")
            self.logger.info(f"Processing result for {inventory_id}: embedding_scope={embedding_scope}, score={score}")
            
            if embedding_scope == "clip":
                # This is a clip result
                self.logger.info(f"Found clip for {inventory_id}: {metadata}")
                if inventory_id not in clips_by_asset:
                    clips_by_asset[inventory_id] = []
                clips_by_asset[inventory_id].append({
                    "score": score,
                    "metadata": metadata
                })
            else:
                # This is a parent asset result (video scope)
                self.logger.info(f"Found parent asset for {inventory_id}: embedding_scope={embedding_scope}")
                if inventory_id not in parent_asset_scores or score > parent_asset_scores[inventory_id]:
                    parent_asset_scores[inventory_id] = score
        
        # Process results
        final_results = []
        processed_assets = set()
        
        self.logger.info(f"Processing clips_by_asset: {len(clips_by_asset)} assets with clips")
        self.logger.info(f"Processing parent_asset_scores: {len(parent_asset_scores)} parent assets")
        
        # Process assets that have clips
        for inventory_id, clips in clips_by_asset.items():
            self.logger.info(f"Processing clips for {inventory_id}: {len(clips)} clips found")
            if inventory_id in asset_hit_map and inventory_id not in processed_assets:
                hit = asset_hit_map[inventory_id]
                
                # Get the highest clip score for this asset
                highest_clip_score = max(clip["score"] for clip in clips)
                
                # Use the higher of parent asset score or highest clip score
                final_score = max(parent_asset_scores.get(inventory_id, 0), highest_clip_score)
                
                # Create result with clips
                result = {
                    "_score": final_score,
                    "_source": hit["_source"]
                }
                
                # Add clips array - sort clips by score descending
                sorted_clips = sorted(clips, key=lambda x: x["score"], reverse=True)
                result["clips"] = []
                
                for clip in sorted_clips:
                    metadata = clip["metadata"]
                    clip_data = {
                        "score": clip["score"],
                        "embedding_scope": metadata.get("embedding_scope", "clip"),
                        "start_offset_sec": metadata.get("start_offset_sec"),
                        "end_offset_sec": metadata.get("end_offset_sec"),
                        "start_timecode": metadata.get("start_timecode"),
                        "end_timecode": metadata.get("end_timecode"),
                        "embedding_option": metadata.get("embedding_option"),
                        "timestamp": metadata.get("timestamp"),
                        "content_type": metadata.get("content_type"),
                    }
                    # Only include S3 Vector metadata, not the full OpenSearch record
                    result["clips"].append(clip_data)
                
                self.logger.info(f"Adding result with {len(result['clips'])} clips: {result}")
                final_results.append(result)
                processed_assets.add(inventory_id)
        
        # Process assets that don't have clips but were found in parent results
        for inventory_id, score in parent_asset_scores.items():
            if inventory_id in asset_hit_map and inventory_id not in processed_assets:
                hit = asset_hit_map[inventory_id]
                result = {
                    "_score": score,
                    "_source": hit["_source"],
                    "clips": []  # Empty clips array
                }
                final_results.append(result)
                processed_assets.add(inventory_id)
        
        # Sort results by score descending
        final_results.sort(key=lambda x: x["_score"], reverse=True)
        
        return final_results