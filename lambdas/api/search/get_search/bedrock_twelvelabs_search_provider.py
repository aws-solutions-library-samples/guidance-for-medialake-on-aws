"""
Bedrock TwelveLabs search provider implementation for provider+store architecture.
"""

import json
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
        # Model-specific configuration for embedding types to include in clips
        self.embedding_model = "twelvelabs.marengo-embed-2-7-v1:0"

    def get_allowed_clip_embedding_types(self) -> List[str]:
        """
        Get the list of embedding types that should be included in clips for timeline display.
        This is model-specific as different models return different embedding types.

        For TwelveLabs Marengo 2.7:
        - Returns: audio, visual-text, visual-image
        - We only want visual-text for clips (timeline markers)
        - Filter out audio and visual-image

        For future models (e.g., TwelveLabs 3.0, Nova), this method can be updated
        to return different embedding types based on the model.
        """
        if "marengo-embed-2-7" in self.embedding_model:
            # For Marengo 2.7, only include visual-text for clips
            return ["visual-text"]

        # Default: include visual-text for clips (safest option for timeline display)
        return ["visual-text"]

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
        Generate embeddings using Bedrock TwelveLabs model directly.
        """
        return self._generate_embedding_via_bedrock(query_text)

    def _get_regional_inference_profile(self) -> str:
        """
        Get the appropriate TwelveLabs Marengo Embed v2.7 inference profile based on AWS region.
        """
        if "BEDROCK_INFERENCE_PROFILE_ARN" in os.environ:
            return os.environ["BEDROCK_INFERENCE_PROFILE_ARN"]

        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        model_suffix = ".twelvelabs.marengo-embed-2-7-v1:0"

        if aws_region.startswith("us-"):
            regional_prefix = "us"
        elif aws_region.startswith("eu-"):
            regional_prefix = "eu"
        elif aws_region.startswith("ap-"):
            regional_prefix = "apac"
        else:
            self.logger.warning(
                f"Unknown AWS region: {aws_region}, defaulting to US inference profile"
            )
            regional_prefix = "us"

        inference_profile_id = f"{regional_prefix}{model_suffix}"
        self.logger.info(
            f"Selected inference profile {inference_profile_id} for region {aws_region}"
        )
        return inference_profile_id

    def _generate_embedding_via_bedrock(self, query_text: str) -> List[float]:
        """
        Generate text embedding using TwelveLabs model via AWS Bedrock InvokeModel.
        """
        import json

        try:
            bedrock_client = boto3.client("bedrock-runtime")
            inference_profile_id = self._get_regional_inference_profile()

            self.logger.info(f"Using Bedrock inference profile: {inference_profile_id}")

            payload = {"inputType": "text", "inputText": query_text}

            self.logger.info(
                f"Starting Bedrock embedding creation for query: {query_text}"
            )

            response = bedrock_client.invoke_model(
                modelId=inference_profile_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )

            response_body = json.loads(response["body"].read())

            # Extract embedding from response
            if "data" in response_body and response_body["data"]:
                if (
                    isinstance(response_body["data"], list)
                    and len(response_body["data"]) > 0
                    and "embedding" in response_body["data"][0]
                ):
                    embedding = response_body["data"][0]["embedding"]
                    self.logger.info(
                        f"Successfully generated Bedrock embedding with {len(embedding)} dimensions"
                    )
                    return embedding

            # Format 2: Direct embedding array
            if "embedding" in response_body:
                embedding = response_body["embedding"]
                self.logger.info(
                    f"Successfully generated Bedrock embedding with {len(embedding)} dimensions"
                )
                return embedding

            raise Exception(
                f"Unexpected Bedrock response format: {list(response_body.keys())}"
            )

        except Exception as e:
            self.logger.error(f"Bedrock embedding generation failed: {str(e)}")
            raise

    def execute_store_search(
        self, embeddings: List[float], query: SearchQuery
    ) -> SearchResult:
        """Execute search against the configured vector store (OpenSearch or S3 Vectors)"""
        # Route to appropriate store based on configuration
        store_type = self.config.store or "opensearch"

        if store_type == "s3_vectors":
            return self._execute_s3_vector_search(embeddings, query)
        else:
            return self._execute_opensearch_search(embeddings, query)

    def _execute_s3_vector_search(
        self, embeddings: List[float], query: SearchQuery
    ) -> SearchResult:
        """Execute search against S3 Vectors"""
        try:
            from s3_vector_embedding_store import S3VectorEmbeddingStore

            self.logger.info(
                "Executing Bedrock TwelveLabs semantic query via S3 Vectors"
            )

            # Create S3 Vector store instance
            s3_vector_store = S3VectorEmbeddingStore(self.logger, self.metrics)

            # Create params-like object that S3VectorEmbeddingStore expects
            # We need to create a mock params object with the fields that build_semantic_query needs
            class MockParams:
                def __init__(self, query_obj):
                    self.q = query_obj.query_text
                    self.pageSize = query_obj.page_size
                    self.page = (query_obj.page_offset // query_obj.page_size) + 1
                    # Add filter parameters if present
                    self.type = None
                    self.extension = None
                    self.asset_size_gte = None
                    self.asset_size_lte = None
                    self.ingested_date_gte = None
                    self.ingested_date_lte = None

                    # Extract filters from SearchQuery
                    if query_obj.filters:
                        for filter_item in query_obj.filters:
                            key = filter_item.get("key")
                            value = filter_item.get("value")
                            if key == "mediaType" and isinstance(value, list):
                                self.type = ",".join(value)
                            elif (
                                key == "DigitalSourceAsset.MainRepresentation.Format"
                                and isinstance(value, list)
                            ):
                                self.extension = ",".join(value)

            params = MockParams(query)

            # Build semantic query - let S3VectorEmbeddingStore generate embeddings internally
            # But we already have embeddings, so we need to override them
            semantic_query = s3_vector_store.build_semantic_query(
                params, allowed_embedding_types=self.get_allowed_clip_embedding_types()
            )

            # Override the embedding with our Bedrock-generated one
            semantic_query["embedding"] = embeddings

            # Execute search
            search_start = time.time()
            store_result = s3_vector_store.execute_search(semantic_query, params)
            search_time = time.time() - search_start

            self.logger.info(
                f"[PERF] S3 Vector search execution took: {search_time:.3f}s"
            )
            self.logger.info(
                f"S3 Vector search returned {len(store_result.hits)} results"
            )

            # Convert BaseEmbeddingStore SearchResult to unified SearchResult
            from unified_search_models import MediaType, SearchHit

            search_hits = []
            for hit in store_result.hits:
                # Determine media type from source data
                asset_type = (
                    hit.get("_source", {})
                    .get("DigitalSourceAsset", {})
                    .get("Type", "video")
                )
                try:
                    media_type = MediaType(asset_type.lower())
                except ValueError:
                    media_type = MediaType.VIDEO

                # Get source data and preserve clips if they exist
                source_data = hit.get("_source", {}).copy()
                if "clips" in hit:
                    source_data["clips"] = hit["clips"]

                search_hit = SearchHit(
                    asset_id=source_data.get("InventoryID", ""),
                    score=hit.get("_score", 0.0),
                    source=source_data,
                    media_type=media_type,
                    provider_metadata={
                        "provider": "bedrock_twelvelabs",
                        "store": "s3_vectors",
                        "embedding_model": "twelvelabs.marengo-embed-2-7-v1:0",
                    },
                )
                search_hits.append(search_hit)

            return SearchResult(
                hits=search_hits,
                total_results=store_result.total_results,
                max_score=max([h.score for h in search_hits]) if search_hits else 0.0,
                took_ms=int(search_time * 1000),
                provider="bedrock_twelvelabs",
                architecture_type=SearchArchitectureType.PROVIDER_PLUS_STORE,
                provider_location=ProviderLocation.INTERNAL,
            )
        except Exception as e:
            self.logger.error(f"S3 Vector search failed: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())
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

    def _execute_opensearch_search(
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
                f"Bedrock TwelveLabs search returned {len(hits)} raw hits from {total_results} total"
            )

            # Debug: Log sample hits to see actual document structure
            if hits:
                self.logger.info(
                    f"[DEBUG] Sample hit structure: {json.dumps(hits[0], indent=2)}"
                )
            else:
                self.logger.warning(
                    "[DEBUG] No hits returned - query may be too restrictive or no matching documents in index"
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

            # Filter clips based on allowed embedding types (post-processing)
            allowed_types = self.get_allowed_clip_embedding_types()
            filtered_results = []
            total_clips_before = 0
            total_clips_after = 0

            for result in processed_results:
                clips = result.get("clips", [])
                total_clips_before += len(clips)

                # Filter clips to only include allowed embedding types
                filtered_clips = [
                    clip
                    for clip in clips
                    if clip.get("embedding_option") in allowed_types
                ]
                total_clips_after += len(filtered_clips)

                result["clips"] = filtered_clips
                filtered_results.append(result)

            self.logger.info(
                f"Filtered clips from {total_clips_before} to {total_clips_after} "
                f"(kept only {allowed_types})"
            )

            processed_results = filtered_results

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
                        "provider": "bedrock_twelvelabs",
                        "embedding_model": "twelvelabs.marengo-embed-2-7-v1:0",
                    },
                )
                search_hits.append(search_hit)

            return SearchResult(
                hits=search_hits,
                total_results=len(search_hits),
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
