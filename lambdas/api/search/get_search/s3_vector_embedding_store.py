"""
S3 Vector embedding store implementation for semantic search.
"""
import os
import time
import boto3
from typing import Dict, List, Any
from base_embedding_store import BaseEmbeddingStore, SearchResult
from api_utils import get_api_key
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
            # S3 Vector requirements
            s3_vector_vars = ["S3_VECTOR_BUCKET_NAME", "AWS_REGION"]
            # OpenSearch requirements for metadata filtering
            opensearch_vars = ["OPENSEARCH_ENDPOINT", "SCOPE", "OPENSEARCH_INDEX"]
            
            required_env_vars = s3_vector_vars + opensearch_vars
            return all(os.environ.get(var) for var in required_env_vars)
        except Exception as e:
            self.logger.warning(f"S3 Vector availability check failed: {str(e)}")
            return False
    
    def build_semantic_query(self, params) -> Dict[str, Any]:
        """Build S3 Vector semantic query using Twelve Labs embeddings"""
        from twelvelabs import TwelveLabs

        start_time = time.time()
        self.logger.info(f"[PERF] Starting S3 Vector semantic query build for: {params.q}")

        # Get the API key from Secrets Manager
        api_key_start = time.time()
        api_key = get_api_key()
        self.logger.info(f"[PERF] API key retrieval took: {time.time() - api_key_start:.3f}s")

        if not api_key:
            raise Exception(
                "Search provider API key not configured or provider not enabled"
            )

        # Initialize the Twelve Labs client
        client_init_start = time.time()
        twelve_labs_client = TwelveLabs(api_key=api_key)
        self.logger.info(
            f"[PERF] TwelveLabs client initialization took: {time.time() - client_init_start:.3f}s"
        )

        try:
            # Create embedding for the search query
            embedding_start = time.time()
            self.logger.info(f"[PERF] Starting embedding creation for query: {params.q}")
            res = twelve_labs_client.embed.create(
                model_name="Marengo-retrieval-2.7",
                text=params.q,
            )
            self.logger.info(
                f"[PERF] Embedding creation took: {time.time() - embedding_start:.3f}s"
            )

            if res.text_embedding is not None and res.text_embedding.segments is not None:
                embedding = list(res.text_embedding.segments[0].embeddings_float)
                if not all(isinstance(x, (int, float)) for x in embedding):
                    raise Exception("Invalid embedding format")

                self.logger.info(
                    f"Generated embedding for query: {params.q} (length: {len(embedding)})"
                )

                # Return S3 Vector query parameters
                query = {
                    "embedding": embedding,
                    "topK": params.pageSize * 20,
                    "params": params,
                    "bucket_name": os.environ.get("S3_VECTOR_BUCKET_NAME"),
                    "index_name": os.environ.get("S3_VECTOR_INDEX_NAME", "media-vec")
                }
                
                self.logger.info(
                    f"[PERF] Total S3 Vector semantic query build time: {time.time() - start_time:.3f}s"
                )
                return query
            else:
                raise Exception("Failed to generate embedding for search term")
        except Exception as e:
            self.logger.exception("Error generating embedding for search term")
            raise Exception(f"Error generating embedding: {str(e)}")
    
    def execute_search(self, query: Dict[str, Any], params) -> SearchResult:
        """Execute hybrid search: S3 Vector for similarity + OpenSearch for filtering"""
        try:
            # Step 1: Perform S3 Vector similarity search
            s3_vector_client = self._get_s3_vector_client()
            bucket_name = query["bucket_name"]
            index_name = query["index_name"]
            
            if not bucket_name:
                raise Exception("S3 Vector bucket not configured")
            
            self.logger.info("Executing S3 Vector semantic query")
            s3_vector_start = time.time()
            
            # Get more results from S3 Vector to account for filtering
            vector_topK = max(query["topK"] * 3, 1000)  # Get 3x more results for filtering
            
            response = s3_vector_client.query_vectors(
                vectorBucketName=bucket_name,
                indexName=index_name,
                queryVector={"float32": query["embedding"]},
                topK=vector_topK
            )
            
            s3_vector_time = time.time() - s3_vector_start
            self.logger.info(f"[PERF] S3 Vector query execution took: {s3_vector_time:.3f}s")
            
            # Step 2: Extract asset IDs and scores from S3 Vector results
            vector_results = response.get("results", [])
            if not vector_results:
                self.logger.info("S3 Vector returned no results")
                return SearchResult(hits=[], total_results=0)
            
            # Create mapping of asset ID to vector score
            asset_scores = {}
            asset_ids = []
            for result in vector_results:
                asset_id = result.get("key", "")
                if asset_id:
                    asset_scores[asset_id] = result.get("score", 0.0)
                    asset_ids.append(asset_id)
            
            self.logger.info(f"S3 Vector returned {len(asset_ids)} asset IDs")
            
            # Step 3: Query OpenSearch for metadata filtering
            if asset_ids:
                opensearch_hits = self._query_opensearch_for_assets(asset_ids, params)
                
                # Step 4: Merge results maintaining vector similarity ranking
                final_hits = self._merge_vector_and_metadata_results(opensearch_hits, asset_scores)
                
                self.logger.info(f"Hybrid search returned {len(final_hits)} filtered results")
                
                return SearchResult(
                    hits=final_hits,
                    total_results=len(final_hits),
                    aggregations=None,  # Could be added by querying OpenSearch aggregations
                    suggestions=None
                )
            else:
                return SearchResult(hits=[], total_results=0)
            
        except Exception as e:
            self.logger.exception("Error performing hybrid S3 Vector + OpenSearch search")
            raise Exception(f"Hybrid search error: {str(e)}")
    
    def _convert_s3_vector_results(self, results: List[Dict]) -> List[Dict]:
        """Convert S3 Vector results to OpenSearch-like format for compatibility"""
        hits = []
        
        for result in results:
            # Extract metadata and create hit structure
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)
            key = result.get("key", "")
            
            # Create a hit structure similar to OpenSearch
            hit = {
                "_score": score,
                "_source": {
                    "InventoryID": key,
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
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"terms": {"InventoryID": asset_ids}},
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