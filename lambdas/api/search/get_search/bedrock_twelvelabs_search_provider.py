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
