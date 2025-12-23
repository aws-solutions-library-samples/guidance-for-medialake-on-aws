"""
OpenSearch embedding store implementation for semantic search.
"""

import os
import time
from typing import Any, Dict

import boto3
from base_embedding_store import BaseEmbeddingStore, SearchResult
from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestError,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)


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
            required_env_vars = [
                "OPENSEARCH_ENDPOINT",
                "AWS_REGION",
                "SCOPE",
                "OPENSEARCH_INDEX",
            ]
            return all(os.environ.get(var) for var in required_env_vars)
        except Exception as e:
            self.logger.warning(f"OpenSearch availability check failed: {str(e)}")
            return False

    def build_semantic_query(self, params) -> Dict[str, Any]:
        """Build OpenSearch semantic query using Twelve Labs embeddings with dual-structure support"""
        start_time = time.time()
        self.logger.info(
            f"[PERF] Starting OpenSearch semantic query build for: {params.q}"
        )

        # Use centralized embedding generation
        embedding = self.generate_text_embedding(params.q)
        embedding_dimension = len(embedding)

        # Determine which field name to use for asset_embeddings structure
        field_name = self._get_embedding_field_name(embedding_dimension)

        self.logger.info(
            f"Generated embedding with dimension {embedding_dimension}, using field: {field_name}"
        )

        # Build dual-query that works with both legacy and new asset_embeddings structure
        # This uses a "should" clause so it matches documents in either structure
        query = {
            "size": params.pageSize * 20,
            "query": {
                "bool": {
                    "filter": {"bool": {"must": []}},
                    "should": [
                        # Legacy structure: root-level embedding field
                        {
                            "knn": {
                                "embedding": {
                                    "vector": embedding,
                                    "k": params.pageSize * 20,
                                }
                            }
                        },
                        # New structure: asset_embeddings nested array with dimension-specific field
                        {
                            "nested": {
                                "path": "asset_embeddings",
                                "score_mode": "max",  # Use the best matching embedding
                                "query": {
                                    "knn": {
                                        f"asset_embeddings.{field_name}": {
                                            "vector": embedding,
                                            "k": params.pageSize * 20,
                                        }
                                    }
                                },
                            }
                        },
                    ],
                    "minimum_should_match": 1,  # Match at least one structure
                }
            },
            "_source": {
                "excludes": [
                    "embedding",
                    "audio_embedding",
                    "asset_embeddings.embedding_256_cosine",
                    "asset_embeddings.embedding_384_cosine",
                    "asset_embeddings.embedding_512_cosine",
                    "asset_embeddings.embedding_1024_cosine",
                    "asset_embeddings.embedding_1536_cosine",
                    "asset_embeddings.embedding_3072_cosine",
                ]
            },
        }

        # Add filters based on parameters
        self._add_filters_to_query(query, params)

        self.logger.info(
            f"Built dual-structure query supporting both legacy and asset_embeddings formats"
        )
        self.logger.info(
            f"[PERF] Total OpenSearch semantic query build time: {time.time() - start_time:.3f}s"
        )
        return query

    def _get_embedding_field_name(
        self, dimension: int, space_type: str = "cosine"
    ) -> str:
        """
        Get the field name for an embedding based on its dimension and space type.

        Args:
            dimension: The embedding dimension (256, 384, 512, 1024, 1536, 3072)
            space_type: The similarity space type (default: "cosine")

        Returns:
            Field name like "embedding_1024_cosine"
        """
        supported_dimensions = [256, 384, 512, 1024, 1536, 3072]
        if dimension not in supported_dimensions:
            self.logger.warning(
                f"Unsupported embedding dimension: {dimension}. Using closest supported dimension."
            )
            # Find closest supported dimension
            dimension = min(supported_dimensions, key=lambda x: abs(x - dimension))

        return f"embedding_{dimension}_{space_type}"

    def _add_filters_to_query(self, query: Dict, params):
        """Add filters to OpenSearch query based on parameters"""
        # If clip logic is disabled, exclude clip hits in the semantic query
        CLIP_LOGIC_ENABLED = True  # This should come from config
        if not CLIP_LOGIC_ENABLED:
            query["query"]["bool"]["must_not"] = [{"term": {"embedding_scope": "clip"}}]

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

        if params.ingested_date_lte is not None or params.ingested_date_gte is not None:
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
            self.logger.info(
                f"[PERF] OpenSearch query execution took: {opensearch_time:.3f}s"
            )

            hits = response.get("hits", {}).get("hits", [])
            total_results = response["hits"]["total"]["value"]

            self.logger.info(
                f"OpenSearch returned {len(hits)} hits from {total_results} total"
            )

            return SearchResult(
                hits=hits,
                total_results=total_results,
                aggregations=response.get("aggregations"),
                suggestions=response.get("suggest"),
            )

        except (RequestError, NotFoundError) as e:
            self.logger.warning(f"OpenSearch error: {str(e)}")
            return SearchResult(hits=[], total_results=0)
        except Exception as e:
            self.logger.error(f"Unexpected OpenSearch error: {str(e)}")
            raise Exception(f"OpenSearch search error: {str(e)}")
