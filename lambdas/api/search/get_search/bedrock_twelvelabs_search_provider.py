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

        # Get target index from config (Phase 3: config-based index selection)
        # Falls back to OPENSEARCH_INDEX for backward compatibility
        self._target_index = getattr(config, "target_index", None)
        if not self._target_index:
            self._target_index = os.environ.get("OPENSEARCH_INDEX", "media")

        self.logger.info(
            f"[INDEX ROUTING] Target index for search: '{self._target_index}'"
        )

        # Determine model version using priority order:
        # 1. Type field (most explicit - e.g., "twelvelabs-bedrock-3-0")
        # 2. Explicit dimensions field (512 for 3.0, 1024 for 2.7)
        # 3. Name field (e.g., "TwelveLabs Marengo 3.0")
        # No fallback - configuration must be explicit

        provider_type = getattr(config, "type", "") or ""
        provider_name = getattr(config, "name", "") or ""
        dimensions = getattr(config, "dimensions", None)

        # Debug logging
        self.logger.info(f"[CONFIG] provider_type: '{provider_type}'")
        self.logger.info(f"[CONFIG] provider_name: '{provider_name}'")
        self.logger.info(
            f"[CONFIG] dimensions: {dimensions} (type: {type(dimensions).__name__})"
        )

        # Prioritize type field check (most explicit and reliable configuration)
        if "3-0" in provider_type or "3.0" in provider_type:
            self.embedding_model = "twelvelabs.marengo-embed-3-0-v1:0"
            self.model_version = "3.0"
            self.embedding_dimension = 512
            self.logger.info(f"Using Marengo 3.0 based on type='{provider_type}'")
        elif "2-7" in provider_type or "2.7" in provider_type:
            self.embedding_model = "twelvelabs.marengo-embed-2-7-v1:0"
            self.model_version = "2.7"
            self.embedding_dimension = 1024
            self.logger.info(f"Using Marengo 2.7 based on type='{provider_type}'")
        elif dimensions == 512 or str(dimensions) == "512":
            self.embedding_model = "twelvelabs.marengo-embed-3-0-v1:0"
            self.model_version = "3.0"
            self.embedding_dimension = 512
            self.logger.info(f"Using Marengo 3.0 based on dimensions={dimensions}")
        elif dimensions == 1024 or str(dimensions) == "1024":
            self.embedding_model = "twelvelabs.marengo-embed-2-7-v1:0"
            self.model_version = "2.7"
            self.embedding_dimension = 1024
            self.logger.info(f"Using Marengo 2.7 based on dimensions={dimensions}")
        elif "3-0" in provider_name or "3.0" in provider_name:
            self.embedding_model = "twelvelabs.marengo-embed-3-0-v1:0"
            self.model_version = "3.0"
            self.embedding_dimension = 512
            self.logger.info(f"Using Marengo 3.0 based on name='{provider_name}'")
        elif "2-7" in provider_name or "2.7" in provider_name:
            self.embedding_model = "twelvelabs.marengo-embed-2-7-v1:0"
            self.model_version = "2.7"
            self.embedding_dimension = 1024
            self.logger.info(f"Using Marengo 2.7 based on name='{provider_name}'")
        else:
            # No fallback - configuration must explicitly specify model version
            error_msg = (
                f"Unable to determine TwelveLabs model version from configuration. "
                f"Provided: type='{provider_type}', dimensions={dimensions}, name='{provider_name}'. "
                f"Configuration must include one of: "
                f"type='twelvelabs-bedrock-3-0' or 'twelvelabs-bedrock-2-7', "
                f"dimensions=512 or 1024, "
                f"or name containing '3.0' or '2.7'"
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self.logger.info(
            f"Initialized Bedrock TwelveLabs provider with model: {self.embedding_model} "
            f"(version: {self.model_version}, dimension: {self.embedding_dimension}, "
            f"target_index: {self._target_index})"
        )

    def get_allowed_clip_embedding_types(
        self, search_modes: List[str] = None
    ) -> List[str]:
        """
        Get the list of embedding types that should be included in clips for timeline display.
        This is model-specific as different models return different embedding types.

        For TwelveLabs Marengo 2.7:
        - Embedding types: audio, visual-text, visual-image
        - We only want visual-text for clips (timeline markers)

        For TwelveLabs Marengo 3.0:
        - Embedding types: visual, audio, transcription
        - Respects search_modes parameter to filter by user-selected modes
        """
        if "marengo-embed-2-7" in self.embedding_model or self.model_version == "2.7":
            # For Marengo 2.7, only include visual-text for clips
            return ["visual-text"]

        if "marengo-embed-3-0" in self.embedding_model or self.model_version == "3.0":
            # For Marengo 3.0, use search_modes to determine allowed types
            if search_modes:
                from unified_search_models import get_allowed_types_for_modes

                allowed = get_allowed_types_for_modes(search_modes)
                if allowed is not None:
                    return allowed
            # Default: visual + transcription (original behavior)
            return ["visual", "transcription"]

        # Default: include common types across models
        return ["visual-text", "visual"]

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
        Get the appropriate TwelveLabs Marengo Embed inference profile based on AWS region.
        Supports both v2.7 and v3.0 models.
        """
        # Log entry point for debugging
        self.logger.info(
            f"[PROFILE] Getting inference profile - model_version='{self.model_version}', "
            f"embedding_model='{self.embedding_model}'"
        )

        if "BEDROCK_INFERENCE_PROFILE_ARN" in os.environ:
            profile_arn = os.environ["BEDROCK_INFERENCE_PROFILE_ARN"]
            self.logger.info(
                f"[PROFILE] Using env var BEDROCK_INFERENCE_PROFILE_ARN: {profile_arn}"
            )
            return profile_arn

        aws_region = os.environ.get("AWS_REGION", "us-east-1")

        # Use the model version determined in __init__
        # CRITICAL: Check model_version explicitly
        self.logger.info(
            f"[PROFILE] Checking model_version: '{self.model_version}' (type: {type(self.model_version).__name__})"
        )

        if self.model_version == "3.0":
            model_suffix = ".twelvelabs.marengo-embed-3-0-v1:0"
            self.logger.info(f"[PROFILE] Selected 3.0 suffix: {model_suffix}")
        elif self.model_version == "2.7":
            model_suffix = ".twelvelabs.marengo-embed-2-7-v1:0"
            self.logger.info(f"[PROFILE] Selected 2.7 suffix: {model_suffix}")
        else:
            # Fallback with explicit error
            error_msg = (
                f"Invalid model_version: '{self.model_version}'. Must be '3.0' or '2.7'"
            )
            self.logger.error(f"[PROFILE] {error_msg}")
            raise ValueError(error_msg)

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
            f"[PROFILE] ✓ Final inference profile: {inference_profile_id} "
            f"(region={aws_region}, model={self.embedding_model}, version={self.model_version}, dim={self.embedding_dimension})"
        )
        return inference_profile_id

    def _get_embedding_field_name(
        self, dimension: int, space_type: str = "cosine"
    ) -> str:
        """
        Get the field name for an embedding based on its dimension and space type.

        Args:
            dimension: The embedding dimension (256, 384, 512, 1024, 1536, 3072)
            space_type: The similarity space type (default: "cosine")

        Returns:
            Field name like "embedding_512_cosine"
        """
        supported_dimensions = [256, 384, 512, 1024, 1536, 3072]
        if dimension not in supported_dimensions:
            self.logger.warning(
                f"Unsupported embedding dimension: {dimension}. Using closest supported dimension."
            )
            dimension = min(supported_dimensions, key=lambda x: abs(x - dimension))

        return f"embedding_{dimension}_{space_type}"

    def _generate_embedding_via_bedrock(self, query_text: str) -> List[float]:
        """
        Generate text embedding using TwelveLabs model via AWS Bedrock InvokeModel.
        Supports both Marengo 2.7 and 3.0 API formats.
        """
        import json

        try:
            bedrock_client = boto3.client("bedrock-runtime")
            inference_profile_id = self._get_regional_inference_profile()

            self.logger.info(f"Using Bedrock inference profile: {inference_profile_id}")

            # API format differs between model versions:
            # Marengo 2.7: {"inputType": "text", "inputText": query_text}
            # Marengo 3.0: {"inputType": "text", "text": {"inputText": query_text}}
            if self.model_version == "3.0":
                payload = {"inputType": "text", "text": {"inputText": query_text}}
            else:
                payload = {"inputType": "text", "inputText": query_text}

            self.logger.info(
                f"Starting Bedrock embedding creation for query: {query_text} "
                f"(using {'3.0' if self.model_version == '3.0' else '2.7'} API format)"
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
            search_modes = getattr(query, "search_modes", None)
            semantic_query = s3_vector_store.build_semantic_query(
                params,
                allowed_embedding_types=self.get_allowed_clip_embedding_types(
                    search_modes=search_modes
                ),
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

                # For images, promote embedding metadata to top level instead of clips
                # Images have a single asset-level embedding — the clips wrapper is misleading
                if asset_type.lower() == "image":
                    clips = hit.get("clips", [])
                    if clips and len(clips) == 1:
                        image_clip = clips[0]
                        source_data["embedding_info"] = {
                            "model_provider": image_clip.get(
                                "model_provider", "twelvelabs"
                            ),
                            "model_name": image_clip.get("model_name", "marengo"),
                            "model_version": image_clip.get("model_version", "3.0"),
                            "embedding_representation": image_clip.get(
                                "embedding_representation", "visual"
                            ),
                            "embedding_granularity": image_clip.get(
                                "embedding_granularity", "asset"
                            ),
                            "type": image_clip.get("type", "image"),
                        }
                    # else: no clips for this image, no embedding_info either — that's fine
                elif "clips" in hit:
                    source_data["clips"] = hit["clips"]

                search_hit = SearchHit(
                    asset_id=source_data.get("InventoryID", ""),
                    score=hit.get("_score", 0.0),
                    source=source_data,
                    media_type=media_type,
                    provider_metadata={
                        "provider": "bedrock_twelvelabs",
                        "store": "s3_vectors",
                        "embedding_model": self.embedding_model,
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
            # Use target index from config (Phase 3: config-based index selection)
            index_name = self._target_index

            # Determine embedding dimension and field name
            embedding_dimension = len(embeddings)
            field_name = self._get_embedding_field_name(embedding_dimension)

            self.logger.info(
                f"[INDEX ROUTING] Querying index '{index_name}' with {embedding_dimension}d embeddings "
                f"(model: {self.embedding_model}, field: {field_name})"
            )

            # Build query structure based on model version
            # Marengo 3.0 (512d): ONLY use asset_embeddings nested structure
            # Marengo 2.7 (1024d): Use BOTH legacy embedding field AND asset_embeddings for backward compatibility

            # Get allowed embedding types for filtering the nested query
            allowed_types = self.get_allowed_clip_embedding_types(
                search_modes=getattr(query, "search_modes", None)
            )

            if self.model_version == "3.0":
                # Marengo 3.0: Query separate embedding documents with inventory_id reference
                # Uses embedding_representation (visual/audio/text/video) for filtering
                # Build dynamic filters based on search_modes
                from unified_search_models import get_os_filters_for_modes

                search_modes = getattr(query, "search_modes", ["visual"])
                mode_filters = get_os_filters_for_modes(search_modes)

                if mode_filters is not None:
                    # Specific modes selected — apply representation filter
                    filter_clause = {
                        "bool": {
                            "should": mode_filters,
                            "minimum_should_match": 1,
                            "must": [],
                        }
                    }
                else:
                    # All modes selected — no representation filter, but keep bool
                    # wrapper so _add_filters_to_opensearch_query can append to ["bool"]["must"]
                    filter_clause = {"bool": {"must": []}}

                opensearch_query = {
                    "size": query.page_size * 20,
                    "query": {
                        "bool": {
                            "filter": filter_clause,
                            "must": [
                                {
                                    "knn": {
                                        field_name: {
                                            "vector": embeddings,
                                            "k": query.page_size * 20,
                                        }
                                    }
                                }
                            ],
                        }
                    },
                    "_source": {
                        "excludes": [
                            "embedding_256_cosine",
                            "embedding_384_cosine",
                            "embedding_512_cosine",
                            "embedding_1024_cosine",
                            "embedding_1536_cosine",
                            "embedding_3072_cosine",
                        ]
                    },
                }
                self.logger.info(
                    f"Using Marengo 3.0 separate documents query "
                    f"(field: {field_name}, search_modes: {search_modes})"
                )
            else:
                # Marengo 2.7: Try legacy first, fallback to new structure if needed
                # This provides backward compatibility while supporting transition period
                opensearch_query = {
                    "size": query.page_size * 20,
                    "query": {
                        "bool": {
                            "filter": {"bool": {"must": []}},
                            "should": [
                                # Legacy structure: root-level embedding field (preferred)
                                {
                                    "knn": {
                                        "embedding": {
                                            "vector": embeddings,
                                            "k": query.page_size * 20,
                                        }
                                    }
                                },
                                # Fallback: Check asset_embeddings for transition period
                                # This handles documents that were indexed with new structure
                                {
                                    "bool": {
                                        "must": [
                                            {"exists": {"field": "asset_embeddings"}},
                                            {
                                                "script_score": {
                                                    "query": {"match_all": {}},
                                                    "script": {
                                                        "source": """
                                                            if (doc.containsKey('asset_embeddings.embedding_1024_cosine') &&
                                                                doc['asset_embeddings.embedding_1024_cosine'].size() > 0) {
                                                                def embedding = doc['asset_embeddings.embedding_1024_cosine'];
                                                                double score = 0.0;
                                                                for (int i = 0; i < Math.min(params.query_vector.length, embedding.size()); i++) {
                                                                    score += params.query_vector[i] * embedding[i];
                                                                }
                                                                return score;
                                                            }
                                                            return 0.0;
                                                        """,
                                                        "params": {
                                                            "query_vector": embeddings
                                                        },
                                                    },
                                                }
                                            },
                                        ]
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
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
                self.logger.info(
                    f"Using Marengo 2.7 hybrid query (legacy embedding + asset_embeddings fallback)"
                )

            # Add filters based on query parameters
            deferred_filters = self._add_filters_to_opensearch_query(
                opensearch_query, query
            )

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

            # Process results differently based on model version
            processing_start = time.time()

            if self.model_version == "3.0":
                # Marengo 3.0: Extract clips from inner_hits (nested asset_embeddings)
                processed_results = self._process_marengo_30_results(hits)
                self.logger.info(
                    f"[PERF] Marengo 3.0 clip processing took: {time.time() - processing_start:.3f}s"
                )

                # Apply deferred filters (fields that only exist on parent documents)
                if deferred_filters:
                    processed_results = self._apply_deferred_filters(
                        processed_results, deferred_filters
                    )
                    self.logger.info(
                        f"[FILTER] After deferred filtering: {len(processed_results)} results remain"
                    )
            else:
                # Marengo 2.7: Use legacy clip processing (separate clip documents)
                from index import process_semantic_results_parallel

                processed_results = process_semantic_results_parallel(hits)
                self.logger.info(
                    f"[PERF] Clip processing took: {time.time() - processing_start:.3f}s"
                )

            self.logger.info(
                f"Processed {len(hits)} hits into {len(processed_results)} parent assets with clips"
            )

            # Filter clips based on allowed embedding types (post-processing)
            # allowed_types already computed above with search_modes awareness
            filtered_results = []
            total_clips_before = 0
            total_clips_after = 0

            for result in processed_results:
                clips = result.get("clips", [])
                total_clips_before += len(clips)

                # Images don't have clips — skip clip filtering for them
                if "embedding_info" in result:
                    filtered_results.append(result)
                    continue

                # Debug: Log clip embedding_option values before filtering
                if clips:
                    clip_options = [clip.get("embedding_option") for clip in clips]
                    self.logger.info(
                        f"[DEBUG] Clips before filtering: {len(clips)} clips with embedding_options: {clip_options}, allowed: {allowed_types}"
                    )

                # Filter clips to only include allowed embedding types
                # When allowed_types is None (all modes), keep all clips
                if allowed_types is not None:
                    filtered_clips = [
                        clip
                        for clip in clips
                        if clip.get("embedding_option") in allowed_types
                    ]
                else:
                    filtered_clips = clips
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
                        "embedding_model": self.embedding_model,
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

    def _process_marengo_30_results(self, hits: List[Dict]) -> List[Dict]:
        """
        Process Marengo 3.0 search results from separate clip documents.

        For Marengo 3.0, clips are stored as separate documents with inventory_id reference.
        We need to group clips by inventory_id and fetch parent document details.
        """
        from url_utils import generate_cloudfront_url

        # Group clips by inventory_id (parent asset reference)
        clips_by_parent = {}

        for hit in hits:
            source = hit.get("_source", {})
            parent_id = source.get("inventory_id") or source.get("InventoryID", "")
            embedding_type = source.get("embedding_type", "video")

            # Log the raw asset-embeddings document (excluding vector fields)
            source_for_logging = {
                k: v
                for k, v in source.items()
                if not k.startswith("embedding_")
                or k
                in (
                    "embedding_type",
                    "embedding_granularity",
                    "embedding_representation",
                    "embedding_dimension",
                )
            }
            self.logger.info(
                f"[ASSET-EMBEDDINGS] Raw hit for {parent_id}",
                extra={
                    "score": hit.get("_score", 0.0),
                    "document": source_for_logging,
                },
            )

            # Skip asset-granularity embeddings for videos (they represent the whole video, not clips)
            # BUT keep asset-granularity embeddings for images (images only have asset-level embeddings)
            embedding_granularity = source.get("embedding_granularity", "segment")
            if embedding_granularity == "asset" and embedding_type != "image":
                self.logger.debug(
                    f"Skipping asset-granularity embedding for {parent_id} - not a clip"
                )
                continue

            # Build clip object
            # Use embedding_granularity (not embedding_scope) and embedding_representation (not embedding_type)
            clip = {
                "score": hit.get("_score", 0.0),
                "InventoryID": source.get("InventoryID", parent_id),
                "embedding_scope": embedding_granularity,  # Map to legacy field for UI compatibility
                "embedding_option": source.get(
                    "embedding_representation", "visual"
                ),  # Use representation for UI
                "start_timecode": source.get("start_timecode", "")
                or source.get("start_smpte_timecode", ""),
                "end_timecode": source.get("end_timecode", "")
                or source.get("end_smpte_timecode", ""),
                "start_seconds": source.get("start_seconds"),
                "end_seconds": source.get("end_seconds"),
                "type": source.get("embedding_type") or source.get("type", "video"),
                "model_provider": source.get("model_provider", "twelvelabs"),
                "model_name": source.get("model_name", "marengo"),
                "model_version": source.get("model_version", "3.0"),
                "embedding_representation": source.get(
                    "embedding_representation", "visual"
                ),
                "embedding_granularity": embedding_granularity,
            }

            if parent_id not in clips_by_parent:
                clips_by_parent[parent_id] = []
            clips_by_parent[parent_id].append(clip)

        self.logger.info(
            f"Grouped {len(hits)} clip documents into {len(clips_by_parent)} parent assets"
        )

        # Now fetch parent documents for each parent_id
        # Use the existing OpenSearch client
        client = self._get_opensearch_client()
        index_name = os.environ["OPENSEARCH_INDEX"]

        processed_results = []

        for parent_id, clips in clips_by_parent.items():
            # Fetch parent document
            try:
                search_resp = client.search(
                    index=index_name,
                    body={
                        "query": {
                            "bool": {
                                "filter": [
                                    {"match_phrase": {"InventoryID": parent_id}},
                                    {
                                        "nested": {
                                            "path": "DerivedRepresentations",
                                            "query": {
                                                "exists": {
                                                    "field": "DerivedRepresentations.ID"
                                                }
                                            },
                                        }
                                    },
                                ]
                            }
                        }
                    },
                    size=1,
                )

                if search_resp["hits"]["total"]["value"] > 0:
                    parent_source = search_resp["hits"]["hits"][0]["_source"]

                    # Determine asset type from parent document
                    asset_type = (
                        parent_source.get("DigitalSourceAsset", {})
                        .get("Type", "")
                        .lower()
                    )

                    # Build result from parent document
                    result = {
                        "InventoryID": parent_id,
                        "DigitalSourceAsset": parent_source.get(
                            "DigitalSourceAsset", {}
                        ),
                        "DerivedRepresentations": parent_source.get(
                            "DerivedRepresentations", []
                        ),
                        "FileHash": parent_source.get("FileHash", ""),
                        "Metadata": parent_source.get("Metadata", {}),
                        "score": max(clip["score"] for clip in clips),
                    }

                    # For images, promote embedding metadata to top level instead of wrapping in clips
                    # Images have a single asset-level embedding — the clips wrapper is misleading
                    if asset_type == "image" and len(clips) == 1:
                        image_embedding = clips[0]
                        result["embedding_info"] = {
                            "model_provider": image_embedding.get(
                                "model_provider", "twelvelabs"
                            ),
                            "model_name": image_embedding.get("model_name", "marengo"),
                            "model_version": image_embedding.get(
                                "model_version", "3.0"
                            ),
                            "embedding_representation": image_embedding.get(
                                "embedding_representation", "visual"
                            ),
                            "embedding_granularity": image_embedding.get(
                                "embedding_granularity", "asset"
                            ),
                            "type": image_embedding.get("type", "image"),
                        }
                    else:
                        result["clips"] = sorted(
                            clips, key=lambda x: x.get("score", 0), reverse=True
                        )

                    # Generate URLs for derived representations
                    derived_reps = parent_source.get("DerivedRepresentations", [])
                    for rep in derived_reps:
                        purpose = rep.get("Purpose", "")
                        storage_info = rep.get("StorageInfo", {}).get(
                            "PrimaryLocation", {}
                        )

                        if storage_info.get("StorageType") == "s3":
                            bucket = storage_info.get("Bucket", "")
                            key = storage_info.get("ObjectKey", {}).get("FullPath", "")

                            if bucket and key:
                                url = generate_cloudfront_url(bucket=bucket, key=key)
                                if purpose == "thumbnail":
                                    # Use indexed thumbnail (middle frame)
                                    import re

                                    if ".jpg" in url:
                                        pattern = r"\.(\d{7})\.jpg$"
                                        match = re.search(pattern, url)
                                        if match:
                                            url = re.sub(pattern, ".0000002.jpg", url)
                                        else:
                                            url = url.replace(".jpg", ".0000002.jpg")
                                    result["thumbnailUrl"] = url
                                elif purpose == "proxy":
                                    result["proxyUrl"] = url

                    # Add common ID field
                    if parent_id and ":" in parent_id:
                        result["id"] = parent_id.split(":")[-1]
                    else:
                        result["id"] = parent_id

                    processed_results.append(result)

                    # Log the processed result (what gets sent to the API response)
                    result_summary = {
                        "InventoryID": result.get("InventoryID"),
                        "asset_type": asset_type,
                        "score": result.get("score"),
                        "has_clips": "clips" in result,
                        "clip_count": len(result["clips"]) if "clips" in result else 0,
                        "has_embedding_info": "embedding_info" in result,
                        "embedding_info": result.get("embedding_info"),
                        "has_thumbnailUrl": "thumbnailUrl" in result,
                        "has_proxyUrl": "proxyUrl" in result,
                    }
                    self.logger.info(
                        f"[ASSET-EMBEDDINGS] Processed result for {parent_id}",
                        extra={"result_summary": result_summary},
                    )
                else:
                    self.logger.warning(
                        f"Parent document not found for {parent_id}, skipping clips"
                    )
            except Exception as e:
                self.logger.error(
                    f"Error fetching parent document for {parent_id}: {str(e)}"
                )

        # Sort results by score
        processed_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return processed_results

    def _apply_deferred_filters(
        self, results: List[Dict], deferred_filters: List[Dict]
    ) -> List[Dict]:
        """Apply filters that reference parent-document fields after parent docs are fetched.

        For Marengo 3.0, the KNN search runs against the asset-embeddings index which
        doesn't have parent-level fields like format, fileSize, or createdAt. These
        filters are deferred and applied here as post-processing against the fetched
        parent document data.
        """
        if not deferred_filters:
            return results

        filtered = []
        for result in results:
            if self._result_matches_deferred_filters(result, deferred_filters):
                filtered.append(result)

        self.logger.info(
            f"[FILTER] Deferred filter reduced results from {len(results)} to {len(filtered)}"
        )
        return filtered

    def _result_matches_deferred_filters(
        self, result: Dict, filters: List[Dict]
    ) -> bool:
        """Check if a result matches all deferred filters (AND logic)."""
        for f in filters:
            field_key = f.get("key", "")
            operator = f.get("operator")
            value = f.get("value")

            # Resolve the field value from the result using dot-notation
            actual = self._resolve_field(result, field_key)

            if operator == "in" and isinstance(value, list):
                if actual is None:
                    return False
                # Normalize filter values for comparison (lowercase strings)
                normalized_values = [
                    v.lower() if isinstance(v, str) else v for v in value
                ]
                # Also build a string-lowered set so "100" matches 100 and vice-versa
                normalized_str_values = {str(v).lower() for v in value}
                if isinstance(actual, str):
                    if (
                        actual.lower() not in normalized_values
                        and actual.lower() not in normalized_str_values
                    ):
                        return False
                elif isinstance(actual, list):
                    # At least one element in actual must be in the filter values
                    if not any(
                        (a.lower() if isinstance(a, str) else a) in normalized_values
                        or str(a).lower() in normalized_str_values
                        for a in actual
                    ):
                        return False
                else:
                    # Scalar non-string (int, float, bool): try native check,
                    # then fall back to string comparison so 100 matches "100"
                    if (
                        actual not in normalized_values
                        and str(actual).lower() not in normalized_str_values
                    ):
                        return False
            elif operator in ("==", "eq"):
                if actual is None or actual != value:
                    return False
            elif operator == "range" and isinstance(value, dict):
                if actual is None:
                    return False
                try:
                    actual_num = (
                        float(actual)
                        if not isinstance(actual, (int, float))
                        else actual
                    )
                    if "gte" in value and actual_num < float(value["gte"]):
                        return False
                    if "lte" in value and actual_num > float(value["lte"]):
                        return False
                    if "gt" in value and actual_num <= float(value["gt"]):
                        return False
                    if "lt" in value and actual_num >= float(value["lt"]):
                        return False
                except (ValueError, TypeError):
                    # For date strings, fall back to string comparison
                    actual_str = str(actual)
                    if "gte" in value and actual_str < str(value["gte"]):
                        return False
                    if "lte" in value and actual_str > str(value["lte"]):
                        return False
                    if "gt" in value and actual_str <= str(value["gt"]):
                        return False
                    if "lt" in value and actual_str >= str(value["lt"]):
                        return False
        return True

    @staticmethod
    def _resolve_field(data: Dict, dotted_key: str):
        """Resolve a dot-notation field path against a nested dict.

        e.g. 'DigitalSourceAsset.MainRepresentation.Format' resolves through
        data['DigitalSourceAsset']['MainRepresentation']['Format'].
        """
        parts = dotted_key.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current

    def _add_filters_to_opensearch_query(
        self, query: Dict, search_query: SearchQuery
    ) -> List[Dict]:
        """Add filters to OpenSearch query based on search parameters.

        For Marengo 3.0, the KNN search runs against the asset-embeddings index
        which only has embedding-level fields (embedding_type, embedding_representation,
        etc.). Filters that reference parent-document fields (format, fileSize,
        createdAt, etc.) cannot be applied at query time — they are returned as
        deferred filters to be applied as post-processing after parent documents
        are fetched in _process_marengo_30_results.

        Returns:
            A list of deferred filter dicts that must be applied post-query against
            parent-document data.
        """
        deferred_filters = []

        if not search_query.filters:
            return deferred_filters

        filters_to_add = []

        # Fields that exist on asset-embeddings documents (Marengo 3.0)
        EMBEDDING_DOC_FIELDS = {
            "mediaType",
            "embedding_type",
            "embedding_representation",
        }

        for filter_item in search_query.filters:
            field_key = filter_item.get("key")
            operator = filter_item.get("operator")
            value = filter_item.get("value")

            if operator == "in" and isinstance(value, list):
                if field_key == "mediaType":
                    if self.model_version == "3.0":
                        # Marengo 3.0 separate documents use embedding_type instead of DigitalSourceAsset.Type
                        filters_to_add.append(
                            {"terms": {"embedding_type": [v.lower() for v in value]}}
                        )
                    else:
                        filters_to_add.append(
                            {"terms": {"DigitalSourceAsset.Type": value}}
                        )
                elif field_key == "DigitalSourceAsset.Type":
                    if self.model_version == "3.0":
                        # Legacy 'type' param maps here — translate to embedding_type for query-time filtering
                        filters_to_add.append(
                            {"terms": {"embedding_type": [v.lower() for v in value]}}
                        )
                    else:
                        filters_to_add.append(
                            {"terms": {"DigitalSourceAsset.Type": value}}
                        )
                elif field_key == "DigitalSourceAsset.MainRepresentation.Format":
                    if self.model_version == "3.0":
                        # Field only exists on parent docs — defer to post-processing
                        deferred_filters.append(filter_item)
                    else:
                        filters_to_add.append({"terms": {field_key: value}})
                else:
                    if (
                        self.model_version == "3.0"
                        and field_key not in EMBEDDING_DOC_FIELDS
                    ):
                        deferred_filters.append(filter_item)
                    else:
                        filters_to_add.append({"terms": {field_key: value}})
            elif operator == "==" or operator == "eq":
                if self.model_version == "3.0":
                    if field_key in ("mediaType", "DigitalSourceAsset.Type"):
                        # Single-value type filter — translate to embedding_type
                        filters_to_add.append(
                            {
                                "term": {
                                    "embedding_type": (
                                        value.lower()
                                        if isinstance(value, str)
                                        else value
                                    )
                                }
                            }
                        )
                    elif field_key not in EMBEDDING_DOC_FIELDS:
                        deferred_filters.append(filter_item)
                    else:
                        filters_to_add.append({"term": {field_key: value}})
                else:
                    filters_to_add.append({"term": {field_key: value}})
            elif operator == "range" and isinstance(value, dict):
                if self.model_version == "3.0":
                    # Range filters (fileSize, createdAt) only exist on parent docs
                    deferred_filters.append(filter_item)
                else:
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

        if deferred_filters:
            self.logger.info(
                f"[FILTER] Deferring {len(deferred_filters)} filters to post-processing "
                f"(fields only exist on parent docs): "
                f"{[f.get('key') for f in deferred_filters]}"
            )

        # Add all applicable filters to the query
        # Ensure the 'must' array exists in the filter bool (Marengo 3.0 queries may only have 'should')
        filter_bool = query["query"]["bool"]["filter"]["bool"]
        if "must" not in filter_bool:
            filter_bool["must"] = []
        filter_bool["must"].extend(filters_to_add)

        return deferred_filters

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
