"""
TwelveLabs API search provider implementation for provider+store architecture.
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


class TwelveLabsAPISearchProvider(ProviderPlusStoreSearchProvider):
    """TwelveLabs API provider+store search provider"""

    def __init__(self, config, logger, metrics):
        super().__init__(config, logger, metrics)
        self._opensearch_client = None

    def _get_provider_location(self) -> ProviderLocation:
        return ProviderLocation.EXTERNAL

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
        """Check if TwelveLabs API provider is available and properly configured"""
        try:
            # Check required environment variables
            required_env_vars = [
                "OPENSEARCH_ENDPOINT",
                "AWS_REGION",
                "SCOPE",
                "OPENSEARCH_INDEX",
            ]
            missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

            if missing_vars:
                self.logger.warning(
                    f"Missing required environment variables for TwelveLabs API: {missing_vars}"
                )
                return False

            # Check if we can get the API key from the configuration
            if not self.config.auth or not self.config.auth.get("secret_arn"):
                self.logger.warning("TwelveLabs API key not configured")
                return False

            return True
        except Exception as e:
            self.logger.warning(f"TwelveLabs API availability check failed: {str(e)}")
            return False

    def generate_embeddings(self, query_text: str) -> List[float]:
        """
        Generate embeddings using TwelveLabs API.
        """
        return self._generate_embedding_via_twelvelabs_api(query_text)

    def _generate_embedding_via_twelvelabs_api(self, query_text: str) -> List[float]:
        """
        Generate text embedding using TwelveLabs API.
        """
        from twelvelabs import TwelveLabs

        try:
            # Get API key from secrets manager
            api_key = self._get_api_key()
            if not api_key:
                raise Exception("TwelveLabs API key not available")

            # Initialize TwelveLabs client
            client = TwelveLabs(api_key=api_key)

            self.logger.info(
                f"Generating TwelveLabs API embedding for query: {query_text}"
            )

            # Generate embedding using TwelveLabs API
            embedding_response = client.embed.create(
                model_name="Marengo-retrieval-2.7",
                text=query_text,
                text_truncate="start",
            )

            if not embedding_response or not hasattr(
                embedding_response, "text_embedding"
            ):
                raise Exception("Invalid response from TwelveLabs API")

            # Extract the embedding from the response
            # The text_embedding can be a BaseSegment object with float_ attribute
            # or it can have segments with BaseSegment objects
            text_embedding = embedding_response.text_embedding

            # Handle different response formats
            if hasattr(text_embedding, "segments") and text_embedding.segments:
                # Response has segments array with BaseSegment objects
                embedding = text_embedding.segments[0].float_
            elif hasattr(text_embedding, "float_"):
                # Response is a BaseSegment object directly
                embedding = text_embedding.float_
            elif isinstance(text_embedding, list):
                # Response is already a list
                embedding = text_embedding
            else:
                # Try to convert to list
                embedding = list(text_embedding)

            self.logger.info(
                f"Successfully generated TwelveLabs API embedding with {len(embedding)} dimensions"
            )
            return embedding

        except Exception as e:
            self.logger.error(f"TwelveLabs API embedding generation failed: {str(e)}")
            raise

    def _get_api_key(self) -> str:
        """Get TwelveLabs API key from Secrets Manager"""
        try:
            if not self.config.auth or not self.config.auth.get("secret_arn"):
                return None

            secretsmanager = boto3.client("secretsmanager")
            response = secretsmanager.get_secret_value(
                SecretId=self.config.auth["secret_arn"]
            )

            if response and "SecretString" in response:
                import json

                secret_data = json.loads(response["SecretString"])
                return secret_data.get("x-api-key") or secret_data.get("api_key")

        except Exception as e:
            self.logger.error(f"Failed to get TwelveLabs API key: {str(e)}")

        return None

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

            self.logger.info("Executing TwelveLabs API semantic query via OpenSearch")
            opensearch_start = time.time()
            response = client.search(body=opensearch_query, index=index_name)
            opensearch_time = time.time() - opensearch_start

            self.logger.info(
                f"[PERF] OpenSearch query execution took: {opensearch_time:.3f}s"
            )

            hits = response.get("hits", {}).get("hits", [])
            total_results = response["hits"]["total"]["value"]

            self.logger.info(
                f"TwelveLabs API search returned {len(hits)} raw hits from {total_results} total"
            )

            # Process semantic results to group clips with parent assets
            from index import process_semantic_results_parallel

            processing_start = time.time()
            processed_results = process_semantic_results_parallel(hits)
            self.logger.info(
                f"[PERF] Clip processing took: {time.time() - processing_start:.3f}s"
            )
            self.logger.info(
                f"Processed {len(hits)} hits into {len(processed_results)} parent assets with clips"
            )

            # Convert processed results to SearchHit format
            search_hits = []
            max_score = 0.0

            for result in processed_results:
                score = result.get("score", 0.0)
                if score > max_score:
                    max_score = score

                # Determine media type from source data
                asset_type = result.get("DigitalSourceAsset", {}).get("Type", "video")
                try:
                    media_type = MediaType(asset_type.lower())
                except ValueError:
                    media_type = MediaType.VIDEO

                search_hit = SearchHit(
                    asset_id=result.get("InventoryID", ""),
                    score=score,
                    source=result,
                    media_type=media_type,
                    provider_metadata={
                        "provider": "twelvelabs_api",
                        "embedding_model": "Marengo-retrieval-2.7",
                    },
                )
                search_hits.append(search_hit)

            return SearchResult(
                hits=search_hits,
                total_results=len(search_hits),
                max_score=max_score,
                took_ms=int(opensearch_time * 1000),
                provider="twelvelabs_api",
                architecture_type=SearchArchitectureType.PROVIDER_PLUS_STORE,
                provider_location=ProviderLocation.EXTERNAL,
                facets=response.get("aggregations"),
            )

        except Exception as e:
            self.logger.error(f"TwelveLabs API search failed: {str(e)}")
            # Return empty result on failure
            return SearchResult(
                hits=[],
                total_results=0,
                max_score=0.0,
                took_ms=0,
                provider="twelvelabs_api",
                architecture_type=SearchArchitectureType.PROVIDER_PLUS_STORE,
                provider_location=ProviderLocation.EXTERNAL,
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
            raise Exception("TwelveLabs API provider is not available or configured")

        # Step 1: Generate embeddings using TwelveLabs API
        embeddings = self.generate_embeddings(query.query_text)

        # Step 2: Execute search against the store (OpenSearch)
        return self.execute_store_search(embeddings, query)
