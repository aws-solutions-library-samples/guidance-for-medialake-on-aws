"""
Bedrock TwelveLabs search provider implementation for provider+store architecture.
"""

import os
import time
from typing import Dict, List

import boto3
from opensearchpy import (
    OpenSearch,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)
from unified_search_models import (
    MediaType,
    ProviderLocation,
    SearchArchitectureType,
    SearchHit,
    SearchQuery,
    SearchResult,
)
from unified_search_provider import ProviderPlusStoreSearchProvider


class BedrockTwelveLabsSearchProvider(ProviderPlusStoreSearchProvider):
    """Bedrock TwelveLabs provider+store search provider"""

    def __init__(self, config, logger, metrics):
        super().__init__(config, logger, metrics)
        self._opensearch_client = None

    def _get_provider_location(self) -> ProviderLocation:
        return ProviderLocation.INTERNAL

    def _get_opensearch_client(self) -> OpenSearch:
        """Create and return a cached OpenSearch client"""
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
        """Check if Bedrock TwelveLabs provider is available and properly configured"""
        try:
            # Check required environment variables
            required_env_vars = [
                "OPENSEARCH_ENDPOINT",
                "AWS_REGION",
                "SCOPE",
                "OPENSEARCH_INDEX",
                "S3_VECTOR_BUCKET_NAME",  # Required for Bedrock embedding output
            ]
            missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

            if missing_vars:
                self.logger.warning(
                    f"Missing required environment variables for Bedrock TwelveLabs: {missing_vars}"
                )
                return False

            # Check if Bedrock service is available
            try:
                bedrock_runtime = boto3.client(
                    "bedrock-runtime", region_name=os.environ["AWS_REGION"]
                )
                # This is a simple check to see if we can create the client
                # In a production environment, you might want to make a test call
                self.logger.info("Bedrock runtime client created successfully")
            except Exception as e:
                self.logger.warning(
                    f"Failed to create Bedrock runtime client: {str(e)}"
                )
                return False

            return True
        except Exception as e:
            self.logger.warning(
                f"Bedrock TwelveLabs availability check failed: {str(e)}"
            )
            return False

    def generate_embeddings(self, query_text: str) -> List[float]:
        """
        Generate embeddings using Bedrock TwelveLabs model.
        This method delegates to the base embedding store's generate_text_embedding method.
        """
        # Import here to avoid circular imports
        from base_embedding_store import BaseEmbeddingStore

        # Create a temporary embedding store instance to use the centralized embedding generation
        temp_store = BaseEmbeddingStore.__new__(BaseEmbeddingStore)
        temp_store.logger = self.logger
        temp_store.metrics = self.metrics

        return temp_store.generate_text_embedding(query_text)

    def execute_store_search(
        self, embeddings: List[float], query: SearchQuery
    ) -> SearchResult:
        """Execute search against OpenSearch using the generated embeddings"""
        try:
            client = self._get_opensearch_client()
            index_name = os.environ["OPENSEARCH_INDEX"]

            # Build OpenSearch query with embeddings
            opensearch_query = {
                "size": query.page_size * 20,  # Get more results for better ranking
                "query": {
                    "bool": {
                        "filter": {"bool": {"must": []}},
                        "must": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": embeddings,
                                        "k": query.page_size * 20,
                                    }
                                }
                            }
                        ],
                    }
                },
                "_source": {"excludes": ["embedding"]},
            }

            # Add filters based on query parameters
            self._add_filters_to_opensearch_query(opensearch_query, query)

            self.logger.info(
                "Executing Bedrock TwelveLabs semantic query via OpenSearch"
            )
            opensearch_start = time.time()
            response = client.search(body=opensearch_query, index=index_name)
            opensearch_time = time.time() - opensearch_start

            self.logger.info(
                f"[PERF] OpenSearch query execution took: {opensearch_time:.3f}s"
            )

            hits = response.get("hits", {}).get("hits", [])
            total_results = response["hits"]["total"]["value"]

            self.logger.info(
                f"Bedrock TwelveLabs search returned {len(hits)} hits from {total_results} total"
            )

            # Convert hits to SearchHit format
            search_hits = []
            max_score = 0.0

            for hit in hits:
                score = hit.get("_score", 0.0)
                if score > max_score:
                    max_score = score

                # Determine media type from source data
                source = hit.get("_source", {})
                asset_type = source.get("DigitalSourceAsset", {}).get("Type", "video")
                try:
                    media_type = MediaType(asset_type.lower())
                except ValueError:
                    media_type = MediaType.VIDEO  # default fallback

                search_hit = SearchHit(
                    asset_id=source.get("InventoryID", ""),
                    score=score,
                    source=source,
                    media_type=media_type,
                    provider_metadata={
                        "provider": "bedrock_twelvelabs",
                        "embedding_model": "twelvelabs.marengo-embed-2-7-v1:0",
                    },
                )
                search_hits.append(search_hit)

            return SearchResult(
                hits=search_hits,
                total_results=total_results,
                max_score=max_score,
                took_ms=int(opensearch_time * 1000),
                provider="bedrock_twelvelabs",
                architecture_type=SearchArchitectureType.PROVIDER_PLUS_STORE,
                provider_location=ProviderLocation.INTERNAL,
                facets=response.get("aggregations"),
            )

        except Exception as e:
            self.logger.error(f"Bedrock TwelveLabs search failed: {str(e)}")
            # Return empty result on failure
            return SearchResult(
                hits=[],
                total_results=0,
                max_score=0.0,
                took_ms=0,
                provider="bedrock_twelvelabs",
                architecture_type=SearchArchitectureType.PROVIDER_PLUS_STORE,
                provider_location=ProviderLocation.INTERNAL,
            )

    def _add_filters_to_opensearch_query(self, query: Dict, search_query: SearchQuery):
        """Add filters to OpenSearch query based on search parameters"""
        if not search_query.filters:
            return

        filters_to_add = []

        for filter_item in search_query.filters:
            field_key = filter_item.get("key")
            operator = filter_item.get("operator")
            value = filter_item.get("value")

            if operator == "in" and isinstance(value, list):
                if field_key == "mediaType":
                    filters_to_add.append({"terms": {"DigitalSourceAsset.Type": value}})
                elif field_key == "DigitalSourceAsset.MainRepresentation.Format":
                    filters_to_add.append({"terms": {field_key: value}})
            elif operator == "==" or operator == "eq":
                filters_to_add.append({"term": {field_key: value}})
            elif operator == "range" and isinstance(value, dict):
                range_filter = {"range": {field_key: {}}}
                if "gte" in value:
                    range_filter["range"][field_key]["gte"] = value["gte"]
                if "lte" in value:
                    range_filter["range"][field_key]["lte"] = value["lte"]
                if "gt" in value:
                    range_filter["range"][field_key]["gt"] = value["gt"]
                if "lt" in value:
                    range_filter["range"][field_key]["lt"] = value["lt"]
                filters_to_add.append(range_filter)

        # Add all filters to the query
        query["query"]["bool"]["filter"]["bool"]["must"].extend(filters_to_add)

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute the complete search process"""
        if not self.is_available():
            raise Exception(
                "Bedrock TwelveLabs provider is not available or configured"
            )

        # Step 1: Generate embeddings using Bedrock TwelveLabs
        embeddings = self.generate_embeddings(query.query_text)

        # Step 2: Execute search against the store (OpenSearch)
        return self.execute_store_search(embeddings, query)
