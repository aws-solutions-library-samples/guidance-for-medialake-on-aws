"""
OpenSearch embedding store implementation for semantic search.
"""
import os
import time
import boto3
from typing import Dict, List, Any
from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestError,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)
from base_embedding_store import BaseEmbeddingStore, SearchResult
from api_utils import get_api_key


class OpenSearchEmbeddingStore(BaseEmbeddingStore):
    """OpenSearch implementation of embedding store"""
    
    def __init__(self, logger, metrics):
        super().__init__(logger, metrics)
        self._client = None
    
    def _get_client(self) -> OpenSearch:
        """Create and return a cached OpenSearch client with optimized settings."""
        if self._client is None:
            host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ["SCOPE"]

            auth = RequestsAWSV4SignerAuth(
                boto3.Session().get_credentials(), region, service_scope
            )

            self._client = OpenSearch(
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

        return self._client
    
    def is_available(self) -> bool:
        """Check if OpenSearch is available and properly configured."""
        try:
            required_env_vars = ["OPENSEARCH_ENDPOINT", "AWS_REGION", "SCOPE", "OPENSEARCH_INDEX"]
            return all(os.environ.get(var) for var in required_env_vars)
        except Exception as e:
            self.logger.warning(f"OpenSearch availability check failed: {str(e)}")
            return False
    
    def build_semantic_query(self, params) -> Dict[str, Any]:
        """Build OpenSearch semantic query using Twelve Labs embeddings"""
        from twelvelabs import TwelveLabs

        start_time = time.time()
        self.logger.info(f"[PERF] Starting OpenSearch semantic query build for: {params.q}")

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

                query = {
                    "size": params.pageSize * 20,
                    "query": {
                        "bool": {
                            "filter": {"bool": {"must": []}},
                            "must": [
                                {
                                    "knn": {
                                        "embedding": {
                                            "vector": embedding,
                                            "k": params.pageSize * 20,
                                        }
                                    }
                                }
                            ],
                        }
                    },
                    "_source": {"excludes": ["embedding"]},
                }
                
                # Add filters based on parameters
                self._add_filters_to_query(query, params)
                
                self.logger.info(
                    f"[PERF] Total OpenSearch semantic query build time: {time.time() - start_time:.3f}s"
                )
                return query
            else:
                raise Exception("Failed to generate embedding for search term")
        except Exception as e:
            self.logger.exception("Error generating embedding for search term")
            raise Exception(f"Error generating embedding: {str(e)}")
    
    def _add_filters_to_query(self, query: Dict, params):
        """Add filters to OpenSearch query based on parameters"""
        # If clip logic is disabled, exclude clip hits in the semantic query
        CLIP_LOGIC_ENABLED = True  # This should come from config
        if not CLIP_LOGIC_ENABLED:
            query["query"]["bool"]["must_not"] = [
                {"term": {"embedding_scope": "clip"}}
            ]

        # Process Facet filters
        if params.type is not None:
            var_type = params.type.split(",")
            query["query"]["bool"]["filter"]["bool"]["must"].append(
                {"terms": {"DigitalSourceAsset.Type": var_type}}
            )

        if params.extension is not None:
            var_ext = params.extension.split(",")
            query["query"]["bool"]["filter"]["bool"]["must"].append(
                {"terms": {"DigitalSourceAsset.MainRepresentation.Format": var_ext}}
            )

        if params.asset_size_lte is not None or params.asset_size_gte is not None:
            try:
                query["query"]["bool"]["filter"]["bool"]["must"].append(
                    {
                        "range": {
                            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": {
                                "gte": params.asset_size_gte,
                                "lte": params.asset_size_lte,
                            }
                        }
                    }
                )
            except ValueError:
                self.logger.warning(
                    f"Invalid values for asset size: {params.asset_size_gte, params.asset_size_lte}"
                )

        if (
            params.ingested_date_lte is not None
            or params.ingested_date_gte is not None
        ):
            try:
                query["query"]["bool"]["filter"]["bool"]["must"].append(
                    {
                        "range": {
                            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate": {
                                "gte": params.ingested_date_gte,
                                "lte": params.ingested_date_lte,
                            }
                        }
                    }
                )
            except ValueError:
                self.logger.warning(
                    f"Invalid values for ingested date: {params.ingested_date_gte, params.ingested_date_lte}"
                )
    
    def execute_search(self, query: Dict[str, Any], params) -> SearchResult:
        """Execute the search query against OpenSearch"""
        try:
            client = self._get_client()
            index_name = os.environ["OPENSEARCH_INDEX"]
            
            self.logger.info("Executing OpenSearch semantic query")
            opensearch_start = time.time()
            response = client.search(body=query, index=index_name)
            opensearch_time = time.time() - opensearch_start
            self.logger.info(f"[PERF] OpenSearch query execution took: {opensearch_time:.3f}s")

            hits = response.get("hits", {}).get("hits", [])
            total_results = response["hits"]["total"]["value"]
            
            self.logger.info(
                f"OpenSearch returned {len(hits)} hits from {total_results} total"
            )

            return SearchResult(
                hits=hits,
                total_results=total_results,
                aggregations=response.get("aggregations"),
                suggestions=response.get("suggest")
            )

        except (RequestError, NotFoundError) as e:
            self.logger.warning(f"OpenSearch error: {str(e)}")
            return SearchResult(hits=[], total_results=0)
        except Exception as e:
            self.logger.error(f"Unexpected OpenSearch error: {str(e)}")
            raise Exception(f"OpenSearch search error: {str(e)}")